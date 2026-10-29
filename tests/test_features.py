"""Tests for bookmarks, alerts, schedules, export, live events and SDR control."""

import io
import json
import threading
import time
import zipfile

import pytest
from flask.testing import FlaskClient

from radiomoni import alerts
from radiomoni import events
from radiomoni import sdr_lock


# ============================================================================ bookmarks
class TestBookmarks:
    def test_defaults_when_empty(self, client: FlaskClient):
        data = client.get('/bookmarks').get_json()
        assert data['bookmarks'] == []
        assert any(b['mode'] == 'aprs' for b in data['defaults'])

    def test_crud(self, client: FlaskClient):
        created = client.post('/bookmarks', json={'name': 'Local repeater', 'frequency': 438_925_000,
                                                  'modulation': 'FM', 'mode': 'vox', 'tags': ['ham', ' ']})
        assert created.status_code == 201
        item = created.get_json()
        assert item['tags'] == ['ham']
        listed = client.get('/bookmarks').get_json()
        assert listed['defaults'] == []
        assert listed['bookmarks'][0]['id'] == item['id']

        updated = client.put(f"/bookmarks/{item['id']}", json={**{k: item[k] for k in
                                                                   ('frequency', 'modulation', 'mode')},
                                                                'name': 'Renamed'})
        assert updated.get_json()['name'] == 'Renamed'
        assert client.delete(f"/bookmarks/{item['id']}").status_code == 200
        assert client.delete(f"/bookmarks/{item['id']}").status_code == 404

    def test_validation(self, client: FlaskClient):
        assert client.post('/bookmarks', json={'name': '', 'frequency': 1e6}).status_code == 400
        assert client.post('/bookmarks', json={'name': 'x', 'frequency': -5}).status_code == 400
        assert client.put('/bookmarks/not-a-uuid', json={'name': 'x', 'frequency': 1e6}).status_code == 400

    def test_import_export(self, client: FlaskClient):
        payload = {'bookmarks': [{'name': 'A', 'frequency': 145_500_000}, {'name': 'B', 'frequency': 144_800_000,
                                                                           'mode': 'aprs'}]}
        assert client.post('/bookmarks/import', json=payload).get_json()['imported'] == 2
        exported = client.get('/bookmarks/export')
        assert 'attachment' in exported.headers['Content-Disposition']
        assert len(exported.get_json()['bookmarks']) == 2


# ============================================================================ alerts
class TestAlertMatching:
    def rule(self, **kw):
        base = {'id': 'r1', 'name': 'r', 'enabled': True, 'source': 'any', 'field': 'any',
                'match_type': 'contains', 'pattern': 'HB9', 'case_sensitive': False, 'channels': [],
                'cooldown_seconds': 0}
        return {**base, **kw}

    def test_contains_any_field(self):
        assert alerts.matches(self.rule(), 'aprs', {'source_callsign': 'hb9xyz-7'})
        assert not alerts.matches(self.rule(), 'aprs', {'source_callsign': 'DL1ABC'})

    def test_source_filter(self):
        assert not alerts.matches(self.rule(source='pocsag'), 'aprs', {'source_callsign': 'HB9XYZ'})

    def test_equals_and_case(self):
        rule = self.rule(match_type='equals', field='address', pattern='1234567')
        assert alerts.matches(rule, 'pocsag', {'address': 1234567})
        assert not alerts.matches(self.rule(case_sensitive=True, pattern='hb9'), 'aprs', {'source_callsign': 'HB9X'})

    def test_regex(self):
        rule = self.rule(match_type='regex', field='text', pattern=r'\bfire\b')
        assert alerts.matches(rule, 'pocsag', {'message_text': 'FIRE alarm station 3'})
        assert not alerts.matches(rule, 'pocsag', {'message_text': 'firewall'})

    def test_evaluate_fires_once_per_cooldown(self, client: FlaskClient):
        rule = alerts.save_rule({**self.rule(cooldown_seconds=60), 'pattern': 'HB9'})
        doc = {'source_callsign': 'HB9ABC', 'message_text': 'hello'}
        assert len(alerts.evaluate('aprs', doc)) == 1
        assert alerts.evaluate('aprs', doc) == []
        recent = client.get('/alerts/recent').get_json()['alerts']
        assert recent[0]['rule_id'] == rule['id']
        from radiomoni.storage import get_storage
        assert get_storage().search_events('alerts', hours=1)['total'] == 1

    def test_disabled_rule(self):
        alerts.save_rule({**self.rule(), 'enabled': False})
        assert alerts.evaluate('aprs', {'source_callsign': 'HB9ABC'}) == []

    def test_evaluate_never_raises(self, monkeypatch):
        monkeypatch.setattr(alerts, '_active_rules', lambda: 1 / 0)
        assert alerts.evaluate('aprs', {}) == []


