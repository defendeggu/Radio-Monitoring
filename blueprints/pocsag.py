"""
POCSAG endpoints: search, statistics, recent messages and file decoding.
"""

import logging

from flask import Blueprint, Response, jsonify

import alerts
import events
from api_docs import api, parse_body, parse_query
from errors import ApiError
from schemas import DecodeFileRequest, HoursLimitQuery, PocsagSearchQuery
from services import get_pocsag_decoder, validate_file_path
from storage import get_storage

logger = logging.getLogger(__name__)
pocsag_bp = Blueprint('pocsag', __name__)


@pocsag_bp.get('/pocsag/search')
@api('Search POCSAG messages', tags=['POCSAG'], query=PocsagSearchQuery)
def search_pocsag() -> Response:
    q = parse_query(PocsagSearchQuery)
    results = get_storage().search_pocsag(address=q.address, message_type=q.type, hours=q.hours, limit=q.limit)
    return jsonify({'status': 'success', 'count': results['total'], 'results': results['hits']})


@pocsag_bp.get('/pocsag/stats')
@api('POCSAG statistics', tags=['POCSAG'], query=HoursLimitQuery)
def get_pocsag_stats() -> Response:
    q = parse_query(HoursLimitQuery)
    return jsonify({'status': 'success', 'statistics': get_storage().get_pocsag_stats(hours=q.hours)})


@pocsag_bp.get('/pocsag/messages')
@api('Recent POCSAG messages', tags=['POCSAG'], query=HoursLimitQuery)
def get_pocsag_messages() -> Response:
    q = parse_query(HoursLimitQuery)
    results = get_storage().search_pocsag(hours=q.hours, limit=q.limit)
    return jsonify({'status': 'success', 'count': results['total'], 'messages': results['hits']})


@pocsag_bp.post('/pocsag/decode')
@api('Decode POCSAG messages from a recording', tags=['POCSAG'], body=DecodeFileRequest)
def decode_pocsag() -> Response:
    req = parse_body(DecodeFileRequest)
    try:
        audio_file = validate_file_path(req.audio_file)
    except ValueError as e:
        raise ApiError(str(e), 403)
    try:
        messages = [dict(m) for m in get_pocsag_decoder().decode(audio_file)]
    except FileNotFoundError:
        raise ApiError('Audio file not found', 404)
    except RuntimeError as e:
        raise ApiError(str(e), 503)
    storage = get_storage()
    for message in messages:
        if req.frequency:
            message['frequency'] = req.frequency
        if req.index_to_es:
            try:
                storage.index_pocsag(message)
            except Exception as e:
                logger.warning(f"Failed to store POCSAG message: {e}")
        events.publish('pocsag', message)
        alerts.evaluate('pocsag', message)
    return jsonify({'status': 'success', 'count': len(messages), 'messages': messages})
