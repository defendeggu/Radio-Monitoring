"""
Tracks for the Kibana maps: the positions of one aircraft (ADS-B), ship (AIS) or APRS station
joined into lines, in radio-tracks-<day> (geo_shape field `track`).

Kibana's own track layer needs the geo_line aggregation, which the Basic licence does not have;
so RadioMoni builds the lines itself.

- One document per object and segment. A segment ends after a gap (ADS-B 10 min, AIS and APRS
  30 min) and at midnight UTC, so a segment lies in one daily index.
- Fixed id from kind, object and first point: a growing segment replaces its document.
- Positions that would mean an impossible speed (bad decode, MLAT outlier) are left out.
- Every minute (one API process, Redis leader lock) the objects with new positions are rebuilt for
  their day; documents of that object and day that are no longer a segment are removed.
- `python -m radiomoni.tracks --days N` rebuilds the last N days (backfill).
"""

import argparse
import hashlib
import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from radiomoni import config
from radiomoni.integrations.leader import LeaderLock

logger = logging.getLogger(__name__)

INDEX = 'radio-tracks'
MAX_POINTS = 5000            # per segment
DIRTY_MARGIN = 5 * 60        # seconds before the last run that count as new (late documents)


@dataclass(frozen=True)
class Kind:
    name: str
    index: str               # source pattern
    entity: str              # field that names the object
    max_gap: int             # seconds without position that end a segment
    max_kmh: float           # faster than this between two points: the second one is dropped
    fields: tuple[str, ...]  # copied from the points (last value) to the track
    exclude: Optional[str] = None   # documents with this field are not part of a track


KINDS = {
    'adsb': Kind('adsb', 'radio-adsb-*', 'icao', 10 * 60, 1500.0,
                 ('flight', 'registration', 'aircraft_type', 'operator', 'origin', 'destination', 'receiver',
                  'position_source')),
    'ais': Kind('ais', 'radio-ais-*', 'mmsi', 30 * 60, 120.0, ('shipname', 'callsign', 'destination')),
    'aprs': Kind('aprs', 'radio-aprs-*', 'source_callsign', 30 * 60, 1000.0,
                 ('symbol', 'symbol_id', 'reception'), exclude='object_name'),
}


def _time(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lon, lat) points."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def point_of(doc: dict[str, Any]) -> Optional[tuple[float, float]]:
    pos = doc.get('position')
    lat = lon = None
    if isinstance(pos, dict):
        lat, lon = pos.get('lat'), pos.get('lon')
    if lat is None or lon is None:
        lat, lon = doc.get('latitude'), doc.get('longitude')
    try:
        lat_f, lon_f = float(lat), float(lon)     # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180) or (lat_f == 0 and lon_f == 0):
        return None
    return (round(lon_f, 6), round(lat_f, 6))


def segments(kind: Kind, docs: Iterable[dict[str, Any]]) -> list[list[tuple[datetime, tuple[float, float], dict[str, Any]]]]:
    """Points of one object -> segments (lists of (time, (lon, lat), doc)), sorted by time."""
    points = []
    for doc in docs:
        p = point_of(doc)
        ts = doc.get('@timestamp') or doc.get('timestamp')
        if p is None or not ts:
            continue
        try:
            points.append((_time(ts), p, doc))
        except ValueError:
            continue
    points.sort(key=lambda x: x[0])
    out: list[list[tuple[datetime, tuple[float, float], dict[str, Any]]]] = []
    current: list[tuple[datetime, tuple[float, float], dict[str, Any]]] = []
    for t, p, doc in points:
        if current:
            last_t, last_p, _ = current[-1]
            gap = (t - last_t).total_seconds()
            if gap > kind.max_gap or t.date() != last_t.date():
                out.append(current)
                current = []
            else:
                dist = km(last_p, p)
                if dist > 2 and dist / max(gap, 1) * 3600 > kind.max_kmh:
                    continue        # outlier
        current.append((t, p, doc))
    if current:
        out.append(current)
    return out


