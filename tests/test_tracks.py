"""Map tracks (radiomoni/tracks.py): segments, outliers, documents, rebuild."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from radiomoni import tracks

T0 = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)


def point(minutes: float, lat: float, lon: float, **extra: Any) -> dict[str, Any]:
    return {'@timestamp': (T0 + timedelta(minutes=minutes)).isoformat(), 'position': {'lat': lat, 'lon': lon},
            **extra}


def test_segments_split_on_gap_and_sorted():
    kind = tracks.KINDS['adsb']
    docs = [point(10, 47.02, 8.0), point(0, 47.0, 8.0), point(1, 47.01, 8.0),
            point(30, 47.1, 8.1), point(31, 47.11, 8.1)]
    segs = tracks.segments(kind, docs)
    assert [len(s) for s in segs] == [3, 2]
    assert segs[0][0][0] == T0


def test_segments_split_at_midnight():
    kind = tracks.KINDS['aprs']
    late = datetime(2026, 11, 26, 23, 55, tzinfo=timezone.utc)
    docs = [{'@timestamp': (late + timedelta(minutes=m)).isoformat(), 'latitude': 47 + m / 1000, 'longitude': 8}
            for m in (0, 4, 8, 12)]
    assert [len(s) for s in tracks.segments(kind, docs)] == [2, 2]


def test_outlier_dropped():
    kind = tracks.KINDS['adsb']
    # 1 min later 300 km away (18 000 km/h): a bad position
    docs = [point(0, 47.0, 8.0), point(1, 49.7, 8.0), point(2, 47.03, 8.0)]
    seg = tracks.segments(kind, docs)[0]
    assert [p for _, p, _ in seg] == [(8.0, 47.0), (8.0, 47.03)]


def test_invalid_positions_ignored():
    kind = tracks.KINDS['ais']
    docs = [point(0, 0, 0), {'@timestamp': T0.isoformat()}, point(1, 95, 8), point(2, 'x', 8)]
    assert tracks.segments(kind, docs) == []


def test_track_document_adsb():
    kind = tracks.KINDS['adsb']
    docs = [point(0, 47.0, 8.0, icao='4b1234', altitude_ft=20000, receiver='airsquitter'),
            point(1, 47.0, 8.0, icao='4b1234'),       # same position: one coordinate
            point(2, 47.1, 8.0, icao='4b1234', flight='SWR12', altitude_ft=24000, registration='HB-ABC')]
    doc = tracks.track_document(kind, '4b1234', tracks.segments(kind, docs)[0])
    assert doc is not None
    assert doc['track'] == {'type': 'LineString', 'coordinates': [[8.0, 47.0], [8.0, 47.1]]}
    assert doc['points'] == 3 and doc['label'] == 'SWR12' and doc['icao'] == '4b1234'
    assert doc['receiver'] == 'airsquitter' and doc['registration'] == 'HB-ABC'
    assert doc['max_altitude_ft'] == 24000
    assert doc['distance_km'] == pytest.approx(11.1, abs=0.1)
    assert doc['start'] == T0.isoformat() and doc['@timestamp'] == doc['end']
    assert doc['uuid'] == tracks.track_id('adsb', '4b1234', T0)


def test_track_document_needs_two_positions():
    kind = tracks.KINDS['aprs']
    docs = [point(0, 47.0, 8.0), point(5, 47.0, 8.0)]
    assert tracks.track_document(kind, 'TEST-9', tracks.segments(kind, docs)[0]) is None


def test_track_document_thins_long_tracks(monkeypatch):
    monkeypatch.setattr(tracks, 'MAX_POINTS', 10)
    kind = tracks.KINDS['ais']
    docs = [point(m, 47 + m / 1000, 8) for m in range(25)]
    doc = tracks.track_document(kind, '269000000', tracks.segments(kind, docs)[0])
    assert doc is not None
    coords = doc['track']['coordinates']
    assert len(coords) <= 11 and coords[0] == [8.0, 47.0] and coords[-1] == [8.0, 47.024]


class FakeIndices:
    def exists(self, index: str) -> bool:
        return True


class FakeES:
    def __init__(self) -> None:
        self.indices = FakeIndices()
        self.deleted: list[dict[str, Any]] = []

    def delete_by_query(self, index: str, query: dict[str, Any], **_: Any) -> None:
        self.deleted.append({'index': index, 'query': query})


def test_rebuild_writes_and_removes_stale(monkeypatch):
    import elasticsearch.helpers as helpers
    hits = [{'_source': point(m, 47 + m / 100, 8, source_callsign='TEST-9', reception='internet')}
            for m in range(3)]
    hits.append({'_source': point(0, 46, 7, source_callsign='TEST-7')})     # one position only: no track
    written: list[dict[str, Any]] = []
    monkeypatch.setattr(helpers, 'scan', lambda es, **kw: iter(hits))
    monkeypatch.setattr(helpers, 'bulk', lambda es, actions, **kw: written.extend(actions) or (len(actions), []))
    es = FakeES()
    n = tracks.Builder(es).rebuild('aprs', date(2026, 11, 26), ['TEST-9', 'TEST-7'])
    assert n == 1
    assert written[0]['_index'] == 'radio-tracks-2026.11.26'
    assert written[0]['_source']['reception'] == 'internet'
    stale = es.deleted[0]['query']['bool']
    assert stale['must_not'] == [{'ids': {'values': [written[0]['_id']]}}]
    assert {'terms': {'entity': ['TEST-9', 'TEST-7']}} in stale['filter']


def test_start_needs_elasticsearch(monkeypatch):
    monkeypatch.setattr(tracks.config, 'STORAGE_BACKEND', 'sqlite')
    monkeypatch.setattr(tracks, '_started', False)
    tracks.start()
    assert tracks._started is False
