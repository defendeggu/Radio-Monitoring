"""Jetvision AirSquitter as network ADS-B source: parsing aircraftlist.json, poller, receiver filter, alerts.

The entries follow the device's real list (fields and values as delivered), with made-up flights and
registrations.
"""

import json
import time

import pytest
import requests

from radiomoni import airsquitter, config

NOW = int(time.time())
ADSB = {"uti": NOW, "ns": 300000000, "hex": "44046e", "fli": "TST17", "src": "A", "ava": "AM", "lat": 46.02308,
        "lon": 8.23302, "alt": 27575, "gda": "A", "spd": 449, "trk": 291, "vrt": 2304, "tmp": -41, "wsp": 79,
        "wdi": 200, "cat": "A3", "org": "LSZH", "dst": "", "opr": None, "typ": "GLEX", "reg": "OE-TST",
        "dis": 118.5, "dbm": -74, "cou": "Ausr", "squ": "1000", "tru": 292, "lla": 0, "alr": 0, "spi": 0,
        "altg": 27900}
MLAT = {"uti": NOW, "ns": 300000000, "hex": "45B86F", "fli": None, "src": "M", "ava": "M", "lat": 47.75989,
        "lon": 10.18973, "alt": 29000, "gda": "A", "spd": 337, "trk": 255, "vrt": -1433, "tmp": None, "wsp": None,
        "wdi": None, "cat": None, "org": None, "dst": None, "opr": "TST", "typ": "J328", "reg": "OY-TST",
        "dis": 160.0, "dbm": -75, "cou": "Denm", "squ": None, "tru": 37, "lla": 13, "alr": 0, "spi": 0}
FLARM = {"uti": NOW, "ns": 0, "hex": "3E1234", "fli": "D-TEST", "src": "F", "ava": "MF", "lat": 47.1, "lon": 8.3,
         "alt": 4500, "gda": "A", "spd": 60, "trk": 90, "vrt": 200, "reg": "D-TEST", "typ": "DG80", "dis": 12.0,
         "dbm": -60, "squ": None, "lla": 2, "alr": 0, "spi": 0}
STALE = {**ADSB, "hex": "4B1111", "fli": "OLD1", "lla": 300}
TISB = {**ADSB, "hex": "4B2222", "fli": None, "gda": "a"}
EMERGENCY = {**ADSB, "hex": "4B7700", "fli": "SOS77", "squ": "7700", "alr": 1}


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, data):
        self.data, self.fail, self.urls = data, False, []

    def get(self, url, timeout=None):
        self.urls.append(url)
        if self.fail:
            raise requests.ConnectionError('no route to host')
        return FakeResponse(self.data)


def test_parse_sources_and_fields():
    by_icao = {a['icao']: a for a in airsquitter.parse_aircraftlist([ADSB, MLAT, FLARM, TISB, {"x": 1}],
                                                                    receiver='airsquitter')}
    assert set(by_icao) == {'44046E', '45B86F', '3E1234', '4B2222'}
    a = by_icao['44046E']
    assert a['position_source'] == 'adsb' and a['available_sources'] == 'adsb,mlat'
    assert a['flight'] == 'TST17' and a['registration'] == 'OE-TST' and a['aircraft_type'] == 'GLEX'
    assert a['altitude_ft'] == 27575 and a['gnss_altitude_ft'] == 27900 and a['ground_speed_kt'] == 449
    assert a['origin'] == 'LSZH' and 'destination' not in a and 'operator' not in a     # empty and null dropped
    assert a['rssi'] == -74 and a['distance_km'] == 118.5 and a['receiver'] == 'airsquitter'
    assert a['timestamp'].startswith(time.strftime('%Y-%m-%dT', time.gmtime(NOW)))
    assert 'alert_flag' not in a and 'spi' not in a
    m = by_icao['45B86F']
    assert m['position_source'] == 'mlat' and 'flight' not in m and m['operator'] == 'TST'
    assert by_icao['3E1234']['position_source'] == 'flarm' and by_icao['3E1234']['available_sources'] == 'mlat,flarm'
    assert by_icao['4B2222']['position_source'] == 'tisb'
    assert airsquitter.parse_aircraftlist({'aircraft': [ADSB]})[0]['icao'] == '44046E'
    assert airsquitter.parse_aircraftlist(None) == []


@pytest.fixture
def device(monkeypatch):
    monkeypatch.setattr(config, 'AIRSQUITTER_URL', 'http://airsquitter.test')
    monkeypatch.setattr(config, 'AIRSQUITTER_NAME', 'airsquitter')
    monkeypatch.setattr(config, 'AIRSQUITTER_STORE_SECONDS', 60)
    return FakeHttp([ADSB, MLAT, FLARM, STALE])


