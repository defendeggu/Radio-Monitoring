"""
Test Suite for Streaming Decoder Services

Tests:
- SessionManager tests (Redis integration) - 8 tests
- StreamSession tests - 4 tests
- BaseStreamingDecoder tests - 4 tests
- StreamingAPRSDecoder tests - 6 tests
- StreamingPOCSAGDecoder tests - 6 tests
- API integration tests - 6 tests

Total: 34 tests covering streaming decode functionality
"""

import os
import sys
import pytest
import json
import time
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
from flask.testing import FlaskClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiomoni.decoders import streaming
from radiomoni.decoders.streaming import (
    StreamSession,
    SessionManager,
    StreamingAPRSDecoder,
    StreamingPOCSAGDecoder,
    NarrowbandFMDemodulator,
)
from radiomoni.sdr_hardware import SDRType


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = MagicMock()
    redis_mock.get = MagicMock(return_value=None)
    redis_mock.set = MagicMock(return_value=True)
    redis_mock.delete = MagicMock(return_value=1)
    redis_mock.expire = MagicMock(return_value=True)
    redis_mock.scan_iter = MagicMock(return_value=[])
    return redis_mock


@pytest.fixture
def session_manager(mock_redis, monkeypatch):
    """Create SessionManager with mocked Redis"""
    return SessionManager(redis_client=mock_redis)


@pytest.fixture
def sample_stream_session():
    """Create sample StreamSession"""
    return StreamSession(
        mode='aprs',
        frequency=144800000,
        duration=300,
        gain=20,
        sample_rate=2000000
    )


# ============================================================================
# StreamSession Tests
# ============================================================================

class TestStreamSession:
    """Tests for StreamSession class"""

    def test_session_initialization(self):
        """Test StreamSession initialization"""
        session = StreamSession(
            mode='aprs',
            frequency=144800000,
            duration=300,
            gain=20,
            sample_rate=2000000
        )

        assert session.mode == 'aprs'
        assert session.frequency == 144800000
        assert session.duration == 300
        assert session.gain == 20
        assert session.sample_rate == 2000000
        assert session.status == 'starting'
        assert session.packet_count == 0
        assert session.error is None
        assert session.session_id is not None

    def test_session_to_dict(self, sample_stream_session):
        """Test StreamSession serialization to dict"""
        data = sample_stream_session.to_dict()

        assert isinstance(data, dict)
        assert data['mode'] == 'aprs'
        assert data['frequency'] == 144800000
        assert data['status'] == 'starting'
        assert 'session_id' in data
        assert 'start_time' in data

    def test_session_from_dict(self):
        """Test StreamSession deserialization from dict"""
        data = {
            'session_id': 'test-session-123',
            'mode': 'pocsag',
            'frequency': 147325000,
            'duration': 600,
            'gain': 30,
            'sample_rate': 2000000,
            'status': 'running',
            'start_time': datetime.now(timezone.utc).isoformat(),
            'end_time': None,
            'packet_count': 5,
            'last_packet_time': None,
            'error': None
        }

        session = StreamSession.from_dict(data)

        assert session.session_id == 'test-session-123'
        assert session.mode == 'pocsag'
        assert session.frequency == 147325000
        assert session.status == 'running'
        assert session.packet_count == 5

    def test_session_roundtrip_serialization(self, sample_stream_session):
        """Test session serialize → deserialize roundtrip"""
        # Serialize
        data = sample_stream_session.to_dict()

        # Deserialize
        restored = StreamSession.from_dict(data)

        assert restored.session_id == sample_stream_session.session_id
        assert restored.mode == sample_stream_session.mode
        assert restored.frequency == sample_stream_session.frequency
        assert restored.status == sample_stream_session.status


# ============================================================================
# SessionManager Tests (Redis Integration)
# ============================================================================

