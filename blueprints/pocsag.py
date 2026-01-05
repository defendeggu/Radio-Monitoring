"""
POCSAG Decoder Blueprint

Provides endpoints for POCSAG (pager protocol) decoding:
- Search POCSAG messages
- Get POCSAG statistics
- Get recent messages
- Decode POCSAG from audio files
"""

from flask import Blueprint, request, jsonify, Response
from typing import Any, cast
from api_service import get_elasticsearch_service, get_pocsag_decoder
import logging

logger = logging.getLogger(__name__)

# Create blueprint
pocsag_bp = Blueprint('pocsag', __name__)


@pocsag_bp.route('/pocsag/search', methods=['GET'])
def search_pocsag() -> Response | tuple[Response, int]:
    """
    Search POCSAG messages in database

    Query parameters:
    - address: Filter by pager address
    - type: Filter by message type (alphanumeric, numeric, tone)
    - hours: Time window in hours (default 24)
    - limit: Maximum results (default 100)
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        address = request.args.get('address', type=int)
        message_type = request.args.get('type')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)

        # Search
        results = es.search_pocsag(
            address=address,
            message_type=message_type,
            hours=hours,
            limit=limit
        )

        return jsonify({
            'status': 'success',
            'count': results['total'],
            'results': results['hits']
        })

    except Exception as e:
        logger.error(f"POCSAG search failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@pocsag_bp.route('/pocsag/stats', methods=['GET'])
def get_pocsag_stats() -> Response | tuple[Response, int]:
    """Get POCSAG statistics"""
    try:
        es = get_elasticsearch_service()
        stats = es.get_pocsag_stats()

        return jsonify({
            'status': 'success',
            'statistics': stats
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pocsag_bp.route('/pocsag/messages', methods=['GET'])
def get_pocsag_messages() -> Response | tuple[Response, int]:
    """
    Get recent POCSAG messages

    Query parameters:
    - limit: Maximum results (default 50)
    - offset: Offset for pagination (default 0)
    """
    try:
        es = get_elasticsearch_service()
        limit = request.args.get('limit', 50, type=int)

        results = es.search_pocsag(limit=limit)

        return jsonify({
            'status': 'success',
            'count': results['total'],
            'messages': results['hits']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pocsag_bp.route('/pocsag/decode', methods=['POST'])
def decode_pocsag() -> Response | tuple[Response, int]:
    """
    Decode POCSAG messages from audio file

    Request body (JSON):
    {
        "audio_file": "/path/to/audio.wav",
        "frequency": 147325000,  // Optional: frequency in Hz
        "index_to_es": true      // Optional: index to Elasticsearch (default: true)
    }

    Returns:
    {
        "status": "success",
        "count": 3,
        "messages": [...]
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400

        audio_file = data.get('audio_file')
        if not audio_file:
            return jsonify({'error': 'Missing required field: audio_file'}), 400

        frequency = data.get('frequency')
        index_to_es = data.get('index_to_es', True)

        # Decode POCSAG messages
        decoder = get_pocsag_decoder()
        messages = decoder.decode(audio_file)

        # Add metadata to messages
        for message in messages:
            if frequency:
                message['frequency'] = frequency

        # Index to Elasticsearch if requested
        if index_to_es and messages:
            es = get_elasticsearch_service()
            for message in messages:
                try:
                    es.index_pocsag(cast(dict[str, Any], message))
                except Exception as e:
                    logger.warning(f"Failed to index POCSAG message: {e}")

        return jsonify({
            'status': 'success',
            'count': len(messages),
            'messages': messages
        })

    except FileNotFoundError as e:
        return jsonify({'error': f'Audio file not found: {str(e)}'}), 404
    except Exception as e:
        logger.error(f"POCSAG decode failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
