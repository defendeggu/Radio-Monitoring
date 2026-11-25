"""
OnAir (on-air.dev) endpoints: status, modes, start/stop, stored messages, map, pictures.

OnAir runs in its own container; see radiomoni/onair and docs/onair.md.
"""

import logging
import os
from typing import Any

from flask import Blueprint, Response, jsonify, send_file

from radiomoni import config, events
from radiomoni.api_docs import api, parse_body, parse_query
from radiomoni.errors import ApiError, call_action
from radiomoni.onair import ATTRIBUTION, CONTRIBUTORS_URL, modes
from radiomoni.onair.client import OnAirClient, OnAirError, enabled
from radiomoni.onair.session import KIND
from radiomoni.schemas import HoursLimitQuery, OnAirRequest, OnAirSearchQuery
from radiomoni.session_store import session_manager
from radiomoni.storage.base import get_storage

logger = logging.getLogger(__name__)
onair_bp = Blueprint('onair', __name__)


def _sessions() -> list[dict[str, Any]]:
    session_manager.reap_orphaned_sessions()
    out = []
    for s in session_manager.list_sessions():
        if s.mode != KIND or s.status not in ('starting', 'running'):
            continue
        item = s.to_dict()
        decoder = session_manager.get_decoder(s.session_id)
        if decoder is not None:
            item.update(decoder.state())
            item['telemetry'] = decoder.telemetry
        out.append(item)
    return out


@onair_bp.get('/onair/status')
@api('OnAir: reachable, version, receiver and the running sessions', tags=['OnAir'])
def status() -> Response:
    info: dict[str, Any] = {'enabled': enabled(), 'attribution': ATTRIBUTION, 'contributors': CONTRIBUTORS_URL,
                            'sessions': _sessions()}
    if not enabled():
        return jsonify({'status': 'success', **info, 'reachable': False})
    client = OnAirClient(timeout=3.0)
    try:
        server = client.get('x/server')
        server = server if isinstance(server, dict) else {}
        info.update({'reachable': True, 'version': server.get('version'), 'autostart': server.get('autostart'),
                     'receiver': client.status()})
    except OnAirError as e:
        info.update({'reachable': False, 'error': str(e)})
    return jsonify({'status': 'success', **info})


@onair_bp.get('/onair/modes')
@api('OnAir modes RadioMoni offers, grouped (all of them with ONAIR_ALL_MODES)', tags=['OnAir'])
def list_modes() -> Response:
    try:
        offered = modes.offered(OnAirClient(timeout=5.0).modes())
    except OnAirError as e:
        raise ApiError(str(e), 503)
    return jsonify({'status': 'success', 'count': len(offered), 'groups': list(modes.GROUPS), 'modes': offered})


@onair_bp.post('/onair/start')
@api('Run an OnAir mode (takes the SDR lock; OnAir decodes, RadioMoni stores)', tags=['OnAir'], body=OnAirRequest,
     responses={409: 'SDR busy', 503: 'OnAir not set up or not reachable'})
def start() -> Response:
    from radiomoni import actions
    req = parse_body(OnAirRequest)
    return jsonify({'status': 'success', 'message': f'OnAir {req.mode} started',
                    **call_action(actions.start_onair, req)})


@onair_bp.post('/onair/stop')
@api('Stop every running OnAir session', tags=['OnAir'])
def stop() -> Response:
    from radiomoni.blueprints.streaming import stop_session
    stopped = []
    for s in _sessions():
        sid = s['session_id']
        if not stop_session(sid):
            events.send_control('stop', session_id=sid)
        stopped.append(sid)
    return jsonify({'status': 'success', 'stopped': stopped})


def _search_term(q: OnAirSearchQuery) -> dict[str, Any]:
    return {k: v for k, v in (('event_type', q.event_type), ('family', q.family), ('ident', q.ident),
                              ('session_id', q.session_id)) if v}


