"""API tests: health, captures, transcription, recordings, search, OpenAPI."""

import os

import pytest
from flask.testing import FlaskClient

from tests.conftest import wait_for_capture


class TestHealth:
    def test_health(self, client: FlaskClient):
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        from radiomoni.version import __version__
        assert data['version'] == __version__

    def test_ready_reports_dependencies(self, client: FlaskClient):
        response = client.get('/health/ready')
        assert response.status_code == 200
        checks = response.get_json()['checks']
        assert checks['redis'] == 'ok'
        assert checks['storage']['backend'] == 'sqlite'
        assert checks['sdr']['busy'] is False

    def test_correlation_id_header(self, client: FlaskClient):
        response = client.get('/health', headers={'X-Correlation-ID': 'abc-123'})
        assert response.headers['X-Correlation-ID'] == 'abc-123'

    def test_correlation_id_rejects_garbage(self, client: FlaskClient):
        response = client.get('/health', headers={'X-Correlation-ID': '<script>'})
        assert response.headers['X-Correlation-ID'] != '<script>'


class TestCaptureValidation:
    def test_requires_frequency(self, client: FlaskClient):
        response = client.post('/capture-and-transcribe', json={'mode': 'voice'})
        assert response.status_code == 400
        assert 'frequency' in response.get_json()['error']

    @pytest.mark.parametrize('body', [
        {'frequency': 'abc'},
        {'frequency': 100e6, 'duration': 0},
        {'frequency': 100e6, 'duration': 601},
        {'frequency': 100e6, 'mode': 'pocsag', 'duration': 200},
        {'frequency': 100e6, 'gain': 500},
        {'frequency': 100e6, 'modulation': 'XYZ'},
        {'frequency': 100e6, 'mode': 'fax'},
        {'frequency': 100e6, 'language': 'english; rm -rf'},
        {'frequency': 100e6, 'unexpected': 1},
        {'frequency': 1},
    ])
    def test_rejects_invalid_parameters(self, client: FlaskClient, body):
        assert client.post('/capture-and-transcribe', json=body).status_code == 400

    def test_invalid_json(self, client: FlaskClient):
        response = client.post('/capture-and-transcribe', data='not json', content_type='application/json')
        assert response.status_code == 400

    def test_accepts_float_frequency(self, client: FlaskClient, mock_sdr_hardware):
        response = client.post('/capture-and-transcribe', json={'frequency': 144.8e6, 'duration': 1})
        assert response.status_code == 202

    def test_unsupported_frequency_for_device(self, client: FlaskClient, mock_sdr_hardware):
        response = client.post('/capture-and-transcribe', json={'frequency': 600, 'duration': 1})
        assert response.status_code == 400
        assert 'does not support' in response.get_json()['error']

    def test_no_sdr_is_503(self, client: FlaskClient, monkeypatch):
        from radiomoni import jobs
        from radiomoni.sdr_hardware import SDRType
        monkeypatch.setattr(jobs, 'detect_sdr', lambda *a, **k: SDRType.UNKNOWN)
        response = client.post('/capture-and-transcribe', json={'frequency': 100e6, 'duration': 1})
        assert response.status_code == 503


