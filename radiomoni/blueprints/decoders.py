"""
Read access to ADS-B, AIS and ISM sensor data plus decoder availability.
"""

from typing import Any

from flask import Blueprint, Response, jsonify

from radiomoni.api_docs import api, parse_query
from radiomoni.errors import ApiError
from radiomoni.external_decoders import DEFAULT_FREQUENCIES, TOOLS, tool_available
from radiomoni.schemas import EventSearchQuery
from radiomoni.storage import get_storage

decoders_bp = Blueprint('decoders', __name__)

KINDS = ('adsb', 'ais', 'ism')


@decoders_bp.get('/decoders')
@api('Available external decoders', tags=['Decoders'])
def list_decoders() -> Response:
    return jsonify({'decoders': [
        {'decoder': kind, 'tool': TOOLS[kind], 'installed': tool_available(kind),
         'default_frequency': DEFAULT_FREQUENCIES[kind], 'hardware': 'rtlsdr'}
        for kind in KINDS]})


@decoders_bp.get('/decoders/<kind>/search')
@api('Search stored ADS-B / AIS / ISM documents', tags=['Decoders'], query=EventSearchQuery)
def search(kind: str) -> Response:
    if kind not in KINDS:
        raise ApiError('Unknown decoder', 404)
    q = parse_query(EventSearchQuery)
    term: dict[str, Any] = {}
    if q.icao:
        term['icao'] = q.icao.upper()
    if q.mmsi:
        term['mmsi'] = q.mmsi
    if q.model:
        term['model'] = q.model
    if q.sensor_id:
        term['sensor_id'] = q.sensor_id
    results = get_storage().search_events(kind, hours=q.hours, limit=q.limit, term=term or None)
    return jsonify({'status': 'success', 'count': results['total'], 'results': results['hits']})


@decoders_bp.get('/decoders/<kind>/latest')
@api('Latest document per aircraft / ship / sensor', tags=['Decoders'], query=EventSearchQuery)
def latest(kind: str) -> Response:
    if kind not in KINDS:
        raise ApiError('Unknown decoder', 404)
    q = parse_query(EventSearchQuery)
    key = {'adsb': 'icao', 'ais': 'mmsi', 'ism': 'sensor_id'}[kind]
    hits = get_storage().search_events(kind, hours=q.hours, limit=min(q.limit * 20, 5000))['hits']
    seen: dict[str, dict[str, Any]] = {}
    for doc in hits:  # newest first
        ident = str(doc.get(key) or '')
        if ident and ident not in seen:
            seen[ident] = doc
    items = list(seen.values())[:q.limit]
    return jsonify({'status': 'success', 'count': len(items), 'results': items})
