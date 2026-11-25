"""
aprs-stats -> RadioMoni storage (Elasticsearch / SQLite), so its data shows up in the UI and in Kibana.

Every run (one API process at a time, Redis leader lock):
- packets (GET /api/feed/packets, cursor in Redis)
    internet (aprs_is, beacon): a new APRS document `aprsstats-pkt-<id>`, parsed like the RF ones,
        reception=internet, with iGate, digipeaters, municipality and canton, `also_rf` when the same
        packet was heard over the air too
    rf: the document RadioMoni already stored (ext_ref = its uuid) gets municipality and canton
- positions without a packet (aprs.fi import): APRS documents `aprsstats-pos-<id>`, reception=internet
- every 15 min the trips of the last 7 days -> radio-aprstrips-* (fixed id per device and start)
- every 60 min the places -> radio-aprsplaces-current (replaced)
"""

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from radiomoni import config, events
from radiomoni.aprs_parse import parse_line, summary, symbol_id, symbol_name
from radiomoni.aprsstats import RECEPTION_INTERNET
from radiomoni.aprsstats.client import AprsStatsClient, AprsStatsError, enabled
from radiomoni.integrations.leader import LeaderLock
from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)

CURSOR_PACKETS = 'aprsstats:cursor:packets'
CURSOR_POSITIONS = 'aprsstats:cursor:positions'
STATUS_KEY = 'aprsstats:sync'
TRIPS_EVERY = 15 * 60
PLACES_EVERY = 60 * 60
TRIP_DAYS = 7
BATCH = 500
RF_WAIT = timedelta(minutes=10)      # an RF document that is not in the storage yet (Logstash) is retried this long


