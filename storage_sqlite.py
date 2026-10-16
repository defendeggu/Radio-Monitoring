"""
SQLite storage backend for the "light" deployment profile (no ELK stack).

All documents live in one table, keyed by kind. JSON1 functions are used for
filters, which is plenty for a single station's data volume. Kibana dashboards
are not available in this mode; the web UI dashboard and exports still work.
"""

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from storage import EVENT_KINDS, StorageBackend, enrich_aprs

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    uuid      TEXT PRIMARY KEY,
    kind      TEXT NOT NULL,
    ts        REAL NOT NULL,
    frequency INTEGER,
    data      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS docs_kind_ts ON docs(kind, ts DESC);
CREATE TABLE IF NOT EXISTS repeaters (
    id   TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""

KINDS = ('captures', 'aprs', 'pocsag', 'repeater') + EVENT_KINDS


def _to_epoch(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            pass
    return time.time()


class SQLiteStorage(StorageBackend):
    name = 'sqlite'

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._local = threading.local()
        self._all: list[sqlite3.Connection] = []
        self._all_lock = threading.Lock()
        with self._conn() as conn:
            conn.executescript(SCHEMA)
        logger.info(f"SQLite storage initialized at {path}")

    def _conn(self) -> sqlite3.Connection:
        conn: Optional[sqlite3.Connection] = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            self._local.conn = conn
            with self._all_lock:
                self._all.append(conn)
        return conn

    def close(self) -> None:
        """Close the connections of all threads."""
        with self._all_lock:
            for conn in self._all:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._all.clear()
        self._local = threading.local()

    # ------------------------------------------------------------------ core
    def _insert(self, kind: str, doc: dict[str, Any], ts_field: str = 'timestamp') -> str:
        doc.setdefault('uuid', str(uuid.uuid4()))
        ts_value = doc.get('@timestamp') or doc.get(ts_field) or doc.get('created_at')
        if not ts_value:
            ts_value = datetime.now(timezone.utc).isoformat()
        doc['@timestamp'] = ts_value
        if doc.get('frequency'):
            doc['frequency_mhz'] = doc['frequency'] / 1_000_000.0
        with self._conn() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO docs(uuid, kind, ts, frequency, data) VALUES (?,?,?,?,?)',
                (doc['uuid'], kind, _to_epoch(ts_value), doc.get('frequency'), json.dumps(doc, default=str)))
        return str(doc['uuid'])

    def _select(self, kind: str, hours: Optional[int] = None, where: str = '', params: Iterable[Any] = (),
                limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        clauses = ['kind = ?']
        args: list[Any] = [kind]
        if hours is not None:
            clauses.append('ts >= ?')
            args.append(time.time() - hours * 3600)
        if where:
            clauses.append(where)
            args.extend(params)
        sql_where = ' AND '.join(clauses)
        conn = self._conn()
        # sql_where only contains fixed clauses with ? placeholders (field names are whitelisted)
        total = int(conn.execute(f'SELECT COUNT(*) FROM docs WHERE {sql_where}', args).fetchone()[0])  # noqa: S608
        rows = conn.execute(f'SELECT data FROM docs WHERE {sql_where} ORDER BY ts DESC LIMIT ? OFFSET ?',  # noqa: S608
                            [*args, limit, offset]).fetchall()
        return [json.loads(r['data']) for r in rows], total

    def _count(self, kind: str, hours: Optional[int] = None) -> int:
        return self._select(kind, hours, limit=0)[1]

    # ------------------------------------------------------------------ health
    def health_check(self) -> dict[str, Any]:
        try:
            self._conn().execute('SELECT 1').fetchone()
            return {'status': 'green', 'backend': 'sqlite'}
        except sqlite3.Error as e:
            logger.error(f"SQLite health check failed: {e}")
            return {'status': 'error', 'backend': 'sqlite'}

    def get_overall_stats(self) -> dict[str, Any]:
        return {
            'total_captures': self._count('captures'),
            'total_aprs_messages': self._count('aprs'),
            'total_pocsag_messages': self._count('pocsag'),
            'total_repeater_scans': self._count('repeater'),
            'total_adsb': self._count('adsb'),
            'total_ais': self._count('ais'),
            'total_ism': self._count('ism'),
            'cluster_health': self.health_check(),
        }

    def get_dashboard_stats(self, hours: int = 24) -> dict[str, Any]:
        counts = {kind: self._count(kind, hours) for kind in KINDS}
        since = time.time() - hours * 3600
        rows = self._conn().execute(
            "SELECT kind, CAST((ts - ?) / 3600 AS INTEGER) AS bucket, COUNT(*) AS n FROM docs "
            "WHERE ts >= ? AND kind IN ('captures','aprs','pocsag','adsb','ais','ism') GROUP BY kind, bucket",
            (since, since)).fetchall()
        buckets: dict[int, dict[str, int]] = {i: {} for i in range(hours)}
        for r in rows:
            b = min(int(r['bucket']), hours - 1)
            buckets[b][r['kind']] = buckets[b].get(r['kind'], 0) + int(r['n'])
        timeline = [{'time': datetime.fromtimestamp(since + i * 3600, timezone.utc).isoformat(), **v}
                    for i, v in sorted(buckets.items())]
        return {
            'hours': hours, 'counts': counts, 'timeline': timeline,
            'latest': {
                'aprs': self._select('aprs', hours, limit=5)[0],
                'pocsag': self._select('pocsag', hours, limit=5)[0],
                'captures': self._select('captures', hours, limit=5)[0],
            },
        }

    # ------------------------------------------------------------------ captures
    def index_capture(self, capture: dict[str, Any]) -> Optional[str]:
        return self._insert('captures', capture, 'created_at')

    def search_captures(self, query: Optional[str] = None, frequency_min: Optional[int] = None,
                        frequency_max: Optional[int] = None, modulation: Optional[str] = None,
                        language: Optional[str] = None, sdr_type: Optional[str] = None,
                        hours: int = 24, limit: int = 100, offset: int = 0,
                        mode: Optional[str] = None) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if query:
            clauses.append("LOWER(json_extract(data, '$.transcription')) LIKE ?")
            params.append(f"%{query.lower()}%")
        if frequency_min:
            clauses.append('frequency >= ?')
            params.append(frequency_min)
        if frequency_max:
            clauses.append('frequency <= ?')
            params.append(frequency_max)
        for field, value in (('modulation', modulation), ('detected_language', language),
                             ('sdr_type', sdr_type), ('mode', mode)):
            if value:
                clauses.append(f"json_extract(data, '$.{field}') = ?")
                params.append(value)
        hits, total = self._select('captures', hours, ' AND '.join(clauses), params, limit, offset)
        return {'hits': hits, 'total': total, 'limit': limit, 'offset': offset}

    def get_capture_by_id(self, capture_id: str) -> Optional[dict[str, Any]]:
        row = self._conn().execute("SELECT data FROM docs WHERE kind='captures' AND uuid=?",
                                   (capture_id,)).fetchone()
        return json.loads(row['data']) if row else None

    def get_frequency_usage(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn().execute(
            "SELECT frequency, COUNT(*) AS n, MAX(ts) AS last, GROUP_CONCAT(DISTINCT json_extract(data,'$.modulation')) AS mods "
            "FROM docs WHERE kind='captures' AND frequency IS NOT NULL GROUP BY frequency ORDER BY n DESC LIMIT ?",
            (limit,)).fetchall()
        return [{
            'frequency': r['frequency'],
            'frequency_mhz': r['frequency'] / 1_000_000.0,
            'count': r['n'],
            'modulations': [m for m in (r['mods'] or '').split(',') if m],
            'last_capture': datetime.fromtimestamp(r['last'], timezone.utc).isoformat(),
        } for r in rows]

    # ------------------------------------------------------------------ APRS
    def index_aprs(self, message: dict[str, Any]) -> Optional[str]:
        return self._insert('aprs', enrich_aprs(message))

    def search_aprs(self, callsign: Optional[str] = None, packet_type: Optional[str] = None,
                    hours: int = 24, limit: int = 100) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if callsign:
            clauses.append("UPPER(json_extract(data,'$.source_callsign')) = ?")
            params.append(callsign.upper())
        if packet_type:
            clauses.append("json_extract(data,'$.packet_type') = ?")
            params.append(packet_type)
        hits, total = self._select('aprs', hours, ' AND '.join(clauses), params, limit)
        return {'hits': hits, 'total': total}

    def get_aprs_stats(self, hours: int = 24) -> dict[str, Any]:
        docs, total = self._select('aprs', hours, limit=100_000)
        calls = Counter(d.get('source_callsign') for d in docs if d.get('source_callsign'))
        types = Counter(d.get('packet_type') or d.get('aprs_type') or 'unknown' for d in docs)
        return {
            'total_packets': total,
            'unique_callsigns': len(calls),
            'top_callsigns': [{'callsign': k, 'count': v} for k, v in calls.most_common(15)],
            'packet_types': [{'type': k, 'count': v} for k, v in types.most_common(10)],
        }

    # ------------------------------------------------------------------ POCSAG
    def index_pocsag(self, message: dict[str, Any]) -> Optional[str]:
        return self._insert('pocsag', message)

    def search_pocsag(self, address: Optional[int] = None, message_type: Optional[str] = None,
                      hours: int = 24, limit: int = 100) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if address:
            clauses.append("json_extract(data,'$.address') = ?")
            params.append(address)
        if message_type:
            clauses.append("json_extract(data,'$.message_type') = ?")
            params.append(message_type)
        hits, total = self._select('pocsag', hours, ' AND '.join(clauses), params, limit)
        return {'hits': hits, 'total': total}

    def get_pocsag_stats(self, hours: int = 24) -> dict[str, Any]:
        docs, total = self._select('pocsag', hours, limit=100_000)
        addresses = Counter(d.get('address') for d in docs if d.get('address') is not None)
        types = Counter(d.get('message_type') or 'unknown' for d in docs)
        bauds = Counter(d.get('baud_rate') for d in docs if d.get('baud_rate'))
        return {
            'total_messages': total,
            'unique_addresses': len(addresses),
            'top_addresses': [{'address': k, 'count': v} for k, v in addresses.most_common(15)],
            'message_types': [{'type': k, 'count': v} for k, v in types.most_common(10)],
            'baud_rates': [{'baud': k, 'count': v} for k, v in bauds.most_common()],
        }

    # ------------------------------------------------------------------ repeaters
    def index_repeater_activity(self, activity: dict[str, Any]) -> Optional[str]:
        return self._insert('repeater', activity, 'created_at')

    def get_repeater_activity_summary(self, hours: int = 24, band: Optional[str] = None,
                                      canton: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
        docs, _ = self._select('repeater', hours, limit=100_000)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for d in docs:
            if not d.get('carrier_detected'):
                continue
            if band and d.get('band') != band:
                continue
            if canton and (d.get('canton') or '').upper() != canton.upper():
                continue
            grouped.setdefault(d.get('repeater_callsign') or '?', []).append(d)
        result = []
        for call, items in grouped.items():
            signals = [i['average_signal_strength'] for i in items if i.get('average_signal_strength') is not None]
            result.append({
                'callsign': call,
                'avg_activity_pct': round(sum(i.get('activity_percentage') or 0 for i in items) / len(items), 2),
                'total_transmissions': int(sum(i.get('transmission_count') or 0 for i in items)),
                'avg_signal_db': round(sum(signals) / len(signals), 1) if signals else None,
                'frequency_mhz': items[0].get('frequency_mhz'),
                'band': items[0].get('band'),
                'canton': items[0].get('canton'),
            })
        result.sort(key=lambda r: float(r['avg_activity_pct'] or 0), reverse=True)
        return result[:limit]

    def index_repeater(self, repeater: dict[str, Any]) -> Optional[str]:
        repeater_id = repeater.get('id') or repeater.get('uuid')
        if repeater_id is None:
            raise ValueError("Repeater must have an id or uuid")
        with self._conn() as conn:
            conn.execute('INSERT OR REPLACE INTO repeaters(id, data) VALUES (?, ?)',
                         (str(repeater_id), json.dumps(repeater, default=str)))
        return str(repeater_id)

    def get_repeaters(self, band: Optional[str] = None, canton: Optional[str] = None,
                      mode: Optional[str] = None, status: Optional[str] = None,
                      limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn().execute('SELECT data FROM repeaters').fetchall()
        out = []
        for r in rows:
            d = json.loads(r['data'])
            if band and band != 'all' and d.get('band') != band:
                continue
            if canton and (d.get('canton') or '').upper() != canton.upper():
                continue
            if mode and d.get('mode') != mode:
                continue
            if status and d.get('status') != status:
                continue
            out.append(d)
        out.sort(key=lambda d: d.get('callsign') or '')
        return out[:limit]

    def get_repeater_by_id(self, repeater_id: Any) -> Optional[dict[str, Any]]:
        row = self._conn().execute('SELECT data FROM repeaters WHERE id=?', (str(repeater_id),)).fetchone()
        return json.loads(row['data']) if row else None

    # ------------------------------------------------------------------ events
    def index_event(self, kind: str, doc: dict[str, Any]) -> Optional[str]:
        if kind not in EVENT_KINDS:
            raise ValueError(f"Unknown event kind: {kind}")
        return self._insert(kind, doc)

    def search_events(self, kind: str, hours: int = 24, limit: int = 100,
                      term: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        for field, value in (term or {}).items():
            if not field.replace('_', '').isalnum():
                raise ValueError(f"Invalid field name: {field}")
            clauses.append(f"json_extract(data,'$.{field}') = ?")
            params.append(value)
        hits, total = self._select(kind, hours, ' AND '.join(clauses), params, limit)
        return {'hits': hits, 'total': total}
