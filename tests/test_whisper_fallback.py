"""Whisper GPU self-test: fall back to the CPU when the card cannot run the model."""

import sys
import types

import pytest
from flask.testing import FlaskClient

from radiomoni import services
from radiomoni.transcription_service import TranscriptionService


class FakeModel:
    """Stands in for faster_whisper.WhisperModel; behaviour per device set by the test."""
    loads: list[tuple[str, str]] = []
    fail_load: set[str] = set()
    fail_run: set[str] = set()

    def __init__(self, name, device, compute_type):
        FakeModel.loads.append((device, compute_type))
        if device in FakeModel.fail_load:
            raise RuntimeError('CUDA failed with error out of memory')
        self.device = device

    def transcribe(self, audio, **kwargs):
        if self.device in FakeModel.fail_run:
            raise RuntimeError('parallel_for failed: cudaErrorInvalidDevice: invalid device ordinal')
        return iter([]), types.SimpleNamespace(language='en', language_probability=1.0, duration=1.0)


@pytest.fixture
def fake_whisper(monkeypatch):
    FakeModel.loads, FakeModel.fail_load, FakeModel.fail_run = [], set(), set()
    monkeypatch.setitem(sys.modules, 'faster_whisper', types.SimpleNamespace(WhisperModel=FakeModel))
    return FakeModel


def load(device: str, compute_type: str) -> TranscriptionService:
    # bypass the autouse fixture that replaces __init__ with simulation mode
    svc = TranscriptionService.__new__(TranscriptionService)
    svc.model_name, svc.device, svc.compute_type = 'small', device, compute_type
    svc.model, svc.simulation_mode, svc.fallback_reason = None, False, None
    svc._load_model()
    return svc


class TestFallback:
    def test_working_gpu_is_kept(self, fake_whisper):
        svc = load('cuda', 'float16')
        assert (svc.device, svc.compute_type, svc.fallback_reason) == ('cuda', 'float16', None)
        assert fake_whisper.loads == [('cuda', 'float16')]

    def test_unsupported_card_falls_back(self, fake_whisper, caplog):
        fake_whisper.fail_run = {'cuda'}
        svc = load('cuda', 'float32')
        assert (svc.device, svc.compute_type) == ('cpu', 'int8')
        assert 'cudaErrorInvalidDevice' in svc.fallback_reason
        assert fake_whisper.loads == [('cuda', 'float32'), ('cpu', 'int8')]
        assert 'falling back to the CPU' in caplog.text

    def test_out_of_memory_at_load_falls_back(self, fake_whisper):
        fake_whisper.fail_load = {'cuda'}
        svc = load('cuda', 'float16')
        assert svc.device == 'cpu' and 'out of memory' in svc.fallback_reason
        assert svc.model is not None

    def test_cpu_is_not_self_tested(self, fake_whisper):
        fake_whisper.fail_run = {'cpu'}  # a self-test on the CPU would raise
        svc = load('cpu', 'int8')
        assert svc.device == 'cpu' and svc.fallback_reason is None


class TestReadiness:
    def test_reports_whisper_device(self, client: FlaskClient, monkeypatch):
        svc = TranscriptionService.__new__(TranscriptionService)
        svc.model_name, svc.device, svc.compute_type, svc.fallback_reason = 'small', 'cpu', 'int8', 'RuntimeError: x'
        monkeypatch.setattr(services, '_transcription', svc)
        whisper = client.get('/health/ready').get_json()['checks']['whisper']
        assert whisper['loaded'] is True and whisper['device'] == 'cpu'
        assert whisper['fallback_reason'] == 'RuntimeError: x'

    def test_not_loaded_yet(self, client: FlaskClient):
        assert client.get('/health/ready').get_json()['checks']['whisper']['loaded'] is False
