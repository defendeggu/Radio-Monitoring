"""
Read access to ADS-B, AIS and ISM sensor data plus decoder availability.
"""

from typing import Any, Optional

from flask import Blueprint, Response, jsonify

from radiomoni import airsquitter
from radiomoni.api_docs import api, parse_query
from radiomoni.errors import ApiError
from radiomoni.decoders.external import DEFAULT_FREQUENCIES, TOOLS, tool_available
from radiomoni.schemas import EventSearchQuery
from radiomoni.storage.base import get_storage

decoders_bp = Blueprint('decoders', __name__)

KINDS = ('adsb', 'ais', 'ism')
OWN_RECEIVER = 'radiomoni'


def _receiver_filter(docs: list[dict[str, Any]], receiver: Optional[str]) -> list[dict[str, Any]]:
    """ADS-B documents of one receiver; documents without `receiver` (before 5.8.0) are the own SDR."""
    if not receiver:
        return docs
    return [d for d in docs if (d.get('receiver') or OWN_RECEIVER) == receiver]


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
    if q.receiver and q.receiver != OWN_RECEIVER:
        term['receiver'] = q.receiver
    limit = q.limit if q.receiver != OWN_RECEIVER else min(q.limit * 10, 5000)
    results = get_storage().search_events(kind, hours=q.hours, limit=limit, term=term or None)
    if q.receiver == OWN_RECEIVER:
        hits = _receiver_filter(results['hits'], q.receiver)[:q.limit]
        return jsonify({'status': 'success', 'count': len(hits), 'results': hits})
    return jsonify({'status': 'success', 'count': results['total'], 'results': results['hits']})


@decoders_bp.get('/decoders/<kind>/latest')
@api('Latest document per aircraft / ship / sensor', tags=['Decoders'], query=EventSearchQuery)
def latest(kind: str) -> Response:
    if kind not in KINDS:
        raise ApiError('Unknown decoder', 404)
    q = parse_query(EventSearchQuery)
    key = {'adsb': 'icao', 'ais': 'mmsi', 'ism': 'sensor_id'}[kind]
    hits = get_storage().search_events(kind, hours=q.hours, limit=min(q.limit * 20, 5000))['hits']
    hits = _receiver_filter(hits, q.receiver)
    seen: dict[str, dict[str, Any]] = {}
    for doc in hits:  # newest first
        ident = str(doc.get(key) or '')
        if ident and ident not in seen:
            seen[ident] = doc
    items = list(seen.values())[:q.limit]
    return jsonify({'status': 'success', 'count': len(items), 'results': items})


@decoders_bp.get('/decoders/airsquitter/status')
@api('Jetvision AirSquitter / Radarcape as network ADS-B source: reachable, aircraft by ADS-B / MLAT / FLARM',
     tags=['Decoders'])
def airsquitter_status() -> Response:
    return jsonify({'status': 'success', **airsquitter.status()})
