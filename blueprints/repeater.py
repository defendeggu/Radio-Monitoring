"""
Repeater Scanning Blueprint

Provides endpoints for repeater activity scanning:
- Start repeater scan
- Get scan progress
- Get scan session details
- List repeaters
- Get activity summary

Note: _scan_repeaters_worker() remains in api_service.py as it's
a background worker function that needs access to thread pools.
"""

from flask import Blueprint, request, jsonify, Response
from typing import Dict, Any

# Import from api_service (shared utilities)
# Note: _scan_repeaters_worker is imported at runtime to avoid circular imports
from api_service import (
    get_elasticsearch_service,
    has_active_scan,
    scan_thread_pool
)
from scan_session_manager import get_scan_session_manager, RepeaterScanSession

import logging

logger = logging.getLogger(__name__)

# Get session manager
scan_session_manager = get_scan_session_manager()

# Create blueprint
repeater_bp = Blueprint('repeater', __name__)


@repeater_bp.route('/scan-repeaters', methods=['POST'])
def scan_repeaters() -> Response | tuple[Response, int]:
    """
    Start a repeater activity scan.

    Request body:
    {
        "duration_per_repeater": 120,    // Seconds (default: 120)
        "band": "2m",                     // optional: "2m", "70cm", "all"
        "canton": "ZH",                   // optional: Filter by canton
        "repeater_ids": [1, 2, 3],       // optional: Specific repeater IDs
        "sample_rate": 2000000,           // optional: IQ sample rate
        "gain": 20                        // optional: RF gain
    }

    Response:
    {
        "status": "success",
        "session_id": 1,
        "message": "Scan started",
        "repeaters_count": 10,
        "estimated_duration_seconds": 1200
    }
    """
    try:
        # Check if a scan is already in progress
        if has_active_scan():
            return jsonify({
                'status': 'error',
                'message': 'A scan is already in progress. Please wait for it to complete.',
                'code': 'SCAN_IN_PROGRESS'
            }), 409

        data = request.get_json() or {}

        # Parse parameters
        duration_per_repeater = data.get('duration_per_repeater', 120)
        band = data.get('band')
        canton = data.get('canton')
        repeater_ids = data.get('repeater_ids')
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)

        es = get_elasticsearch_service()

        # Get repeaters to scan
        if repeater_ids:
            # Specific repeaters by ID
            repeaters = []
            for rid in repeater_ids:
                repeater = es.get_repeater_by_id(rid)
                if repeater:
                    repeaters.append(repeater)
        else:
            # Filter by band/canton
            repeaters = es.get_repeaters(
                band=band,
                canton=canton,
                mode='FM',
                status='active'
            )

        if not repeaters:
            return jsonify({
                'status': 'error',
                'message': 'No repeaters found matching criteria'
            }), 404

        # Generate session ID using Redis atomic counter
        session_id = scan_session_manager.get_next_session_id()

        # Create and save session to Redis
        session = RepeaterScanSession(
            session_id=session_id,
            repeaters_total=len(repeaters),
            duration_per_repeater=duration_per_repeater,
            sample_rate=sample_rate,
            gain=gain
        )
        scan_session_manager.save_session(session)

        # Import worker at runtime to avoid circular dependency
        from api_service import _scan_repeaters_worker

        # Submit scan to thread pool (max 1 concurrent scan)
        scan_thread_pool.submit(
            _scan_repeaters_worker,
            session_id,
            repeaters,
            duration_per_repeater,
            sample_rate,
            gain
        )

        estimated_duration = len(repeaters) * duration_per_repeater

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'Scan started',
            'repeaters_count': len(repeaters),
            'estimated_duration_seconds': estimated_duration
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@repeater_bp.route('/scan-repeaters/<int:session_id>/progress', methods=['GET'])
def get_scan_progress(session_id: int) -> Response | tuple[Response, int]:
    """Get progress of a repeater scan session"""
    try:
        # Get session from Redis
        session_obj = scan_session_manager.get_session(session_id)

        if not session_obj:
            return jsonify({
                'status': 'error',
                'message': 'Scan session not found'
            }), 404

        # Calculate progress
        current = session_obj.current_index
        total = session_obj.repeaters_total
        elapsed = session_obj.elapsed_time

        # Estimate remaining time
        if current > 0 and elapsed > 0:
            avg_time_per_repeater = elapsed / current
            remaining_repeaters = total - current
            estimated_remaining = int(avg_time_per_repeater * remaining_repeaters)
        else:
            estimated_remaining = 0

        response = {
            'status': session_obj.status,
            'session_id': session_id,
            'progress': {
                'current_repeater': current + 1,  # 1-indexed for display
                'total_repeaters': total,
                'current_callsign': session_obj.current_repeater,
                'elapsed_seconds': int(elapsed),
                'estimated_remaining_seconds': estimated_remaining,
                'repeaters_scanned': session_obj.repeaters_scanned,
                'repeaters_with_activity': session_obj.repeaters_with_activity
            },
            'results': session_obj.results
        }

        if session_obj.status == 'failed':
            response['error'] = session_obj.error

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@repeater_bp.route('/scan-repeaters/<int:session_id>', methods=['GET'])
def get_scan_session_details(session_id: int) -> Response | tuple[Response, int]:
    """Get complete details of a scan session from database"""
    try:
        # Get session from Redis
        session_obj = scan_session_manager.get_session(session_id)

        if not session_obj:
            return jsonify({
                'status': 'error',
                'message': 'Scan session not found'
            }), 404

        return jsonify({
            'status': 'success',
            'session': session_obj.to_dict()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@repeater_bp.route('/repeaters', methods=['GET'])
def get_repeaters_endpoint() -> Response | tuple[Response, int]:
    """
    Get list of repeaters with optional filters.

    Query parameters:
    - band: Filter by band (2m, 70cm, 23cm)
    - canton: Filter by canton (ZH, BE, etc.)
    - mode: Filter by mode (FM, DMR, etc.) - default: FM
    - status: Filter by status (active, inactive) - default: active
    - limit: Maximum results (default 100)
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        band = request.args.get('band')
        canton = request.args.get('canton')
        mode = request.args.get('mode', 'FM')
        status = request.args.get('status', 'active')
        limit = request.args.get('limit', 100, type=int)

        # Get repeaters
        repeaters = es.get_repeaters(
            band=band,
            canton=canton,
            mode=mode,
            status=status
        )

        # Limit results
        repeaters = repeaters[:limit]

        return jsonify({
            'status': 'success',
            'count': len(repeaters),
            'repeaters': repeaters
        })

    except Exception as e:
        logger.error(f"Failed to get repeaters: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@repeater_bp.route('/repeater-activity/summary', methods=['GET'])
def get_repeater_activity_summary() -> Response | tuple[Response, int]:
    """
    Get summary of repeater activity from recent scans.

    Returns statistics about repeater activity including:
    - Total repeaters scanned
    - Repeaters with detected activity
    - Activity by band
    - Activity by canton
    """
    try:
        es = get_elasticsearch_service()

        # Get recent repeater activity data
        hours = request.args.get('hours', 24, type=int)

        summary = es.get_repeater_activity_summary(hours=hours)

        return jsonify({
            'status': 'success',
            'summary': summary
        })

    except Exception as e:
        logger.error(f"Failed to get repeater activity summary: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
