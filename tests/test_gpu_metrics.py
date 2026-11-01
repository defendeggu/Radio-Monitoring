"""GPU metrics endpoint (Prometheus text for Metricbeat) and the read-only metrics key."""

import subprocess
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from radiomoni import config
from radiomoni.blueprints import health

KEY = 'k' * 43
METRICS_KEY = 'm' * 43
CSV = '0, 37, 12, 900, 2048, 41, [N/A], Quadro M1000M\n1, 80, 50, 4000, 8192, 70, 120.5, RTX "Test", 8 GB\n'


@pytest.fixture
def fake_smi(monkeypatch):
    monkeypatch.setattr(health.shutil, 'which', lambda name: '/usr/bin/nvidia-smi')
    run = MagicMock(return_value=MagicMock(stdout=CSV))
    monkeypatch.setattr(health.subprocess, 'run', run)
    return run


@pytest.fixture
def secured(client: FlaskClient, monkeypatch):
    monkeypatch.setattr(config, 'API_KEYS', [KEY])
    monkeypatch.setattr(config, 'TRUSTED_IPS', [])
    monkeypatch.setattr(config, 'METRICS_API_KEY', METRICS_KEY)
    client.environ_base['REMOTE_ADDR'] = '172.18.0.7'  # Metricbeat on the Docker network
    return client


class TestPrometheusText:
    def test_metrics_and_labels(self):
        text = health.gpu_metrics_text(CSV)
        assert 'radiomoni_gpu_utilization_percent{gpu="0",name="Quadro M1000M"} 37.0' in text
        assert 'radiomoni_gpu_memory_used_mib{gpu="1",name="RTX Test, 8 GB"} 4000.0' in text
        assert '# TYPE radiomoni_gpu_temperature_celsius gauge' in text

    def test_not_available_values_are_skipped(self):
        power = [line for line in health.gpu_metrics_text(CSV).splitlines()
                 if line.startswith('radiomoni_gpu_power_draw_watts{')]
        assert power == ['radiomoni_gpu_power_draw_watts{gpu="1",name="RTX Test, 8 GB"} 120.5']


class TestEndpoint:
    def test_returns_prometheus_text(self, client: FlaskClient, fake_smi):
        response = client.get('/metrics/gpu')
        assert response.status_code == 200
        assert response.mimetype == 'text/plain'
        assert 'radiomoni_gpu_utilization_percent' in response.get_data(as_text=True)

    def test_no_gpu_503(self, client: FlaskClient, monkeypatch):
        monkeypatch.setattr(health.shutil, 'which', lambda name: None)
        assert client.get('/metrics/gpu').status_code == 503

    def test_nvidia_smi_failure_503(self, client: FlaskClient, fake_smi):
        fake_smi.side_effect = subprocess.CalledProcessError(9, 'nvidia-smi')
        assert client.get('/metrics/gpu').status_code == 503


class TestMetricsKey:
    def test_metrics_key_opens_metrics(self, secured: FlaskClient, fake_smi):
        assert secured.get('/metrics/gpu', headers={'X-API-Key': METRICS_KEY}).status_code == 200

    def test_metrics_key_opens_nothing_else(self, secured: FlaskClient):
        assert secured.get('/stats', headers={'X-API-Key': METRICS_KEY}).status_code == 403
        assert secured.get('/recordings', headers={'X-API-Key': METRICS_KEY}).status_code == 403

    def test_metrics_still_need_a_key(self, secured: FlaskClient, fake_smi):
        assert secured.get('/metrics/gpu').status_code == 401
        assert secured.get('/metrics/gpu', headers={'X-API-Key': KEY}).status_code == 200

    def test_disabled_without_metrics_key(self, secured: FlaskClient, monkeypatch, fake_smi):
        monkeypatch.setattr(config, 'METRICS_API_KEY', '')
        assert secured.get('/metrics/gpu', headers={'X-API-Key': ''}).status_code == 401
