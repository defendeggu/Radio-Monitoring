"""
Spectrum / waterfall with live listening.

A SpectrumSession streams IQ from the SDR, turns it into averaged FFT rows
(waterfall) and, while someone listens, demodulates one narrow channel inside
the bandwidth into audio. Both go out as small binary frames over Redis
pub/sub; GET /spectrum/<id>/stream forwards them to the browser.

    SDR ─IQ─► SpectrumTap ──► spectrum frame ─┐
          └─► ChannelReceiver ──► audio frame ─┴─► Redis radiomoni:spectrum:<id> ─► browser

The waterfall only uses the SDR while nothing else needs it: it registers as
preemptible with the SDR lock, so any other job stops it and takes over.
VOX and CW sessions feed their own IQ into a SpectrumTap, so their waterfall
can be watched without a second SDR.

Frame format (little endian): u8 type, u32 payload length, payload
    1 spectrum: u64 centre Hz, u32 span Hz, f64 unix time, f32 dB min, f32 dB max, u16 n, n × u8
    2 audio:    u32 rate Hz, f64 unix time, u32 n, n × i16
    3 JSON:     UTF-8 JSON (state, end of session)
"""

import json
import logging
import queue
import struct
import time
from typing import Any, Iterator, Optional

import numpy as np
from numpy.typing import NDArray

from radiomoni import events
from radiomoni import sdr_lock
from radiomoni.decoders.streaming import BaseStreamingDecoder, SessionManager
from radiomoni.decoders.vox import SquelchGate, chunk_power_db
from radiomoni.dsp import ChannelReceiver, SpectrumAnalyzer, mask_dc, to_uint8
from radiomoni.redis_client import get_redis, get_redis_raw
from radiomoni.sdr_hardware import SDRType, get_sdr_instance

logger = logging.getLogger(__name__)

FRAME_SPECTRUM, FRAME_AUDIO, FRAME_JSON = 1, 2, 3
DB_MIN, DB_MAX = -130.0, -10.0        # transport range of the uint8 spectrum values
CHUNK_SECONDS = 0.05
VIEWER_TTL = 20                       # s; refreshed by every open stream
IDLE_TIMEOUT = 60                     # s without a viewer → the session ends and frees the SDR
AUDIO_BLOCK_SECONDS = 0.1

# Bandwidth (= IQ sample rate) each device supports for the waterfall
SPAN_LIMITS = {
    SDRType.HACKRF: (2_000_000, 10_000_000),
    SDRType.RTLSDR: (250_000, 2_400_000),
    SDRType.AIRSPYHF: (768_000, 768_000),
    SDRType.USRP: (200_000, 10_000_000),
}


def channel_name(session_id: str) -> str:
    return f'radiomoni:spectrum:{session_id}'


def _viewer_key(session_id: str) -> str:
    return f'spectrum:viewers:{session_id}'


def _listen_key(session_id: str) -> str:
    return f'spectrum:listen:{session_id}'


def state_key(session_id: str) -> str:
    return f'spectrum:state:{session_id}'


# ------------------------------------------------------------------ frames
def _frame(kind: int, payload: bytes) -> bytes:
    return struct.pack('<BI', kind, len(payload)) + payload


def pack_spectrum(centre: int, span: int, ts: float, bins: NDArray[np.uint8],
                  db_min: float = DB_MIN, db_max: float = DB_MAX) -> bytes:
    head = struct.pack('<QIdffH', int(centre), int(span), ts, db_min, db_max, len(bins))
    return _frame(FRAME_SPECTRUM, head + bins.astype(np.uint8).tobytes())


def pack_audio(rate: float, ts: float, pcm: NDArray[np.int16]) -> bytes:
    head = struct.pack('<IdI', int(round(rate)), ts, len(pcm))
    return _frame(FRAME_AUDIO, head + pcm.astype('<i2').tobytes())


def pack_json(data: dict[str, Any]) -> bytes:
    return _frame(FRAME_JSON, json.dumps(data, default=str).encode())


def unpack_frames(data: bytes) -> Iterator[tuple[int, Any]]:
    """Inverse of the pack_* functions (used by tests and tools)."""
    pos = 0
    while pos + 5 <= len(data):
        kind, length = struct.unpack_from('<BI', data, pos)
        payload = data[pos + 5:pos + 5 + length]
        pos += 5 + length
        if kind == FRAME_SPECTRUM:
            centre, span, ts, db_min, db_max, n = struct.unpack_from('<QIdffH', payload)
            bins = np.frombuffer(payload[struct.calcsize('<QIdffH'):], dtype=np.uint8, count=n)
            yield kind, {'centre': centre, 'span': span, 'time': ts, 'db_min': db_min, 'db_max': db_max,
                         'bins': bins}
        elif kind == FRAME_AUDIO:
            rate, ts, n = struct.unpack_from('<IdI', payload)
            pcm = np.frombuffer(payload[struct.calcsize('<IdI'):], dtype='<i2', count=n)
            yield kind, {'rate': rate, 'time': ts, 'pcm': pcm}
        elif kind == FRAME_JSON:
            yield kind, json.loads(payload.decode())


