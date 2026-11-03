"""
Live CW (Morse) decoder: start, retune, stored transmissions.

Text arrives as live events ("cw"); the waterfall and the audio of a CW session
come over GET /spectrum/<id>/stream. Stopping goes through DELETE /stream-decode/<id>.
"""

from flask import Blueprint, Response, jsonify

from radiomoni import actions
from radiomoni.api_docs import api, parse_body, parse_query
from radiomoni.blueprints.spectrum import tune_session
from radiomoni.errors import call_action
from radiomoni.schemas import CwRequest, CwSearchQuery, TuneRequest
from radiomoni.storage.base import get_storage

cw_bp = Blueprint('cw', __name__)


@cw_bp.post('/cw/start')
@api('Start the live CW decoder on a frequency', tags=['CW'], body=CwRequest,
     responses={409: 'SDR busy', 503: 'No SDR detected'})
def start_cw() -> Response:
    req = parse_body(CwRequest)
    result = call_action(actions.start_cw, req)
    return jsonify({'status': 'success', 'message': 'CW decoder started', **result})


@cw_bp.post('/cw/<session_id>/tune')
@api('Retune a running CW decoder (e.g. to an RBN spot); no restart inside the bandwidth', tags=['CW'],
     body=TuneRequest, responses={400: 'Invalid frequency', 409: 'Session not running'})
def tune_cw(session_id: str) -> Response:
    req = parse_body(TuneRequest)
    if req.channel is not None and req.centre is None:
        # outside the bandwidth the session moves its centre itself (with its DC offset)
        state = tune_session(session_id, req.model_copy(update={'centre': None}), allow_outside=True)
    else:
        state = tune_session(session_id, req)
    return jsonify({'status': 'success', 'state': state})


@cw_bp.get('/cw/transmissions')
@api('Stored CW transmissions (decoded text, callsigns, speed)', tags=['CW'], query=CwSearchQuery)
def list_transmissions() -> Response:
    q = parse_query(CwSearchQuery)
    hits = get_storage().search_events('cw', hours=q.hours, limit=q.limit if not q.call else 1000)['hits']
    if q.call:
        call = q.call.upper()
        hits = [h for h in hits if any(call in c for c in h.get('callsigns') or [])][:q.limit]
    return jsonify({'status': 'success', 'count': len(hits), 'transmissions': hits})
