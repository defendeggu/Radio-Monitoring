"""
CW (Morse) decoding session.

Streams IQ from the SDR, tunes to the CW signal and decodes it live with
radiomoni.morse.CwDecoder. Text is published character by character (event
"cw"); a pause of 3 s (or 60 s of continuous text) ends a transmission, which
is stored (index radio-cw-*), checked against the alert rules and optionally
saved as WAV for the play button in Kibana.

The SDR is tuned a little beside the wanted frequency (HackRF and RTL-SDR
have a DC spike in the centre); the mixer moves the signal back. Like the
waterfall, the session feeds a SpectrumTap and sends audio while someone
listens, both over GET /spectrum/<id>/stream. tune() retunes without a restart
as long as the new frequency is inside the bandwidth (clicks on RBN spots).
"""

import logging
import os
import queue
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray
from scipy.io import wavfile

from radiomoni import alerts
from radiomoni import events
from radiomoni.decoders import spectrum
from radiomoni.decoders.streaming import BaseStreamingDecoder, SessionManager
from radiomoni.dsp import ChannelReceiver, Decimator, Mixer
from radiomoni.morse import CwDecoder, callsigns
from radiomoni.rbn import band_of
from radiomoni.sdr_hardware import SDRType, detect_sdr, get_sdr_instance

logger = logging.getLogger(__name__)

CHUNK_SECONDS = 0.05
DECODER_RATE = 4000            # Hz of the complex baseband fed to the decoder
PAUSE_SECONDS = 3.0            # silence that ends a transmission
MAX_TRANSMISSION_SECONDS = 60
EDGE = 0.45                    # usable part of the bandwidth on each side of the centre

SAMPLE_RATES = {SDRType.HACKRF: 2_000_000, SDRType.RTLSDR: 1_024_000, SDRType.AIRSPYHF: 768_000,
                SDRType.USRP: 1_000_000}


