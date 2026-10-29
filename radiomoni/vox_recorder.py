"""
Squelch / VOX controlled voice recording (N5).

The SDR streams continuously; recording only happens while a signal is
present. Each transmission becomes its own WAV segment which is stored,
optionally transcribed with Whisper and checked against the alert rules.
This makes 24/7 monitoring of a channel practical without filling the disk
with silence.

    power (dB) ──► SquelchGate ──open──► demodulate + buffer audio
                                 close──► write WAV ─► transcribe ─► store/alert
"""

import logging
import os
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import IO, Any, Optional

import numpy as np
from numpy.typing import NDArray
from scipy.io import wavfile

from radiomoni import alerts
from radiomoni import events
from radiomoni.sdr_hardware import SDRType, detect_sdr, get_sdr_instance
from radiomoni.streaming_decoder_service import BaseStreamingDecoder, SessionManager

logger = logging.getLogger(__name__)

AUDIO_RATE = 16_000
CHUNK_SECONDS = 0.05
_transcribe_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='vox-transcribe')


@dataclass
class SquelchGate:
    """
    Hysteresis squelch with an adaptive noise floor.

    The noise floor is the 20th percentile of recent chunk powers while the
    gate is closed, so it follows slow changes but ignores transmissions.
    """
    squelch_db: float = 10.0
    hang_time: float = 1.5           # seconds the gate stays open after the signal drops
    chunk_seconds: float = CHUNK_SECONDS
    history_seconds: float = 10.0
    noise_floor: Optional[float] = None
    is_open: bool = False
    _history: deque[float] = field(default_factory=deque)
    _below_since: Optional[float] = None
    _t: float = 0.0

    def update(self, power_db: float) -> Optional[str]:
        """Feed one chunk's power. Returns 'open', 'close' or None."""
        self._t += self.chunk_seconds
        if not self.is_open:
            self._history.append(power_db)
            max_len = max(1, int(self.history_seconds / self.chunk_seconds))
            while len(self._history) > max_len:
                self._history.popleft()
            self.noise_floor = float(np.percentile(np.fromiter(self._history, dtype=np.float64), 20))
            # need ~0.5 s of history before the first decision
            if len(self._history) >= max(5, int(0.5 / self.chunk_seconds)) and \
                    power_db > self.noise_floor + self.squelch_db:
                self.is_open = True
                self._below_since = None
                return 'open'
            return None
        assert self.noise_floor is not None
        # close threshold a bit lower than open threshold (hysteresis)
        if power_db < self.noise_floor + self.squelch_db - 3.0:
            if self._below_since is None:
                self._below_since = self._t
            elif self._t - self._below_since >= self.hang_time:
                self.is_open = False
                self._below_since = None
                return 'close'
        else:
            self._below_since = None
        return None


def chunk_power_db(iq: NDArray[np.complex64]) -> float:
    power = float(np.mean(np.abs(iq) ** 2)) if len(iq) else 0.0
    return float(10.0 * np.log10(power + 1e-12))


