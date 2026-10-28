"""
Repeater activity scanning endpoints.
"""

from typing import Optional

from flask import Blueprint, Response, jsonify

from api_docs import api, parse_body, parse_query
from errors import ApiError, call_action
from jobs import stop_repeater_scan, submit_repeater_scan
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
    remaining: Optional[int]
    if session.until_stopped:
        remaining = None  # runs until stopped
    elif session.total_duration:
        remaining = max(0, int(session.total_duration - elapsed))
    else:
        remaining = (total - current) * session.duration_per_repeater
    if session.status != 'in_progress':
        remaining = 0
    response = {
        'status': session.status,
        'session_id': session_id,
        'progress': {
            'current_repeater': current + 1,
            'total_repeaters': total,
            'current_callsign': session.current_repeater,
            'current_round': session.current_round,
            'rounds_completed': session.rounds_completed,
            'duration_per_repeater': session.duration_per_repeater,
            'total_duration': session.total_duration,
            'until_stopped': session.until_stopped,
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


@repeater_bp.post('/scan-repeaters/<int:session_id>/stop')
@api('Stop a running repeater scan', tags=['Repeater'], responses={404: 'Unknown session', 409: 'Not running'})
def stop_scan(session_id: int) -> Response:
    if get_scan_session_manager().get_session(session_id) is None:
        raise ApiError('Scan session not found', 404)
    if not stop_repeater_scan(session_id):
        raise ApiError('Scan is not running', 409)
    return jsonify({'status': 'success', 'message': 'Scan is stopping'})


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