def track_id(kind: str, entity: str, start: datetime) -> str:
    return hashlib.sha256(f'{kind}|{entity}|{start.isoformat()}'.encode()).hexdigest()[:32]


def track_document(kind: Kind, entity: str, seg: list[tuple[datetime, tuple[float, float], dict[str, Any]]]
                   ) -> Optional[dict[str, Any]]:
    """A segment -> track document, None when it has fewer than two different positions."""
    coords: list[tuple[float, float]] = []
    for _, p, _ in seg:
        if not coords or coords[-1] != p:
            coords.append(p)
    if len(coords) < 2:
        return None
    if len(coords) > MAX_POINTS:
        step = math.ceil(len(coords) / MAX_POINTS)
        coords = coords[::step] + ([coords[-1]] if (len(coords) - 1) % step else [])
    start, end = seg[0][0], seg[-1][0]
    doc: dict[str, Any] = {
        'uuid': track_id(kind.name, entity, start),
        '@timestamp': end.isoformat(), 'start': start.isoformat(), 'end': end.isoformat(),
        'kind': kind.name, 'entity': entity, kind.entity: seg[-1][2].get(kind.entity, entity),
        'points': len(seg),
        'distance_km': round(sum(km(a, b) for a, b in zip(coords, coords[1:], strict=False)), 2),
        'duration_min': round((end - start).total_seconds() / 60, 1),
        'track': {'type': 'LineString', 'coordinates': [list(c) for c in coords]},
    }
    for field in kind.fields:
        for _, _, d in reversed(seg):
            if d.get(field) not in (None, ''):
                doc[field] = d[field]
                break
    if kind.name == 'adsb':
        alts = [d['altitude_ft'] for _, _, d in seg if isinstance(d.get('altitude_ft'), (int, float))]
        if alts:
            doc['max_altitude_ft'] = max(alts)
    label = {'adsb': doc.get('flight') or doc.get('registration'), 'ais': doc.get('shipname')}.get(kind.name)
    doc['label'] = str(label or entity).strip()
    return doc


class Builder:
    def __init__(self, es: Any):
        self.es = es

    def _points(self, kind: Kind, day: date, entities: Optional[list[str]]) -> dict[str, list[dict[str, Any]]]:
        from elasticsearch.helpers import scan
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        must: list[dict[str, Any]] = [
            {'range': {'@timestamp': {'gte': start.isoformat(), 'lt': (start + timedelta(days=1)).isoformat()}}},
            {'exists': {'field': 'position'}}]
        if entities is not None:
            must.append({'terms': {kind.entity: entities}})
        query: dict[str, Any] = {'bool': {'must': must}}
        if kind.exclude:
            query['bool']['must_not'] = [{'exists': {'field': kind.exclude}}]
        fields = ['@timestamp', 'position', 'latitude', 'longitude', kind.entity, *kind.fields, kind.exclude or '',
                  'altitude_ft']
        grouped: dict[str, list[dict[str, Any]]] = {}
        for hit in scan(self.es, index=kind.index, query={'query': query, '_source': [f for f in fields if f]},
                        size=5000, ignore_unavailable=True, allow_no_indices=True):
            src = hit['_source']
            entity = src.get(kind.entity)
            if entity not in (None, ''):
                grouped.setdefault(str(entity), []).append(src)
        return grouped

    def rebuild(self, kind_name: str, day: date, entities: Optional[list[str]] = None) -> int:
        """Rebuild the tracks of one kind and day (all objects, or the given ones). Returns the number written."""
        from elasticsearch.helpers import bulk
        kind = KINDS[kind_name]
        grouped = self._points(kind, day, entities)
        index = f'{INDEX}-{day:%Y.%m.%d}'
        docs = [doc for entity, items in grouped.items() for seg in segments(kind, items)
                if (doc := track_document(kind, entity, seg))]
        if docs:
            bulk(self.es, [{'_op_type': 'index', '_index': index, '_id': d['uuid'], '_source': d} for d in docs],
                 raise_on_error=True, refresh='wait_for')
        # segments that merged or vanished
        stale: dict[str, Any] = {'bool': {'filter': [{'term': {'kind': kind.name}}],
                                          'must_not': [{'ids': {'values': [d['uuid'] for d in docs]}}]}}
        if entities is not None:
            stale['bool']['filter'].append({'terms': {'entity': [str(e) for e in entities]}})
        if self.es.indices.exists(index=index):
            self.es.delete_by_query(index=index, query=stale, conflicts='proceed', refresh=True)
        return len(docs)

    def dirty(self, kind_name: str, since: datetime) -> dict[date, list[str]]:
        """Objects with positions since `since`, per day."""
        kind = KINDS[kind_name]
        out: dict[date, list[str]] = {}
        now = datetime.now(timezone.utc)
        day = since.date()
        while day <= now.date():
            start = max(since, datetime(day.year, day.month, day.day, tzinfo=timezone.utc))
            end = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1)
            result = self.es.search(
                index=kind.index, size=0, ignore_unavailable=True, allow_no_indices=True,
                query={'bool': {'filter': [{'range': {'@timestamp': {'gte': start.isoformat(),
                                                                    'lt': end.isoformat()}}},
                                           {'exists': {'field': 'position'}}]}},
                aggs={'e': {'terms': {'field': kind.entity, 'size': 10000}}})
            names = [str(b['key']) for b in result.get('aggregations', {}).get('e', {}).get('buckets', [])]
            if names:
                out[day] = names
            day += timedelta(days=1)
        return out

    def update(self, since: datetime) -> dict[str, int]:
        written: dict[str, int] = {}
        for name in KINDS:
            n = 0
            for day, entities in self.dirty(name, since).items():
                for i in range(0, len(entities), 500):
                    n += self.rebuild(name, day, entities[i:i + 500])
            written[name] = n
        return written