class VoxRecorder(BaseStreamingDecoder):
    """Streams IQ from the SDR and records only while the squelch is open."""

    def __init__(self, frequency: int, duration: int, gain: int, sample_rate: int,
                 modulation: str = 'FM', squelch_db: float = 10.0, hang_time_ms: int = 1500,
                 min_segment_ms: int = 800, max_segment_s: int = 60, transcribe: bool = True,
                 language: Optional[str] = None, device_type: Optional[str] = None,
                 device_address: Optional[str] = None, output_dir: str = './recordings'):
        super().__init__(frequency, duration, gain, sample_rate)
        self.device_address = device_address
        self.sdr_type = detect_sdr(preferred_type=device_type, device_address=device_address)
        if self.sdr_type == SDRType.UNKNOWN:
            raise ValueError("No SDR hardware detected")
        if self.sdr_type == SDRType.HACKRF:
            self.sample_rate = max(self.sample_rate, 2_000_000)   # HackRF minimum
        get_sdr_instance(frequency=frequency, sample_rate=self.sample_rate, gain=gain,
                         sdr_type=self.sdr_type, device_address=device_address)
        self.modulation = modulation.upper()
        self.gate = SquelchGate(squelch_db=squelch_db, hang_time=hang_time_ms / 1000.0)
        self.min_segment_s = min_segment_ms / 1000.0
        self.max_segment_s = max_segment_s
        self.transcribe = transcribe
        self.language = language
        self.output_dir = output_dir
        self.segment_count = 0
        self._segment: list[NDArray[np.int16]] = []
        self._segment_started: Optional[datetime] = None
        self._segment_peak_db = -200.0

    # abstract members (VOX has no external decoder process)
    def _start_decoder(self) -> Any:  # pragma: no cover - not used
        raise NotImplementedError

    def _parse_decoder_line(self, line: str) -> Optional[dict[str, Any]]:  # pragma: no cover
        return None

    def _index_packet(self, packet: dict[str, Any]) -> None:  # pragma: no cover
        pass

    def _get_mode(self) -> str:
        return 'vox'

    # ------------------------------------------------------------------ pipeline
    def _stream_worker_simple(self, session_manager: SessionManager) -> None:
        assert self.session is not None
        try:
            self.session.status = 'running'
            session_manager.save_session(self.session)
            self.sdr_proc = self._start_sdr_capture()
            self._vox_loop(self.sdr_proc.stdout, session_manager)
        except Exception as e:
            logger.error(f"VOX session failed: {e}", exc_info=True)
            self.session.status = 'failed'
            self.session.error = str(e)
            session_manager.save_session(self.session)
        finally:
            if self._segment:
                self._finish_segment(session_manager)
            self._cleanup()
            self._finish_session(session_manager)

    def _vox_loop(self, iq_stream: Optional[IO[bytes]], session_manager: SessionManager) -> None:
        assert iq_stream is not None and self.session is not None
        bytes_per_value = 2 if self.sdr_type in (SDRType.AIRSPYHF, SDRType.USRP) else 1
        chunk_bytes = int(self.sample_rate * CHUNK_SECONDS) * 2 * bytes_per_value
        started = time.time()
        last_save = started
        while not self.stop_event.is_set():
            if self.duration and time.time() - started >= self.duration:
                break
            raw = self._read_with_timeout(iq_stream, chunk_bytes, timeout=5.0)
            if not raw:
                logger.info("VOX: SDR stream ended")
                break
            self.process_chunk(self._bytes_to_iq(raw), session_manager)
            if time.time() - last_save > 5:
                session_manager.save_session(self.session)
                last_save = time.time()

    def process_chunk(self, iq: NDArray[np.complex64], session_manager: SessionManager) -> None:
        """Run one IQ chunk through the gate (public for tests)."""
        power = chunk_power_db(iq)
        transition = self.gate.update(power)
        if transition == 'open':
            self._segment = []
            self._segment_started = datetime.now(timezone.utc)
            self._segment_peak_db = power
            events.publish('vox', {'session_id': self.session.session_id if self.session else None,
                                   'state': 'open', 'power_db': round(power, 1), 'frequency': self.frequency})
        if self.gate.is_open or transition == 'close':
            self._segment.append(self._demodulate(iq))
            self._segment_peak_db = max(self._segment_peak_db, power)
            seconds = len(self._segment) * CHUNK_SECONDS
            if transition == 'close' or seconds >= self.max_segment_s:
                self._finish_segment(session_manager)
                if transition != 'close':
                    # long transmission: keep recording into a new segment
                    self._segment_started = datetime.now(timezone.utc)

    def _demodulate(self, iq: NDArray[np.complex64]) -> NDArray[np.int16]:
        if self.modulation == 'AM':
            audio = np.abs(iq).astype(np.float64)
            audio -= audio.mean()
            gain = 1.0 / (np.max(np.abs(audio)) + 1e-9)
        else:
            audio = np.angle(iq[1:] * np.conj(iq[:-1])).astype(np.float64)
            gain = float(self.sample_rate) / (2.0 * np.pi * 5000.0)   # 5 kHz NFM deviation → ±1
        audio16k = self._resample(audio, int(self.sample_rate), AUDIO_RATE)
        pcm: NDArray[np.int16] = (np.clip(audio16k * gain, -1.0, 1.0) * 32767).astype(np.int16)
        return pcm

    def _finish_segment(self, session_manager: SessionManager) -> None:
        chunks, self._segment = self._segment, []
        seconds = len(chunks) * CHUNK_SECONDS
        if not chunks or seconds < self.min_segment_s:
            return
        started = self._segment_started or datetime.now(timezone.utc)
        os.makedirs(self.output_dir, exist_ok=True)
        name = f"vox_{started:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.wav"
        path = os.path.join(self.output_dir, name)
        wavfile.write(path, AUDIO_RATE, np.concatenate(chunks))
        self.segment_count += 1
        if self.session is not None:
            self.session.packet_count = self.segment_count
            self.session.last_packet_time = datetime.now(timezone.utc)
            session_manager.save_session(self.session)
        session_id = self.session.session_id if self.session else None
        doc: dict[str, Any] = {
            'uuid': str(uuid.uuid4()), 'created_at': started.isoformat(), 'frequency': int(self.frequency),
            'modulation': self.modulation, 'duration_seconds': round(seconds, 2), 'rf_gain': self.gain,
            'sample_rate': self.sample_rate, 'audio_file': name, 'sdr_type': self.sdr_type.value,
            'mode': 'vox', 'peak_power_db': round(self._segment_peak_db, 1),
            'noise_floor_db': round(self.gate.noise_floor or 0.0, 1),
            'metadata': {'session_id': session_id},
        }
        events.publish('vox', {'session_id': session_id, 'state': 'segment',
                               'audio_file': name, 'duration': doc['duration_seconds'],
                               'frequency': doc['frequency']})
        if self.transcribe:
            _transcribe_pool.submit(self._transcribe_and_store, path, doc)
        else:
            self._store(doc)

    def _transcribe_and_store(self, path: str, doc: dict[str, Any]) -> None:
        try:
            from radiomoni.services import get_transcription_service
            result = get_transcription_service().transcribe(path, language=self.language)
            doc.update({'transcription': result.get('text'), 'detected_language': result.get('language'),
                        'confidence_score': result.get('language_probability'), 'segments': result.get('segments')})
            alerts.evaluate('voice', {'transcription': result.get('text'), 'frequency': doc['frequency']})
            events.publish('vox', {'session_id': doc['metadata']['session_id'], 'state': 'transcribed',
                                   'audio_file': doc['audio_file'], 'text': result.get('text')})
        except Exception as e:
            logger.warning(f"VOX transcription failed for {doc['audio_file']}: {e}")
            doc['transcription_error'] = str(e)[:500]
            events.publish('vox', {'session_id': doc['metadata']['session_id'], 'state': 'transcription_failed',
                                   'audio_file': doc['audio_file'], 'error': str(e)[:200]})
        self._store(doc)

    @staticmethod
    def _store(doc: dict[str, Any]) -> None:
        try:
            from radiomoni.storage import get_storage
            get_storage().index_capture(doc)
        except Exception as e:
            logger.warning(f"Could not store VOX segment: {e}")

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)
