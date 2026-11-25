"""OnAir (on-air.dev) integration: client, modes, message mapping, session with the SDR lock, endpoints.

The OnAir lines are real ones from onair-server 4.6.0 (HackRF on 131.650 MHz and 144.800 MHz),
plus examples from OnAir's event catalogue.
"""

import json
import os
import time

import pytest

from radiomoni import config
from radiomoni.onair import mapping, modes
from radiomoni.onair.client import OnAirClient, OnAirError, find_device_index

ACARS = ('{"fields":{"downlink":true,"flight":"MU0218","label":"11","msg_num":"M92","tail":"B-5961",'
         '"text":"POS\\nCAS 251,LAT N 47.174,LON E  8.008,ALT 34216"},"freq_hz":131725000,"ident":"MU0218",'
         '"mode":"ACARS","source":"OnAir","time":1795602455.31,"type":"acars.message"}')
APRS = ('{"fields":{"from":"HB9AF-10","info":";145.600-L*111112z4703.84N/00820.29Er T71.9","lat":47.064,'
        '"lon":8.33816666667,"path":"WIDE1-1","summary":"Object 145.600-L 47.0640N 8.3382E [/r]  T71.9",'
        '"to":"APMI06","type":"Object"},"freq_hz":0,"ident":"","mode":"APRS","source":"OnAir",'
        '"time":1795602744.76,"type":"aprs.packet"}')
SONDE = ('{"fields":{"serial":"V1234567","type":"RS41","lat":46.81,"lon":6.94,"alt_m":12000,"vspeed_ms":5},'
         '"freq_hz":402500000,"ident":"V1234567","mode":"Sonde","source":"OnAir","time":1795602800,'
         '"type":"sonde.update"}')
CALL = ('{"fields":{"session_id":"1766010347528192001","key":"TG 228/slot1","title":"DMR TG 228, 12 s",'
        '"kind":"call","verdict":"encrypted","duration_s":12},"freq_hz":438212500,"ident":"TG 228",'
        '"mode":"DMR","source":"OnAir","time":1795602900,"type":"session.call"}')
STATE = '{"fields":{"detail":"receiver started","state":"started"},"freq_hz":0,"ident":"","mode":"","type":"receiver.state"}'

MODES = [{'family': 18, 'id': 'acars', 'name': 'ACARS', 'sub': None, 'defaultMhz': 131.5},
         {'family': 15, 'id': 'sonde', 'name': 'Radiosonde', 'sub': None, 'defaultMhz': 403},
         {'family': 11, 'id': 'dmr', 'name': 'DMR', 'sub': None, 'defaultMhz': 446.10625},
         {'family': 48, 'id': 'tetra', 'name': 'TETRA', 'sub': None, 'defaultMhz': 392.5},
         {'family': 7, 'id': 'fm', 'name': 'FM broadcast', 'sub': None, 'defaultMhz': 100}]
DEVICES = [{'index': 0, 'name': 'HackRF One (gFromRAM)', 'kind': 'hackrf', 'serial': 'RunningFromRAM'},
           {'index': 1, 'name': 'Test signal (no radio)', 'kind': 'synthetic', 'serial': ''}]


# ------------------------------------------------------------------ a fake onair-server
class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data, self.reason = status, data, 'x'
        self.text = data if isinstance(data, str) else json.dumps(data)

    def json(self):
        if isinstance(self._data, str):
            raise ValueError('not json')
        return self._data


class FakeOnAir:
    """Just enough of onair-server: state, mode list, devices, start/stop; records every call."""

    def __init__(self):
        self.calls = []
        self.running = False
        self.state = {'family': 7, 'frequencyHz': 100_000_000, 'gainDb': 30}
        self.fail_start = None

    def get(self, url, headers=None, timeout=None):
        path = url.split('/api/v1', 1)[1].strip('/')
        self.calls.append(('GET', path, None))
        assert headers == {'Authorization': 'Bearer test-token-0123456789'}
        if path == 'status':
            return FakeResponse(200, {'running': self.running, 'wanted': self.running, **self.state,
                                      'sampleRateHz': 2_000_000 if self.running else 0, 'error': ''})
        if path == 'modes':
            return FakeResponse(200, MODES)
        if path == 'devices':
            return FakeResponse(200, DEVICES)
        if path == 'telemetry':
            return FakeResponse(200, {'running': self.running, 'blocksOk': 3})
        if path == 'metrics':
            return FakeResponse(200, '# TYPE onair_receiver_running gauge\nonair_receiver_running 0\n')
        if path == '':
            return FakeResponse(200, {'name': 'onair-server', 'version': '4.6.0'})
        return FakeResponse(404, {'error': 'no'})

    def post(self, url, json=None, headers=None, timeout=None):
        path = url.split('/api/v1/', 1)[1]
        self.calls.append(('POST', path, json))
        if path == 'start':
            if self.fail_start:
                return FakeResponse(400, {'error': self.fail_start})
            self.running = True
        elif path == 'stop':
            self.running = False
        elif path == 'mode':
            self.state['family'] = json['family']
        elif path == 'frequency':
            self.state['frequencyHz'] = json['hz']
        elif path == 'gain':
            self.state['gainDb'] = json['db']
        return FakeResponse(200, {'ok': True})

    def posted(self):
        return [p for m, p, _ in self.calls if m == 'POST']


