"""Pytest configuration and shared fixtures"""

import os
import sys
import tempfile
import pytest
import numpy as np
from scipy.io import wavfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_service import app
from transcription_service import TranscriptionService
from sdr_hardware import HackRFCapture, SDRType, detect_sdr, get_sdr_instance


@pytest.fixture(scope='session')
def temp_recording_dir():
    """Temporary directory for test recordings (session-wide)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, temp_recording_dir):
    """Setup test environment before any test runs"""
    # Set environment variables BEFORE importing api_service
    monkeypatch.setenv('API_KEYS', '')
    monkeypatch.setenv('AUDIO_OUTPUT_DIR', temp_recording_dir)

    # Import and patch api_service
    import api_service
    monkeypatch.setattr(api_service, 'RECORDING_DIR', temp_recording_dir)

    # Ensure the directory exists
    os.makedirs(temp_recording_dir, exist_ok=True)


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    app.config['DEBUG'] = False
    with app.test_client() as client:
        # Set test client to use localhost IP
        client.environ_base['REMOTE_ADDR'] = '127.0.0.1'
        yield client


@pytest.fixture
def sample_audio_file(temp_recording_dir) -> str:
    """Create a sample WAV file for testing inside temp RECORDING_DIR"""
    # Use the session-scoped temp directory (same as API uses)
    recording_dir = temp_recording_dir
    os.makedirs(recording_dir, exist_ok=True)

    # Generate 1 second of test audio (16kHz for Whisper compatibility)
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Create a simple tone
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440 Hz tone
    audio_int16 = np.int16(audio * 32767)

    # Create file INSIDE temp recording_dir
    filename = 'test_audio.wav'
    filepath = os.path.join(recording_dir, filename)
    wavfile.write(filepath, sample_rate, audio_int16)

    # Return full path for TranscriptionService tests
    # API tests will use os.path.basename() to get just the filename
    return filepath


@pytest.fixture(autouse=True)
def mock_transcription_service(monkeypatch):
    """Mock TranscriptionService __init__ to avoid loading Whisper model (CUDA errors)"""
    # Only mock __init__ to prevent model loading, keep real transcribe() method
    # This allows FileNotFoundError and other real behavior to work
    def mock_init(self, model='base', device='cpu', compute_type='int8'):
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.model = None  # Don't actually load the model
        self.simulation_mode = True  # Force simulation mode

    monkeypatch.setattr(TranscriptionService, '__init__', mock_init)


@pytest.fixture
def mock_hackrf_capture(monkeypatch):
    """Mock HackRFCapture for testing without hardware"""
    original_init = HackRFCapture.__init__

    def mock_init(self, *args, **kwargs):
        # Call original init to set attributes
        original_init(self, *args, **kwargs)

    def mock_capture(self, duration: int, output_file: str) -> None:
        # Always use simulation mode
        self._simulate_capture(duration, output_file)

    monkeypatch.setattr(HackRFCapture, '__init__', mock_init)
    monkeypatch.setattr(HackRFCapture, 'capture', mock_capture)


@pytest.fixture
def mock_sdr_hardware(monkeypatch, temp_recording_dir):
    """Mock SDR hardware for API tests"""
    import sdr_hardware

    # Mock detect_sdr to return HackRF available
    def mock_detect():
        return SDRType.HACKRF

    monkeypatch.setattr(sdr_hardware, 'detect_sdr', mock_detect)

    # Mock is_available to return True
    monkeypatch.setattr(HackRFCapture, 'is_available', lambda self: True)

    # Mock capture_audio to create a dummy WAV file
    def mock_capture_audio(self, duration: int, output_file: str, modulation: str = 'FM'):
        """Create a dummy WAV file instead of capturing"""
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)

        # Generate dummy audio
        sample_rate = 16000
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.1 * np.sin(2 * np.pi * 440 * t)
        audio_int16 = np.int16(audio * 32767)

        wavfile.write(output_file, sample_rate, audio_int16)

    monkeypatch.setattr(HackRFCapture, 'capture_audio', mock_capture_audio)

    # Mock capture_iq to create a dummy IQ file
    def mock_capture_iq(self, duration: int, output_file: str):
        """Create a dummy IQ file instead of capturing"""
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)

        # Generate dummy IQ samples
        num_samples = int(self.sample_rate * duration)
        iq_data = np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
        iq_data = iq_data.astype(np.complex64)

        # Save as binary
        iq_data.tofile(output_file)

    monkeypatch.setattr(HackRFCapture, 'capture_iq', mock_capture_iq)