class CwSession(BaseStreamingDecoder):
    """Live CW decoder on one frequency; retunable while running."""

    def __init__(self, frequency: int, gain: int, duration: int, sample_rate: Optional[int] = None,
                 wpm: float = 20.0, cw_bandwidth: int = 200, tone_hz: int = 700, record: bool = False,
                 device_type: Optional[str] = None, device_address: Optional[str] = None,
                 output_dir: str = './recordings'):
        sdr_type = detect_sdr(preferred_type=device_type, device_address=device_address)
        if sdr_type == SDRType.UNKNOWN:
            raise ValueError("No SDR hardware detected")
        rate = int(sample_rate or SAMPLE_RATES.get(sdr_type, 1_000_000))
        if sdr_type == SDRType.HACKRF:
            rate = max(rate, 2_000_000)
        super().__init__(frequency, duration, gain, rate)
        self.sdr_type = sdr_type
        self.device_address = device_address
        self.target = int(frequency)
        # keep the wanted signal away from the DC spike of zero-IF receivers
        self.dc_offset = int(rate / 4) if sdr_type in (SDRType.HACKRF, SDRType.RTLSDR) else 0
        self.frequency = self.target + self.dc_offset          # hardware centre
        get_sdr_instance(frequency=int(self.frequency), sample_rate=rate, gain=gain, sdr_type=sdr_type,
                         device_address=device_address)
        self.wpm = wpm
        self.cw_bandwidth = int(cw_bandwidth)
        self.tone_hz = int(tone_hz)
        self.record = record
        self.output_dir = output_dir
        self._commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self._build_chain()
        self.tap: Optional[spectrum.SpectrumTap] = None
        self._listener: Optional[ChannelReceiver] = None
        self._audio_out: list[NDArray[np.float64]] = []
        self._audio_out_samples = 0
        self._tx: Optional[dict[str, Any]] = None
        self._tx_audio: list[NDArray[np.float64]] = []
        self.transmissions = 0

    def _build_chain(self) -> None:
        self.mixer = Mixer(self.sample_rate, self.target - self.frequency)
        self.decimator = Decimator(self.sample_rate, DECODER_RATE)
        self.decoder = CwDecoder(self.decimator.output_rate, bandwidth_hz=self.cw_bandwidth, wpm_guess=self.wpm)
        self._recorder: Optional[ChannelReceiver] = None

    # abstract members (no external decoder process)
    def _start_decoder(self) -> Any:  # pragma: no cover - not used
        raise NotImplementedError

    def _parse_decoder_line(self, line: str) -> Optional[dict[str, Any]]:  # pragma: no cover
        return None

    def _index_packet(self, packet: dict[str, Any]) -> None:  # pragma: no cover
        pass

    def _get_mode(self) -> str:
        return 'cw'

    # ------------------------------------------------------------------ state / control
    def state(self) -> dict[str, Any]:
        return {
            'session_id': self.session.session_id if self.session else None, 'mode': 'cw',
            'centre': int(self.frequency), 'span': int(self.sample_rate), 'channel': int(self.target),
            'modulation': 'CW', 'cw_bandwidth': self.cw_bandwidth, 'tone_hz': self.tone_hz,
            'sdr_type': self.sdr_type.value, 'record': self.record, 'tunable': True, 'dc_offset': self.dc_offset,
            'wpm': self.decoder.wpm, 'snr_db': self.decoder.snr_db, 'afc_hz': round(self.decoder.offset_hz),
        }

    def tune(self, **changes: Any) -> None:
        """Queue a change (channel, centre, cw_bandwidth); applied by the stream thread."""
        self._commands.put(changes)

    def _apply_commands(self) -> bool:
        """Apply queued changes. Returns True when the SDR must be retuned."""
        retune = changed = False
        while True:
            try:
                cmd = self._commands.get_nowait()
            except queue.Empty:
                break
            changed = True
            if cmd.get('cw_bandwidth'):
                self.cw_bandwidth = int(cmd['cw_bandwidth'])
            channel = cmd.get('channel')
            if channel is not None and int(channel) != self.target:
                self.target = int(channel)
            centre = cmd.get('centre')
            if centre is not None and int(centre) != self.frequency:
                self.frequency = int(centre)
                retune = True
            if abs(self.target - self.frequency) > self.sample_rate * EDGE:
                self.frequency = self.target + self.dc_offset
                retune = True
        if changed:
            self._end_transmission()           # a new station: close the old transmission
            self._build_chain()                # new offset, fresh timing and noise levels
            self._listener = None
            if retune and self.tap is not None:
                self.tap.set_centre(int(self.frequency))
            self._publish_state()
        return retune

    def _publish_state(self) -> None:
        if self.session is None:
            return
        state = self.state()
        spectrum.save_state(self.session.session_id, state)
        spectrum.publish(self.session.session_id, spectrum.pack_json({'state': state}))

    # ------------------------------------------------------------------ pipeline
    def _stream_worker_simple(self, session_manager: SessionManager) -> None:
        assert self.session is not None
        sid = self.session.session_id
        flags = spectrum._Flags(sid)
        self.tap = spectrum.SpectrumTap(sid, int(self.frequency), self.sample_rate,
                                        dc_spike=self.sdr_type == SDRType.HACKRF, flags=flags)
        try:
            self.session.status = 'running'
            self.session.frequency = self.target
            session_manager.save_session(self.session)
            self._publish_state()
            while not self.stop_event.is_set():
                self.sdr_proc = self._start_sdr_capture()
                if not self._run(flags, session_manager):
                    break
                self._cleanup()                # retune: restart the SDR process at the new centre
                self.sdr_proc = None
        except Exception as e:
            logger.error(f"CW session failed: {e}", exc_info=True)
            self.session.status = 'failed'
            self.session.error = str(e)
            session_manager.save_session(self.session)
        finally:
            self._end_transmission()
            self._cleanup()
            self._finish_session(session_manager)
            spectrum.publish(sid, spectrum.pack_json({'end': self.session.status, 'reason': self.session.error}))

    def _run(self, flags: Any, session_manager: SessionManager) -> bool:
        assert self.sdr_proc is not None and self.sdr_proc.stdout is not None and self.session is not None
        bytes_per_value = 2 if self.sdr_type in (SDRType.AIRSPYHF, SDRType.USRP) else 1
        chunk_bytes = int(self.sample_rate * CHUNK_SECONDS) * 2 * bytes_per_value
        started = self.session.start_time.timestamp()
        last_save = last_state = time.time()
        while not self.stop_event.is_set():
            if self.duration and time.time() - started >= self.duration:
                return False
            if self._apply_commands():
                if self.session is not None:
                    self.session.frequency = self.target
                    session_manager.save_session(self.session)
                return True
            raw = self._read_with_timeout(self.sdr_proc.stdout, chunk_bytes, timeout=5.0)
            if not raw:
                logger.info("CW: SDR stream ended")
                return False
            self.process_chunk(self._bytes_to_iq(raw), flags, session_manager)
            now = time.time()
            if now - last_state > 2:            # WPM / SNR / AFC for the page
                self._publish_state()
                last_state = now
            if now - last_save > 5:
                session_manager.save_session(self.session)
                last_save = now
        return False

    def process_chunk(self, iq: NDArray[np.complex64], flags: Any, session_manager: SessionManager) -> None:
        """Decode one IQ chunk (public for tests)."""
        if self.tap is not None:
            self.tap.feed(iq)
        flags.refresh()
        text = self.decoder.process(self.decimator.process(self.mixer.process(iq)))
        audio: Optional[NDArray[np.float64]] = None
        if flags.listening or self.record:
            if self._recorder is None:
                self._recorder = ChannelReceiver(self.sample_rate, self.target - self.frequency, 'CW',
                                                 cw_bandwidth_hz=max(250, self.cw_bandwidth), bfo_hz=self.tone_hz)
            audio = self._recorder.process(iq)
            if flags.listening:
                self._send_audio(audio)
        if text.strip():
            self._add_text(text)
        elif text and self._tx is not None:
            self._tx['text'] += text
        if self._tx is not None:
            if self.record and audio is not None:
                self._tx_audio.append(audio)
            age = (datetime.now(timezone.utc) - self._tx['started']).total_seconds()
            if self.decoder.seconds_since_mark() >= PAUSE_SECONDS or age >= MAX_TRANSMISSION_SECONDS:
                self._end_transmission(session_manager)

    def _send_audio(self, audio: NDArray[np.float64]) -> None:
        assert self._recorder is not None
        self._audio_out.append(audio)
        self._audio_out_samples += len(audio)
        if self._audio_out_samples >= self._recorder.audio_rate * spectrum.AUDIO_BLOCK_SECONDS and self.session:
            pcm: NDArray[np.int16] = (np.concatenate(self._audio_out) * 32767).astype(np.int16)
            self._audio_out, self._audio_out_samples = [], 0
            spectrum.publish(self.session.session_id, spectrum.pack_audio(self._recorder.audio_rate, time.time(), pcm))

    def _add_text(self, text: str) -> None:
        sid = self.session.session_id if self.session else None
        if self._tx is None:
            self._tx = {'started': datetime.now(timezone.utc), 'text': '', 'frequency': self.target}
            self._tx_audio = []
        self._tx['text'] += text
        events.publish('cw', {'session_id': sid, 'state': 'text', 'text': text, 'frequency': self.target,
                              'wpm': self.decoder.wpm, 'snr_db': self.decoder.snr_db})

    def _end_transmission(self, session_manager: Optional[SessionManager] = None) -> None:
        tx, self._tx = self._tx, None
        audio, self._tx_audio = self._tx_audio, []
        if tx is None:
            return
        text = ' '.join(tx['text'].split())
        if len(text.replace(' ', '')) < 2:      # a stray character is no transmission
            return
        ended = datetime.now(timezone.utc)
        sid = self.session.session_id if self.session else None
        doc: dict[str, Any] = {
            'uuid': str(uuid.uuid4()), 'timestamp': tx['started'].isoformat(), 'ended': ended.isoformat(),
            'duration_seconds': round((ended - tx['started']).total_seconds(), 1),
            'frequency': int(tx['frequency']), 'frequency_mhz': tx['frequency'] / 1e6,
            'band': band_of(tx['frequency'] / 1000.0), 'text': text,
            'callsigns': callsigns(text), 'wpm': self.decoder.wpm, 'snr_db': self.decoder.snr_db,
            'sdr_type': self.sdr_type.value, 'session_id': sid,
        }
        if self.record and audio:
            doc.update(self._save_wav(tx['started'], audio))
        self.transmissions += 1
        if self.session is not None:
            self.session.packet_count = self.transmissions
            self.session.last_packet_time = ended
            if session_manager is not None:
                session_manager.save_session(self.session)
        try:
            from radiomoni.storage.base import get_storage
            get_storage().index_event('cw', doc)
        except Exception as e:
            logger.warning(f"Could not store CW transmission: {e}")
        events.publish('cw', {'session_id': sid, 'state': 'transmission', **doc})
        alerts.evaluate('cw', {'text': text, 'callsign': ' '.join(doc['callsigns']), 'frequency': doc['frequency']})

    def _save_wav(self, started: datetime, audio: list[NDArray[np.float64]]) -> dict[str, Any]:
        from radiomoni import recording_links
        assert self._recorder is not None
        os.makedirs(self.output_dir, exist_ok=True)
        name = f"cw_{started:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.wav"
        pcm = (np.concatenate(audio) * 32767).astype(np.int16)
        wavfile.write(os.path.join(self.output_dir, name), int(round(self._recorder.audio_rate)), pcm)
        result: dict[str, Any] = {'audio_file': name}
        url = recording_links.audio_url(name)
        if url:
            result['audio_url'] = url
        return result

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)