class TestCaptureJobs:
    def test_voice_capture_workflow(self, client: FlaskClient, mock_sdr_hardware, temp_recording_dir):
        response = client.post('/capture-and-transcribe', json={'frequency': 100e6, 'duration': 1,
                                                               'mode': 'voice', 'language': 'de'})
        assert response.status_code == 202
        capture_id = response.get_json()['capture_id']
        result = wait_for_capture(client, capture_id)
        assert result['status'] == 'completed', result
        payload = result['result']
        assert payload['mode'] == 'voice'
        assert payload['simulation_mode'] is True
        audio = payload['capture']['audio_file']
        assert '/' not in audio  # file names only, no server paths
        assert os.path.exists(os.path.join(temp_recording_dir, audio))
        assert os.path.exists(os.path.join(temp_recording_dir, audio.replace('.wav', '.json')))

        stored = client.get(f"/captures/{payload['capture']['id']}")
        assert stored.status_code == 200
        assert stored.get_json()['capture']['mode'] == 'voice'

    def test_raw_capture(self, client: FlaskClient, mock_sdr_hardware):
        response = client.post('/capture', json={'frequency': 100e6, 'duration': 1, 'modulation': 'AM'})
        assert response.status_code == 202
        result = wait_for_capture(client, response.get_json()['capture_id'])
        assert result['status'] == 'completed'
        assert result['result']['mode'] == 'raw'

    @pytest.mark.parametrize('mode,key', [('aprs', 'packets'), ('pocsag', 'messages')])
    def test_decode_modes(self, client: FlaskClient, mock_sdr_hardware, mode, key):
        response = client.post('/capture-and-transcribe', json={'frequency': 144.8e6, 'duration': 1, 'mode': mode})
        assert response.status_code == 202
        result = wait_for_capture(client, response.get_json()['capture_id'])
        assert result['status'] == 'completed', result
        assert isinstance(result['result'][mode][key], list)

    def test_sdr_busy_returns_409(self, client: FlaskClient, mock_sdr_hardware):
        from radiomoni import sdr_lock
        assert sdr_lock.acquire('stream:xyz', 'aprs')
        response = client.post('/capture-and-transcribe', json={'frequency': 100e6, 'duration': 1})
        assert response.status_code == 409
        assert response.get_json()['holder']['kind'] == 'aprs'

    def test_lock_released_after_capture(self, client: FlaskClient, mock_sdr_hardware):
        from radiomoni import sdr_lock
        response = client.post('/capture', json={'frequency': 100e6, 'duration': 1})
        wait_for_capture(client, response.get_json()['capture_id'])
        assert sdr_lock.current_holder() is None

    def test_failed_capture_reports_error(self, client: FlaskClient, mock_sdr_hardware, monkeypatch):
        from radiomoni.sdr_hardware import HackRFCapture

        def boom(self, *a, **k):
            raise RuntimeError('hackrf_transfer failed: USB error')

        monkeypatch.setattr(HackRFCapture, 'capture_audio', boom)
        response = client.post('/capture', json={'frequency': 100e6, 'duration': 1})
        result = wait_for_capture(client, response.get_json()['capture_id'])
        assert result['status'] == 'failed'
        assert 'USB error' in result['error']

    def test_status_unknown_id(self, client: FlaskClient):
        assert client.get('/capture-status/00000000-0000-0000-0000-000000000000').status_code == 404
        assert client.get('/capture-status/..%2F..%2Fetc').status_code in (400, 404)

    def test_disk_full_is_rejected(self, client: FlaskClient, mock_sdr_hardware, monkeypatch):
        from radiomoni import config
        monkeypatch.setattr(config, 'MIN_FREE_DISK_MB', 10**12)
        response = client.post('/capture', json={'frequency': 100e6, 'duration': 1})
        assert response.status_code == 400
        assert 'disk space' in response.get_json()['error']


class TestTranscribe:
    def test_requires_audio_file(self, client: FlaskClient):
        assert client.post('/transcribe', json={}).status_code == 400

    def test_missing_file(self, client: FlaskClient):
        assert client.post('/transcribe', json={'audio_file': 'nope.wav'}).status_code == 404

    @pytest.mark.parametrize('path', ['../../etc/passwd', '/etc/passwd', 'sub/../../x.wav'])
    def test_path_traversal_blocked(self, client: FlaskClient, path):
        assert client.post('/transcribe', json={'audio_file': path}).status_code == 403

    def test_transcribe_file(self, client: FlaskClient, sample_audio_file):
        response = client.post('/transcribe', json={'audio_file': os.path.basename(sample_audio_file),
                                                    'language': 'en', 'beam_size': 2})
        assert response.status_code == 200
        assert response.get_json()['result']['simulation_mode'] is True

    def test_symlink_escape_blocked(self, client: FlaskClient, temp_recording_dir):
        link = os.path.join(temp_recording_dir, 'escape.wav')
        if not os.path.lexists(link):
            os.symlink('/etc/hostname', link)
        try:
            assert client.post('/transcribe', json={'audio_file': 'escape.wav'}).status_code == 403
        finally:
            os.remove(link)


class TestDecodeFileEndpoints:
    @pytest.mark.parametrize('endpoint', ['/aprs/decode', '/pocsag/decode'])
    def test_path_traversal_blocked(self, client: FlaskClient, endpoint):
        response = client.post(endpoint, json={'audio_file': '../../../etc/passwd'})
        assert response.status_code == 403

    @pytest.mark.parametrize('endpoint', ['/aprs/decode', '/pocsag/decode'])
    def test_missing_file(self, client: FlaskClient, endpoint):
        assert client.post(endpoint, json={'audio_file': 'missing.wav'}).status_code == 404

    @pytest.mark.parametrize('endpoint,key', [('/aprs/decode', 'packets'), ('/pocsag/decode', 'messages')])
    def test_decode_tone_file(self, client: FlaskClient, sample_audio_file, endpoint, key):
        response = client.post(endpoint, json={'audio_file': os.path.basename(sample_audio_file)})
        assert response.status_code == 200
        assert response.get_json()['count'] == len(response.get_json()[key])


