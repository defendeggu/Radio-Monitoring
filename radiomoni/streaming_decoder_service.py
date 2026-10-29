#!/usr/bin/env python3
"""
Streaming Decoder Service for Radio Monitoring System
Provides continuous real-time decoding without storing audio files

Supports:
- APRS (direwolf)
- POCSAG (multimon-ng)
- Multi-channel DDC (USRP N200)

Every decoded packet is stored, published on the live event bus (SSE) and
checked against the alert rules.
"""

import os
import time
import uuid
import logging
import threading
import subprocess
import numpy as np
import gc
import psutil
import select
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, IO, List, Union
from dataclasses import dataclass, field
from numpy.typing import NDArray
from scipy import signal
import json

from radiomoni import alerts
from radiomoni import events
from radiomoni.redis_client import get_redis
from radiomoni.sdr_hardware import detect_sdr, SDRType, get_sdr_instance, apply_hackrf_iq_correction
from radiomoni.sdr_lock import SdrLease, current_holder

logger = logging.getLogger(__name__)

# Stop a stream when the API process grows beyond this (the Whisper model alone needs ~1 GB)
MAX_RSS_MB = int(os.getenv('STREAM_MAX_RSS_MB', '3000'))


@dataclass
class ChannelConfig:
    """Configuration for one DDC channel in a multi-channel session."""
    mode: str               # 'aprs' or 'pocsag'
    frequency: int          # channel RF frequency in Hz
    label: str = ''
    channel_bw_hz: int = 16000   # 16 kHz for APRS, 25 kHz for POCSAG

    # Derived by MultiChannelStreamingDecoder.__init__:
    freq_offset: float = 0.0
    decoder_audio_rate: int = 48000
    fm_gain: float = 1.0

    # Runtime state (written only by the converter thread):
    fir_taps: NDArray[np.float32] = field(default_factory=lambda: np.array([], dtype=np.float32))
    fir_zi_i: Optional[NDArray[np.float32]] = None
    fir_zi_q: Optional[NDArray[np.float32]] = None
    phase_acc: float = 0.0
    decoder_proc: Optional[subprocess.Popen[bytes]] = None
    packet_count: int = 0


class StreamSession:
    """Represents a streaming decode session"""

    def __init__(self, mode: str, frequency: int, duration: int, gain: int, sample_rate: int):
        self.session_id = str(uuid.uuid4())
        self.mode = mode
        self.frequency = frequency
        self.duration = duration
        self.gain = gain
        self.sample_rate = sample_rate
        self.status = 'starting'  # starting, running, stopping, completed, failed
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.packet_count = 0
        self.last_packet_time: Optional[datetime] = None
        self.error: Optional[str] = None
        self.channel_configs: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dict for Redis storage"""
        return {
            'session_id': self.session_id,
            'mode': self.mode,
            'frequency': self.frequency,
            'duration': self.duration,
            'gain': self.gain,
            'sample_rate': self.sample_rate,
            'status': self.status,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time is not None else None,
            'packet_count': self.packet_count,
            'last_packet_time': self.last_packet_time.isoformat() if self.last_packet_time is not None else None,
            'error': self.error,
            'channel_configs': self.channel_configs
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamSession':
        """Deserialize session from dict"""
        session = cls(
            mode=data['mode'],
            frequency=data['frequency'],
            duration=data['duration'],
            gain=data['gain'],
            sample_rate=data['sample_rate']
        )
        session.session_id = data['session_id']
        session.status = data['status']
        session.start_time = datetime.fromisoformat(data['start_time'])
        session.end_time = datetime.fromisoformat(data['end_time']) if data.get('end_time') else None
        session.packet_count = data['packet_count']
        session.last_packet_time = datetime.fromisoformat(data['last_packet_time']) if data.get('last_packet_time') else None
        session.error = data.get('error')
        session.channel_configs = data.get('channel_configs')
        return session


class SessionManager:
    """Manages streaming sessions in Redis"""

    def __init__(self, redis_client: Any = None) -> None:
        self.redis: Any = redis_client if redis_client is not None else get_redis()
        # In-memory registry of live decoder instances (session_id → decoder)
        # This allows stop_streaming_session to call stop_stream() directly
        self._decoder_registry: Dict[str, Any] = {}

    def save_session(self, session: StreamSession) -> None:
        """Save session to Redis"""
        key = f"stream_session:{session.session_id}"
        self.redis.set(key, json.dumps(session.to_dict()))
        self.redis.expire(key, 86400 * 7)  # 7 days TTL

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        """Retrieve session from Redis"""
        key = f"stream_session:{session_id}"
        data_str = self.redis.get(key)
        if not data_str:
            return None
        data = json.loads(str(data_str))
        return StreamSession.from_dict(data)

    def delete_session(self, session_id: str) -> None:
        """Delete session from Redis"""
        key = f"stream_session:{session_id}"
        self.redis.delete(key)

    def list_sessions(self) -> list[StreamSession]:
        """List all active sessions"""
        sessions = []
        for key in self.redis.scan_iter("stream_session:*"):
            data_str = self.redis.get(key)
            if data_str:
                data = json.loads(str(data_str))
                sessions.append(StreamSession.from_dict(data))
        return sessions

    def register_decoder(self, session_id: str, decoder: Any) -> None:
        """Register a live decoder instance so it can be stopped by session_id."""
        self._decoder_registry[session_id] = decoder

    def get_decoder(self, session_id: str) -> Optional[Any]:
        """Return the live decoder instance for a session, or None."""
        return self._decoder_registry.get(session_id)

    def unregister_decoder(self, session_id: str) -> None:
        """Remove decoder from registry when session ends."""
        self._decoder_registry.pop(session_id, None)

    def get_all_active_decoders(self) -> Dict[str, Any]:
        """Return all registered (running) decoder instances."""
        return dict(self._decoder_registry)

    def reap_orphaned_sessions(self) -> int:
        """Mark sessions left 'starting'/'running' by a restarted or crashed API as failed.

        Every stream takes the SDR lock before its session is created and saves
        its final state before releasing it. So while the lock is free, a
        session without a decoder in this process cannot be alive anymore.
        Returns the number of sessions marked.
        """
        if current_holder() is not None:
            return 0
        reaped = 0
        for session in self.list_sessions():
            if session.status in ('starting', 'running') and self.get_decoder(session.session_id) is None:
                session.status = 'failed'
                session.error = 'Interrupted — the API was restarted'
                session.end_time = session.end_time or datetime.now(timezone.utc)
                self.save_session(session)
                reaped += 1
        if reaped:
            logger.warning(f"Marked {reaped} orphaned streaming session(s) as failed")
        return reaped

    def get_user_active_session(self, user_id: str = 'default') -> Optional[StreamSession]:
        """Get user's active session (max 1 per user)"""
        for session in self.list_sessions():
            if session.status in ['starting', 'running']:
                # In future: check user_id
                return session
        return None

    def create_session(self, decoder_type: str, decoder: 'BaseStreamingDecoder',
                      frequency: int, sample_rate: int, gain: int) -> str:
        """Create a new streaming session"""
        # Create session from decoder parameters
        session = StreamSession(
            mode=decoder_type,
            frequency=frequency,
            duration=decoder.duration,
            gain=gain,
            sample_rate=sample_rate
        )

        # Save to Redis
        self.save_session(session)

        # Store session in decoder
        decoder.session = session

        # Register live instance so stop_streaming_session can find it
        self.register_decoder(session.session_id, decoder)

        return session.session_id


