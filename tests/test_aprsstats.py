"""aprs-stats in the stack: RF feed, sync into the storage, reception (rf / internet), endpoints."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from radiomoni import config
from radiomoni.aprs_parse import parse_line
from radiomoni.aprsstats import feed, sync
from radiomoni.aprsstats.client import AprsStatsClient, AprsStatsError

TOKEN = 'aprsstats-test-token-0123'
OLD = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data, self.reason = status, data, 'x'
        self.text = json.dumps(data)

    def json(self):
        return self._data


class FakeAprsStats:
    """Just enough of aprs-stats' API; records the calls."""

    def __init__(self):
        self.calls = []
        self.packets = []
        self.positions = []
        self.trips = []
        self.places = []
        self.ingested = []

    def get(self, url, params=None, headers=None, timeout=None):
        assert headers == {'Authorization': f'Bearer {TOKEN}'}
        path = url.split('/api/', 1)[1]
        self.calls.append(('GET', path, params))
        if path in ('feed/packets', 'feed/positions'):
            items = [x for x in (self.packets if path == 'feed/packets' else self.positions)
                     if x['id'] > params['after_id']][:params['limit']]
            return FakeResponse(200, {'items': items, 'next': items[-1]['id'] if items else params['after_id'],
                                      'pending': False})
        if path == 'stats/trips':
            return FakeResponse(200, self.trips)
        if path == 'stats/places':
            return FakeResponse(200, self.places)
        if path == 'stats/summary':
            return FakeResponse(200, {'km': 12.5, 'points': 30, 'devices': 2, 'days': 1, 'by_source': {'rf': 4},
                                      'areas': {'gemeinden': 3, 'gemeinden_total': 2110, 'kantone': 1,
                                                'kantone_total': 26}})
        if path == 'status':
            return FakeResponse(200, {'version': '0.6.0', 'collector': {'state': 'connected'},
                                      'counts': {'positions': 30}, 'boundaries': {'state': 'ready'}})
        return FakeResponse(404, {'detail': 'no'})

    def post(self, url, json=None, headers=None, timeout=None):
        path = url.split('/api/', 1)[1]
        self.calls.append(('POST', path, json))
        self.ingested.append(json)
        return FakeResponse(200, {'stored': True, 'callsign': 'N0CALL-9', 'packet_id': 1, 'position': 'new'})


@pytest.fixture
def aprsstats(monkeypatch):
    from radiomoni.aprsstats import client as client_mod
    fake = FakeAprsStats()
    monkeypatch.setattr(config, 'APRSSTATS_URL', 'http://aprsstats-web:8000')
    monkeypatch.setattr(config, 'APRSSTATS_TOKEN', TOKEN)
    monkeypatch.setattr(config, 'APRSSTATS_FEED_RF', True)
    orig = client_mod.AprsStatsClient.__init__

    def init(self, base_url=None, token=None, timeout=15.0, session=None):
        orig(self, base_url, token, timeout, session or fake)
    monkeypatch.setattr(client_mod.AprsStatsClient, '__init__', init)
    for k in feed.stats:
        feed.stats[k] = 0
    return fake


# ------------------------------------------------------------------ RF feed
def test_tnc2_from_direwolf_line():
    assert feed.tnc2('[0.1] N0CALL-9>TWPQT0,WIDE1-1:`~-vlqC>\\`"8t}_5<0x0d>') == \
        'N0CALL-9>TWPQT0,WIDE1-1:`~-vlqC>\\`"8t}_5'
    assert feed.tnc2('[0] N0CALL>APRS::N0OTHER  :hi<0x1c>') == 'N0CALL>APRS::N0OTHER  :hi\x1c'
    assert feed.tnc2('garbage') is None and feed.tnc2('') is None


def test_rf_packets_go_to_aprsstats_with_their_uuid(aprsstats):
    from radiomoni.storage.base import get_storage
    packet = parse_line('[0] N0CALL-9>APRS,WIDE1-1:!4703.50N/00818.00E>mobil')
    packet['timestamp'] = OLD
    uid = get_storage().index_aprs(packet)
    feed.drain()
    assert aprsstats.ingested == [{'raw': 'N0CALL-9>APRS,WIDE1-1:!4703.50N/00818.00E>mobil',
                                   'received_at': OLD, 'ext_ref': uid}]
    stored = get_storage().search_aprs(hours=2)['hits'][0]
    assert stored['reception'] == 'rf' and stored['reception_source'] == 'rf'
    assert feed.stats['sent'] == 1 and feed.stats['kept'] == 1


def test_no_feed_when_off_or_internet(aprsstats, monkeypatch):
    from radiomoni.storage.base import get_storage
    get_storage().index_aprs({**parse_line('[0] N0CALL>APRS:>status'), 'reception': 'internet'})
    monkeypatch.setattr(config, 'APRSSTATS_FEED_RF', False)
    get_storage().index_aprs(parse_line('[0] N0CALL>APRS:>status'))
    feed.drain()
    assert aprsstats.ingested == []


