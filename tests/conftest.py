"""Pytest configuration and shared fixtures"""

import os
import sys
import tempfile
import time

import numpy as np
import pytest
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# One temp directory for the whole session — environment must be set BEFORE importing the app
_TEST_DIR = tempfile.mkdtemp(prefix='pytest-radiomoni-')
_TEST_RECORDING_DIR = os.path.join(_TEST_DIR, 'recordings')
os.makedirs(_TEST_RECORDING_DIR, exist_ok=True)

os.environ.update({
    'API_KEYS': '',
    'ALLOW_INSECURE': 'true',
    'SKIP_REDIS_CHECK': '1',          # in-process fakeredis
    'STORAGE_BACKEND': 'sqlite',
    'SQLITE_PATH': os.path.join(_TEST_DIR, 'session.sqlite3'),
    'AUDIO_OUTPUT_DIR': _TEST_RECORDING_DIR,
    'JSON_LOGGING': 'false',
    'SCHEDULER_ENABLED': 'false',
    'MIN_FREE_DISK_MB': '1',
    'PROXY_COUNT': '0',
})

from radiomoni.api_service import app  # noqa: E402
from radiomoni.sdr_hardware import HackRFCapture, SDRType  # noqa: E402
from radiomoni.transcription_service import TranscriptionService  # noqa: E402


@pytest.fixture(scope='session')
def temp_recording_dir():
    return _TEST_RECORDING_DIR


def pytest_sessionfinish(session, exitstatus):
    import shutil
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, mock_transcription_service):
    """Fresh Redis and storage for every test."""
    from radiomoni import alerts
    import radiomoni.blueprints.sdr
    from radiomoni.redis_client import get_redis
    from radiomoni.storage.base import set_storage
    from radiomoni.storage.sqlite import SQLiteStorage

    get_redis().flushall()
    set_storage(SQLiteStorage(str(tmp_path / 'storage.sqlite3')))
    alerts._invalidate()
    radiomoni.blueprints.sdr._detect_cache = (0.0, {})
    yield
    _drain_job_pools()
    get_redis().flushall()
    from radiomoni.storage import base as storage
    if isinstance(storage._instance, SQLiteStorage):
        storage._instance.close()
    set_storage(None)


def _drain_job_pools(timeout: float = 30.0) -> None:
    """Wait for background jobs of the finished test (pools are FIFO, one worker each)."""
    from concurrent.futures import ThreadPoolExecutor

    from radiomoni import jobs
    for pool in (jobs.capture_pool, jobs.scan_pool):
        # call the class method: tests may monkeypatch pool.submit
        ThreadPoolExecutor.submit(pool, lambda: None).result(timeout=timeout)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        client.environ_base['REMOTE_ADDR'] = '127.0.0.1'
        yield client


@pytest.fixture
def sample_audio_file(temp_recording_dir) -> str:
    """1 s 440 Hz tone WAV inside the recordings directory"""
    sample_rate = 16000
    t = np.linspace(0, 1.0, sample_rate)
    audio = np.int16(0.3 * np.sin(2 * np.pi * 440 * t) * 32767)
    filepath = os.path.join(temp_recording_dir, 'test_audio.wav')
    wavfile.write(filepath, sample_rate, audio)
    return filepath


@pytest.fixture(autouse=True)
def mock_transcription_service(monkeypatch):
    """Never load a Whisper model in tests: use simulation mode."""
    def mock_init(self, model='base', device='cpu', compute_type='int8'):
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self.simulation_mode = True
        self.fallback_reason = None

    monkeypatch.setattr(TranscriptionService, '__init__', mock_init)
    from radiomoni import services
    monkeypatch.setattr(services, '_transcription', None)


@pytest.fixture
def mock_sdr_hardware(monkeypatch):
    """Pretend a HackRF is connected; captures produce synthetic files."""
    from radiomoni import jobs
    from radiomoni import sdr_hardware
    from radiomoni.decoders import streaming
    from radiomoni.decoders import vox

    detect = lambda *args, **kwargs: SDRType.HACKRF  # noqa: E731
    for module in (sdr_hardware, jobs, streaming, vox):
        monkeypatch.setattr(module, 'detect_sdr', detect)
    import radiomoni.blueprints.sdr
    monkeypatch.setattr(radiomoni.blueprints.sdr, 'detect_sdr', detect)
    monkeypatch.setattr(HackRFCapture, 'is_available', lambda self: True)

    def mock_capture_audio(self, duration: int, output_file: str, modulation: str = 'FM'):
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        t = np.linspace(0, duration, int(16000 * duration))
        wavfile.write(output_file, 16000, np.int16(0.1 * np.sin(2 * np.pi * 440 * t) * 32767))

    def mock_capture_iq(self, duration: int, output_file: str):
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        n = int(self.sample_rate * duration)
        (np.random.randn(n) + 1j * np.random.randn(n)).astype(np.complex64).tofile(output_file)

    monkeypatch.setattr(HackRFCapture, 'capture_audio', mock_capture_audio)
    monkeypatch.setattr(HackRFCapture, 'capture_iq', mock_capture_iq)
    yield
    _drain_job_pools()  # jobs must finish while the hardware mocks are still active


def wait_for_capture(client, capture_id: str, timeout: float = 15.0) -> dict:
    """Poll /capture-status until the job finishes."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f'/capture-status/{capture_id}').get_json()
        if data['status'] in ('completed', 'failed'):
            return data
        time.sleep(0.1)
    raise AssertionError(f'capture {capture_id} did not finish')