class TestAlertApi:
    def test_rule_crud(self, client: FlaskClient):
        created = client.post('/alerts/rules', json={'name': 'Fire', 'source': 'pocsag', 'field': 'text',
                                                     'match_type': 'regex', 'pattern': 'FIRE|BRAND',
                                                     'channels': ['ntfy']})
        assert created.status_code == 201
        rule_id = created.get_json()['id']
        data = client.get('/alerts/rules').get_json()
        assert data['rules'][0]['name'] == 'Fire'
        assert data['channels']['ntfy'] is False
        assert client.put(f'/alerts/rules/{rule_id}', json={'name': 'Fire2', 'pattern': 'x'}).status_code == 200
        assert client.delete(f'/alerts/rules/{rule_id}').status_code == 200

    def test_invalid_regex_rejected(self, client: FlaskClient):
        response = client.post('/alerts/rules', json={'name': 'bad', 'match_type': 'regex', 'pattern': '(['})
        assert response.status_code == 400

    def test_notification_channels(self, client: FlaskClient, monkeypatch):
        from radiomoni import config
        sent = []

        class Resp:
            def raise_for_status(self):
                pass

        monkeypatch.setattr(config, 'NTFY_URL', 'https://ntfy.example/topic')
        monkeypatch.setattr(alerts.requests, 'post', lambda url, **kw: sent.append(url) or Resp())
        results = client.post('/alerts/test', json={'channels': ['ntfy', 'telegram']}).get_json()['results']
        assert results == {'ntfy': 'sent', 'telegram': 'not configured'}
        assert sent == ['https://ntfy.example/topic']


# ============================================================================ schedules
class TestSchedules:
    BODY = {'name': 'Morning APRS', 'cron': '0 7 * * *', 'action': 'stream',
            'params': {'mode': 'aprs', 'frequency': 144_800_000, 'duration': 3600}}

    def test_crud(self, client: FlaskClient):
        created = client.post('/schedules', json=self.BODY)
        assert created.status_code == 201
        sid = created.get_json()['id']
        assert client.get('/schedules').get_json()['schedules'][0]['name'] == 'Morning APRS'
        assert client.put(f'/schedules/{sid}', json={**self.BODY, 'enabled': False}).status_code == 200
        assert client.delete(f'/schedules/{sid}').status_code == 200

    @pytest.mark.parametrize('patch', [
        {'cron': 'every morning'},
        {'action': 'reboot'},
        {'params': {'mode': 'aprs'}},                       # frequency missing
        {'params': {'mode': 'aprs', 'frequency': 144800000, 'duration': 10 ** 9}},
    ])
    def test_validation(self, client: FlaskClient, patch):
        assert client.post('/schedules', json={**self.BODY, **patch}).status_code == 400

    def test_run_now(self, client: FlaskClient, monkeypatch):
        from radiomoni import actions
        calls = []
        monkeypatch.setattr(actions, 'start_stream', lambda req: calls.append(req) or {'session_id': 's1'})
        sid = client.post('/schedules', json=self.BODY).get_json()['id']
        result = client.post(f'/schedules/{sid}/run').get_json()
        assert result['status'] == 'started'
        assert calls[0].frequency == 144_800_000
        assert client.get('/schedules').get_json()['schedules'][0]['last_status'] == 'started'

    def test_run_skipped_when_busy(self, client: FlaskClient):
        sid = client.post('/schedules', json=self.BODY).get_json()['id']
        sdr_lock.acquire('someone', 'capture')
        assert client.post(f'/schedules/{sid}/run').get_json()['status'] == 'skipped'

    def test_fire_dedupe(self, monkeypatch):
        from radiomoni import actions
        from radiomoni import scheduler
        monkeypatch.setattr(actions, 'start_stream', lambda req: {'session_id': 's'})
        item = scheduler.save_schedule(dict(self.BODY))
        assert scheduler.run_schedule(item['id'], fire_key='202601010700', wait=0)['status'] == 'started'
        assert scheduler.run_schedule(item['id'], fire_key='202601010700', wait=0)['status'] == 'duplicate'

    def test_scheduler_registers_jobs(self, monkeypatch):
        from radiomoni import config
        from radiomoni import scheduler
        monkeypatch.setattr(config, 'SCHEDULER_ENABLED', True)
        try:
            scheduler.start()
            item = scheduler.save_schedule(dict(self.BODY))
            assert scheduler.get_schedule(item['id'])['next_run'] is not None
        finally:
            scheduler.shutdown()


