"""Signed recording links (audio player in Kibana): creation, validation, scope."""

import os
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from radiomoni import config, recording_links

KEY = 'k' * 43
SECRET = 's' * 43


@pytest.fixture
def secured(client: FlaskClient, monkeypatch):
    """API keys on, link secret set, request from an untrusted address."""
    monkeypatch.setattr(config, 'API_KEYS', [KEY])
    monkeypatch.setattr(config, 'TRUSTED_IPS', [])
    monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', SECRET)
    client.environ_base['REMOTE_ADDR'] = '203.0.113.5'
    return client


def _url(filename: str) -> str:
    url = recording_links.audio_url(filename)
    assert url is not None
    return url.removeprefix('/api')  # the API sees the path without the nginx prefix


class TestLinks:
    def test_url_format(self, monkeypatch):
        monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', SECRET)
        url = recording_links.audio_url('vox_1.wav')
        assert url is not None and url.startswith('/api/recordings/vox_1.wav?sig=')
        assert len(url.split('sig=')[1]) == 32

    def test_signature_depends_on_file_and_secret(self, monkeypatch):
        monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', SECRET)
        a, b = recording_links.sign('a.wav'), recording_links.sign('b.wav')
        monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', 'other' * 9)
        assert a != b and a != recording_links.sign('a.wav')

    @pytest.mark.parametrize('name', [None, '', 'capture.json', 'dir/x.wav'])
    def test_no_link_for_non_wav(self, monkeypatch, name):
        monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', SECRET)
        assert recording_links.audio_url(name) is None

    def test_no_secret_no_links(self, monkeypatch):
        monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', '')
        assert recording_links.audio_url('vox_1.wav') is None
        assert not recording_links.is_signed_request('/recordings/vox_1.wav', 'anything')


class TestSignedAccess:
    def test_valid_link_plays_without_key(self, secured: FlaskClient, sample_audio_file):
        response = secured.get(_url(os.path.basename(sample_audio_file)))
        assert response.status_code == 200
        assert response.mimetype == 'audio/wav'

    def test_range_request_for_seeking(self, secured: FlaskClient, sample_audio_file):
        response = secured.get(_url(os.path.basename(sample_audio_file)), headers={'Range': 'bytes=0-99'})
        assert response.status_code == 206

    def test_wrong_signature_rejected(self, secured: FlaskClient, sample_audio_file):
        name = os.path.basename(sample_audio_file)
        assert secured.get(f'/recordings/{name}?sig={"0" * 32}').status_code == 401
        assert secured.get(f'/recordings/{name}').status_code == 401

    def test_signature_of_other_file_rejected(self, secured: FlaskClient, sample_audio_file):
        sig = recording_links.sign('other.wav')
        assert secured.get(f'/recordings/{os.path.basename(sample_audio_file)}?sig={sig}').status_code == 401

    def test_link_opens_nothing_else(self, secured: FlaskClient, sample_audio_file):
        name = os.path.basename(sample_audio_file)
        sig = recording_links.sign(name)
        assert secured.delete(f'/recordings/{name}?sig={sig}').status_code == 401
        assert secured.get(f'/recordings?sig={sig}').status_code == 401
        assert secured.get(f'/recordings/{name.replace(".wav", ".json")}?sig={sig}').status_code == 401
        assert os.path.exists(sample_audio_file)


class TestIndexing:
    @pytest.fixture
    def es(self):
        from radiomoni.storage.elasticsearch import ElasticsearchService
        svc = ElasticsearchService(hosts=['http://es:9200'])
        svc.es_client = MagicMock()
        svc._http = MagicMock()
        svc._http.post.return_value = MagicMock(status_code=200)
        return svc

    def test_capture_gets_audio_url(self, es, monkeypatch):
        monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', SECRET)
        es.index_capture({'frequency': 145_500_000, 'audio_file': 'vox_1.wav', 'mode': 'vox'})
        doc = es._http.post.call_args.kwargs['json']
        assert doc['audio_url'] == recording_links.audio_url('vox_1.wav')

    def test_no_audio_url_without_secret(self, es, monkeypatch):
        monkeypatch.setattr(config, 'RECORDING_LINK_SECRET', '')
        es.index_capture({'frequency': 145_500_000, 'audio_file': 'vox_1.wav'})
        assert 'audio_url' not in es._http.post.call_args.kwargs['json']