def _ts(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _parse_time(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def area_fields(item: dict[str, Any]) -> dict[str, Any]:
    """Municipality (Gemeinde), BFS number and canton of a feed item (only what is known)."""
    out = {'gemeinde': item.get('gemeinde'), 'bfs_nr': item.get('bfs_nr'), 'kanton': item.get('kanton'),
           'country': item.get('country')}
    return {k: v for k, v in out.items() if v is not None}


def packet_document(item: dict[str, Any]) -> dict[str, Any]:
    """A packet from aprs-stats (APRS-IS or own beacon) -> an APRS document like the ones heard over the air."""
    raw = str(item.get('raw') or '')
    doc = parse_line(raw) or {'source_callsign': item.get('callsign'), 'raw_packet': raw,
                              'packet_type': 'unknown', 'message_text': raw}
    when = _ts(item['received_at'])
    doc.update({
        'uuid': f"aprsstats-pkt-{item['id']}",
        'timestamp': when,
        '@timestamp': when,
        'reception': RECEPTION_INTERNET,
        'reception_source': item.get('source'),
        'igate': item.get('igate'),
        'digis': item.get('digis') or [],
        'qconstruct': item.get('qconstruct'),
        'also_rf': bool(item.get('also_rf')),
        'aprsstats_id': item['id'],
        **area_fields(item),
    })
    return doc


def import_document(item: dict[str, Any]) -> dict[str, Any]:
    """A position imported from aprs.fi (no raw packet) -> an APRS document."""
    symbol = str(item.get('symbol') or '')
    table, code = (symbol[0], symbol[1]) if len(symbol) == 2 else (None, None)
    when = _ts(item['ts'])
    doc: dict[str, Any] = {
        'uuid': f"aprsstats-pos-{item['id']}",
        'timestamp': when,
        '@timestamp': when,
        'source_callsign': item.get('callsign'),
        'packet_type': 'position',
        'format': 'import',
        'latitude': item.get('lat'),
        'longitude': item.get('lon'),
        'speed': item.get('speed_kmh'),
        'course': item.get('course'),
        'altitude': item.get('altitude_m'),
        'comment': item.get('comment') or '',
        'symbol_table': table,
        'symbol_code': code,
        'symbol': symbol_name(table, code),
        'symbol_id': symbol_id(table, code),
        'reception': RECEPTION_INTERNET,
        'reception_source': 'import',
        'aprsstats_id': item['id'],
        **area_fields(item),
    }
    doc['message_text'] = summary(doc)
    return doc


def trip_document(t: dict[str, Any]) -> dict[str, Any]:
    key = f"{t['callsign']}|{t['start']}"
    doc: dict[str, Any] = {
        'uuid': 'trip-' + hashlib.sha256(key.encode()).hexdigest()[:20],
        '@timestamp': _ts(t['start']),
        'callsign': t['callsign'],
        'start': _ts(t['start']),
        'end': _ts(t['end']) if t.get('end') else None,
        'km': t.get('km'),
        'seconds': t.get('seconds'),
        'points': t.get('points'),
        'max_speed': t.get('max_speed'),
        'from': t.get('from'),
        'to': t.get('to'),
        'round_trip': bool(t.get('from')) and t.get('from') == t.get('to'),
        'start_gemeinde': t.get('start_gemeinde'), 'start_kanton': t.get('start_kanton'),
        'end_gemeinde': t.get('end_gemeinde'), 'end_kanton': t.get('end_kanton'),
    }
    if t.get('seconds') and t.get('km'):
        doc['avg_speed'] = round(float(t['km']) / (float(t['seconds']) / 3600.0), 1)
    for end in ('start', 'end'):
        lat, lon = t.get(f'{end}_lat'), t.get(f'{end}_lon')
        if lat is not None and lon is not None:
            doc[f'{end}_position'] = {'lat': lat, 'lon': lon}
    return doc


def place_document(p: dict[str, Any], snapshot: str) -> dict[str, Any]:
    key = f"{round(float(p['lat']), 3)}|{round(float(p['lon']), 3)}"
    return {
        'uuid': 'place-' + hashlib.sha256(key.encode()).hexdigest()[:20],
        '@timestamp': snapshot,
        'name': p.get('name') or p.get('gemeinde'),
        'own_name': bool(p.get('name')),
        'gemeinde': p.get('gemeinde'),
        'kanton': p.get('kanton'),
        'position': {'lat': p['lat'], 'lon': p['lon']},
        'hours': p.get('hours'),
        'days': p.get('days'),
        'points': p.get('points'),
        'first': _ts(p['first']) if p.get('first') else None,
        'last': _ts(p['last']) if p.get('last') else None,
        'callsigns': p.get('callsigns') or [],
    }


class Syncer:
    def __init__(self, client: Optional[AprsStatsClient] = None):
        self.client = client or AprsStatsClient()
        self.last_trips = 0.0
        self.last_places = 0.0

    def _cursor(self, key: str) -> int:
        return int(get_redis().get(key) or 0)

    def sync_packets(self) -> dict[str, int]:
        from radiomoni.storage.base import get_storage
        storage = get_storage()
        counts = {'internet': 0, 'rf_updated': 0, 'rf_missing': 0}
        after = self._cursor(CURSOR_PACKETS)
        while True:
            feed = self.client.get('feed/packets', {'after_id': after, 'limit': BATCH})
            items = feed.get('items') or []
            for item in items:
                if item.get('source') == 'rf':
                    if item.get('ext_ref'):
                        ok = storage.update_aprs(item['ext_ref'], _ts(item['received_at']),
                                                 {**area_fields(item), 'aprsstats_id': item['id'],
                                                  'reception_source': 'rf'})
                        if ok:
                            counts['rf_updated'] += 1
                        elif datetime.now(timezone.utc) - _parse_time(item['received_at']) < RF_WAIT:
                            get_redis().set(CURSOR_PACKETS, after)
                            return counts           # not in the storage yet (Logstash): next run
                        else:
                            counts['rf_missing'] += 1
                else:
                    doc = packet_document(item)
                    storage.index_aprs(doc)
                    events.publish('aprs', doc)
                    counts['internet'] += 1
                after = int(item['id'])
            get_redis().set(CURSOR_PACKETS, after)
            if len(items) < BATCH or feed.get('pending'):
                return counts

    def sync_positions(self) -> int:
        from radiomoni.storage.base import get_storage
        storage = get_storage()
        n = 0
        after = self._cursor(CURSOR_POSITIONS)
        while True:
            feed = self.client.get('feed/positions', {'after_id': after, 'limit': BATCH})
            items = feed.get('items') or []
            for item in items:
                storage.index_aprs(import_document(item))
                after = int(item['id'])
                n += 1
            get_redis().set(CURSOR_POSITIONS, after)
            if len(items) < BATCH or feed.get('pending'):
                return n

    def sync_trips(self) -> int:
        from radiomoni.storage.base import get_storage
        since = (datetime.now(timezone.utc) - timedelta(days=TRIP_DAYS)).isoformat()
        trips = self.client.get('stats/trips', {'from': since}) or []
        return get_storage().put_docs('aprstrips', [trip_document(t) for t in trips])

    def sync_places(self) -> int:
        from radiomoni.storage.base import get_storage
        places = self.client.get('stats/places') or []
        snapshot = datetime.now(timezone.utc).isoformat()
        docs = {d['uuid']: d for d in (place_document(p, snapshot) for p in places)}   # same cell once
        return get_storage().put_docs('aprsplaces', list(docs.values()), replace=True)

    def run_once(self, force: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {'time': datetime.now(timezone.utc).isoformat()}
        result['packets'] = self.sync_packets()
        result['imports'] = self.sync_positions()
        now = time.time()
        if force or now - self.last_trips >= TRIPS_EVERY:
            result['trips'] = self.sync_trips()
            self.last_trips = now
        if force or now - self.last_places >= PLACES_EVERY:
            result['places'] = self.sync_places()
            self.last_places = now
        return result


def status() -> dict[str, Any]:
    import json
    raw = get_redis().get(STATUS_KEY)
    return json.loads(raw) if raw else {}


def _save_status(data: dict[str, Any]) -> None:
    import json
    get_redis().set(STATUS_KEY, json.dumps(data, default=str), ex=7 * 86400)


_started = False


def start() -> None:
    """Background sync, in the process that holds the leader lock."""
    global _started
    if _started or not enabled() or not config.APRSSTATS_SYNC:
        return
    _started = True
    lock = LeaderLock('aprsstats:sync:leader', ttl=max(120, config.APRSSTATS_SYNC_SECONDS * 3))

    def loop() -> None:
        syncer = Syncer()
        while True:
            try:
                if lock.hold():
                    result = syncer.run_once()
                    _save_status({**result, 'ok': True, 'error': None})
            except AprsStatsError as e:
                _save_status({'time': datetime.now(timezone.utc).isoformat(), 'ok': False, 'error': str(e)})
                logger.debug(f"aprs-stats sync: {e}")
            except Exception as e:      # never let the thread die
                _save_status({'time': datetime.now(timezone.utc).isoformat(), 'ok': False, 'error': str(e)})
                logger.warning(f"aprs-stats sync failed: {e}", exc_info=True)
            time.sleep(config.APRSSTATS_SYNC_SECONDS)

    threading.Thread(target=loop, name='aprsstats-sync', daemon=True).start()
