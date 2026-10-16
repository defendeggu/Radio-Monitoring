"""
Statistics, dashboard data and the live event stream (SSE).
"""

from flask import Blueprint, Response, jsonify, request, stream_with_context

from api_docs import api, parse_query
from events import sse_stream
from schemas import HoursLimitQuery
from storage import get_storage

stats_bp = Blueprint('stats', __name__)

EVENT_TYPES = {'aprs', 'pocsag', 'adsb', 'adsb_snapshot', 'ais', 'ism', 'vox', 'alert', 'capture',
               'session', 'scan', 'schedule', 'sdr'}


@stats_bp.get('/stats')
@api('Totals across all data types', tags=['Statistics'])
def get_statistics() -> Response:
    return jsonify({'status': 'success', 'statistics': get_storage().get_overall_stats()})


@stats_bp.get('/stats/frequencies')
@api('Most used frequencies', tags=['Statistics'], query=HoursLimitQuery)
def get_frequency_stats() -> Response:
    q = parse_query(HoursLimitQuery)
    return jsonify({'status': 'success', 'frequencies': get_storage().get_frequency_usage(limit=min(q.limit, 100))})


@stats_bp.get('/dashboard/stats')
@api('Dashboard: counts per type, hourly timeline, latest items', tags=['Statistics'], query=HoursLimitQuery)
def dashboard_stats() -> Response:
    q = parse_query(HoursLimitQuery)
    return jsonify({'status': 'success', **get_storage().get_dashboard_stats(hours=min(q.hours, 24 * 7))})


@stats_bp.get('/events')
@api('Live events as Server-Sent Events (text/event-stream)', tags=['Live'],
     description='Optional ?types=aprs,pocsag,alert filters event types.')
def live_events() -> Response:
    raw = request.args.get('types', '')
    types = {t for t in raw.split(',') if t in EVENT_TYPES} or None
    response = Response(stream_with_context(sse_stream(types)), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'   # nginx: do not buffer
    return response