def _es() -> Optional[Any]:
    if config.STORAGE_BACKEND != 'elasticsearch':
        return None
    from radiomoni.storage.base import get_storage
    return getattr(get_storage(), 'es_client', None)


status: dict[str, Any] = {'last_run': None, 'written': {}, 'error': None}
_started = False


def start() -> None:
    """Background job, in the process that holds the leader lock."""
    global _started
    if _started or not config.TRACKS_ENABLED or config.STORAGE_BACKEND != 'elasticsearch':
        return
    _started = True
    lock = LeaderLock('tracks:leader', ttl=max(120, config.TRACKS_SECONDS * 3))

    def loop() -> None:
        last = datetime.now(timezone.utc) - timedelta(hours=1)
        while True:
            try:
                if lock.hold():
                    es = _es()
                    if es is not None:
                        now = datetime.now(timezone.utc)
                        status['written'] = Builder(es).update(last - timedelta(seconds=DIRTY_MARGIN))
                        status.update(last_run=now.isoformat(), error=None)
                        last = now
            except Exception as e:      # never let the thread die
                status['error'] = str(e)
                logger.warning(f"tracks: {e}", exc_info=True)
            time.sleep(config.TRACKS_SECONDS)

    threading.Thread(target=loop, name='tracks', daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description='Rebuild the map tracks (radio-tracks-*) of the last days.')
    parser.add_argument('--days', type=int, default=7, help='how many days back, today included (default 7)')
    parser.add_argument('--kind', choices=sorted(KINDS), action='append', help='only this kind (repeatable)')
    args = parser.parse_args()
    es = _es()
    if es is None:
        raise SystemExit('Tracks need STORAGE_BACKEND=elasticsearch')
    builder = Builder(es)
    today = datetime.now(timezone.utc).date()
    for offset in range(args.days - 1, -1, -1):
        day = today - timedelta(days=offset)
        for name in args.kind or KINDS:
            n = builder.rebuild(name, day)
            if n:
                print(f'{day} {name}: {n} tracks')


if __name__ == '__main__':
    main()