# ============================================================================ export
class TestExport:
    @pytest.fixture
    def data(self):
        from radiomoni.storage import get_storage
        s = get_storage()
        s.index_aprs({'source_callsign': 'HB9AA', 'latitude': 47.1, 'longitude': 8.5, 'message_text': 'hi <b>'})
        s.index_aprs({'source_callsign': 'HB9AA', 'latitude': 47.0, 'longitude': 8.4, 'timestamp': '2020-01-01T00:00:00+00:00'})
        s.index_event('ais', {'mmsi': '269000000', 'latitude': 46.5, 'longitude': 6.6, 'shipname': 'LEMAN'})
        return s

    def test_csv(self, client: FlaskClient, data):
        response = client.get('/export/aprs.csv?hours=24')
        assert response.mimetype == 'text/csv'
        lines = response.get_data(as_text=True).strip().splitlines()
        assert lines[0].startswith('@timestamp,source_callsign')
        assert len(lines) == 2

    def test_unknown_kind(self, client: FlaskClient):
        assert client.get('/export/passwords.csv').status_code == 404

    def test_geojson_latest_per_station(self, client: FlaskClient, data):
        features = client.get('/export/aprs.geojson?hours=8760').get_json()['features']
        assert len(features) == 1
        assert features[0]['geometry']['coordinates'] == [8.5, 47.1]
        ais = client.get('/export/ais.geojson').get_json()['features']
        assert ais[0]['properties']['shipname'] == 'LEMAN'

    def test_kml_escapes(self, client: FlaskClient, data):
        body = client.get('/export/aprs.kml').get_data(as_text=True)
        assert '<name>HB9AA</name>' in body
        assert 'hi &lt;b&gt;' in body

    def test_capture_zip(self, client: FlaskClient, sample_audio_file):
        from radiomoni.storage import get_storage
        cid = get_storage().index_capture({'audio_file': 'test_audio.wav', 'transcription': 'hello',
                                           'json_file': '../../etc/passwd'})
        response = client.get(f'/export/capture/{cid}.zip')
        assert response.status_code == 200
        names = zipfile.ZipFile(io.BytesIO(response.data)).namelist()
        assert set(names) == {'metadata.json', 'transcript.txt', 'test_audio.wav'}
        assert client.get('/export/capture/unknown.zip').status_code == 404


