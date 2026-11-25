"""
APRS endpoints: search, statistics, map data (GeoJSON) and file decoding.
"""

import logging
from typing import Any

from flask import Blueprint, Response, jsonify

from radiomoni import alerts
from radiomoni import events
from radiomoni.api_docs import api, parse_body, parse_query
from radiomoni.errors import ApiError
from radiomoni.schemas import AprsMapQuery, AprsSearchQuery, DecodeFileRequest, HoursLimitQuery
from radiomoni.services import get_aprs_decoder, validate_file_path
from radiomoni.storage.base import get_storage

logger = logging.getLogger(__name__)
aprs_bp = Blueprint('aprs', __name__)


@aprs_bp.get('/aprs/search')
@api('Search APRS packets', tags=['APRS'], query=AprsSearchQuery)
def search_aprs() -> Response:
    q = parse_query(AprsSearchQuery)
    results = get_storage().search_aprs(callsign=q.callsign, packet_type=q.type, hours=q.hours, limit=q.limit,
                                        reception=q.reception)
    return jsonify({'status': 'success', 'count': results['total'], 'results': results['hits']})


@aprs_bp.get('/aprs/stats')
@api('APRS statistics', tags=['APRS'], query=HoursLimitQuery)
def get_aprs_stats() -> Response:
    q = parse_query(HoursLimitQuery)
    return jsonify({'status': 'success', 'statistics': get_storage().get_aprs_stats(hours=q.hours)})


def to_geojson(packets: list[dict[str, Any]]) -> dict[str, Any]:
    """Latest position per station as a GeoJSON FeatureCollection."""
    latest: dict[str, dict[str, Any]] = {}
    for packet in packets:
        lat, lon = packet.get('latitude'), packet.get('longitude')
        if lat is None or lon is None:
            continue
        # objects and items (repeaters, meeting points) are stations of their own
        call = packet.get('object_name') or packet.get('source_callsign') or '?'
        if packet.get('object_killed'):
            latest.setdefault(call, {})          # deleted object: hide older positions
            continue
        if call not in latest:  # packets are sorted newest first
            latest[call] = packet
    latest = {call: packet for call, packet in latest.items() if packet}
    features = []
    for call, packet in latest.items():
        ts = packet.get('@timestamp') or packet.get('timestamp') or packet.get('created_at')
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [packet['longitude'], packet['latitude']]},
            'properties': {
                'callsign': call,
                'message': packet.get('message_text', ''),
                'type': packet.get('aprs_type') or packet.get('packet_type', 'unknown'),
                'symbol': f"{packet.get('symbol_table') or ''}{packet.get('symbol_code') or ''}" or None,
                'symbol_name': packet.get('symbol'),
                'symbol_id': packet.get('symbol_id'),
                'source_callsign': packet.get('source_callsign'),
                'timestamp': str(ts) if ts else None,
                'altitude': packet.get('altitude_meters') or packet.get('altitude'),
                'speed': packet.get('speed_kmh') or packet.get('speed'),
                'course': packet.get('course'),
                'frequency': packet.get('frequency'),
                'reception': packet.get('reception') or 'rf',
                'reception_source': packet.get('reception_source') or 'rf',
                'gemeinde': packet.get('gemeinde'),
                'kanton': packet.get('kanton'),
            },
        })
    return {'type': 'FeatureCollection', 'features': features}


@aprs_bp.get('/aprs/map')
@api('APRS station positions as GeoJSON (latest per callsign)', tags=['APRS'], query=AprsMapQuery)
def get_aprs_map_data() -> Response:
    q = parse_query(AprsMapQuery)
    results = get_storage().search_aprs(hours=q.hours, limit=1000, reception=q.reception)
    return jsonify(to_geojson(results.get('hits', [])))


@aprs_bp.post('/aprs/decode')
@api('Decode APRS packets from a recording', tags=['APRS'], body=DecodeFileRequest)
def decode_aprs() -> Response:
    req = parse_body(DecodeFileRequest)
    try:
        audio_file = validate_file_path(req.audio_file)
    except ValueError as e:
        raise ApiError(str(e), 403)
    try:
        packets = [dict(p) for p in get_aprs_decoder().decode(audio_file)]
    except FileNotFoundError:
        raise ApiError('Audio file not found', 404)
    except RuntimeError as e:
        raise ApiError(str(e), 503)
    storage = get_storage()
    for packet in packets:
        if req.frequency:
            packet['frequency'] = req.frequency
        if req.index_to_es:
            try:
                storage.index_aprs(packet)
            except Exception as e:
                logger.warning(f"Failed to store APRS packet: {e}")
        events.publish('aprs', packet)
        alerts.evaluate('aprs', packet)
    return jsonify({'status': 'success', 'count': len(packets), 'packets': packets})