@onair_bp.get('/onair/search')
@api('Search stored OnAir messages', tags=['OnAir'], query=OnAirSearchQuery)
def search() -> Response:
    q = parse_query(OnAirSearchQuery)
    term = _search_term(q)
    results = get_storage().search_events(KIND, hours=q.hours, limit=q.limit, term=term or None)
    return jsonify({'status': 'success', 'count': results['total'], 'results': results['hits']})


def to_geojson(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Latest position per sender (sonde, aircraft, mesh node ...) with its track, newest first in `docs`."""
    latest: dict[str, dict[str, Any]] = {}
    tracks: dict[str, list[list[float]]] = {}
    for doc in docs:
        lat, lon = doc.get('latitude'), doc.get('longitude')
        if lat is None or lon is None:
            continue
        key = f"{doc.get('family')}:{doc.get('ident') or doc.get('text') or doc.get('uuid')}"
        latest.setdefault(key, doc)
        track = tracks.setdefault(key, [])
        if len(track) < 500:
            track.append([lon, lat])
    features = []
    for key, doc in latest.items():
        props = {'ident': doc.get('ident'), 'event_type': doc.get('event_type'), 'family': doc.get('family'),
                 'mode': doc.get('mode'), 'text': doc.get('text'), 'altitude': doc.get('altitude'),
                 'frequency': doc.get('frequency'), 'timestamp': doc.get('@timestamp') or doc.get('timestamp')}
        features.append({'type': 'Feature', 'geometry': {'type': 'Point',
                                                         'coordinates': [doc['longitude'], doc['latitude']]},
                         'properties': props})
        if len(tracks[key]) > 1:
            features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': tracks[key][::-1]},
                             'properties': {**props, 'track': True}})
    return {'type': 'FeatureCollection', 'features': features}


@onair_bp.get('/onair/map')
@api('OnAir positions as GeoJSON (latest per sender, with track)', tags=['OnAir'], query=HoursLimitQuery)
def map_data() -> Response:
    q = parse_query(HoursLimitQuery)
    hits = get_storage().search_events(KIND, hours=q.hours, limit=5000)['hits']
    return jsonify(to_geojson(hits))


@onair_bp.get('/onair/images/<doc_id>')
@api('A picture OnAir made (weather satellite, SSTV ...), by message id', tags=['OnAir'])
def image(doc_id: str) -> Response:
    if not doc_id.replace('-', '').isalnum() or len(doc_id) > 64:
        raise ApiError('Invalid id', 400)
    hits = get_storage().search_events(KIND, hours=24 * 400, limit=1, term={'uuid': doc_id})['hits']
    path = hits[0].get('image_path') if hits else None
    if not path:
        raise ApiError('Picture not found', 404)
    root = os.path.realpath(config.ONAIR_DATA_DIR)
    real = os.path.realpath(path)
    if not real.startswith(root + os.sep) or not real.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise ApiError('Picture not found', 404)
    if not os.path.isfile(real):
        raise ApiError('Picture no longer exists', 404)
    return send_file(real, mimetype='image/png' if real.lower().endswith('.png') else 'image/jpeg', conditional=True)


@onair_bp.get('/onair/link')
@api("Address and token of OnAir's own page (waterfall, Listen) behind the nginx proxy", tags=['OnAir'])
def link() -> Response:
    if not enabled():
        raise ApiError('OnAir is not set up', 503)
    return jsonify({'status': 'success', 'url': config.ONAIR_PUBLIC_URL or None, 'port': 8765,
                    'token': config.ONAIR_TOKEN})


@onair_bp.get('/metrics/onair')
@api("OnAir's receiver metrics (Prometheus text, passed on; empty when OnAir is off)", tags=['System'])
def metrics() -> Response:
    """For Metricbeat (monitoring/metricbeat/onair.yml): onair_receiver_running, frequency, load, dropped samples ..."""
    text = ''
    if enabled():
        try:
            text = str(OnAirClient(timeout=3.0).get('metrics'))
        except OnAirError as e:
            logger.debug(f"OnAir metrics: {e}")
    return Response(text, mimetype='text/plain', headers={'Cache-Control': 'no-store'})
