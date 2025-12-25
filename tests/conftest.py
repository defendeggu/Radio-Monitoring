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
from radio_capture import HackRFCapture


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    app.config['DEBUG'] = False
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_recording_dir():
    """Temporary directory for test recordings"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_audio_file(temp_recording_dir: str) -> str:
    """Create a sample WAV file for testing"""
    # Generate 1 second of test audio (16kHz for Whisper compatibility)
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Create a simple tone
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440 Hz tone
    audio_int16 = np.int16(audio * 32767)

    filepath = os.path.join(temp_recording_dir, 'test_audio.wav')
    wavfile.write(filepath, sample_rate, audio_int16)

    return filepath


@pytest.fixture
def mock_transcription_service(monkeypatch):
    """Mock TranscriptionService for testing without faster-whisper"""
    def mock_transcribe(self, audio_file: str, language: str | None = None):
        return {
            'text': 'Test transcription result',
            'language': 'en',
            'language_probability': 0.95,
            'duration': 1.0,
            'segments': [
                {
                    'start': 0.0,
                    'end': 1.0,
                    'text': 'Test transcription result'
                }
            ],
            'audio_file': audio_file,
            'timestamp': '2025-01-01T00:00:00'
        }

    monkeypatch.setattr(TranscriptionService, 'transcribe', mock_transcribe)


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
def set_recording_dir(temp_recording_dir: str, monkeypatch):
    """Set RECORDING_DIR to temporary directory"""
    monkeypatch.setenv('AUDIO_OUTPUT_DIR', temp_recording_dir)
    import api_service
    monkeypatch.setattr(api_service, 'RECORDING_DIR', temp_recording_dir)
