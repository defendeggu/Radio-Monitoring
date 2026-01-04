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
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, IO
from numpy.typing import NDArray
from scipy import signal
import redis
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, redis_db: int = 0) -> None:
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

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

    def get_user_active_session(self, user_id: str = 'default') -> Optional[StreamSession]:
        """Get user's active session (max 1 per user)"""
        for session in self.list_sessions():
            if session.status in ['starting', 'running']:
                # In future: check user_id
                return session
        return None


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
        """Launch hackrf_transfer with stdout pipe"""
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
            samples = int(self.sample_rate * self.duration)
            cmd.extend(['-n', str(samples * 2)])  # *2 for I+Q

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
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
        CHUNK_SIZE = self.sample_rate * 2 * 1  # 1 second (I+Q, int8)

        try:
            while not self.stop_event.is_set():
                # Read IQ chunk
                iq_bytes = iq_stream.read(CHUNK_SIZE)
                if not iq_bytes or len(iq_bytes) == 0:
                    logger.info("SDR stream ended")
                    break

                # Convert to complex64
                iq_data = np.frombuffer(iq_bytes, dtype=np.int8)
                iq_float = iq_data.astype(np.float32) / 127.0
                iq_complex: NDArray[np.complex64] = (iq_float[0::2] + 1j * iq_float[1::2]).astype(np.complex64)

                # FM demodulation
                audio = self._fm_demodulate(iq_complex)

                # Resample to 48kHz for decoder
                audio_48k = self._resample(audio, self.sample_rate, 48000)

                # Convert to int16 WAV format
                audio_int16 = (audio_48k * 32767).astype(np.int16)

                # Write to decoder stdin
                audio_sink.write(audio_int16.tobytes())
                audio_sink.flush()

        except Exception as e:
            logger.error(f"IQ conversion error: {e}", exc_info=True)
        finally:
            try:
                audio_sink.close()
            except:
                pass

    def _fm_demodulate(self, iq_complex: NDArray[np.complex64]) -> NDArray[np.float64]:
        """FM demodulation using phase differentiation"""
        # Phase differentiation
        phase = np.angle(iq_complex)
        phase_diff = np.diff(phase)

        # Unwrap phase
        phase_diff = np.unwrap(phase_diff)

        # Normalize
        audio: NDArray[np.float64] = phase_diff / np.pi

        return audio

    def _resample(self, audio: NDArray[np.float64], from_rate: int, to_rate: int) -> NDArray[np.float64]:
        """Resample audio to target rate"""
        if from_rate == to_rate:
            return audio

        # Calculate resampling ratio
        ratio = to_rate / from_rate
        num_samples = int(len(audio) * ratio)

        # Resample using scipy
        resampled: NDArray[np.float64] = signal.resample(audio, num_samples)

        return resampled

    def _decoder_output_indexer(self, decoder_stdout: Optional[IO[bytes]], session_manager: SessionManager) -> None:
        """Parse decoder output and index to Elasticsearch"""
        assert decoder_stdout is not None
        assert self.session is not None
        try:
            for line_bytes in decoder_stdout:
                if self.stop_event.is_set():
                    break

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
        """Cleanup processes"""
        if self.sdr_proc:
            try:
                self.sdr_proc.terminate()
                self.sdr_proc.wait(timeout=5)
            except:
                self.sdr_proc.kill()

        if self.decoder_proc:
            try:
                self.decoder_proc.terminate()
                self.decoder_proc.wait(timeout=5)
            except:
                self.decoder_proc.kill()


class StreamingAPRSDecoder(BaseStreamingDecoder):
    """Streaming APRS decoder using direwolf"""

    def _get_mode(self) -> str:
        return 'aprs'

    def _start_decoder(self) -> subprocess.Popen[bytes]:
        """Launch direwolf with stdin/stdout pipes"""
        cmd = [
            'direwolf',
            '-c', '/dev/null',  # No config file
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

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
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