def test_poll_stores_publishes_and_throttles(device, monkeypatch):
    from radiomoni.storage.base import get_storage
    published = []
    monkeypatch.setattr(airsquitter.events, 'publish', lambda t, d: published.append((t, d)))
    poller = airsquitter.Poller(http=device)
    status = poller.poll_once()
    assert device.urls == ['http://airsquitter.test/aircraftlist.json']
    assert status['ok'] and status['aircraft'] == 4 and status['stored'] == 3          # the stale one is not stored
    assert status['by_source'] == {'adsb': 2, 'mlat': 1, 'flarm': 1}
    assert published[0][0] == 'adsb_snapshot' and published[0][1]['receiver'] == 'airsquitter'
    assert len(published[0][1]['aircraft']) == 4
    assert poller.poll_once()['stored'] == 0                                           # within 60 s: not again
    docs = get_storage().search_events('adsb', hours=1)['hits']
    assert len(docs) == 3 and {d['receiver'] for d in docs} == {'airsquitter'}
    assert {d['position_source'] for d in docs} == {'adsb', 'mlat', 'flarm'}
    saved = json.loads(airsquitter.get_redis().get(airsquitter.STATUS_KEY))
    assert saved['with_position'] == 4


def test_unreachable_device_is_reported(device):
    device.fail = True
    status = airsquitter.Poller(http=device).poll_once()
    assert status['ok'] is False and 'no route' in status['error'] and status['failures'] == 1
    assert airsquitter.status()['ok'] is False and airsquitter.status()['enabled'] is True


def test_alert_on_emergency_squawk_and_registration(client, device):
    from radiomoni import alerts
    for rule in ({'name': '7700', 'source': 'adsb', 'field': 'squawk', 'match_type': 'equals', 'pattern': '7700'},
                 {'name': 'Reg', 'source': 'adsb', 'field': 'icao', 'match_type': 'equals', 'pattern': 'OY-TST'}):
        assert client.post('/alerts/rules', json=rule).status_code in (200, 201)
    alerts._invalidate()
    device.data = [EMERGENCY, MLAT]
    airsquitter.Poller(http=device).poll_once()
    names = {a['rule_name'] for a in client.get('/alerts/recent').get_json()['alerts']}
    assert names == {'7700', 'Reg'}
    doc = next(d for d in __import__('radiomoni.storage.base', fromlist=['x']).get_storage()
               .search_events('adsb', hours=1)['hits'] if d['icao'] == '4B7700')
    assert doc['alert_flag'] is True


def test_receiver_filter_and_status_endpoint(client, device):
    from radiomoni.storage.base import get_storage
    airsquitter.Poller(http=device).poll_once()
    get_storage().index_event('adsb', {'icao': 'ABCDEF', 'flight': 'OWN1', 'latitude': 47.0, 'longitude': 8.0})
    get_storage().index_event('adsb', {'icao': 'ABC123', 'receiver': 'radiomoni', 'latitude': 47.1, 'longitude': 8.1})

    def icaos(q):
        return sorted(d['icao'] for d in client.get(f'/decoders/adsb/latest?hours=1{q}').get_json()['results'])
    assert icaos('&receiver=radiomoni') == ['ABC123', 'ABCDEF']            # without the field: own SDR
    assert icaos('&receiver=airsquitter') == ['3E1234', '44046E', '45B86F']
    assert len(icaos('')) == 5
    found = client.get('/decoders/adsb/search?hours=1&receiver=airsquitter').get_json()['results']
    assert {d['receiver'] for d in found} == {'airsquitter'}
    own = client.get('/decoders/adsb/search?hours=1&receiver=radiomoni').get_json()['results']
    assert {d['icao'] for d in own} == {'ABCDEF', 'ABC123'}
    st = client.get('/decoders/airsquitter/status').get_json()
    assert st['enabled'] and st['ok'] and st['by_source']['mlat'] == 1
    assert client.get('/decoders/adsb/latest?receiver=Bad Name').status_code == 400


def test_own_readsb_aircraft_are_marked():
    from radiomoni.decoders.external import parse_readsb_aircraft
    ac = parse_readsb_aircraft({'aircraft': [{'hex': 'abc123', 'lat': 47.0, 'lon': 8.0, 'mlat': ['lat', 'lon']},
                                             {'hex': 'abc124', 'tisb': ['flight']}, {'hex': 'abc125'}]})
    assert [(a['receiver'], a['position_source']) for a in ac] == [('radiomoni', 'mlat'), ('radiomoni', 'tisb'),
                                                                   ('radiomoni', 'adsb')]