class TestRecordings:
    def test_list_empty_or_files(self, client: FlaskClient):
        response = client.get('/recordings')
        assert response.status_code == 200
        assert 'stats' in response.get_json()

    def test_list_contains_names_only(self, client: FlaskClient, sample_audio_file):
        data = client.get('/recordings').get_json()
        names = [r['filename'] for r in data['recordings']]
        assert 'test_audio.wav' in names
        assert all('path' not in r for r in data['recordings'])
        legacy = client.get('/list-recordings').get_json()
        assert any(r['filename'] == 'test_audio.wav' for r in legacy['recordings'])

    def test_download(self, client: FlaskClient, sample_audio_file):
        response = client.get('/recordings/test_audio.wav')
        assert response.status_code == 200
        assert response.mimetype == 'audio/wav'
        assert response.data[:4] == b'RIFF'

    @pytest.mark.parametrize('name', ['..%2F..%2Fetc%2Fpasswd', '.hidden.wav', 'x.sh'])
    def test_download_rejects_bad_names(self, client: FlaskClient, name):
        assert client.get(f'/recordings/{name}').status_code in (400, 404)

    def test_delete(self, client: FlaskClient, temp_recording_dir):
        path = os.path.join(temp_recording_dir, 'delete_me.wav')
        open(path, 'wb').write(b'RIFF0000')
        assert client.delete('/recordings/delete_me.wav').status_code == 200
        assert not os.path.exists(path)
        assert client.delete('/recordings/delete_me.wav').status_code == 404

    def test_retention_cleanup(self, client: FlaskClient, temp_recording_dir, monkeypatch):
        from radiomoni import config
        path = os.path.join(temp_recording_dir, 'old.wav')
        open(path, 'wb').write(b'RIFF')
        os.utime(path, (1, 1))
        monkeypatch.setattr(config, 'RECORDING_RETENTION_DAYS', 30)
        assert client.post('/recordings/cleanup').get_json()['removed'] >= 1
        assert not os.path.exists(path)


class TestSearchAndStats:
    def test_search_empty(self, client: FlaskClient):
        response = client.get('/search?query=test&hours=48')
        assert response.status_code == 200
        assert response.get_json()['count'] == 0

    def test_search_validation(self, client: FlaskClient):
        assert client.get('/search?limit=999999').status_code == 400
        assert client.get('/search?hours=abc').status_code == 400

    def test_search_finds_transcription(self, client: FlaskClient):
        from radiomoni.storage import get_storage
        get_storage().index_capture({'transcription': 'CQ CQ de HB9XYZ', 'frequency': 145500000, 'mode': 'voice'})
        data = client.get('/search?query=hb9xyz').get_json()
        assert data['count'] == 1
        assert client.get('/search?mode=aprs').get_json()['count'] == 0

    def test_stats(self, client: FlaskClient):
        data = client.get('/stats').get_json()
        assert data['statistics']['total_captures'] == 0

    def test_dashboard(self, client: FlaskClient):
        from radiomoni.storage import get_storage
        get_storage().index_aprs({'source_callsign': 'HB9AA', 'packet_type': 'position'})
        data = client.get('/dashboard/stats?hours=6').get_json()
        assert data['counts']['aprs'] == 1
        assert len(data['timeline']) == 6
        assert data['latest']['aprs'][0]['source_callsign'] == 'HB9AA'

    def test_frequency_stats(self, client: FlaskClient):
        from radiomoni.storage import get_storage
        for _ in range(3):
            get_storage().index_capture({'frequency': 145500000, 'modulation': 'FM'})
        freqs = client.get('/stats/frequencies').get_json()['frequencies']
        assert freqs[0]['count'] == 3

    def test_captures_invalid_id(self, client: FlaskClient):
        assert client.get('/captures/not-a-valid-id!').status_code in (400, 404)


class TestOpenApi:
    def test_document(self, client: FlaskClient):
        doc = client.get('/openapi.json').get_json()
        assert doc['openapi'].startswith('3.1')
        assert '/capture-and-transcribe' in doc['paths']
        body = doc['paths']['/stream-decode']['post']['requestBody']
        assert body['content']['application/json']['schema']['$ref'].endswith('StreamRequest')
        assert 'StreamRequest' in doc['components']['schemas']
        assert doc['paths']['/stream/aprs/start']['post']['deprecated'] is True

    def test_all_routes_documented(self, client: FlaskClient):
        from radiomoni.api_service import app
        doc = client.get('/openapi.json').get_json()
        documented = {p.replace('{', '<').replace('}', '>') for p in doc['paths']}
        missing = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint == 'static':
                continue
            path = rule.rule.replace('<int:', '<')
            if path not in documented:
                missing.append(rule.rule)
        assert missing == []