@pytest.fixture
def onair(monkeypatch, tmp_path):
    """OnAir switched on, with a fake server, a fake HackRF and the data volume in tmp_path."""
    from radiomoni import devices
    from radiomoni.devices import Device
    from radiomoni.onair import client as client_mod
    from radiomoni.sdr_hardware import SDRType

    fake = FakeOnAir()
    monkeypatch.setattr(config, 'ONAIR_URL', 'http://onair:8765')
    monkeypatch.setattr(config, 'ONAIR_TOKEN', 'test-token-0123456789')
    monkeypatch.setattr(config, 'ONAIR_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(config, 'ONAIR_ALL_MODES', False)
    orig_init = client_mod.OnAirClient.__init__

    def init(self, base_url=None, token=None, timeout=8.0, session=None):
        orig_init(self, base_url, token, timeout, session or fake)
    monkeypatch.setattr(client_mod.OnAirClient, '__init__', init)
    hackrf = Device(id='hackrf:RunningFromRAM', type=SDRType.HACKRF, serial='RunningFromRAM', label='HackRF One')
    monkeypatch.setattr(devices, 'list_devices', lambda refresh=False: [hackrf])
    (tmp_path / 'events').mkdir()
    (tmp_path / 'events' / 'onair-events.jsonl').write_text(STATE + '\n')   # an old line: not read again
    return fake


def _append(tmp_path, *lines):
    with open(tmp_path / 'events' / 'onair-events.jsonl', 'a') as f:
        for line in lines:
            f.write(line + '\n')


def _wait(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


# ------------------------------------------------------------------ client
def test_client_refuses_transmit_and_unknown_paths(onair):
    c = OnAirClient()
    for path in ('tx/start', 'tx', '/tx/start', 'x/rds', 'recording/start', 'rotator/goto', 'start/../tx/start'):
        with pytest.raises(OnAirError, match='not allowed'):
            c.post(path, {'mhz': 145})
    for path in ('events', 'memories', 'scheduler', 'settings'):
        with pytest.raises(OnAirError, match='not allowed'):
            c.get(path)
    assert not onair.calls


def test_client_tune_and_errors(onair):
    c = OnAirClient()
    c.tune(18, None, 131_650_000, 40.0)
    assert onair.posted() == ['stop', 'mode', 'frequency', 'gain']
    c.tune(15, None, None, None)
    assert onair.posted()[-3:] == ['stop', 'mode', 'autogain']
    onair.fail_start = 'could not start the receiver: LIBUSB_ERROR_BUSY'
    with pytest.raises(OnAirError, match='LIBUSB_ERROR_BUSY'):
        c.start(0)
    with pytest.raises(OnAirError, match='not configured'):
        OnAirClient(base_url='').status()


def test_find_device_index():
    assert find_device_index(DEVICES, 'hackrf', 'RunningFromRAM') == 0
    assert find_device_index(DEVICES, 'hackrf') == 0
    with pytest.raises(OnAirError, match='does not see the rtlsdr'):
        find_device_index(DEVICES, 'rtlsdr')
    busy = [{'index': 0, 'name': 'HackRF (LIBUSB_ERROR_NO_DEVICE)', 'kind': 'hackrf'}]
    with pytest.raises(OnAirError):
        find_device_index(busy, 'hackrf')


# ------------------------------------------------------------------ modes
def test_modes_are_curated():
    ids = [m['id'] for m in modes.offered(MODES, all_modes=False)]
    assert ids == ['acars', 'sonde', 'dmr', 'fm']          # group order; TETRA is left out
    acars = modes.offered(MODES, all_modes=False)[0]
    assert acars['group'] == 'aviation' and acars['default_frequency'] == 131_500_000
    every = modes.offered(MODES, all_modes=True)
    assert every[-1]['id'] == 'tetra' and every[-1]['group'] == 'other'
    with pytest.raises(ValueError, match='not offered'):
        modes.find(MODES, 'tetra')


# ------------------------------------------------------------------ mapping
def test_acars_and_aprs_lines():
    doc = mapping.to_document(ACARS)
    assert doc is not None and doc['event_type'] == 'acars.message' and doc['family'] == 'acars'
    assert doc['ident'] == 'MU0218' and doc['frequency'] == 131_725_000
    assert doc['text'].startswith('MU0218 B-5961 · label 11 · POS CAS 251')
    assert doc['@timestamp'].startswith('2026-11-25T')
    doc = mapping.to_document(APRS)
    assert doc is not None and doc['latitude'] == pytest.approx(47.064) and doc['longitude'] == pytest.approx(8.3382, abs=1e-4)
    assert 'frequency' not in doc and doc['ident'] is None and doc['text'].startswith('Object 145.600-L')


def test_sonde_call_image_and_skipped_lines(monkeypatch, tmp_path):
    doc = mapping.to_document(SONDE)
    assert doc is not None and doc['altitude'] == 12000 and doc['text'] == 'RS41 V1234567 · 12000 m'
    doc = mapping.to_document(CALL)
    assert doc is not None and doc['text'] == 'encrypted · DMR TG 228, 12 s' and doc['fields']['duration_s'] == 12
    monkeypatch.setattr(config, 'ONAIR_DATA_DIR', str(tmp_path))
    image = ('{"type":"image.done","mode":"Meteor","fields":{"path":"/data/OnAir/images/m.png",'
             '"satellite":"Meteor-M2 4","detail":"channels 1 2 3"},"time":1795603000}')
    doc = mapping.to_document(image)
    assert doc is not None and doc['image_path'] == str(tmp_path / 'OnAir' / 'images' / 'm.png')
    assert doc['text'] == 'Meteor-M2 4 channels 1 2 3'
    outside = image.replace('/data/OnAir', '/data/../etc')
    assert mapping.to_document(outside)['image_path'] is None
    assert mapping.to_document(STATE) is None
    assert mapping.to_document('{"type":"insight.pager_silent","fields":{}}', store_insights=False) is None
    assert mapping.to_document('{"type":"insight.pager_silent","fields":{}}', store_insights=True) is not None
    assert mapping.to_document('not json') is None and mapping.to_document('[1,2]') is None
    nested = mapping.to_document('{"type":"lora.packet","fields":{"a":{"b":1},"lat":0,"lon":0}}')
    assert nested['fields']['a'] == '{"b": 1}' and 'latitude' not in nested


def test_jsonl_tail_follows_appends_and_rotation(tmp_path):
    from radiomoni.onair.session import JsonlTail
    path = tmp_path / 'e.jsonl'
    path.write_text('old\n')
    tail = JsonlTail(str(path))
    assert tail.read() == []
    with open(path, 'a') as f:
        f.write('one\ntw')
    assert tail.read() == ['one']
    with open(path, 'a') as f:
        f.write('o\nthree\n')
    assert tail.read() == ['two', 'three']
    with open(path, 'a') as f:
        f.write('four\n')
    os.rename(path, str(path) + '.1')          # OnAir rotates: file -> file.1, a new file starts
    path.write_text('five\n')
    assert tail.read() == ['four', 'five']
    missing = JsonlTail(str(tmp_path / 'nothing.jsonl'))
    assert missing.read() == []
    (tmp_path / 'nothing.jsonl').write_text('first\n')
    assert missing.read() == ['first']


# ------------------------------------------------------------------ session with the SDR lock
def test_session_holds_lock_stores_and_stops(client, onair, tmp_path):
    from radiomoni import sdr_lock
    r = client.post('/onair/start', json={'mode': 'acars', 'frequency': 131_650_000, 'gain': 40, 'duration': 60})
    assert r.status_code == 200, r.get_json()
    sid = r.get_json()['session_id']
    assert r.get_json()['onair_mode'] == 'acars'
    assert _wait(lambda: onair.running)
    holder = sdr_lock.current_holder('hackrf:RunningFromRAM')
    assert holder and holder['kind'] == 'onair'
    assert onair.posted()[:5] == ['stop', 'mode', 'frequency', 'gain', 'start']
    assert ('POST', 'start', {'device': 0}) in onair.calls

    _append(tmp_path, ACARS, STATE, SONDE)
    assert _wait(lambda: client.get('/onair/search?hours=8760').get_json()['count'] == 2)
    status = client.get('/onair/status').get_json()
    assert status['reachable'] and status['version'] == '4.6.0' and status['sessions'][0]['session_id'] == sid
    assert 'Kristijonas Adomaitis' in status['attribution']

    r = client.post('/onair/stop')
    assert r.get_json()['stopped'] == [sid]
    assert not onair.running and onair.posted()[-1] == 'stop'
    assert sdr_lock.current_holder('hackrf:RunningFromRAM') is None
    hits = client.get('/onair/search?hours=8760&event_type=sonde.update').get_json()['results']
    assert len(hits) == 1 and hits[0]['session_id'] == sid and hits[0]['device_id'] == 'hackrf:RunningFromRAM'


def test_session_fails_when_onair_cannot_open_the_radio(client, onair):
    from radiomoni import sdr_lock
    from radiomoni.session_store import session_manager
    onair.fail_start = 'could not start the receiver: LIBUSB_ERROR_BUSY'
    sid = client.post('/onair/start', json={'mode': 'sonde', 'duration': 60}).get_json()['session_id']
    assert _wait(lambda: session_manager.get_session(sid).status == 'failed')
    assert 'LIBUSB_ERROR_BUSY' in session_manager.get_session(sid).error
    assert _wait(lambda: sdr_lock.current_holder('hackrf:RunningFromRAM') is None)


def test_start_needs_offered_mode_free_sdr_and_setup(client, onair, monkeypatch):
    from radiomoni import sdr_lock
    assert client.post('/onair/start', json={'mode': 'tetra'}).status_code == 400
    assert client.post('/onair/start', json={'mode': 'acars', 'gain': 200}).status_code == 400
    sdr_lock.acquire('stream:other', 'aprs', {}, 'hackrf:RunningFromRAM')
    assert client.post('/onair/start', json={'mode': 'acars'}).status_code == 409
    assert not onair.running
    monkeypatch.setattr(config, 'ONAIR_URL', '')
    r = client.post('/onair/start', json={'mode': 'acars'})
    assert r.status_code == 503 and 'not set up' in r.get_json()['error']


def test_recover_stops_onair_without_lock(onair):
    from radiomoni import sdr_lock
    from radiomoni.onair.session import recover
    onair.running = True
    sdr_lock.acquire('stream:x', 'onair', {}, 'hackrf:RunningFromRAM')
    assert recover() is False and onair.running
    sdr_lock.release('stream:x', 'hackrf:RunningFromRAM')
    assert recover() is True and not onair.running
    assert recover() is False


# ------------------------------------------------------------------ endpoints, alerts
def test_status_and_modes_endpoints(client, onair, monkeypatch):
    modes_resp = client.get('/onair/modes').get_json()
    assert [m['id'] for m in modes_resp['modes']] == ['acars', 'sonde', 'dmr', 'fm']
    assert 'aviation' in modes_resp['groups']
    monkeypatch.setattr(config, 'ONAIR_URL', '')
    status = client.get('/onair/status').get_json()
    assert status['enabled'] is False and status['reachable'] is False
    assert client.get('/onair/link').status_code == 503


def test_map_and_images(client, onair, tmp_path):
    from radiomoni.storage.base import get_storage
    for line in (SONDE, SONDE.replace('"lat":46.81', '"lat":46.85'), APRS, ACARS):
        get_storage().index_event('onair', mapping.to_document(line))
    features = client.get('/onair/map?hours=8760').get_json()['features']
    points = [f for f in features if f['geometry']['type'] == 'Point']
    tracks = [f for f in features if f['geometry']['type'] == 'LineString']
    assert len(points) == 2 and len(tracks) == 1 and len(tracks[0]['geometry']['coordinates']) == 2

    img_dir = tmp_path / 'OnAir' / 'images'
    img_dir.mkdir(parents=True)
    (img_dir / 'm.png').write_bytes(b'\x89PNG\r\n\x1a\nfake')
    doc = mapping.to_document('{"type":"image.done","mode":"Meteor","fields":{"path":"/data/OnAir/images/m.png"}}')
    get_storage().index_event('onair', doc)
    r = client.get(f"/onair/images/{doc['uuid']}")
    assert r.status_code == 200 and r.mimetype == 'image/png' and r.data.startswith(b'\x89PNG')
    assert client.get('/onair/images/nope').status_code == 404
    assert client.get('/onair/images/..%2F..%2Fetc').status_code in (400, 404)


def test_alert_rule_on_event_type(client):
    from radiomoni import alerts
    r = client.post('/alerts/rules', json={'name': 'Sonde', 'source': 'onair', 'field': 'event_type',
                                            'match_type': 'equals', 'pattern': 'sonde.landed'})
    assert r.status_code in (200, 201), r.get_json()
    alerts._invalidate()
    assert alerts.evaluate('onair', mapping.to_document(SONDE)) == []
    landed = mapping.to_document(SONDE.replace('sonde.update', 'sonde.landed'))
    fired = alerts.evaluate('onair', landed)
    assert len(fired) == 1 and 'V1234567' in fired[0]['summary']
    any_rule = {'source': 'any', 'field': 'any', 'match_type': 'contains', 'pattern': 'sonde'}
    assert not alerts.matches(any_rule, 'onair', mapping.to_document(SONDE))   # the type is not searched as text


def test_metrics_passthrough(client, onair, monkeypatch):
    r = client.get('/metrics/onair')
    assert r.status_code == 200 and r.mimetype == 'text/plain' and b'onair_receiver_running 0' in r.data
    monkeypatch.setattr(config, 'ONAIR_URL', '')
    r = client.get('/metrics/onair')
    assert r.status_code == 200 and r.data == b''
