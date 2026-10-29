"""Security regression tests (authentication, trusted IPs, CORS, headers, startup)."""

import pytest
from flask.testing import FlaskClient

from radiomoni import config
from radiomoni import security

KEY = 'k' * 43


@pytest.fixture
def with_keys(monkeypatch):
    monkeypatch.setattr(config, 'API_KEYS', [KEY])
    monkeypatch.setattr(config, 'TRUSTED_IPS', [])


class TestApiKeys:
    def test_health_is_public(self, client: FlaskClient, with_keys):
        client.environ_base['REMOTE_ADDR'] = '203.0.113.5'
        assert client.get('/health').status_code == 200
        assert client.get('/openapi.json').status_code == 200

    def test_missing_key_401(self, client: FlaskClient, with_keys):
        client.environ_base['REMOTE_ADDR'] = '203.0.113.5'
        assert client.get('/stats').status_code == 401

    def test_wrong_key_403(self, client: FlaskClient, with_keys):
        client.environ_base['REMOTE_ADDR'] = '203.0.113.5'
        assert client.get('/stats', headers={'X-API-Key': 'wrong'}).status_code == 403

    def test_valid_key(self, client: FlaskClient, with_keys):
        client.environ_base['REMOTE_ADDR'] = '203.0.113.5'
        assert client.get('/stats', headers={'X-API-Key': KEY}).status_code == 200

    def test_docker_network_is_not_trusted(self, client: FlaskClient, with_keys):
        """172.16.0.0/12 used to bypass auth — every container on the bridge could control the SDR"""
        client.environ_base['REMOTE_ADDR'] = '172.18.0.5'
        assert client.get('/stats').status_code == 401

    def test_loopback_is_trusted(self, client: FlaskClient, with_keys):
        client.environ_base['REMOTE_ADDR'] = '127.0.0.1'
        assert client.get('/stats').status_code == 200

    def test_explicit_trusted_network(self, client: FlaskClient, with_keys, monkeypatch):
        monkeypatch.setattr(config, 'TRUSTED_IPS', ['192.168.10.0/24'])
        client.environ_base['REMOTE_ADDR'] = '192.168.10.20'
        assert client.get('/stats').status_code == 200
        client.environ_base['REMOTE_ADDR'] = '192.168.11.20'
        assert client.get('/stats').status_code == 401


class TestHelpers:
    @pytest.mark.parametrize('ip,trusted,expected', [
        ('127.0.0.1', [], True),
        ('::1', [], True),
        ('172.17.0.1', [], False),
        ('10.0.0.1', [], False),
        ('10.0.0.1', ['10.0.0.0/8'], True),
        ('10.0.0.1', ['10.0.0.1'], True),
        ('not-an-ip', ['10.0.0.0/8'], False),
        (None, [], False),
        ('10.0.0.1', ['garbage'], False),
    ])
    def test_is_trusted_ip(self, ip, trusted, expected):
        assert security.is_trusted_ip(ip, trusted) is expected

    def test_api_key_comparison(self):
        assert security.is_valid_api_key(KEY, [KEY, 'other'])
        assert not security.is_valid_api_key(KEY[:-1], [KEY])
        assert not security.is_valid_api_key('', [KEY])
        assert not security.is_valid_api_key(None, [KEY])


class TestStartup:
    def test_refuses_to_start_without_keys(self, monkeypatch):
        monkeypatch.setattr(config, 'API_KEYS', [])
        monkeypatch.setattr(config, 'ALLOW_INSECURE', False)
        with pytest.raises(security.InsecureConfigurationError):
            security.check_startup_security()

    def test_explicit_insecure_mode(self, monkeypatch):
        monkeypatch.setattr(config, 'API_KEYS', [])
        monkeypatch.setattr(config, 'ALLOW_INSECURE', True)
        security.check_startup_security()

    def test_keys_configured(self, monkeypatch):
        monkeypatch.setattr(config, 'API_KEYS', [KEY])
        monkeypatch.setattr(config, 'ALLOW_INSECURE', False)
        security.check_startup_security()


class TestHttpHardening:
    def test_no_wildcard_cors(self, client: FlaskClient):
        response = client.get('/health', headers={'Origin': 'https://evil.example'})
        assert 'Access-Control-Allow-Origin' not in response.headers

    def test_security_headers(self, client: FlaskClient):
        response = client.get('/health')
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert response.headers['X-Frame-Options'] == 'DENY'

    def test_errors_do_not_leak_internals(self, client: FlaskClient, monkeypatch):
        from radiomoni import storage

        class Broken:
            def get_overall_stats(self):
                raise RuntimeError('/secret/path/db.sqlite exploded')

        monkeypatch.setattr(storage, '_instance', Broken())
        response = client.get('/stats')
        assert response.status_code == 500
        assert 'secret' not in response.get_data(as_text=True)
        assert response.get_json()['correlation_id']

    def test_body_size_limit(self, client: FlaskClient):
        response = client.post('/bookmarks', data='x' * (2 * 1024 * 1024), content_type='application/json')
        assert response.status_code == 413

    def test_csv_formula_injection_neutralised(self, client: FlaskClient):
        from radiomoni.storage import get_storage
        get_storage().index_pocsag({'address': 123, 'message_type': 'alpha',
                                    'message_text': '=HYPERLINK("http://evil","x")'})
        body = client.get('/export/pocsag.csv').get_data(as_text=True)
        assert "'=HYPERLINK" in body