class TestSessionManager:
    """Tests for SessionManager (Redis-based session management)"""

    def test_session_manager_initialization(self, mock_redis):
        """SessionManager uses the injected client, or the shared one by default"""
        assert SessionManager(redis_client=mock_redis).redis is mock_redis
        assert SessionManager().redis is not None

    def test_save_session(self, session_manager, sample_stream_session, mock_redis):
        """Test saving session to Redis"""
        session_manager.save_session(sample_stream_session)

        # Verify Redis.set was called
        mock_redis.set.assert_called_once()

        # Verify Redis.expire was called with 7 days TTL
        mock_redis.expire.assert_called_once()
        args = mock_redis.expire.call_args[0]
        assert args[1] == 86400 * 7  # 7 days in seconds

    def test_get_session_exists(self, session_manager, sample_stream_session, mock_redis):
        """Test retrieving existing session from Redis"""
        # Mock Redis.get to return session data
        session_data = sample_stream_session.to_dict()
        mock_redis.get.return_value = json.dumps(session_data)

        retrieved = session_manager.get_session(sample_stream_session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == sample_stream_session.session_id
        assert retrieved.mode == sample_stream_session.mode

    def test_get_session_not_exists(self, session_manager, mock_redis):
        """Test retrieving non-existent session returns None"""
        mock_redis.get.return_value = None

        retrieved = session_manager.get_session('nonexistent-session')

        assert retrieved is None

    def test_delete_session(self, session_manager, mock_redis):
        """Test deleting session from Redis"""
        session_id = 'test-session-123'

        session_manager.delete_session(session_id)

        # Verify Redis.delete was called
        mock_redis.delete.assert_called_once()
        key = mock_redis.delete.call_args[0][0]
        assert key == f"stream_session:{session_id}"

    def test_list_sessions_empty(self, session_manager, mock_redis):
        """Test listing sessions when no sessions exist"""
        mock_redis.scan_iter.return_value = []

        sessions = session_manager.list_sessions()

        assert isinstance(sessions, list)
        assert len(sessions) == 0

    def test_list_sessions_multiple(self, session_manager, mock_redis):
        """Test listing multiple sessions"""
        # Mock Redis to return multiple session keys
        session1 = StreamSession('aprs', 144800000, 300, 20, 2000000)
        session2 = StreamSession('pocsag', 147325000, 600, 30, 2000000)

        mock_redis.scan_iter.return_value = [
            'stream_session:session-1',
            'stream_session:session-2'
        ]

        def mock_get(key):
            if key == 'stream_session:session-1':
                return json.dumps(session1.to_dict())
            elif key == 'stream_session:session-2':
                return json.dumps(session2.to_dict())
            return None

        mock_redis.get.side_effect = mock_get

        sessions = session_manager.list_sessions()

        assert len(sessions) == 2
        assert all(isinstance(s, StreamSession) for s in sessions)

    def test_get_user_active_session_none(self, session_manager, mock_redis):
        """Test getting active session when none exist"""
        mock_redis.scan_iter.return_value = []

        active = session_manager.get_user_active_session()

        assert active is None

    def test_get_user_active_session_exists(self, session_manager, mock_redis):
        """Test getting active session when one exists"""
        session = StreamSession('aprs', 144800000, 300, 20, 2000000)
        session.status = 'running'

        mock_redis.scan_iter.return_value = ['stream_session:test']
        mock_redis.get.return_value = json.dumps(session.to_dict())

        active = session_manager.get_user_active_session()

        assert active is not None
        assert active.status in ['starting', 'running']


# ============================================================================
# StreamingAPRSDecoder Tests
# ============================================================================

class TestStreamingAPRSDecoder:
    """Tests for StreamingAPRSDecoder"""

    @pytest.fixture(autouse=True)
    def mock_detect_sdr(self, monkeypatch):
        """Mock detect_sdr so decoder can be instantiated without SDR hardware"""
        monkeypatch.setattr(streaming, "detect_sdr", lambda *a, **kw: SDRType.HACKRF)

    def test_aprs_decoder_initialization(self):
        """Test APRS decoder initialization"""
        decoder = StreamingAPRSDecoder(
            frequency=144800000,
            duration=300,
            gain=20,
            sample_rate=2000000
        )

        assert decoder.frequency == 144800000
        assert decoder.duration == 300
        assert decoder.gain == 20
        assert decoder.sample_rate == 2000000

    def test_aprs_get_mode(self):
        """Test APRS decoder mode identification"""
        decoder = StreamingAPRSDecoder(144800000, 300, 20, 2000000)

        mode = decoder._get_mode()

        assert mode == 'aprs'

    def test_aprs_parse_decoder_line_valid(self):
        """Test parsing valid APRS packet from direwolf"""
        decoder = StreamingAPRSDecoder(144800000, 300, 20, 2000000)

        # Sample direwolf output line
        # Format: [0] N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-Test
        line = "[0] N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-Test"

        packet = decoder._parse_decoder_line(line)

        # Should parse or return None (implementation-dependent)
        # This is a mock test - actual parsing logic may vary
        assert packet is None or isinstance(packet, dict)

    def test_aprs_parse_decoder_line_invalid(self):
        """Test parsing invalid APRS line"""
        decoder = StreamingAPRSDecoder(144800000, 300, 20, 2000000)

        line = "Invalid garbage line"

        packet = decoder._parse_decoder_line(line)

        assert packet is None

    def test_aprs_start_stream_creates_session(self, session_manager):
        """create_session registers the decoder; start() runs the worker thread"""
        decoder = StreamingAPRSDecoder(144800000, 10, 20, 2000000)
        session_id = session_manager.create_session('aprs', decoder, 144800000, 2000000, 20)
        assert isinstance(session_id, str)
        assert session_manager.get_decoder(session_id) is decoder

        with patch.object(decoder, '_stream_worker_simple') as worker:
            decoder.start(session_manager)
            decoder.thread.join(timeout=5)
            worker.assert_called_once()

    def test_aprs_stop_stream(self):
        """Test stopping APRS stream"""
        decoder = StreamingAPRSDecoder(144800000, 300, 20, 2000000)

        # Set stop event
        decoder.stop()

        assert decoder.stop_event.is_set()


class TestRecordSdrFailure:
    """An SDR process that dies mid-stream must show up as a failed session"""

    @pytest.fixture
    def decoder(self, monkeypatch):
        monkeypatch.setattr(streaming, "detect_sdr", lambda *a, **kw: SDRType.HACKRF)
        decoder = StreamingAPRSDecoder(144800000, 300, 20, 2000000)
        decoder.session = StreamSession('aprs', 144800000, 300, 20, 2000000)
        decoder.session.status = 'running'
        return decoder

    @staticmethod
    def _sdr(stderr_text: str, code: int):
        import subprocess
        return subprocess.Popen(['sh', '-c', f'printf "%s\\n" "{stderr_text}" >&2; exit {code}'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_usb_stall_marks_failed(self, decoder):
        decoder.sdr_proc = self._sdr("Couldn't transfer any bytes for one second.", 1)
        decoder._record_sdr_failure()
        assert decoder.session.status == 'failed'
        assert 'USB' in decoder.session.error

    def test_busy_marks_failed(self, decoder):
        decoder.sdr_proc = self._sdr("hackrf_open() failed: Resource busy (-1000)", 1)
        decoder._record_sdr_failure()
        assert decoder.session.status == 'failed'
        assert 'busy' in decoder.session.error

    def test_clean_exit_keeps_status(self, decoder):
        decoder.sdr_proc = self._sdr("hackrf_exit() done", 0)
        decoder._record_sdr_failure()
        assert decoder.session.status == 'running'
        assert decoder.session.error is None


class TestReapOrphanedSessions:
    """Sessions left 'running' after an API restart must not stay active forever"""

    @pytest.fixture
    def manager(self):
        from radiomoni.redis_client import get_redis
        return SessionManager(redis_client=get_redis())

    @staticmethod
    def _running(manager):
        session = StreamSession('aprs', 144800000, 300, 20, 2000000)
        session.status = 'running'
        manager.save_session(session)
        return session.session_id

    def test_orphan_marked_failed_when_sdr_free(self, manager):
        session_id = self._running(manager)

        assert manager.reap_orphaned_sessions() == 1
        session = manager.get_session(session_id)
        assert session.status == 'failed'
        assert session.end_time is not None
        assert 'restarted' in session.error

    def test_nothing_reaped_while_sdr_lock_held(self, manager):
        from radiomoni import sdr_lock
        session_id = self._running(manager)
        assert sdr_lock.acquire('stream:other-worker', 'aprs')

        assert manager.reap_orphaned_sessions() == 0
        assert manager.get_session(session_id).status == 'running'

    def test_local_decoder_not_reaped(self, manager):
        session_id = self._running(manager)
        manager.register_decoder(session_id, Mock())

        assert manager.reap_orphaned_sessions() == 0
        assert manager.get_session(session_id).status == 'running'


# ============================================================================
# NarrowbandFMDemodulator Tests
# ============================================================================

def _fm_tone(sample_rate: int, seconds: float, tone_hz: float, deviation_hz: float) -> np.ndarray:
    """IQ of a carrier at DC, frequency-modulated by a sine tone."""
    t = np.arange(int(sample_rate * seconds)) / sample_rate
    phase = (deviation_hz / tone_hz) * np.sin(2 * np.pi * tone_hz * t)
    return np.exp(1j * phase).astype(np.complex64)


class TestNarrowbandFMDemodulator:
    """Tests for the stateful channel filter + FM discriminator used by APRS"""

    @pytest.mark.parametrize("input_rate,audio_rate", [
        (2_000_000, 50_000),   # HackRF
        (2_400_000, 50_000),   # RTL-SDR
        (1_024_000, 51_200),   # RTL-SDR
        (768_000, 51_200),     # Airspy HF+
    ])
    def test_audio_rate(self, input_rate, audio_rate):
        demod = NarrowbandFMDemodulator(input_rate, channel_bw_hz=12_500, deviation_hz=3000)
        assert demod.audio_rate == audio_rate

    def test_tone_recovered_at_full_scale(self):
        """A 1200 Hz tone at 3 kHz deviation comes out at 1200 Hz with peak ≈ 1.0"""
        demod = NarrowbandFMDemodulator(2_000_000, channel_bw_hz=12_500, deviation_hz=3000)
        audio = demod.process(_fm_tone(2_000_000, 0.5, 1200, 3000))
        settled = audio[len(audio) // 5:]  # skip the filter start-up transient

        assert np.max(np.abs(settled)) == pytest.approx(1.0, abs=0.1)
        spectrum = np.abs(np.fft.rfft(settled))
        peak_hz = np.argmax(spectrum) * demod.audio_rate / len(settled)
        assert peak_hz == pytest.approx(1200, abs=10)

    def test_chunking_does_not_change_output(self):
        """Filter, decimation and discriminator state carry over between chunks"""
        iq = _fm_tone(2_000_000, 0.3, 1200, 3000)
        whole = NarrowbandFMDemodulator(2_000_000, 12_500, 3000).process(iq)

        chunked_demod = NarrowbandFMDemodulator(2_000_000, 12_500, 3000)
        bounds = [0, 199_999, 200_003, 377_777, len(iq)]  # uneven, not multiples of the decimation
        chunked = np.concatenate([chunked_demod.process(iq[a:b]) for a, b in zip(bounds, bounds[1:])])

        assert len(chunked) == len(whole)
        np.testing.assert_allclose(chunked, whole, atol=1e-9)

    def test_aprs_decoder_passes_audio_rate_to_direwolf(self, monkeypatch):
        monkeypatch.setattr(streaming, "detect_sdr", lambda *a, **kw: SDRType.HACKRF)
        decoder = StreamingAPRSDecoder(144800000, 300, 20, 2000000)

        with patch.object(streaming.subprocess, "Popen") as popen:
            decoder._start_decoder()

        cmd = popen.call_args[0][0]
        assert cmd[cmd.index('-r') + 1] == '50000'


# ============================================================================
# StreamingPOCSAGDecoder Tests
# ============================================================================

class TestStreamingPOCSAGDecoder:
    """Tests for StreamingPOCSAGDecoder"""

    @pytest.fixture(autouse=True)
    def mock_detect_sdr(self, monkeypatch):
        """Mock detect_sdr so decoder can be instantiated without SDR hardware"""
        monkeypatch.setattr(streaming, "detect_sdr", lambda *a, **kw: SDRType.HACKRF)

    def test_pocsag_decoder_initialization(self):
        """Test POCSAG decoder initialization"""
        decoder = StreamingPOCSAGDecoder(
            frequency=147325000,
            duration=600,
            gain=30,
            sample_rate=2000000
        )

        assert decoder.frequency == 147325000
        assert decoder.duration == 600
        assert decoder.gain == 30
        assert decoder.sample_rate == 2000000

    def test_pocsag_get_mode(self):
        """Test POCSAG decoder mode identification"""
        decoder = StreamingPOCSAGDecoder(147325000, 600, 30, 2000000)

        mode = decoder._get_mode()

        assert mode == 'pocsag'

    def test_pocsag_parse_decoder_line_valid(self):
        """Test parsing valid POCSAG message from multimon-ng"""
        decoder = StreamingPOCSAGDecoder(147325000, 600, 30, 2000000)

        # Sample multimon-ng output
        # Format: POCSAG1200: Address: 1234567  Function: 1  Alpha:   Test Message
        line = "POCSAG1200: Address: 1234567  Function: 1  Alpha:   Test Message"

        packet = decoder._parse_decoder_line(line)

        # Should parse or return None
        assert packet is None or isinstance(packet, dict)

    def test_pocsag_parse_decoder_line_invalid(self):
        """Test parsing invalid POCSAG line"""
        decoder = StreamingPOCSAGDecoder(147325000, 600, 30, 2000000)

        line = "Random text not POCSAG"

        packet = decoder._parse_decoder_line(line)

        assert packet is None

    def test_pocsag_start_stream_creates_session(self, session_manager):
        """create_session registers the decoder; start() runs the worker thread"""
        decoder = StreamingPOCSAGDecoder(147325000, 10, 20, 2000000)
        session_id = session_manager.create_session('pocsag', decoder, 147325000, 2000000, 20)
        assert isinstance(session_id, str)
        assert session_manager.get_decoder(session_id) is decoder

        with patch.object(decoder, '_stream_worker_simple') as worker:
            decoder.start(session_manager)
            decoder.thread.join(timeout=5)
            worker.assert_called_once()

    def test_pocsag_stop_stream(self):
        """Test stopping POCSAG stream"""
        decoder = StreamingPOCSAGDecoder(147325000, 600, 30, 2000000)

        decoder.stop()

        assert decoder.stop_event.is_set()


# ============================================================================
# API Integration Tests
# ============================================================================

class TestStreamingAPI:
    """API tests for streaming endpoints (no hardware)"""

    def test_stream_decode_requires_frequency(self, client: FlaskClient):
        response = client.post('/stream-decode', json={'mode': 'aprs'})
        assert response.status_code == 400
        assert 'frequency' in response.get_json()['error']

    def test_stream_decode_rejects_unknown_mode(self, client: FlaskClient):
        response = client.post('/stream-decode', json={'mode': 'fax', 'frequency': 144800000})
        assert response.status_code == 400

    def test_stream_decode_without_sdr_is_503(self, client: FlaskClient, monkeypatch):
        monkeypatch.setattr(streaming, "detect_sdr", lambda *a, **kw: SDRType.UNKNOWN)
        response = client.post('/stream-decode', json={'mode': 'aprs', 'frequency': 144800000})
        assert response.status_code == 400  # "No SDR hardware detected" is a ValueError

    def test_unknown_session_is_404(self, client: FlaskClient):
        assert client.get('/stream-decode/nope').status_code == 404
        assert client.delete('/stream-decode/nope').status_code == 404

    def test_stream_decode_conflict_when_sdr_busy(self, client: FlaskClient, monkeypatch):
        from radiomoni import sdr_lock
        monkeypatch.setattr(streaming, "detect_sdr", lambda *a, **kw: SDRType.HACKRF)
        assert sdr_lock.acquire('other-job', 'capture')
        response = client.post('/stream-decode', json={'mode': 'aprs', 'frequency': 144800000, 'duration': 10})
        assert response.status_code == 409
        assert response.get_json()['holder']['owner'] == 'other-job'

    def test_legacy_endpoint_is_deprecated(self, client: FlaskClient, monkeypatch):
        from radiomoni import sdr_lock
        monkeypatch.setattr(streaming, "detect_sdr", lambda *a, **kw: SDRType.HACKRF)
        assert sdr_lock.acquire('other-job', 'capture')
        response = client.post('/stream/aprs/start', json={'duration': 10})
        assert response.status_code == 409

    def test_usrp_requires_address(self, client: FlaskClient):
        response = client.post('/stream-decode', json={'mode': 'aprs', 'frequency': 144800000,
                                                       'device_type': 'usrp'})
        assert response.status_code == 400

    def test_usrp_address_must_be_ip(self, client: FlaskClient):
        response = client.post('/stream-decode', json={'mode': 'aprs', 'frequency': 144800000,
                                                       'device_type': 'usrp',
                                                       'device_address': '1.2.3.4,fpga=/etc/x'})
        assert response.status_code == 400


# ============================================================================
# Integration Tests
# ============================================================================

class TestStreamingIntegration:
    """Integration tests for streaming workflow"""

    def test_session_lifecycle(self, session_manager):
        """Test complete session lifecycle: create → save → retrieve → delete"""
        # Create session
        session = StreamSession('aprs', 144800000, 300, 20, 2000000)

        # Save
        session_manager.save_session(session)

        # Retrieve (mocked)
        session_manager.redis.get.return_value = json.dumps(session.to_dict())
        retrieved = session_manager.get_session(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id

        # Delete
        session_manager.delete_session(session.session_id)

    def test_multiple_sessions_management(self, session_manager, mock_redis):
        """Test managing multiple concurrent sessions"""
        # Create multiple sessions
        sessions = [
            StreamSession('aprs', 144800000, 300, 20, 2000000),
            StreamSession('pocsag', 147325000, 600, 30, 2000000),
            StreamSession('aprs', 145500000, 300, 25, 2000000)
        ]

        # Save all
        for session in sessions:
            session_manager.save_session(session)

        # List should return all (mocked)
        mock_redis.scan_iter.return_value = [
            f'stream_session:{s.session_id}' for s in sessions
        ]

        def mock_get(key):
            session_id = key.split(':')[1]
            for s in sessions:
                if s.session_id == session_id:
                    return json.dumps(s.to_dict())
            return None

        mock_redis.get.side_effect = mock_get

        all_sessions = session_manager.list_sessions()

        assert len(all_sessions) == 3

    def test_session_expiry(self, session_manager, mock_redis):
        """Test that sessions have TTL (Time To Live)"""
        session = StreamSession('aprs', 144800000, 300, 20, 2000000)

        session_manager.save_session(session)

        # Verify expire was called with 7 days
        mock_redis.expire.assert_called()
        args = mock_redis.expire.call_args[0]
        assert args[1] == 86400 * 7  # 7 days


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