class _DecimationStage:
    """IIR low-pass followed by decimation; filter state and decimation phase
    carry over between chunks."""

    def __init__(self, input_rate: float, cutoff_hz: float, factor: int, order: int):
        self.factor = factor
        self.sos = signal.butter(order, cutoff_hz, fs=input_rate, output='sos')
        self.zi = np.zeros((self.sos.shape[0], 2), dtype=np.complex128)
        self.offset = 0  # index in the next chunk of the next sample to keep

    def process(self, x: NDArray[np.complex128]) -> NDArray[np.complex128]:
        y, self.zi = signal.sosfilt(self.sos, x, zi=self.zi)
        out: NDArray[np.complex128] = y[self.offset::self.factor]
        self.offset = (self.offset - len(y)) % self.factor
        return out


class NarrowbandFMDemodulator:
    """Channel filter, decimation and FM discriminator for one narrowband FM
    channel at the tuned frequency.

    Filtering the IQ down to the channel *before* demodulating keeps the noise
    of the full SDR bandwidth out of the discriminator; without it, signals of
    typical strength never decode. All state carries over between chunks, so
    chunk boundaries leave no artefacts in the audio.

    Output: audio at ``audio_rate`` (≥ min_audio_rate, an integer divisor chain
    of the input rate), scaled so the given deviation maps to ±1.0.
    """

    def __init__(self, input_rate: int, channel_bw_hz: float, deviation_hz: float,
                 min_audio_rate: int = 44100):
        stage1_factor = max(1, input_rate // 200_000)
        rate1 = input_rate / stage1_factor
        stage2_factor = max(1, int(rate1 // min_audio_rate))
        self.audio_rate = int(round(rate1 / stage2_factor))

        self._stages: List[_DecimationStage] = []
        if stage1_factor > 1:
            self._stages.append(_DecimationStage(input_rate, 0.2 * rate1, stage1_factor, order=5))
        self._stages.append(_DecimationStage(rate1, 0.6 * channel_bw_hz, stage2_factor, order=6))

        self._gain = self.audio_rate / (2.0 * np.pi * deviation_hz)
        self._last: Optional[complex] = None

    def process(self, iq: NDArray[np.complex64]) -> NDArray[np.float64]:
        x: NDArray[np.complex128] = iq.astype(np.complex128)
        for stage in self._stages:
            x = stage.process(x)
        if len(x) == 0:
            return np.zeros(0, dtype=np.float64)
        if self._last is None:
            self._last = complex(x[0])
        prev = np.concatenate(([self._last], x[:-1]))
        self._last = complex(x[-1])
        audio: NDArray[np.float64] = np.angle(x * np.conj(prev)) * self._gain
        return audio


class BaseStreamingDecoder(ABC):
    """Base class for streaming decoders"""

    def __init__(self, frequency: int, duration: int, gain: int, sample_rate: int):
        self.frequency = frequency
        self.duration = duration
        self.gain = gain
        self.sample_rate = sample_rate
        self.session: Optional[StreamSession] = None
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.sdr_proc: Optional[subprocess.Popen[bytes]] = None
        self.decoder_proc: Optional[subprocess.Popen[bytes]] = None
        self.sdr_type: SDRType = SDRType.UNKNOWN  # Set by subclass __init__
        self.device_address: Optional[str] = None  # IP address for USRP N200
        self.lease: Optional[SdrLease] = None  # SDR lock held while streaming

    @property
    def _decoder_audio_rate(self) -> int:
        """Target audio sample rate for the decoder process (override in subclasses)"""
        return 48000  # Default: direwolf expects 48000 Hz

    @property
    def _fm_gain(self) -> float:
        """FM audio gain: scale demodulated output so expected deviation → ±1.0.
        Override in subclasses with the actual signal deviation.
        Default: generic NFM at 5 kHz deviation."""
        return float(self.sample_rate) / (2.0 * 3.141592653589793 * 5000.0)

    def _iq_to_decoder_audio(self, iq_complex: NDArray[np.complex64]) -> NDArray[np.float64]:
        """Turn one IQ chunk into decoder audio, scaled so full deviation → ±1.0.
        Default: demodulate at the full SDR rate and resample each chunk."""
        audio = self._fm_demodulate(iq_complex)
        # direwolf: 48000 Hz, multimon-ng -t raw: 22050 Hz
        audio_rs = self._resample(audio, self.sample_rate, self._decoder_audio_rate)
        return audio_rs * self._fm_gain

    @abstractmethod
    def _start_decoder(self) -> subprocess.Popen[bytes]:
        """Start decoder process (direwolf/multimon-ng)"""
        pass

    @abstractmethod
    def _parse_decoder_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse decoder output line to packet dict"""
        pass

    @abstractmethod
    def _index_packet(self, packet: Dict[str, Any]) -> None:
        """Index packet to Elasticsearch"""
        pass

    @abstractmethod
    def _get_mode(self) -> str:
        """Return mode name (aprs/pocsag)"""
        pass

    def start(self, session_manager: 'SessionManager') -> None:
        """Start streaming (without creating session - session already created)"""
        # Start background thread
        assert self.session is not None, "Session must be initialized before calling start()"

        self.thread = threading.Thread(target=self._stream_worker_simple, args=(session_manager,))
        self.thread.daemon = False
        self.thread.start()

    def _stream_worker_simple(self, session_manager: 'SessionManager') -> None:
        """Simplified streaming worker when session already exists"""
        try:
            assert self.session is not None, "Session must be initialized"
            self.session.status = 'running'
            session_manager.save_session(self.session)

            # 1. Start SDR process (stdout pipe)
            self.sdr_proc = self._start_sdr_capture()
            logger.info(f"SDR capture started for session {self.session.session_id}")

            # 2. Start decoder process (stdin/stdout pipes)
            self.decoder_proc = self._start_decoder()
            logger.info(f"Decoder started for session {self.session.session_id}")

            # 3. Stream IQ → Audio → Decoder → ES
            self._stream_pipeline(session_manager)

        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            if self.session is not None:
                self.session.status = 'failed'
                self.session.error = str(e)
                session_manager.save_session(self.session)
        finally:
            self._cleanup()
            self._finish_session(session_manager)

    def _finish_session(self, session_manager: 'SessionManager') -> None:
        """Mark the session finished (keeping 'failed'), free the SDR and notify listeners."""
        if self.session is not None:
            if self.session.status not in ('failed', 'completed'):
                self.session.status = 'completed'
            self.session.end_time = self.session.end_time or datetime.now(timezone.utc)
            session_manager.save_session(self.session)
            session_manager.unregister_decoder(self.session.session_id)
            events.publish('session', self.session.to_dict())
            logger.info(f"Stream session {self.session.session_id} finished ({self.session.status})")
        if self.lease is not None:
            self.lease.release()
            self.lease = None

    def _start_sdr_capture(self) -> subprocess.Popen[bytes]:
        """Launch SDR capture with stdout pipe and reduced priority (supports HackRF and RTL-SDR)"""
        # Use nice to reduce CPU priority (prevents CPU saturation)

        if self.sdr_type == SDRType.HACKRF:
            # HackRF LNA gain must be a multiple of 8 (0, 8, 16, 24, 32, 40)
            lna_gain = min(40, round(self.gain / 8) * 8)
            # HackRF command (no nice: priority reduction causes USB stalls via pipe backpressure)
            cmd = [
                'hackrf_transfer',
                '-r', '-',  # Write to stdout
                '-f', str(int(self.frequency)),
                '-s', str(self.sample_rate),
                '-l', str(lna_gain),
                '-g', str(self.gain)
            ]
            # Duration limit (optional - or run until stop)
            if self.duration:
                # -n is number of IQ samples (each sample = 2 bytes: 1 byte I + 1 byte Q)
                samples = int(self.sample_rate * self.duration)
                cmd.extend(['-n', str(samples)])

        elif self.sdr_type == SDRType.RTLSDR:
            # RTL-SDR command
            cmd = [
                'nice', '-n', '10',
                'rtl_sdr',
                '-f', str(int(self.frequency)),
                '-s', str(self.sample_rate),
                '-g', str(self.gain),
                '-'  # Output to stdout
            ]
            # NOTE: Don't use -n parameter for duration - let the timer handle it
            # Using -n causes the process to end immediately, leaving threads hanging

        elif self.sdr_type == SDRType.AIRSPYHF:
            # Airspy HF+ command
            cmd = [
                'nice', '-n', '10',
                'airspyhf_rx',
                '-f', f"{self.frequency / 1_000_000:.6f}",  # Frequency in MHz
                '-m', 'on',  # Enable HF AGC
                '-r', '-'  # Output to stdout
            ]
            # Duration limit (optional - or run until stop)
            if self.duration:
                num_samples = int(self.sample_rate * self.duration * 2)  # I+Q
                cmd.insert(-1, '-n')  # Insert before '-'
                cmd.insert(-1, str(num_samples))

        elif self.sdr_type == SDRType.USRP:
            # USRP N200 via Gigabit Ethernet (UHD uhd_rx_cfile)
            # Outputs int16 I/Q interleaved to /dev/stdout
            if not self.device_address:
                raise ValueError("USRP N200 requires device_address (IP address)")
            cmd = [
                'uhd_rx_cfile',
                f'--args=addr={self.device_address}',
                '-f', str(int(self.frequency)),
                '-r', str(self.sample_rate),
                '-g', str(self.gain),
                '--type', 'short',
                '/dev/stdout'
            ]
            if self.duration:
                samples = int(self.sample_rate * self.duration)
                cmd.extend(['-N', str(samples)])

        else:
            raise ValueError(f"Unsupported SDR type: {self.sdr_type}")

        logger.debug(f"Executing {self.sdr_type.name} SDR command: {cmd}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Set process group for easier cleanup
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )

        # Log process info
        logger.info(f"Started {self.sdr_type.name} SDR process (PID: {proc.pid}) with nice +10 priority")

        return proc

    def _stream_pipeline(self, session_manager: SessionManager) -> None:
        """Stream IQ → Audio → Decoder → ES"""

        assert self.sdr_proc is not None and self.decoder_proc is not None
        assert self.session is not None

        # Thread for IQ → Audio conversion
        converter_thread = threading.Thread(
            target=self._iq_to_audio_converter,
            args=(self.sdr_proc.stdout, self.decoder_proc.stdin)
        )
        converter_thread.start()

        # Thread for decoder output → ES
        indexer_thread = threading.Thread(
            target=self._decoder_output_indexer,
            args=(self.decoder_proc.stdout, session_manager)
        )
        indexer_thread.start()

        # Wait for completion or stop signal
        start_time = time.time()
        while not self.stop_event.is_set():
            # Check if duration exceeded
            if self.duration and (time.time() - start_time) >= self.duration:
                logger.info(f"Duration limit reached: {self.duration}s")
                self.stop_event.set()  # Signal threads to stop

                # Terminate SDR and decoder processes to unblock threads
                if self.sdr_proc and self.sdr_proc.poll() is None:
                    logger.info("Terminating SDR process...")
                    self.sdr_proc.terminate()
                if self.decoder_proc and self.decoder_proc.poll() is None:
                    logger.info("Terminating decoder process...")
                    self.decoder_proc.terminate()

                # Explicitly mark session as completed (don't rely on finally block)
                if self.session is not None:
                    self.session.status = 'completed'
                    self.session.end_time = datetime.now(timezone.utc)
                    session_manager.save_session(self.session)
                    logger.info(f"Session {self.session.session_id} marked as completed via duration timeout")

                break

            # Check if threads are still alive - exit if both died
            if not converter_thread.is_alive() and not indexer_thread.is_alive():
                logger.info("Both worker threads completed - ending session")

                # Explicitly mark session as completed (unless it already failed)
                if self.session is not None:
                    if self.session.status != 'failed':
                        self.session.status = 'completed'
                    self.session.end_time = datetime.now(timezone.utc)
                    session_manager.save_session(self.session)
                    logger.info(f"Session {self.session.session_id} marked as {self.session.status} "
                                "via thread completion")

                break

            # Update session status periodically
            if int(time.time()) % 5 == 0:  # Every 5 seconds
                session_manager.save_session(self.session)

            time.sleep(1)

        # Wait for threads to finish
        converter_thread.join(timeout=10)
        indexer_thread.join(timeout=10)

    def _iq_to_audio_converter(self, iq_stream: Optional[IO[bytes]], audio_sink: Optional[IO[bytes]]) -> None:
        """Convert IQ stream to audio and pipe to decoder"""
        assert iq_stream is not None and audio_sink is not None
        # Reduced chunk size from 1 second to 0.1 seconds to prevent memory exhaustion
        CHUNK_DURATION = 0.1  # seconds
        CHUNK_SIZE = int(self.sample_rate * 2 * CHUNK_DURATION)  # I+Q, int8

        chunk_count = 0
        last_gc_time = time.time()

        try:
            while not self.stop_event.is_set():
                # Check process memory usage every 10 chunks (~1 second)
                if chunk_count % 10 == 0:
                    process = psutil.Process()
                    process_mem_mb = process.memory_info().rss / (1024 * 1024)
                    if process_mem_mb > MAX_RSS_MB:
                        logger.error(f"Process memory critical: {process_mem_mb:.1f} MB - stopping stream")
                        self.stop_event.set()
                        break

                # Read IQ chunk with timeout support
                iq_bytes = self._read_with_timeout(iq_stream, CHUNK_SIZE, timeout=5.0)
                if not iq_bytes or len(iq_bytes) == 0:
                    if not self.stop_event.is_set():
                        self._record_sdr_failure()
                    logger.info("SDR stream ended")
                    break

                iq_complex = self._bytes_to_iq(iq_bytes)

                # FM demodulation, resampling and gain
                audio = self._iq_to_decoder_audio(iq_complex)

                # Clip to ±1.0, then convert to int16
                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

                # Write to decoder stdin
                audio_sink.write(audio_int16.tobytes())
                audio_sink.flush()

                # Cleanup arrays to free memory immediately
                del iq_bytes, iq_complex, audio, audio_int16

                chunk_count += 1

                # Force garbage collection every 5 seconds to prevent memory buildup
                current_time = time.time()
                if current_time - last_gc_time > 5.0:
                    gc.collect()
                    last_gc_time = current_time
                    logger.debug(f"GC: Processed {chunk_count} chunks, Memory: {psutil.virtual_memory().percent}%")

                # CPU throttling: small sleep to prevent CPU saturation
                time.sleep(0.001)  # 1ms sleep to allow other processes to run

        except Exception as e:
            logger.error(f"IQ conversion error: {e}", exc_info=True)
        finally:
            try:
                audio_sink.close()
            except Exception:
                pass
            # Final cleanup
            gc.collect()

    def _record_sdr_failure(self) -> None:
        """The IQ stream ended before the session did: if the SDR process exited
        with an error, mark the session failed with a readable reason."""
        proc = self.sdr_proc
        if proc is None:
            return
        try:
            returncode = proc.wait(timeout=3)  # stdout closes just before the process exits
        except subprocess.TimeoutExpired:
            return
        if returncode == 0:
            return

        err_text = ''
        try:
            import fcntl as _fcntl
            if proc.stderr is not None:
                fd = proc.stderr.fileno()
                _fcntl.fcntl(fd, _fcntl.F_SETFL, _fcntl.fcntl(fd, _fcntl.F_GETFL) | os.O_NONBLOCK)
                err_text = (proc.stderr.read() or b'').decode('utf-8', errors='ignore').strip()
        except Exception as e:
            logger.debug(f"Could not read SDR stderr: {e}")
        logger.error(f"SDR process exited ({returncode}): {err_text[-1500:]}")

        lowered = err_text.lower()
        if 'busy' in lowered:
            reason = 'SDR hardware busy — stop other sessions first'
        elif "couldn't transfer any bytes" in lowered:
            reason = 'SDR stopped delivering data (USB transfer stalled) — start the session again'
        else:
            last_line = err_text.splitlines()[-1] if err_text else ''
            reason = f"SDR process exited with code {returncode}" + (f": {last_line}" if last_line else '')
        if self.session is not None:
            self.session.status = 'failed'
            self.session.error = reason

    def _bytes_to_iq(self, iq_bytes: bytes) -> NDArray[np.complex64]:
        """Convert raw SDR output to normalized complex64 samples (device-specific format)."""
        iq_float: NDArray[np.float32]
        if self.sdr_type == SDRType.HACKRF:
            iq_float = np.frombuffer(iq_bytes, dtype=np.int8).astype(np.float32) / 127.0
        elif self.sdr_type == SDRType.RTLSDR:
            iq_float = (np.frombuffer(iq_bytes, dtype=np.uint8).astype(np.float32) - 127.5) / 127.5
        elif self.sdr_type in (SDRType.AIRSPYHF, SDRType.USRP):
            usable = len(iq_bytes) - (len(iq_bytes) % 2)
            iq_float = np.frombuffer(iq_bytes[:usable], dtype=np.int16).astype(np.float32) / 32768.0
        else:
            raise ValueError(f"Unsupported SDR type: {self.sdr_type}")
        if len(iq_float) % 2 != 0:
            iq_float = iq_float[:-1]
        iq_complex: NDArray[np.complex64] = (iq_float[0::2] + 1j * iq_float[1::2]).astype(np.complex64)
        if self.sdr_type == SDRType.HACKRF:
            iq_complex = apply_hackrf_iq_correction(iq_complex)
        return iq_complex

    def _read_with_timeout(self, stream: IO[bytes], size: int, timeout: float) -> bytes:
        """Read from stream with timeout support using select"""
        if hasattr(stream, 'fileno'):
            # Use select for timeout support on file descriptors
            ready, _, _ = select.select([stream], [], [], timeout)
            if not ready:
                logger.warning(f"Read timeout after {timeout}s")
                return b''
        # Fallback to regular read (for non-fd streams)
        return stream.read(size)

    def _fm_demodulate(self, iq_complex: NDArray[np.complex64]) -> NDArray[np.float64]:
        """FM demodulation using conjugate product discriminator"""
        # Conjugate product: angle(x[n] * conj(x[n-1])) = instantaneous phase difference
        product = iq_complex[1:] * np.conj(iq_complex[:-1])
        audio: NDArray[np.float64] = np.angle(product).astype(np.float64)
        return audio

    def _resample(self, audio: NDArray[np.float64], from_rate: int, to_rate: int) -> NDArray[np.float64]:
        """Resample audio using multi-stage decimation for large ratios (performance)"""
        if from_rate == to_rate:
            return audio

        current_rate = from_rate
        current_audio = audio

        # Pre-decimate in steps of 8 or 4 until ratio < 4 (fast FIR-based decimation)
        while current_rate // to_rate >= 4:
            dec_factor = 8 if current_rate // to_rate >= 8 else 4
            current_audio = signal.decimate(current_audio, dec_factor, ftype='fir', zero_phase=True)
            current_rate //= dec_factor

        # Final resample with FFT method (now on a small array)
        if current_rate != to_rate:
            num_samples = max(1, int(len(current_audio) * to_rate / current_rate))
            resampled: NDArray[np.float64] = signal.resample(current_audio, num_samples)
        else:
            resampled = current_audio

        return resampled

    def _decoder_output_indexer(self, decoder_stdout: Optional[IO[bytes]], session_manager: SessionManager) -> None:
        """Parse decoder output and index to Elasticsearch"""
        assert decoder_stdout is not None
        assert self.session is not None
        try:
            line_count = 0
            last_activity = time.time()

            # Set non-blocking mode for timeout support
            if hasattr(decoder_stdout, 'fileno'):
                import fcntl
                fd = decoder_stdout.fileno()
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            while not self.stop_event.is_set():
                # Check for data with timeout
                if hasattr(decoder_stdout, 'fileno'):
                    ready, _, _ = select.select([decoder_stdout], [], [], 1.0)
                    if not ready:
                        # Check if we've been idle too long
                        if time.time() - last_activity > 300:  # 5 minutes
                            logger.warning("No decoder output for 5 minutes, continuing...")
                            last_activity = time.time()  # warn once per idle period
                        continue

                try:
                    line_bytes = decoder_stdout.readline()
                    if not line_bytes:
                        # End of stream
                        break
                except (BlockingIOError, IOError):
                    # No data available yet
                    time.sleep(0.1)
                    continue

                last_activity = time.time()

                # Decode bytes to string (binary mode stdout from decoder)
                line = line_bytes.decode('utf-8', errors='ignore') if isinstance(line_bytes, bytes) else str(line_bytes)

                line = line.strip()
                if not line:
                    continue

                # Parse packet from decoder output
                packet = self._parse_decoder_line(line)
                if not packet:
                    continue

                # Add session metadata
                packet['session_id'] = self.session.session_id
                packet['timestamp'] = datetime.now(timezone.utc).isoformat()
                packet['frequency'] = int(self.frequency)

                # Store, publish live and check alert rules
                self._index_packet(packet)
                mode = self._get_mode()
                events.publish(mode, packet)
                alerts.evaluate(mode, packet)

                # Update session stats
                self.session.packet_count += 1
                self.session.last_packet_time = datetime.now(timezone.utc)
                session_manager.save_session(self.session)

                logger.info(f"Packet #{self.session.packet_count} indexed")

                line_count += 1

                # CPU throttling every 10 packets
                if line_count % 10 == 0:
                    time.sleep(0.01)  # Small sleep to prevent CPU saturation

        except Exception as e:
            logger.error(f"Indexing error: {e}", exc_info=True)

    def stop_stream(self) -> None:
        """Stop streaming gracefully"""
        assert self.session is not None
        logger.info(f"Stopping stream session {self.session.session_id}")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)

    def _cleanup(self) -> None:
        """Cleanup processes with graceful termination"""
        # Graceful shutdown for SDR process
        if self.sdr_proc:
            try:
                # Read any remaining stderr output (non-blocking)
                if self.sdr_proc.stderr is not None:
                    try:
                        # Set non-blocking mode
                        import fcntl
                        fd = self.sdr_proc.stderr.fileno()
                        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                        stderr_output = self.sdr_proc.stderr.read()
                        if stderr_output:
                            # hackrf_transfer & co. print progress to stderr; only a
                            # non-zero exit code makes it an error
                            failed = self.sdr_proc.poll() not in (None, 0)
                            text = stderr_output.decode('utf-8', errors='ignore').strip()[-1500:]
                            logger.log(logging.ERROR if failed else logging.DEBUG,
                                       f"SDR process stderr: {text}")
                    except (BlockingIOError, IOError):
                        pass  # No data available

                # Graceful termination: SIGTERM first
                logger.info("Sending SIGTERM to SDR process...")
                self.sdr_proc.terminate()

                try:
                    # Wait up to 5 seconds for graceful shutdown
                    self.sdr_proc.wait(timeout=5)
                    logger.info("SDR process terminated gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if not responding
                    logger.warning("SDR process not responding, sending SIGKILL...")
                    self.sdr_proc.kill()
                    self.sdr_proc.wait(timeout=2)
                    logger.info("SDR process killed")

                # Brief pause so USB driver fully releases the SDR device
                time.sleep(1.0)

            except Exception as e:
                logger.error(f"Error terminating SDR process: {e}")
                try:
                    self.sdr_proc.kill()
                except Exception:
                    pass

        # Graceful shutdown for decoder process
        if self.decoder_proc:
            try:
                # Read any remaining stderr output (non-blocking)
                if self.decoder_proc.stderr is not None:
                    try:
                        # Set non-blocking mode
                        import fcntl
                        fd = self.decoder_proc.stderr.fileno()
                        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                        stderr_output = self.decoder_proc.stderr.read()
                        if stderr_output:
                            logger.error(f"Decoder process stderr: {stderr_output.decode('utf-8', errors='ignore').strip()}")
                    except (BlockingIOError, IOError):
                        pass  # No data available

                # Graceful termination: SIGTERM first
                logger.info("Sending SIGTERM to decoder process...")
                self.decoder_proc.terminate()

                try:
                    # Wait up to 5 seconds for graceful shutdown
                    self.decoder_proc.wait(timeout=5)
                    logger.info("Decoder process terminated gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if not responding
                    logger.warning("Decoder process not responding, sending SIGKILL...")
                    self.decoder_proc.kill()
                    self.decoder_proc.wait(timeout=2)
                    logger.info("Decoder process killed")

            except Exception as e:
                logger.error(f"Error terminating decoder process: {e}")
                try:
                    self.decoder_proc.kill()
                except Exception:
                    pass

        # Final cleanup
        logger.info("Process cleanup completed")


class StreamingAPRSDecoder(BaseStreamingDecoder):
    """Streaming APRS decoder using direwolf"""

    def __init__(self, frequency: int, duration: int, gain: int, sample_rate: int,
                 device_type: Optional[str] = None, device_address: Optional[str] = None):
        super().__init__(frequency, duration, gain, sample_rate)
        self.device_address = device_address

        # Detect SDR hardware (respects explicit device selection)
        self.sdr_type = detect_sdr(preferred_type=device_type, device_address=device_address)
        if self.sdr_type == SDRType.UNKNOWN:
            raise ValueError(
                "No SDR hardware detected (HackRF, RTL-SDR, Airspy HF+, or USRP N200 required)"
            )

        # Validate frequency and sample rate against detected hardware
        try:
            _ = get_sdr_instance(
                frequency=frequency,
                sample_rate=sample_rate,
                gain=gain,
                sdr_type=self.sdr_type,
                device_address=device_address
            )
        except ValueError as e:
            raise ValueError(f"Invalid parameters for {self.sdr_type.name}: {e}")

        # 12.5 kHz channel, ±3000 Hz deviation (standard APRS/AFSK1200) → ±1.0
        self._demod = NarrowbandFMDemodulator(sample_rate, channel_bw_hz=12_500, deviation_hz=3000.0)

        logger.info(f"Using {self.sdr_type.name} for APRS streaming session "
                    f"(decoder audio {self._demod.audio_rate} Hz)")

    @property
    def _decoder_audio_rate(self) -> int:
        return self._demod.audio_rate

    def _iq_to_decoder_audio(self, iq_complex: NDArray[np.complex64]) -> NDArray[np.float64]:
        return self._demod.process(iq_complex)

    def _get_mode(self) -> str:
        return 'aprs'

    def _start_decoder(self) -> subprocess.Popen[bytes]:
        """Launch direwolf with stdin/stdout pipes"""
        cmd = [
            'direwolf',
            '-c', '/app/direwolf.conf',  # Config with ADEVICE stdin null (no ALSA needed)
            '-r', str(self._decoder_audio_rate),  # Audio sample rate
            '-D', '1',          # No further audio decimation inside direwolf
            '-t', '0',          # Text output format
            '-q', 'd',          # Quiet mode (only decoded packets)
            '-'                 # Read from stdin
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Suppress direwolf info messages
            text=False  # Binary mode for stdin (audio data)
            # bufsize default (binary mode doesn't support line buffering)
        )
        return proc

    def _parse_decoder_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse direwolf output line to APRS packet dict

        Example direwolf output:
        [0] KG6HUM-7>APDR15,WIDE1-1:!3745.75N/12212.47W>088/019/A=000305
        """
        try:
            # Skip empty lines and non-packet lines
            if not line or not line.startswith('['):
                return None

            # Extract components
            # Format: [channel] SOURCE>DEST,PATH:DATA
            parts = line.split(':', 1)
            if len(parts) != 2:
                return None

            header = parts[0]
            data = parts[1].strip()

            # Parse header: [0] SOURCE>DEST,PATH
            header = header.split(']', 1)[1].strip()  # Remove channel number
            source_dest = header.split('>', 1)
            if len(source_dest) != 2:
                return None

            source = source_dest[0].strip()
            dest_and_path = source_dest[1].split(',')
            destination = dest_and_path[0].strip()
            path = ','.join(dest_and_path[1:]) if len(dest_and_path) > 1 else ''

            # Determine packet type from data
            packet_type = 'unknown'
            latitude = None
            longitude = None
            message_text = data

            if data.startswith('!') or data.startswith('='):
                # Position packet
                packet_type = 'position'
                # Try to parse position (simple parsing)
                # Full APRS position parsing is complex, simplified here
                try:
                    # Example: !3745.75N/12212.47W>
                    if len(data) > 19:
                        lat_str = data[1:8]  # 3745.75
                        lat_dir = data[8]     # N
                        lon_str = data[10:18] # 12212.47
                        lon_dir = data[18]    # W

                        # Convert to decimal degrees (simplified)
                        lat_deg = float(lat_str[:2])
                        lat_min = float(lat_str[2:])
                        latitude = lat_deg + (lat_min / 60.0)
                        if lat_dir == 'S':
                            latitude = -latitude

                        lon_deg = float(lon_str[:3])
                        lon_min = float(lon_str[3:])
                        longitude = lon_deg + (lon_min / 60.0)
                        if lon_dir == 'W':
                            longitude = -longitude
                except (ValueError, IndexError):
                    pass  # Position parsing failed, keep as None

            elif data.startswith(':'):
                # Message packet
                packet_type = 'message'

            elif data.startswith('>'):
                # Status packet
                packet_type = 'status'

            elif data.startswith('T#'):
                # Telemetry packet
                packet_type = 'telemetry'

            packet = {
                'uuid': str(uuid.uuid4()),
                'source_callsign': source,
                'destination_callsign': destination,
                'path': path,
                'packet_type': packet_type,
                'message_text': message_text,
                'raw_packet': line,
                'latitude': latitude,
                'longitude': longitude
            }

            return packet

        except Exception as e:
            logger.error(f"Failed to parse APRS line: {line} - {e}")
            return None

    def _index_packet(self, packet: Dict[str, Any]) -> None:
        """Store APRS packet"""
        from radiomoni.storage import get_storage

        try:
            get_storage().index_aprs(packet)
            logger.info(f"Indexed APRS packet from {packet.get('source_callsign')}")
        except Exception as e:
            logger.error(f"Failed to index APRS packet: {e}")

    def stop(self) -> None:
        """Stop streaming (alias for stop_stream that works without session)"""
        logger.info("Stopping APRS stream")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)


class StreamingPOCSAGDecoder(BaseStreamingDecoder):
    """Streaming POCSAG decoder using multimon-ng"""

    def __init__(self, frequency: int, duration: int, gain: int, sample_rate: int,
                 device_type: Optional[str] = None, device_address: Optional[str] = None):
        super().__init__(frequency, duration, gain, sample_rate)
        self.device_address = device_address

        # Detect SDR hardware (respects explicit device selection)
        self.sdr_type = detect_sdr(preferred_type=device_type, device_address=device_address)
        if self.sdr_type == SDRType.UNKNOWN:
            raise ValueError(
                "No SDR hardware detected (HackRF, RTL-SDR, Airspy HF+, or USRP N200 required)"
            )

        # Validate frequency and sample rate against detected hardware
        try:
            _ = get_sdr_instance(
                frequency=frequency,
                sample_rate=sample_rate,
                gain=gain,
                sdr_type=self.sdr_type,
                device_address=device_address
            )
        except ValueError as e:
            raise ValueError(f"Invalid parameters for {self.sdr_type.name}: {e}")

        logger.info(f"Using {self.sdr_type.name} for POCSAG streaming session")

    @property
    def _decoder_audio_rate(self) -> int:
        """multimon-ng -t raw expects 22050 Hz hardcoded"""
        return 22050

    @property
    def _fm_gain(self) -> float:
        """Scale FM output so ±4500 Hz deviation (standard VHF paging) → ±1.0"""
        return float(self.sample_rate) / (2.0 * 3.141592653589793 * 4500.0)

    def _get_mode(self) -> str:
        return 'pocsag'

    def _start_decoder(self) -> subprocess.Popen[bytes]:
        """Launch multimon-ng with stdin/stdout pipes"""
        cmd = [
            'multimon-ng',
            '-a', 'POCSAG512',
            '-a', 'POCSAG1200',
            '-a', 'POCSAG2400',
            '-t', 'raw',  # Raw format
            '-'           # Read from stdin
        ]
        logger.debug(f"Executing Decoder command: {cmd}")

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False  # Binary mode for stdin (audio data)
            # bufsize default (binary mode doesn't support line buffering)
        )
        return proc

    def _parse_decoder_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse multimon-ng output line to POCSAG packet dict

        Example multimon-ng output:
        POCSAG1200: Address: 1234567  Function: 0  Alpha:   This is a test message
        """
        try:
            # Skip non-POCSAG lines
            if not line.startswith('POCSAG'):
                return None

            # Extract baud rate
            if 'POCSAG512' in line:
                baud_rate = 512
            elif 'POCSAG1200' in line:
                baud_rate = 1200
            elif 'POCSAG2400' in line:
                baud_rate = 2400
            else:
                return None

            # Parse: POCSAG1200: Address: 1234567  Function: 0  Alpha:   This is a test message
            parts = line.split(':', 1)[1].strip()  # Remove "POCSAG1200:"

            # Extract address
            address = None
            if 'Address:' in parts:
                addr_part = parts.split('Address:')[1].split()[0].strip()
                try:
                    address = int(addr_part)
                except ValueError:
                    pass

            # Extract function code
            function_code = None
            if 'Function:' in parts:
                func_part = parts.split('Function:')[1].split()[0].strip()
                try:
                    function_code = int(func_part)
                except ValueError:
                    pass

            # Extract message type and text
            message_type = 'unknown'
            message_text = ''

            if 'Alpha:' in parts:
                message_type = 'alpha'
                message_text = parts.split('Alpha:')[1].strip()
            elif 'Numeric:' in parts:
                message_type = 'numeric'
                message_text = parts.split('Numeric:')[1].strip()

            packet = {
                'uuid': str(uuid.uuid4()),
                'address': address,
                'function_code': function_code,
                'message_type': message_type,
                'baud_rate': baud_rate,
                'message_text': message_text,
                'raw_packet': line
            }

            return packet

        except Exception as e:
            logger.error(f"Failed to parse POCSAG line: {line} - {e}")
            return None

    def _index_packet(self, packet: Dict[str, Any]) -> None:
        """Store POCSAG packet"""
        from radiomoni.storage import get_storage

        try:
            get_storage().index_pocsag(packet)
            logger.info(f"Indexed POCSAG message to address {packet.get('address')}")
        except Exception as e:
            logger.error(f"Failed to index POCSAG packet: {e}")

    def stop(self) -> None:
        """Stop streaming (alias for stop_stream that works without session)"""
        logger.info("Stopping POCSAG stream")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)


class MultiChannelStreamingDecoder(BaseStreamingDecoder):
    """Wide-band DDC decoder for USRP N200: one IQ stream, N parallel FM channels."""

    MAX_CHANNELS = 8

    def __init__(self, center_freq: int, wideband_rate: int, gain: int, duration: int,
                 channels: List[ChannelConfig], device_address: str):
        super().__init__(frequency=center_freq, duration=duration,
                         gain=gain, sample_rate=wideband_rate)
        if not device_address:
            raise ValueError("MultiChannelStreamingDecoder requires USRP device_address (IP address)")
        self.device_address = device_address
        self.sdr_type = SDRType.USRP
        self.center_freq = center_freq

        if not (2 <= len(channels) <= self.MAX_CHANNELS):
            raise ValueError(f"2–{self.MAX_CHANNELS} channels required, got {len(channels)}")

        half_bw = wideband_rate / 2.0
        for ch in channels:
            if abs(ch.frequency - center_freq) + ch.channel_bw_hz / 2 > half_bw:
                raise ValueError(
                    f"Channel '{ch.label}' ({ch.frequency} Hz) falls outside "
                    f"wideband range ±{half_bw/1e6:.1f} MHz around {center_freq/1e6:.3f} MHz"
                )

        # Largest power-of-2 decimation factor s.t. intermediate_rate ≥ 2×max(channel_bw)
        max_bw = max(ch.channel_bw_hz for ch in channels)
        D = 1
        while wideband_rate // (D * 2) >= 2 * max_bw:
            D *= 2
        self.decimation_factor = D
        self.intermediate_rate = wideband_rate // D

        TWO_PI = 2.0 * np.pi
        for ch in channels:
            ch.freq_offset = float(ch.frequency - center_freq)
            ch.phase_acc = 0.0
            ch.fir_taps = self._design_channel_filter(wideband_rate, ch.channel_bw_hz)
            n_taps = len(ch.fir_taps)
            ch.fir_zi_i = np.zeros(n_taps - 1, dtype=np.float32)
            ch.fir_zi_q = np.zeros(n_taps - 1, dtype=np.float32)
            if ch.mode == 'aprs':
                ch.decoder_audio_rate = 48000
                ch.fm_gain = self.intermediate_rate / (TWO_PI * 3000.0)
            else:
                ch.decoder_audio_rate = 22050
                ch.fm_gain = self.intermediate_rate / (TWO_PI * 4500.0)

        self.channels = channels
        self.decoder_procs: List[subprocess.Popen[bytes]] = []

    @staticmethod
    def _design_channel_filter(wideband_rate: int, channel_bw_hz: int) -> NDArray[np.float32]:
        nyquist = wideband_rate / 2.0
        cutoff_norm = min((channel_bw_hz / 2.0) / nyquist, 0.95)
        result: NDArray[np.float32] = signal.firwin(63, cutoff_norm, window='hamming').astype(np.float32)
        return result

    # --- Abstract method implementations (multi-channel uses its own pipeline) ---

    def _start_decoder(self) -> subprocess.Popen[bytes]:
        raise NotImplementedError("Use _start_all_decoders() for multi-channel sessions")

    def _parse_decoder_line(self, line: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Use per-channel parsers in _channel_output_indexer()")

    def _index_packet(self, packet: Dict[str, Any]) -> None:
        raise NotImplementedError("Use per-channel indexers in _channel_output_indexer()")

    def _get_mode(self) -> str:
        return 'multi'

    # --- Multi-channel pipeline ---

    def _start_all_decoders(self) -> None:
        for ch in self.channels:
            if ch.mode == 'aprs':
                cmd = [
                    'direwolf',
                    '-c', '/app/direwolf.conf',
                    '-r', '48000',
                    '-D', '1',
                    '-t', '0',
                    '-q', 'd',
                    '-'
                ]
            else:
                cmd = [
                    'multimon-ng',
                    '-a', 'POCSAG512',
                    '-a', 'POCSAG1200',
                    '-a', 'POCSAG2400',
                    '-t', 'raw',
                    '-'
                ]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=False
            )
            ch.decoder_proc = proc
            self.decoder_procs.append(proc)
            logger.info(f"Started {ch.mode.upper()} decoder for channel '{ch.label}' (PID {proc.pid})")

    def _stream_worker_simple(self, session_manager: SessionManager) -> None:
        assert self.session is not None
        try:
            self.session.status = 'running'
            session_manager.save_session(self.session)

            self.sdr_proc = self._start_sdr_capture()
            logger.info(f"USRP wide-band capture started (session {self.session.session_id})")

            self._start_all_decoders()
            self._stream_pipeline_multi(session_manager)

        except Exception as e:
            logger.error(f"Multi-channel stream error: {e}", exc_info=True)
            if self.session:
                self.session.status = 'failed'
                self.session.error = str(e)
                session_manager.save_session(self.session)
        finally:
            self._cleanup_multi()
            self._finish_session(session_manager)

    def _stream_pipeline_multi(self, session_manager: SessionManager) -> None:
        assert self.session is not None
        assert self.sdr_proc is not None

        converter_thread = threading.Thread(
            target=self._iq_to_audio_converter_multi,
            args=(self.sdr_proc.stdout,),
            daemon=True
        )
        converter_thread.start()

        indexer_threads = []
        for ch in self.channels:
            t = threading.Thread(
                target=self._channel_output_indexer,
                args=(ch, session_manager),
                daemon=True
            )
            t.start()
            indexer_threads.append(t)

        start_time = time.time()
        while not self.stop_event.is_set():
            if self.duration and (time.time() - start_time) >= self.duration:
                logger.info(f"Multi-channel duration limit reached: {self.duration}s")
                self.stop_event.set()
                if self.sdr_proc and self.sdr_proc.poll() is None:
                    self.sdr_proc.terminate()
                for ch in self.channels:
                    if ch.decoder_proc and ch.decoder_proc.poll() is None:
                        ch.decoder_proc.terminate()
                if self.session:
                    self.session.status = 'completed'
                    self.session.end_time = datetime.now(timezone.utc)
                    session_manager.save_session(self.session)
                break

            all_done = not converter_thread.is_alive() and not any(t.is_alive() for t in indexer_threads)
            if all_done:
                logger.info("All multi-channel threads completed naturally")
                if self.session:
                    self.session.status = 'completed'
                    self.session.end_time = datetime.now(timezone.utc)
                    session_manager.save_session(self.session)
                break

            if int(time.time()) % 5 == 0:
                session_manager.save_session(self.session)

            time.sleep(1)

        converter_thread.join(timeout=10)
        for t in indexer_threads:
            t.join(timeout=10)

    def _iq_to_audio_converter_multi(self, iq_stream: Optional[IO[bytes]]) -> None:
        if iq_stream is None:
            return

        CHUNK_DURATION = 0.1
        # int16 I/Q interleaved: 2 int16 per sample × 2 bytes each
        CHUNK_SAMPLES = int(self.sample_rate * CHUNK_DURATION)
        CHUNK_SIZE = CHUNK_SAMPLES * 4  # 2 channels (I+Q) × 2 bytes (int16)

        TWO_PI = 2.0 * np.pi
        D = self.decimation_factor
        fs = float(self.sample_rate)

        chunk_count = 0
        last_gc_time = time.time()

        try:
            while not self.stop_event.is_set():
                if chunk_count % 10 == 0:
                    proc_mem = psutil.Process().memory_info().rss / (1024 * 1024)
                    if proc_mem > MAX_RSS_MB:
                        logger.error(f"Memory critical ({proc_mem:.0f} MB) — stopping multi-channel stream")
                        self.stop_event.set()
                        break

                raw = self._read_with_timeout(iq_stream, CHUNK_SIZE, timeout=5.0)
                if not raw:
                    logger.info("USRP IQ stream ended")
                    break

                # USRP int16 → complex64
                iq_int16 = np.frombuffer(raw, dtype=np.int16)
                if len(iq_int16) % 2 != 0:
                    iq_int16 = iq_int16[:-1]
                iq_float = iq_int16.astype(np.float32) / 32768.0
                N = len(iq_float) // 2
                iq_wide = (iq_float[0::2] + 1j * iq_float[1::2]).astype(np.complex64)
                k = np.arange(N, dtype=np.float32)

                for ch in self.channels:
                    try:
                        # 1. Phase-continuous mixing to baseband
                        phase_inc = -TWO_PI * (ch.freq_offset / fs)
                        mixer = np.exp(1j * (ch.phase_acc + phase_inc * k)).astype(np.complex64)
                        iq_mixed = iq_wide * mixer
                        ch.phase_acc = float((ch.phase_acc + phase_inc * N) % TWO_PI)

                        # 2. Anti-alias FIR (state preserved across chunks)
                        iq_i, ch.fir_zi_i = signal.lfilter(
                            ch.fir_taps, [1.0], iq_mixed.real, zi=ch.fir_zi_i
                        )
                        iq_q, ch.fir_zi_q = signal.lfilter(
                            ch.fir_taps, [1.0], iq_mixed.imag, zi=ch.fir_zi_q
                        )

                        # 3. Decimation (anti-alias filter already applied)
                        iq_dec = (iq_i + 1j * iq_q)[::D].astype(np.complex64)

                        # 4. FM demodulation
                        if len(iq_dec) < 2:
                            continue
                        audio = np.angle(iq_dec[1:] * np.conj(iq_dec[:-1])).astype(np.float64)

                        # 5. Resample to decoder audio rate
                        audio_rs = self._resample(audio, self.intermediate_rate, ch.decoder_audio_rate)

                        # 6. Scale, clip, int16, write to decoder stdin
                        audio_scaled = np.clip(audio_rs * ch.fm_gain, -1.0, 1.0)
                        audio_int16 = (audio_scaled * 32767).astype(np.int16)

                        if ch.decoder_proc and ch.decoder_proc.stdin and ch.decoder_proc.poll() is None:
                            ch.decoder_proc.stdin.write(audio_int16.tobytes())
                            ch.decoder_proc.stdin.flush()

                        del iq_i, iq_q, iq_dec, audio, audio_rs, audio_scaled, audio_int16, mixer, iq_mixed

                    except Exception as e:
                        logger.error(f"DDC error for channel '{ch.label}': {e}", exc_info=True)

                del iq_int16, iq_float, iq_wide, k
                chunk_count += 1

                now = time.time()
                if now - last_gc_time > 5.0:
                    gc.collect()
                    last_gc_time = now

                time.sleep(0.001)

        except Exception as e:
            logger.error(f"Multi-channel IQ converter error: {e}", exc_info=True)
        finally:
            for ch in self.channels:
                try:
                    if ch.decoder_proc and ch.decoder_proc.stdin:
                        ch.decoder_proc.stdin.close()
                except Exception:
                    pass
            gc.collect()

    def _channel_output_indexer(self, ch: ChannelConfig, session_manager: SessionManager) -> None:
        assert self.session is not None
        if ch.decoder_proc is None or ch.decoder_proc.stdout is None:
            return

        decoder_stdout = ch.decoder_proc.stdout

        # Reuse parsers via __new__ — _parse_decoder_line is stateless
        parser: Union[StreamingAPRSDecoder, StreamingPOCSAGDecoder]
        if ch.mode == 'aprs':
            parser = StreamingAPRSDecoder.__new__(StreamingAPRSDecoder)
        else:
            parser = StreamingPOCSAGDecoder.__new__(StreamingPOCSAGDecoder)

        try:
            if hasattr(decoder_stdout, 'fileno'):
                import fcntl
                fd = decoder_stdout.fileno()
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            while not self.stop_event.is_set():
                if hasattr(decoder_stdout, 'fileno'):
                    ready, _, _ = select.select([decoder_stdout], [], [], 1.0)
                    if not ready:
                        continue

                try:
                    line_bytes = decoder_stdout.readline()
                    if not line_bytes:
                        break
                except (BlockingIOError, IOError):
                    time.sleep(0.1)
                    continue

                line = (line_bytes.decode('utf-8', errors='ignore')
                        if isinstance(line_bytes, bytes) else str(line_bytes)).strip()
                if not line:
                    continue

                packet = parser._parse_decoder_line(line)
                if not packet:
                    continue

                packet['session_id'] = self.session.session_id
                packet['timestamp'] = datetime.now(timezone.utc).isoformat()
                packet['frequency'] = ch.frequency
                packet['channel_label'] = ch.label

                try:
                    from radiomoni.storage import get_storage
                    if ch.mode == 'aprs':
                        get_storage().index_aprs(packet)
                    else:
                        get_storage().index_pocsag(packet)
                except Exception as e:
                    logger.error(f"Failed to index {ch.mode.upper()} packet for '{ch.label}': {e}")
                events.publish(ch.mode, packet)
                alerts.evaluate(ch.mode, packet)

                ch.packet_count += 1
                self.session.packet_count += 1
                self.session.last_packet_time = datetime.now(timezone.utc)
                session_manager.save_session(self.session)
                logger.info(f"[{ch.label}] Packet #{ch.packet_count} indexed")

        except Exception as e:
            logger.error(f"Output indexer error for channel '{ch.label}': {e}", exc_info=True)

    def _cleanup_multi(self) -> None:
        for ch in self.channels:
            if ch.decoder_proc:
                try:
                    ch.decoder_proc.terminate()
                    ch.decoder_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        ch.decoder_proc.kill()
                        ch.decoder_proc.wait(timeout=2)
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Error terminating decoder for channel '{ch.label}': {e}")
                    try:
                        ch.decoder_proc.kill()
                    except Exception:
                        pass
        self._cleanup()

    def stop(self) -> None:
        logger.info("Stopping multi-channel stream")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)
