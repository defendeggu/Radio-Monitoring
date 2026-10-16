"""
Repeater activity scanning endpoints.
"""

from flask import Blueprint, Response, jsonify

from api_docs import api, parse_body, parse_query
from errors import ApiError, call_action
from jobs import submit_repeater_scan
from scan_session_manager import get_scan_session_manager
from schemas import RepeaterListQuery, RepeaterScanRequest, RepeaterSummaryQuery
from storage import get_storage

repeater_bp = Blueprint('repeater', __name__)


@repeater_bp.post('/scan-repeaters')
@api('Start a repeater activity scan', tags=['Repeater'], body=RepeaterScanRequest,
     responses={404: 'No repeaters match', 409: 'SDR busy'})
def scan_repeaters() -> Response:
    req = parse_body(RepeaterScanRequest)
    info = call_action(submit_repeater_scan, req)
    return jsonify({'status': 'success', 'message': 'Scan started', **info})


@repeater_bp.get('/scan-repeaters/<int:session_id>/progress')
@api('Progress of a repeater scan', tags=['Repeater'], responses={404: 'Unknown session'})
def get_scan_progress(session_id: int) -> Response:
    session = get_scan_session_manager().get_session(session_id)
    if not session:
        raise ApiError('Scan session not found', 404)
    current, total, elapsed = session.current_index, session.repeaters_total, session.elapsed_time
    remaining = int(elapsed / current * (total - current)) if current > 0 and elapsed > 0 else 0
    response = {
        'status': session.status,
        'session_id': session_id,
        'progress': {
            'current_repeater': current + 1,
            'total_repeaters': total,
            'current_callsign': session.current_repeater,
            'elapsed_seconds': int(elapsed),
            'estimated_remaining_seconds': remaining,
            'repeaters_scanned': session.repeaters_scanned,
            'repeaters_with_activity': session.repeaters_with_activity,
        },
        'results': session.results,
    }
    if session.status == 'failed':
        response['error'] = session.error
    return jsonify(response)


@repeater_bp.get('/scan-repeaters/<int:session_id>')
@api('Full details of a repeater scan', tags=['Repeater'], responses={404: 'Unknown session'})
def get_scan_session_details(session_id: int) -> Response:
    session = get_scan_session_manager().get_session(session_id)
    if not session:
        raise ApiError('Scan session not found', 404)
    return jsonify({'status': 'success', 'session': session.to_dict()})


@repeater_bp.get('/repeaters')
@api('Repeater master data', tags=['Repeater'], query=RepeaterListQuery)
def get_repeaters_endpoint() -> Response:
    q = parse_query(RepeaterListQuery)
    repeaters = get_storage().get_repeaters(band=q.band, canton=q.canton, mode=q.mode, status=q.status,
                                            limit=q.limit)
    return jsonify({'status': 'success', 'count': len(repeaters), 'repeaters': repeaters})


@repeater_bp.get('/repeater-activity/summary')
@api('Most active repeaters', tags=['Repeater'], query=RepeaterSummaryQuery)
def get_repeater_activity_summary() -> Response:
    q = parse_query(RepeaterSummaryQuery)
    summary = get_storage().get_repeater_activity_summary(hours=q.hours, band=q.band, canton=q.canton,
                                                          limit=q.limit)
    return jsonify({'status': 'success', 'summary': summary})