def publish(session_id: str, frame: bytes) -> None:
    """Best effort: the waterfall must never break the session feeding it."""
    try:
        get_redis_raw().publish(channel_name(session_id), frame)
    except Exception as e:
        logger.debug(f"Spectrum publish failed: {e}")


def touch_viewer(session_id: str, listening: bool) -> None:
    r = get_redis()
    r.set(_viewer_key(session_id), '1', ex=VIEWER_TTL)
    if listening:
        r.set(_listen_key(session_id), '1', ex=VIEWER_TTL)


def save_state(session_id: str, state: dict[str, Any]) -> None:
    try:
        get_redis().set(state_key(session_id), json.dumps(state), ex=86400)
    except Exception as e:
        logger.debug(f"Spectrum state not saved: {e}")


def load_state(session_id: str) -> Optional[dict[str, Any]]:
    raw = get_redis().get(state_key(session_id))
    return json.loads(str(raw)) if raw else None


class _Flags:
    """Cached 'is anyone watching / listening' lookups (at most one Redis round trip per second)."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._checked = 0.0
        self.viewers = False
        self.listening = False
        self.last_viewer = time.monotonic()

    def refresh(self) -> None:
        now = time.monotonic()
        if now - self._checked < 1.0:
            return
        self._checked = now
        try:
            r = get_redis()
            self.viewers = bool(r.exists(_viewer_key(self.session_id)))
            self.listening = bool(r.exists(_listen_key(self.session_id)))
        except Exception:
            self.viewers = self.listening = False
        if self.viewers:
            self.last_viewer = now


class SpectrumTap:
    """Waterfall rows from the IQ of any session; FFTs only run while someone watches."""

    def __init__(self, session_id: str, centre: int, sample_rate: int, fft_size: int = 2048, fps: float = 10.0,
                 dc_spike: bool = False, flags: Optional[_Flags] = None):
        self.session_id = session_id
        self.centre = int(centre)
        self.sample_rate = int(sample_rate)
        self.fps = float(fps)
        self.dc_spike = dc_spike
        self.analyzer = SpectrumAnalyzer(fft_size)
        self.flags = flags or _Flags(session_id)
        self._next = 0.0

    def set_centre(self, centre: int) -> None:
        self.centre = int(centre)
        self.analyzer = SpectrumAnalyzer(self.analyzer.fft_size)

    def feed(self, iq: NDArray[np.complexfloating]) -> None:
        self.flags.refresh()
        if not self.flags.viewers:
            return
        self.analyzer.feed(iq)
        now = time.monotonic()
        if now < self._next:
            return
        self._next = now + 1.0 / self.fps
        db = self.analyzer.frame()
        if db is None:
            return
        if self.dc_spike:
            db = mask_dc(db, width=max(1, self.analyzer.fft_size // 512))
        publish(self.session_id, pack_spectrum(self.centre, self.sample_rate, time.time(),
                                               to_uint8(db, DB_MIN, DB_MAX)))


class SpectrumSession(BaseStreamingDecoder):
    """Waterfall plus one listening channel; gives way to every other SDR job."""

    def __init__(self, frequency: int, sample_rate: int, gain: int, duration: int, fft_size: int = 2048,
                 fps: float = 10.0, device_type: Optional[str] = None, device_address: Optional[str] = None,
                 device_id: Optional[str] = None):
        super().__init__(frequency, duration, gain, sample_rate)
        self.device_address = device_address
        self._use_device(device_type, device_address, device_id)
        if self.sdr_type == SDRType.UNKNOWN:
            raise ValueError("No SDR hardware detected")
        low, high = SPAN_LIMITS.get(self.sdr_type, (200_000, 10_000_000))
        self.sample_rate = min(max(int(sample_rate), low), high)
        get_sdr_instance(frequency=frequency, sample_rate=self.sample_rate, gain=gain,
                         sdr_type=self.sdr_type, device_address=device_address)
        self.fft_size = int(fft_size)
        self.fps = float(fps)
        self.channel_frequency = int(frequency)
        self.modulation = 'FM'
        self.cw_bandwidth = 500
        self.squelch_db: Optional[float] = None
        self.preempted_by: Optional[str] = None
        self._commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self._receiver: Optional[ChannelReceiver] = None
        self._gate: Optional[SquelchGate] = None
        self._audio: list[NDArray[np.float64]] = []
        self._audio_samples = 0
        self.tap: Optional[SpectrumTap] = None

    # abstract members (no external decoder process)
    def _start_decoder(self) -> Any:  # pragma: no cover - not used
        raise NotImplementedError

    def _parse_decoder_line(self, line: str) -> Optional[dict[str, Any]]:  # pragma: no cover
        return None

    def _index_packet(self, packet: dict[str, Any]) -> None:  # pragma: no cover
        pass

    def _get_mode(self) -> str:
        return 'spectrum'

    # ------------------------------------------------------------------ control
    def state(self) -> dict[str, Any]:
        return {
            'session_id': self.session.session_id if self.session else None, 'mode': 'spectrum',
            'centre': int(self.frequency), 'span': int(self.sample_rate), 'fft_size': self.fft_size,
            'fps': self.fps, 'sdr_type': self.sdr_type.value, 'channel': int(self.channel_frequency),
            'modulation': self.modulation, 'cw_bandwidth': self.cw_bandwidth, 'squelch_db': self.squelch_db,
            'tunable': True,
        }

    def tune(self, **changes: Any) -> None:
        """Queue a change (centre, channel, modulation, cw_bandwidth, squelch_db); applied by the stream thread."""
        self._commands.put(changes)

    def preempt(self, by_kind: str) -> None:
        """Another job needs the SDR: stop now (called from the preempt handler)."""
        self.preempted_by = by_kind
        self.stop_event.set()

    def _apply_commands(self) -> bool:
        """Apply queued changes. Returns True when the SDR must be retuned (new centre)."""
        retune = False
        changed = False
        while True:
            try:
                cmd = self._commands.get_nowait()
            except queue.Empty:
                break
            changed = True
            if cmd.get('centre') is not None and int(cmd['centre']) != self.frequency:
                self.frequency = int(cmd['centre'])
                retune = True
            if cmd.get('channel') is not None:
                self.channel_frequency = int(cmd['channel'])
            if cmd.get('modulation'):
                self.modulation = str(cmd['modulation']).upper()
                self._receiver = None
            if cmd.get('cw_bandwidth'):
                self.cw_bandwidth = int(cmd['cw_bandwidth'])
                self._receiver = None
            if 'squelch_db' in cmd:
                self.squelch_db = cmd['squelch_db']
                self._gate = None
        half = self.sample_rate * 0.45
        if abs(self.channel_frequency - self.frequency) > half:
            self.channel_frequency = int(self.frequency)
        if changed:
            if self._receiver is not None:
                self._receiver.set_offset(self.channel_frequency - self.frequency)
            if self.tap is not None and retune:
                self.tap.set_centre(int(self.frequency))
            self._publish_state()
        return retune

    def _publish_state(self) -> None:
        if self.session is None:
            return
        state = self.state()
        save_state(self.session.session_id, state)
        publish(self.session.session_id, pack_json({'state': state}))
        if self.session.frequency != self.frequency:     # keep the session card on the new centre
            from radiomoni.session_store import session_manager
            self.session.frequency = int(self.frequency)
            session_manager.save_session(self.session)

    # ------------------------------------------------------------------ pipeline
    def _stream_worker_simple(self, session_manager: SessionManager) -> None:
        assert self.session is not None
        sid = self.session.session_id
        flags = _Flags(sid)
        self.tap = SpectrumTap(sid, int(self.frequency), self.sample_rate, self.fft_size, self.fps,
                               dc_spike=self.sdr_type == SDRType.HACKRF, flags=flags)
        try:
            self._publish_state()          # state first: a client may tune as soon as it sees "running"
            self.session.status = 'running'
            session_manager.save_session(self.session)
            while not self.stop_event.is_set():
                self.sdr_proc = self._start_sdr_capture()
                if not self._run(flags, session_manager):
                    break
                self._cleanup()           # retune: restart the SDR process at the new centre
                self.sdr_proc = None
        except Exception as e:
            logger.error(f"Spectrum session failed: {e}", exc_info=True)
            self.session.status = 'failed'
            self.session.error = str(e)
            session_manager.save_session(self.session)
        finally:
            if self.preempted_by:
                self.session.status = 'preempted'
                self.session.error = f'Stopped: the SDR is needed by {self.preempted_by}'
            self._cleanup()
            self._finish_session(session_manager)
            publish(sid, pack_json({'end': self.session.status, 'reason': self.session.error}))

    def _run(self, flags: _Flags, session_manager: SessionManager) -> bool:
        """Read IQ until stop (returns False) or a retune is requested (returns True)."""
        assert self.sdr_proc is not None and self.sdr_proc.stdout is not None and self.session is not None
        bytes_per_value = 2 if self.sdr_type in (SDRType.AIRSPYHF, SDRType.USRP) else 1
        chunk_bytes = int(self.sample_rate * CHUNK_SECONDS) * 2 * bytes_per_value
        started = self.session.start_time.timestamp()
        last_save = time.time()
        while not self.stop_event.is_set():
            if self.duration and time.time() - started >= self.duration:
                return False
            if self._apply_commands():
                return True
            raw = self._read_with_timeout(self.sdr_proc.stdout, chunk_bytes, timeout=5.0)
            if not raw:
                logger.info("Spectrum: SDR stream ended")
                return False
            iq = self._bytes_to_iq(raw)
            assert self.tap is not None
            self.tap.feed(iq)
            if flags.listening:
                self._listen(iq)
            elif self._receiver is not None:
                self._receiver, self._audio, self._audio_samples = None, [], 0
            if time.monotonic() - flags.last_viewer > IDLE_TIMEOUT:
                logger.info(f"Spectrum session {self.session.session_id}: nobody watching, stopping")
                self.session.error = 'Stopped: nobody was watching'
                return False
            if time.time() - last_save > 5:
                session_manager.save_session(self.session)
                last_save = time.time()
        return False

    def _listen(self, iq: NDArray[np.complex64]) -> None:
        if self._receiver is None:
            self._receiver = ChannelReceiver(self.sample_rate, self.channel_frequency - self.frequency,
                                             self.modulation, cw_bandwidth_hz=self.cw_bandwidth)
            self._audio, self._audio_samples = [], 0
        baseband = self._receiver.decimator.process(self._receiver.mixer.process(iq))
        audio = self._receiver.demod.process(baseband)
        if self._receiver.agc is not None:
            audio = self._receiver.agc.process(audio)
        if self.squelch_db is not None:
            if self._gate is None:
                self._gate = SquelchGate(squelch_db=float(self.squelch_db), hang_time=0.5,
                                         chunk_seconds=CHUNK_SECONDS)
            self._gate.update(chunk_power_db(baseband.astype(np.complex64)))
            if not self._gate.is_open:
                audio = np.zeros_like(audio)
        self._audio.append(np.clip(audio, -1.0, 1.0))
        self._audio_samples += len(audio)
        if self._audio_samples >= self._receiver.audio_rate * AUDIO_BLOCK_SECONDS and self.session:
            pcm: NDArray[np.int16] = (np.concatenate(self._audio) * 32767).astype(np.int16)
            self._audio, self._audio_samples = [], 0
            publish(self.session.session_id, pack_audio(self._receiver.audio_rate, time.time(), pcm))

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)


# ------------------------------------------------------------------ preemption
def preempt_local(by_kind: str, owner: Optional[str] = None) -> int:
    """Stop the spectrum session of this process that holds `owner`'s lock (all of them without an
    owner). Returns how many were stopped. Only that device's waterfall gives way."""
    from radiomoni.session_store import session_manager
    stopped = 0
    for decoder in list(session_manager.get_all_active_decoders().values()):
        if not isinstance(decoder, SpectrumSession) or decoder.stop_event.is_set():
            continue
        if owner is not None and (decoder.lease is None or decoder.lease.owner != owner):
            continue
        decoder.preempt(by_kind)
        stopped += 1
    return stopped