# ============================================================================ live events
class TestEvents:
    def test_sse_stream_delivers_events(self):
        stream = events.sse_stream({'aprs'}, heartbeat=0.2)
        assert next(stream).startswith('retry:')
        received = []

        def consume():
            for frame in stream:
                if frame.startswith('event:'):
                    received.append(frame)
                    return

        t = threading.Thread(target=consume)
        t.start()
        time.sleep(0.3)
        events.publish('pocsag', {'x': 1})   # filtered out
        events.publish('aprs', {'source_callsign': 'HB9X'})
        t.join(timeout=5)
        assert received and 'HB9X' in received[0]
        assert received[0].startswith('event: aprs')
        stream.close()

    def test_events_endpoint_headers(self, client: FlaskClient):
        response = client.get('/events?types=aprs', buffered=False)
        assert response.mimetype == 'text/event-stream'
        assert response.headers['X-Accel-Buffering'] == 'no'
        assert next(response.response).startswith(b'retry:')
        response.close()

    def test_control_channel(self):
        got = []
        events.start_control_listener(got.append)
        time.sleep(0.3)
        events.send_control('stop', session_id='abc')
        for _ in range(50):
            if got:
                break
            time.sleep(0.05)
        assert got[0] == {'command': 'stop', 'session_id': 'abc'}


# ============================================================================ SDR control
class TestSdrEndpoints:
    def test_detect_without_hardware(self, client: FlaskClient, monkeypatch):
        import radiomoni.blueprints.sdr
        from radiomoni.sdr_hardware import SDRType
        monkeypatch.setattr(radiomoni.blueprints.sdr, 'detect_sdr', lambda *a, **k: SDRType.UNKNOWN)
        data = client.get('/sdr/detect').get_json()
        assert data == {**data, 'detected': False, 'type': 'unknown'}

    def test_detect_with_hardware(self, client: FlaskClient, mock_sdr_hardware):
        data = client.get('/sdr/detect').get_json()
        assert data['detected'] is True
        assert data['type'] == 'hackrf'

    def test_status_and_force_stop(self, client: FlaskClient):
        sdr_lock.acquire('stream:1', 'aprs', {'frequency': 144800000})
        status = client.get('/sdr/status').get_json()
        assert status['busy'] is True
        assert status['holder']['details']['frequency'] == 144800000
        result = client.post('/sdr/force-stop').get_json()
        assert result['status'] == 'success'
        assert client.get('/sdr/status').get_json()['busy'] is False

    def test_decoders_listed(self, client: FlaskClient):
        decoders = {d['decoder']: d for d in client.get('/decoders').get_json()['decoders']}
        assert set(decoders) == {'adsb', 'ais', 'ism'}

    def test_decoder_search_and_latest(self, client: FlaskClient):
        from radiomoni.storage import get_storage
        s = get_storage()
        s.index_event('ism', {'sensor_id': 'Acurite:1:A', 'model': 'Acurite', 'temperature_C': 21.5})
        s.index_event('ism', {'sensor_id': 'Acurite:1:A', 'model': 'Acurite', 'temperature_C': 22.0})
        s.index_event('ism', {'sensor_id': 'Oregon:2:', 'model': 'Oregon', 'temperature_C': 5.0})
        assert client.get('/decoders/ism/search').get_json()['count'] == 3
        assert client.get('/decoders/ism/search?model=Oregon').get_json()['count'] == 1
        latest = client.get('/decoders/ism/latest').get_json()['results']
        assert len(latest) == 2
        assert client.get('/decoders/fax/search').status_code == 404

    def test_external_decoder_requires_rtlsdr(self, client: FlaskClient):
        response = client.post('/decoders/start', json={'decoder': 'adsb', 'duration': 60})
        assert response.status_code in (400, 409, 503)

    def test_vox_validation(self, client: FlaskClient):
        assert client.post('/vox/start', json={'frequency': 145500000, 'squelch_db': 99}).status_code == 400
        assert client.post('/vox/start', json={'frequency': 145500000, 'modulation': 'USB'}).status_code == 400


def test_json_events_are_serialisable():
    events.publish('aprs', {'when': __import__('datetime').datetime.now()})  # must not raise
    json.dumps({'ok': True})
