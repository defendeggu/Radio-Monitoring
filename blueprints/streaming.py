"""
Streaming Decoder Blueprint

Provides endpoints for real-time streaming decoding:
- Start APRS streaming
- Start POCSAG streaming
- Start generic streaming decode
- Get stream status
- Stop stream
- List active streams
"""

from flask import Blueprint, request, jsonify, Response
from typing import Union
from streaming_decoder_service import (
    StreamingAPRSDecoder,
    StreamingPOCSAGDecoder
)
# Note: session_manager is imported at runtime in each route to avoid circular imports
import logging

logger = logging.getLogger(__name__)

# Create blueprint
streaming_bp = Blueprint('streaming', __name__)


@streaming_bp.route('/stream/aprs/start', methods=['POST'])
def start_aprs_streaming() -> Response | tuple[Response, int]:
    """
    Start APRS streaming decoder session

    Request body:
    {
        "frequency": 144800000,  // APRS frequency in Hz
        "sample_rate": 2000000,  // optional
        "gain": 20              // optional
    }
    """
    try:
        # Import at runtime to avoid circular dependency
        from api_service import session_manager

        data = request.get_json() or {}

        frequency = data.get('frequency', 144800000)
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)
        duration = data.get('duration', 3600)  # Default: 1 hour

        # Create streaming decoder
        decoder = StreamingAPRSDecoder(
            frequency=frequency,
            duration=duration,
            sample_rate=sample_rate,
            gain=gain
        )

        # Create session
        session_id = session_manager.create_session(
            decoder_type='aprs',
            decoder=decoder,
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Start streaming
        decoder.start()

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'APRS streaming started',
            'frequency': frequency
        })

    except Exception as e:
        logger.error(f"Failed to start APRS streaming: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream/pocsag/start', methods=['POST'])
def start_pocsag_streaming() -> Response | tuple[Response, int]:
    """
    Start POCSAG streaming decoder session

    Request body:
    {
        "frequency": 147325000,  // POCSAG frequency in Hz
        "sample_rate": 2000000,  // optional
        "gain": 20              // optional
    }
    """
    try:
        # Import at runtime to avoid circular dependency
        from api_service import session_manager

        data = request.get_json() or {}

        frequency = data.get('frequency', 147325000)
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)
        duration = data.get('duration', 3600)  # Default: 1 hour

        # Create streaming decoder
        decoder = StreamingPOCSAGDecoder(
            frequency=frequency,
            duration=duration,
            sample_rate=sample_rate,
            gain=gain
        )

        # Create session
        session_id = session_manager.create_session(
            decoder_type='pocsag',
            decoder=decoder,
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Start streaming
        decoder.start()

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'POCSAG streaming started',
            'frequency': frequency
        })

    except Exception as e:
        logger.error(f"Failed to start POCSAG streaming: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode', methods=['POST'])
def start_streaming_decode() -> Response | tuple[Response, int]:
    """
    Start a streaming decode session (generic)

    Request body:
    {
        "mode": "aprs",          // "aprs" or "pocsag"
        "frequency": 144800000,
        "sample_rate": 2000000,  // optional
        "gain": 20               // optional
    }
    """
    try:
        # Import at runtime to avoid circular dependency
        from api_service import session_manager

        data = request.get_json() or {}

        mode = data.get('mode', 'aprs')
        frequency = data.get('frequency')
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)
        duration = data.get('duration', 3600)  # Default: 1 hour

        if not frequency:
            return jsonify({'error': 'frequency is required'}), 400

        if mode not in ['aprs', 'pocsag']:
            return jsonify({'error': 'mode must be "aprs" or "pocsag"'}), 400

        # Create appropriate decoder
        decoder: Union[StreamingAPRSDecoder, StreamingPOCSAGDecoder]
        if mode == 'aprs':
            decoder = StreamingAPRSDecoder(
                frequency=frequency,
                duration=duration,
                sample_rate=sample_rate,
                gain=gain
            )
        else:  # pocsag
            decoder = StreamingPOCSAGDecoder(
                frequency=frequency,
                duration=duration,
                sample_rate=sample_rate,
                gain=gain
            )

        # Create session
        session_id = session_manager.create_session(
            decoder_type=mode,
            decoder=decoder,
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Start streaming
        decoder.start()

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': f'{mode.upper()} streaming started',
            'mode': mode,
            'frequency': frequency
        })

    except Exception as e:
        logger.error(f"Failed to start streaming decode: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode/<session_id>', methods=['GET'])
def get_streaming_session(session_id: str) -> Response | tuple[Response, int]:
    """Get status and results of a streaming decode session"""
    try:
        # Import at runtime to avoid circular dependency
        from api_service import session_manager

        session = session_manager.get_session(session_id)

        if not session:
            return jsonify({
                'status': 'error',
                'message': 'Session not found'
            }), 404

        return jsonify({
            'status': 'success',
            'session': session.to_dict()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode/<session_id>', methods=['DELETE'])
def stop_streaming_session(session_id: str) -> Response | tuple[Response, int]:
    """Stop a streaming decode session"""
    try:
        # Import at runtime to avoid circular dependency
        from api_service import session_manager

        session = session_manager.get_session(session_id)

        if not session:
            return jsonify({
                'status': 'error',
                'message': 'Session not found'
            }), 404

        # Kill any running SDR/decoder processes
        # Note: We don't have direct access to decoder instances from Redis
        # So we kill all processes as a workaround
        import subprocess
        try:
            subprocess.run(['pkill', '-9', 'hackrf_transfer'], timeout=2)
            subprocess.run(['pkill', '-9', 'multimon-ng'], timeout=2)
            subprocess.run(['pkill', '-9', 'direwolf'], timeout=2)
        except:
            pass

        # Delete session
        session_manager.delete_session(session_id)

        return jsonify({
            'status': 'success',
            'message': 'Streaming session stopped'
        })

    except Exception as e:
        logger.error(f"Failed to stop streaming session: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@streaming_bp.route('/stream-decode', methods=['GET'])
def list_streaming_sessions() -> Response | tuple[Response, int]:
    """List all active streaming decode sessions"""
    try:
        # Import at runtime to avoid circular dependency
        from api_service import session_manager

        sessions = session_manager.list_sessions()

        return jsonify({
            'status': 'success',
            'count': len(sessions),
            'sessions': [s.to_dict() for s in sessions]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
