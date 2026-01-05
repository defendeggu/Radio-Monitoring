"""
Capture and Transcription Blueprint

Provides endpoints for:
- Audio capture from SDR hardware
- Audio transcription
- Recording file management
- Capture search

Note: /capture-and-transcribe is intentionally kept in api_service.py
due to its complexity (300+ lines with APRS/POCSAG logic).
It will be refactored separately.
"""

import os
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from typing import TYPE_CHECKING

# Import from api_service (shared utilities)
if TYPE_CHECKING:
    from api_service import RecordingInfo

# These will be imported at runtime to avoid circular imports
# They are defined in api_service.py
from api_service import (
    validate_file_path,
    get_transcription_service,
    get_elasticsearch_service,
    RECORDING_DIR,
    RecordingInfo
)

from sdr_hardware import get_sdr_instance
import logging

logger = logging.getLogger(__name__)

# Create blueprint
capture_bp = Blueprint('capture', __name__)


@capture_bp.route('/capture', methods=['POST'])
def capture() -> Response | tuple[Response, int]:
    """
    Capture radio signal

    Request body:
    {
        "frequency": 100000000,
        "modulation": "FM",
        "duration": 30,
        "gain": 20,
        "sample_rate": 2000000
    }
    """
    try:
        data = request.get_json()

        # Validate required parameters
        if 'frequency' not in data:
            return jsonify({'error': 'frequency is required'}), 400

        frequency = int(float(data['frequency']))
        modulation = data.get('modulation', 'FM')
        duration = int(data.get('duration', 30))
        gain = int(data.get('gain', 20))
        sample_rate = int(data.get('sample_rate', 2000000))

        # Generate output filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.wav')

        # Create capture instance (auto-detect SDR hardware)
        capture_instance = get_sdr_instance(
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Perform capture with metrics
        start_time = time.time()
        capture_instance.capture_audio(duration, output_file, modulation)
        capture_duration_seconds = time.time() - start_time

        # Record metrics
        return jsonify({
            'status': 'success',
            'audio_file': output_file,
            'frequency': frequency,
            'modulation': modulation,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@capture_bp.route('/transcribe', methods=['POST'])
def transcribe() -> Response | tuple[Response, int]:
    """
    Transcribe audio file

    Request body:
    {
        "audio_file": "path/to/audio.wav",
        "language": "en"  # optional
    }
    """
    try:
        data = request.get_json()

        # Validate required parameters
        if 'audio_file' not in data:
            return jsonify({'error': 'audio_file is required'}), 400

        # Validate file path to prevent path traversal
        try:
            audio_file = validate_file_path(data['audio_file'])
        except ValueError as e:
            return jsonify({'error': str(e)}), 403

        language = data.get('language')

        # Get transcription service
        service = get_transcription_service()

        # Transcribe with metrics
        start_time = time.time()
        result = service.transcribe(audio_file, language)
        transcription_duration_seconds = time.time() - start_time

        # Record metrics
        return jsonify({
            'status': 'success',
            'result': result
        })

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@capture_bp.route('/list-recordings', methods=['GET'])
def list_recordings() -> Response | tuple[Response, int]:
    """List all recordings in the recordings directory"""
    try:
        if not os.path.exists(RECORDING_DIR):
            return jsonify({'recordings': []})

        files: list[RecordingInfo] = []
        for filename in os.listdir(RECORDING_DIR):
            if filename.endswith('.wav'):
                filepath = os.path.join(RECORDING_DIR, filename)
                stat = os.stat(filepath)
                files.append({
                    'filename': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })

        # Sort by creation time (newest first)
        files.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({'recordings': files})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@capture_bp.route('/search', methods=['GET'])
def search_captures() -> Response | tuple[Response, int]:
    """
    Search captures in database

    Query parameters:
    - query: Full-text search query
    - freq_min: Filter by minimum frequency
    - freq_max: Filter by maximum frequency
    - modulation: Filter by modulation (FM, AM, USB, LSB)
    - language: Filter by language
    - sdr_type: Filter by SDR type
    - hours: Time range in hours (default 24)
    - limit: Maximum results (default 100)
    - offset: Offset for pagination (default 0)
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        query = request.args.get('query')
        freq_min = request.args.get('freq_min', type=int)
        freq_max = request.args.get('freq_max', type=int)
        modulation = request.args.get('modulation')
        language = request.args.get('language')
        sdr_type = request.args.get('sdr_type')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        # Search
        results = es.search_captures(
            query=query,
            frequency_min=freq_min,
            frequency_max=freq_max,
            modulation=modulation,
            language=language,
            sdr_type=sdr_type,
            hours=hours,
            limit=limit,
            offset=offset
        )

        return jsonify({
            'status': 'success',
            'count': results['total'],
            'results': results['hits']
        })

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