def test_client_allow_list(aprsstats):
    c = AprsStatsClient()
    for path in ('stations/1', 'beacons', 'import', 'places/1'):
        with pytest.raises(AprsStatsError, match='not allowed'):
            c.post(path, {})
    with pytest.raises(AprsStatsError, match='not allowed'):
        c.get('export.csv')


# ------------------------------------------------------------------ sync
def _packet(pid, source, raw, **kw):
    return {'id': pid, 'received_at': OLD, 'source': source, 'callsign': raw.split('>')[0], 'raw': raw,
            'path': [], 'digis': kw.get('digis', []), 'qconstruct': kw.get('q'), 'igate': kw.get('igate'),
            'format': 'uncompressed', 'ext_ref': kw.get('ext_ref'), 'also_rf': kw.get('also_rf', False),
            'gemeinde': kw.get('gemeinde'), 'bfs_nr': kw.get('bfs'), 'kanton': kw.get('kanton'),
            'country': 'CH' if kw.get('gemeinde') else None}


def test_sync_internet_packets_imports_and_rf_update(aprsstats):
    from radiomoni.storage.base import get_storage
    storage = get_storage()
    rf = parse_line('[0] N0CALL-9>APRS,WIDE1-1:!4703.50N/00818.00E>mobil')
    rf['timestamp'] = OLD
    rf_uuid = storage.index_aprs(rf)
    aprsstats.packets = [
        _packet(1, 'rf', 'N0CALL-9>APRS,WIDE1-1:!4703.50N/00818.00E>mobil', ext_ref=rf_uuid,
                gemeinde='Luzern', bfs=1061, kanton='LU'),
        _packet(2, 'aprs_is', 'N0CALL-9>APRS,WIDE1-1,qAR,N0GATE-10:!4703.50N/00818.00E>mobil',
                igate='N0GATE-10', q='qAR', also_rf=True, gemeinde='Luzern', bfs=1061, kanton='LU'),
        _packet(3, 'beacon', 'N0HOME-10>APRS:!4705.00N/00820.00E-Heim'),
    ]
    aprsstats.positions = [{'id': 7, 'callsign': 'N0CALL-7', 'ts': OLD, 'lat': 46.95, 'lon': 7.45,
                            'speed_kmh': 4.0, 'course': 90, 'altitude_m': 540, 'comment': 'Bern', 'symbol': '/[',
                            'source': 'import', 'gemeinde': 'Bern', 'bfs_nr': 351, 'kanton': 'BE', 'country': 'CH'}]
    result = sync.Syncer().run_once(force=True)
    assert result['packets'] == {'internet': 2, 'rf_updated': 1, 'rf_missing': 0} and result['imports'] == 1

    hits = {h['uuid']: h for h in storage.search_aprs(hours=2, limit=50)['hits']}
    assert hits[rf_uuid]['reception'] == 'rf' and hits[rf_uuid]['gemeinde'] == 'Luzern' and hits[rf_uuid]['kanton'] == 'LU'
    net = hits['aprsstats-pkt-2']
    assert net['reception'] == 'internet' and net['reception_source'] == 'aprs_is' and net['also_rf'] is True
    assert net['igate'] == 'N0GATE-10' and net['packet_type'] == 'position' and net['maidenhead'].startswith('JN47')
    assert hits['aprsstats-pkt-3']['reception_source'] == 'beacon'
    imp = hits['aprsstats-pos-7']
    assert imp['reception_source'] == 'import' and imp['symbol'] == 'Jogger' and imp['gemeinde'] == 'Bern'
    assert imp['message_text'].startswith('Jogger · 46.9500 N 7.4500 E')

    assert len(storage.search_aprs(hours=2, reception='internet')['hits']) == 3
    assert len(storage.search_aprs(hours=2, reception='rf')['hits']) == 1
    # the cursor moved on: nothing twice
    again = sync.Syncer().run_once()
    assert again['packets'] == {'internet': 0, 'rf_updated': 0, 'rf_missing': 0} and again['imports'] == 0


def test_rf_document_not_yet_stored_is_retried(aprsstats):
    recent = datetime.now(timezone.utc).isoformat()
    aprsstats.packets = [{**_packet(1, 'rf', 'N0CALL-9>APRS:>x', ext_ref='not-there'), 'received_at': recent},
                         _packet(2, 'aprs_is', 'N0CALL-9>APRS,qAR,N0GATE:>y')]
    assert sync.Syncer().sync_packets() == {'internet': 0, 'rf_updated': 0, 'rf_missing': 0}
    from radiomoni.redis_client import get_redis
    assert int(get_redis().get(sync.CURSOR_PACKETS) or 0) == 0
    aprsstats.packets[0]['received_at'] = OLD          # given up after 10 min
    assert sync.Syncer().sync_packets() == {'internet': 1, 'rf_updated': 0, 'rf_missing': 1}


