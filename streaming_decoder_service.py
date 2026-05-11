#!/usr/bin/env python3
"""
Streaming Decoder Service for Radio Monitoring System
Provides continuous real-time decoding without storing audio files

Supports:
- APRS (direwolf)
- POCSAG (multimon-ng)
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
from typing import Optional, Dict, Any, IO
from numpy.typing import NDArray
from scipy import signal
import redis
import json
from sdr_hardware import detect_sdr, SDRType, get_sdr_instance, apply_hackrf_iq_correction

logger = logging.getLogger(__name__)


class MockRedis:
    """Mock Redis client for testing"""
    def __init__(self) -> None:
        self._data: Dict[str, str] = {}

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self._data[key] = value

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count

    def keys(self, pattern: str = '*') -> list[str]:
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return [k for k in self._data.keys() if k.startswith(prefix)]
        return list(self._data.keys())

    def scan_iter(self, match: Optional[str] = None) -> list[str]:
        """Iterate over keys matching pattern"""
        if match and match.endswith('*'):
            prefix = match[:-1]
            return [k for k in self._data.keys() if k.startswith(prefix)]
        return list(self._data.keys())

    def expire(self, key: str, seconds: int) -> None:
        pass


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
            'error': self.error
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
        return session


class SessionManager:
    """Manages streaming sessions in Redis"""

    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, redis_db: int = 0, redis_password: Optional[str] = None) -> None:
        # Use mock Redis in test mode
        if os.getenv('SKIP_REDIS_CHECK') == '1':
            self.redis: Any = MockRedis()
        else:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, password=redis_password, decode_responses=True)
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

    def start_stream(self, session_manager: SessionManager) -> str:
        """Start streaming in background thread"""
        # Create session
        self.session = StreamSession(
            mode=self._get_mode(),
            frequency=self.frequency,
            duration=self.duration,
            gain=self.gain,
            sample_rate=self.sample_rate
        )

        # Save to Redis
        session_manager.save_session(self.session)

        # Start background thread
        self.thread = threading.Thread(target=self._stream_worker, args=(session_manager,))
        self.thread.daemon = False
        self.thread.start()

        return self.session.session_id

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
            # Cleanup
            self._cleanup()
            if self.session is not None:
                self.session.status = 'completed'
                self.session.end_time = datetime.now(timezone.utc)
                session_manager.save_session(self.session)
                logger.info(f"Stream session {self.session.session_id} completed")
                # Remove from live registry — HackRF is now free
                session_manager.unregister_decoder(self.session.session_id)

    def _stream_worker(self, session_manager: SessionManager) -> None:
        """Main streaming worker (runs in background)"""
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
        finally:
            # Cleanup
            self._cleanup()
            if self.session is not None:
                self.session.status = 'completed'
                self.session.end_time = datetime.now(timezone.utc)
                session_manager.save_session(self.session)
                logger.info(f"Stream session {self.session.session_id} completed")

    def _start_sdr_capture(self) -> subprocess.Popen[bytes]:
        """Launch SDR capture with stdout pipe and reduced priority (supports HackRF and RTL-SDR)"""
        # Use nice to reduce CPU priority (prevents CPU saturation)

        if self.sdr_type == SDRType.HACKRF:
            # HackRF command (no nice: priority reduction causes USB stalls via pipe backpressure)
            cmd = [
                'hackrf_transfer',
                '-r', '-',  # Write to stdout
                '-f', str(int(self.frequency)),
                '-s', str(self.sample_rate),
                '-l', str(self.gain),
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

                # Explicitly mark session as completed
                if self.session is not None:
                    self.session.status = 'completed'
                    self.session.end_time = datetime.now(timezone.utc)
                    session_manager.save_session(self.session)
                    logger.info(f"Session {self.session.session_id} marked as completed via thread completion")

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
                    if process_mem_mb > 500:
                        logger.error(f"Process memory critical: {process_mem_mb:.1f} MB - stopping stream")
                        self.stop_event.set()
                        break

                # Read IQ chunk with timeout support
                iq_bytes = self._read_with_timeout(iq_stream, CHUNK_SIZE, timeout=5.0)
                if not iq_bytes or len(iq_bytes) == 0:
                    logger.info("SDR stream ended")
                    break

                # Convert to complex64 with SDR-specific normalization
                if self.sdr_type == SDRType.HACKRF:
                    # HackRF: int8 signed (-128 to 127)
                    iq_data = np.frombuffer(iq_bytes, dtype=np.int8)
                    iq_float = iq_data.astype(np.float32) / 127.0
                elif self.sdr_type == SDRType.RTLSDR:
                    # RTL-SDR: uint8 unsigned (0 to 255)
                    iq_data = np.frombuffer(iq_bytes, dtype=np.uint8)
                    iq_float = (iq_data.astype(np.float32) - 127.5) / 127.5
                elif self.sdr_type == SDRType.AIRSPYHF:
                    # Airspy HF+: int16 signed (-32768 to 32767)
                    iq_data = np.frombuffer(iq_bytes, dtype=np.int16)
                    iq_float = iq_data.astype(np.float32) / 32768.0
                elif self.sdr_type == SDRType.USRP:
                    # USRP N200: int16 signed (-32768 to 32767), same format as Airspy HF+
                    iq_data = np.frombuffer(iq_bytes, dtype=np.int16)
                    iq_float = iq_data.astype(np.float32) / 32768.0
                else:
                    raise ValueError(f"Unsupported SDR type: {self.sdr_type}")

                # Ensure even number of samples for I/Q splitting
                if len(iq_float) % 2 != 0:
                    iq_float = iq_float[:-1]  # Drop last sample if odd

                iq_complex: NDArray[np.complex64] = (iq_float[0::2] + 1j * iq_float[1::2]).astype(np.complex64)
                if self.sdr_type == SDRType.HACKRF:
                    iq_complex = apply_hackrf_iq_correction(iq_complex)

                # FM demodulation
                audio = self._fm_demodulate(iq_complex)

                # Resample to decoder's expected sample rate
                # direwolf: 48000 Hz, multimon-ng -t raw: 22050 Hz
                audio_48k = self._resample(audio, self.sample_rate, self._decoder_audio_rate)

                # Apply FM gain and clip to ±1.0, then convert to int16
                audio_scaled = np.clip(audio_48k * self._fm_gain, -1.0, 1.0)
                audio_int16 = (audio_scaled * 32767).astype(np.int16)

                # Write to decoder stdin
                audio_sink.write(audio_int16.tobytes())
                audio_sink.flush()

                # Cleanup arrays to free memory immediately
                del iq_bytes, iq_data, iq_float, iq_complex, audio, audio_48k, audio_scaled, audio_int16

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
            except:
                pass
            # Final cleanup
            gc.collect()

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

                # Index to Elasticsearch
                self._index_packet(packet)

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
                            logger.error(f"SDR process stderr: {stderr_output.decode('utf-8', errors='ignore').strip()}")
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

            except Exception as e:
                logger.error(f"Error terminating SDR process: {e}")
                try:
                    self.sdr_proc.kill()
                except:
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
                except:
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

        logger.info(f"Using {self.sdr_type.name} for APRS streaming session")

    @property
    def _fm_gain(self) -> float:
        """Scale FM output so ±3000 Hz deviation (standard APRS/AFSK1200) → ±1.0"""
        return float(self.sample_rate) / (2.0 * 3.141592653589793 * 3000.0)

    def _get_mode(self) -> str:
        return 'aprs'

    def _start_decoder(self) -> subprocess.Popen[bytes]:
        """Launch direwolf with stdin/stdout pipes"""
        cmd = [
            'direwolf',
            '-c', '/app/direwolf.conf',  # Config with ADEVICE stdin null (no ALSA needed)
            '-r', '48000',      # Audio sample rate
            '-D', '1',          # Decode channel 1
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
                except:
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
        """Index APRS packet to Elasticsearch"""
        from elasticsearch_service import get_elasticsearch_service

        try:
            es = get_elasticsearch_service()
            es.index_aprs(packet)
            logger.info(f"Indexed APRS packet from {packet.get('source_callsign')}")
        except Exception as e:
            logger.error(f"Failed to index APRS packet: {e}")

    def stop(self) -> None:
        """Stop streaming (alias for stop_stream that works without session)"""
        logger.info(f"Stopping APRS stream")
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
                except:
                    pass

            # Extract function code
            function_code = None
            if 'Function:' in parts:
                func_part = parts.split('Function:')[1].split()[0].strip()
                try:
                    function_code = int(func_part)
                except:
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
        """Index POCSAG packet to Elasticsearch"""
        from elasticsearch_service import get_elasticsearch_service

        try:
            es = get_elasticsearch_service()
            es.index_pocsag(packet)
            logger.info(f"Indexed POCSAG message to address {packet.get('address')}")
        except Exception as e:
            logger.error(f"Failed to index POCSAG packet: {e}")

    def stop(self) -> None:
        """Stop streaming (alias for stop_stream that works without session)"""
        logger.info(f"Stopping POCSAG stream")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)
