"""
APRS Decoder Blueprint

Provides endpoints for APRS (Automatic Packet Reporting System) decoding:
- Search APRS packets
- Get APRS statistics
- Get map data (GeoJSON)
- Decode APRS from audio files
"""

from flask import Blueprint, request, jsonify, Response
from api_service import get_elasticsearch_service, get_aprs_decoder
import logging

logger = logging.getLogger(__name__)

# Create blueprint
aprs_bp = Blueprint('aprs', __name__)


@aprs_bp.route('/aprs/search', methods=['GET'])
def search_aprs() -> Response | tuple[Response, int]:
    """
    Search APRS messages in database

    Query parameters:
    - callsign: Filter by source callsign
    - type: Filter by APRS type (position, message, weather, telemetry)
    - hours: Time window in hours (default 24)
    - limit: Maximum results (default 100)
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        callsign = request.args.get('callsign')
        packet_type = request.args.get('type')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)

        # Search
        results = es.search_aprs(
            callsign=callsign,
            packet_type=packet_type,
            hours=hours,
            limit=limit
        )

        return jsonify({
            'status': 'success',
            'count': results['total'],
            'results': results['hits']
        })

    except Exception as e:
        logger.error(f"APRS search failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@aprs_bp.route('/aprs/stats', methods=['GET'])
def get_aprs_stats() -> Response | tuple[Response, int]:
    """Get APRS statistics"""
    try:
        es = get_elasticsearch_service()
        stats = es.get_aprs_stats()

        return jsonify({
            'status': 'success',
            'statistics': stats
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aprs_bp.route('/aprs/map', methods=['GET'])
def get_aprs_map_data() -> Response | tuple[Response, int]:
    """
    Get APRS position data for map display (GeoJSON format)

    Returns recent APRS packets with position data in GeoJSON format
    suitable for map visualization (Grafana, Leaflet, etc.)
    """
    try:
        es = get_elasticsearch_service()

        # Get recent packets with position data (last 24 hours by default)
        hours = request.args.get('hours', 24, type=int)

        results = es.search_aprs(
            hours=hours,
            limit=1000
        )

        # Filter for packets with position data and convert to GeoJSON
        features = []
        for packet in results.get('hits', []):
            if packet.get('latitude') and packet.get('longitude'):
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [packet['longitude'], packet['latitude']]
                    },
                    'properties': {
                        'callsign': packet['source_callsign'],
                        'message': packet.get('message_text', ''),
                        'type': packet.get('aprs_type', 'unknown'),
                        'timestamp': packet['created_at'].isoformat() if hasattr(packet['created_at'], 'isoformat') else str(packet['created_at']),
                        'altitude': packet.get('altitude_meters'),
                        'speed': packet.get('speed_kmh'),
                        'frequency': packet.get('frequency')
                    }
                })

        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }

        return jsonify(geojson)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aprs_bp.route('/aprs/decode', methods=['POST'])
def decode_aprs() -> Response | tuple[Response, int]:
    """
    Decode APRS packets from audio file

    Request body (JSON):
    {
        "audio_file": "/path/to/audio.wav",
        "frequency": 144800000,  // Optional: frequency in Hz
        "index_to_es": true      // Optional: index to Elasticsearch (default: true)
    }

    Returns:
    {
        "status": "success",
        "count": 5,
        "packets": [...]
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

        # Decode APRS packets
        decoder = get_aprs_decoder()
        packets = decoder.decode(audio_file)

        # Add metadata to packets
        for packet in packets:
            if frequency:
                packet['frequency'] = frequency

        # Index to Elasticsearch if requested
        if index_to_es and packets:
            es = get_elasticsearch_service()
            for packet in packets:
                try:
                    es.index_aprs(packet)
                except Exception as e:
                    logger.warning(f"Failed to index APRS packet: {e}")

        return jsonify({
            'status': 'success',
            'count': len(packets),
            'packets': packets
        })

    except FileNotFoundError as e:
        return jsonify({'error': f'Audio file not found: {str(e)}'}), 404
    except Exception as e:
        logger.error(f"APRS decode failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