def test_trips_and_places(aprsstats):
    from radiomoni.storage.base import get_storage
    trip = {'callsign': 'N0CALL-9', 'start': OLD, 'end': OLD, 'km': 12.3, 'points': 40, 'max_speed': 80,
            'seconds': 1800, 'start_lat': 47.05, 'start_lon': 8.3, 'end_lat': 47.1, 'end_lon': 8.4,
            'from': 'Zuhause', 'to': 'Luzern (LU)', 'start_gemeinde': 'Kriens', 'start_kanton': 'LU',
            'end_gemeinde': 'Luzern', 'end_kanton': 'LU'}
    aprsstats.trips = [trip]
    place = {'lat': 47.05, 'lon': 8.3, 'points': 50, 'hours': 12.5, 'days': 3, 'first': OLD, 'last': OLD,
             'callsigns': ['N0CALL-9'], 'name': 'Zuhause', 'gemeinde': 'Kriens', 'kanton': 'LU'}
    aprsstats.places = [place, {**place, 'lat': 46.0, 'name': None, 'gemeinde': 'Lugano', 'kanton': 'TI'}]
    s = sync.Syncer()
    s.sync_trips()
    s.sync_trips()                                      # same id: replaced, not doubled
    trip_calls = [params for m, path, params in aprsstats.calls if path == 'stats/trips']
    assert trip_calls[0] == {} and 'from' in trip_calls[1]     # first run: all trips, then the last 7 days
    trips = get_storage().search_events('aprstrips', hours=48)['hits']
    assert len(trips) == 1 and trips[0]['avg_speed'] == 24.6 and trips[0]['start_position'] == {'lat': 47.05, 'lon': 8.3}
    assert s.sync_places() == 2
    aprsstats.places = [place]
    s.sync_places()
    places = get_storage().search_events('aprsplaces', hours=1)['hits']
    assert [p['name'] for p in places] == ['Zuhause'] and places[0]['own_name'] is True


# ------------------------------------------------------------------ endpoints, backfill
def test_endpoints(client, aprsstats, monkeypatch):
    st = client.get('/aprsstats/status').get_json()
    assert st['reachable'] and st['version'] == '0.6.0' and st['collector']['state'] == 'connected'
    summ = client.get('/aprsstats/summary').get_json()
    assert summ['today']['km'] == 12.5 and summ['week']['by_source'] == {'rf': 4} and summ['all']['gemeinden'] == 3
    aprsstats.trips = [{'callsign': 'N0CALL-9', 'start': OLD, 'end': OLD, 'km': 5, 'seconds': 600,
                        'from': 'A', 'to': 'A'}]
    trips = client.get('/aprsstats/trips?days=3').get_json()['trips']
    assert trips[0]['round_trip'] is True and trips[0]['avg_speed'] == 30.0
    assert client.get('/aprsstats/link').get_json()['port'] == 8092
    monkeypatch.setattr(config, 'APRSSTATS_URL', '')
    assert client.get('/aprsstats/status').get_json()['enabled'] is False
    assert client.get('/aprsstats/summary').status_code == 503


def test_aprs_search_and_map_by_reception(client):
    from radiomoni.storage.base import get_storage
    storage = get_storage()
    storage.index_aprs(parse_line('[0] N0RF>APRS:!4703.50N/00818.00E>funk'))
    storage.index_aprs({**parse_line('N0NET>APRS,qAR,N0GATE:!4704.50N/00818.00E>netz'), 'reception': 'internet',
                        'reception_source': 'aprs_is'})
    legacy = parse_line('[0] N0OLD>APRS:!4705.50N/00818.00E>alt')        # stored before 5.8.0: no reception
    storage._insert('aprs', legacy)
    def calls(q):
        return sorted(h['source_callsign'] for h in client.get(f'/aprs/search?hours=1{q}').get_json()['results'])
    assert calls('&reception=rf') == ['N0OLD', 'N0RF'] and calls('&reception=internet') == ['N0NET']
    assert client.get('/aprs/search?reception=radio').status_code == 400
    props = {f['properties']['callsign']: f['properties'] for f in client.get('/aprs/map?hours=1').get_json()['features']}
    assert props['N0NET']['reception'] == 'internet' and props['N0OLD']['reception'] == 'rf'
    counts = client.get('/aprsstats/counts?days=1').get_json()
    assert counts['rf'] == 2 and counts['internet'] == 1


def test_backfill_sets_reception(monkeypatch):
    import sys

    from radiomoni import aprs_reparse
    from radiomoni.storage.base import get_storage
    storage = get_storage()
    storage._insert('aprs', parse_line('[0] N0OLD>APRS:>alt'))
    storage.index_aprs({**parse_line('N0NET>APRS:>netz'), 'reception': 'internet'})
    monkeypatch.setattr(sys, 'argv', ['aprs_reparse', '--set-reception'])
    aprs_reparse.main()
    hits = {h['source_callsign']: h for h in storage.search_aprs(hours=1)['hits']}
    assert hits['N0OLD']['reception'] == 'rf' and hits['N0NET']['reception'] == 'internet'
