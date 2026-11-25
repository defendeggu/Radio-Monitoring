"""
aprs-stats endpoints: status, summary tiles, trips, link to its own page.

aprs-stats runs in its own containers (compose profile "aprsstats"); see radiomoni/aprsstats and docs/aprs-stats.md.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, Response, jsonify

from radiomoni import config
from radiomoni.api_docs import api, parse_query
from radiomoni.aprsstats import feed, sync
from radiomoni.aprsstats.client import AprsStatsClient, AprsStatsError, enabled
from radiomoni.errors import ApiError
from radiomoni.schemas import AprsStatsTripsQuery
from radiomoni.storage.base import get_storage

aprsstats_bp = Blueprint('aprsstats', __name__)


@aprsstats_bp.get('/aprsstats/status')
@api('aprs-stats: reachable, version, APRS-IS collector, sync and RF feed', tags=['APRS'])
def status() -> Response:
    info: dict[str, Any] = {'enabled': enabled(), 'feed_rf': config.APRSSTATS_FEED_RF, 'sync': sync.status(),
                            'feed': dict(feed.stats)}
    if not enabled():
        return jsonify({'status': 'success', **info, 'reachable': False})
    try:
        st = AprsStatsClient(timeout=5.0).get('status')
        info.update({'reachable': True, 'version': st.get('version'), 'collector': st.get('collector'),
                     'counts': st.get('counts'), 'boundaries': (st.get('boundaries') or {}).get('state')})
    except AprsStatsError as e:
        info.update({'reachable': False, 'error': str(e)})
    return jsonify({'status': 'success', **info})


def _summary(client: AprsStatsClient, start: datetime) -> dict[str, Any]:
    s = client.get('stats/summary', {'from': start.isoformat()}) or {}
    areas = s.get('areas') or {}
    return {'km': s.get('km'), 'points': s.get('points'), 'devices': s.get('devices'), 'days': s.get('days'),
            'by_source': s.get('by_source') or {}, 'gemeinden': areas.get('gemeinden'),
            'gemeinden_total': areas.get('gemeinden_total'), 'kantone': areas.get('kantone'),
            'kantone_total': areas.get('kantone_total'), 'last': s.get('last')}


@aprsstats_bp.get('/aprsstats/summary')
@api('aprs-stats in numbers: today, last 7 days and everything (km, positions over the air / internet, '
     'municipalities, cantons)', tags=['APRS'])
def summary() -> Response:
    if not enabled():
        raise ApiError('aprs-stats is not set up (compose profile "aprsstats", APRSSTATS_URL; docs/aprs-stats.md)',
                       503)
    client = AprsStatsClient(timeout=20.0)
    now = datetime.now(timezone.utc)
    today = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        return jsonify({'status': 'success', 'today': _summary(client, today),
                        'week': _summary(client, now - timedelta(days=7)),
                        'all': _summary(client, datetime(2000, 1, 1, tzinfo=timezone.utc))})
    except AprsStatsError as e:
        raise ApiError(str(e), 503)


@aprsstats_bp.get('/aprsstats/trips')
@api('Trips from aprs-stats (start, destination, km, duration), newest first', tags=['APRS'],
     query=AprsStatsTripsQuery)
def trips() -> Response:
    q = parse_query(AprsStatsTripsQuery)
    if not enabled():
        raise ApiError('aprs-stats is not set up', 503)
    since = datetime.now(timezone.utc) - timedelta(days=q.days)
    try:
        rows = AprsStatsClient(timeout=20.0).get('stats/trips', {'from': since.isoformat()}) or []
    except AprsStatsError as e:
        raise ApiError(str(e), 503)
    out = [sync.trip_document(t) for t in rows[:q.limit]]
    return jsonify({'status': 'success', 'count': len(out), 'trips': out})


@aprsstats_bp.post('/aprsstats/sync')
@api('Run the aprs-stats sync now (packets, imports, trips, places)', tags=['APRS'])
def sync_now() -> Response:
    if not enabled():
        raise ApiError('aprs-stats is not set up', 503)
    try:
        result = sync.Syncer().run_once(force=True)
    except AprsStatsError as e:
        raise ApiError(str(e), 503)
    return jsonify({'status': 'success', **result})


@aprsstats_bp.get('/aprsstats/link')
@api("Address of aprs-stats' own page (map, heatmap, municipalities, import, beacons) behind nginx", tags=['APRS'])
def link() -> Response:
    if not enabled():
        raise ApiError('aprs-stats is not set up', 503)
    return jsonify({'status': 'success', 'url': config.APRSSTATS_PUBLIC_URL or None, 'port': 8092})


@aprsstats_bp.get('/aprsstats/counts')
@api('APRS documents in RadioMoni by reception (over the air / internet) for the last hours', tags=['APRS'],
     query=AprsStatsTripsQuery)
def counts() -> Response:
    q = parse_query(AprsStatsTripsQuery)
    storage = get_storage()
    hours = q.days * 24
    rf = storage.search_aprs(hours=hours, limit=1, reception='rf')['total']
    internet = storage.search_aprs(hours=hours, limit=1, reception='internet')['total']
    return jsonify({'status': 'success', 'hours': hours, 'rf': rf, 'internet': internet})