def _preempt(holder: dict[str, Any], by_kind: str) -> None:
    owner = holder.get('owner')
    if not preempt_local(by_kind, owner):
        # held by another API process
        events.send_control('preempt', kind='spectrum', by=by_kind, owner=owner)


sdr_lock.register_preemptible('spectrum', _preempt)


def stream_frames(session_id: str, listen: bool, is_running: Any) -> Iterator[bytes]:
    """
    Generator for GET /spectrum/<id>/stream: current state first, then every
    frame of the session. Keeps the viewer (and listener) flags alive and ends
    with the session. `is_running()` tells whether the session still runs.
    """
    pubsub = get_redis_raw().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel_name(session_id))
    try:
        touch_viewer(session_id, listen)
        yield pack_json({'state': load_state(session_id) or {'session_id': session_id}})
        last_touch = time.monotonic()
        while True:
            if time.monotonic() - last_touch > 5:
                touch_viewer(session_id, listen)
                last_touch = time.monotonic()
                if not is_running():
                    yield pack_json({'end': 'finished'})
                    return
            message = pubsub.get_message(timeout=1.0)
            if message is None:
                continue
            data = message.get('data')
            if isinstance(data, bytes):
                yield data
                if data[:1] == bytes([FRAME_JSON]) and b'"end"' in data[:64]:
                    return
    finally:
        try:
            pubsub.close()
        except Exception:
            pass
