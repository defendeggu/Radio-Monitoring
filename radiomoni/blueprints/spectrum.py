"""
Spectrum / waterfall endpoints: start, live binary stream, retune.

The stream also serves the waterfall of running VOX and CW sessions (they feed
a SpectrumTap). Stopping goes through DELETE /stream-decode/<id> like every
other session.
"""

import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request, stream_with_context

from radiomoni import actions
from radiomoni import events
from radiomoni.api_docs import api, parse_body
from radiomoni.decoders import spectrum
from radiomoni.errors import ApiError, call_action
from radiomoni.schemas import SpectrumRequest, TuneRequest
from radiomoni.session_store import session_manager

logger = logging.getLogger(__name__)
spectrum_bp = Blueprint('spectrum', __name__)


def _running(session_id: str) -> bool:
    session = session_manager.get_session(session_id)
    return session is not None and session.status in ('starting', 'running')


@spectrum_bp.post('/spectrum')
@api('Start the spectrum / waterfall view (gives way to every other SDR job)', tags=['Spectrum'],
     body=SpectrumRequest, responses={409: 'SDR busy', 503: 'No SDR detected'})
def start_spectrum() -> Response:
    req = parse_body(SpectrumRequest)
    result = call_action(actions.start_spectrum, req)
    return jsonify({'status': 'success', **result})


@spectrum_bp.get('/spectrum/<session_id>')
@api('Current state of a waterfall (centre, bandwidth, listening channel)', tags=['Spectrum'],
     responses={404: 'Unknown session'})
def get_spectrum(session_id: str) -> Response:
    state = spectrum.load_state(session_id)
    if state is None:
        raise ApiError('Session has no waterfall', 404)
    return jsonify({'status': 'success', 'running': _running(session_id), 'state': state})


@spectrum_bp.get('/spectrum/<session_id>/stream')
@api('Binary live stream: waterfall rows, audio, state (application/octet-stream)', tags=['Spectrum'],
     description='Frames: u8 type, u32 length, payload — 1 spectrum, 2 audio (only with ?audio=1), 3 JSON.',
     responses={404: 'Unknown session'})
def stream_spectrum(session_id: str) -> Response:
    if session_manager.get_session(session_id) is None:
        raise ApiError('Session not found', 404)
    listen = request.args.get('audio') in ('1', 'true')
    body = stream_with_context(spectrum.stream_frames(session_id, listen, lambda: _running(session_id)))
    response = Response(body, mimetype='application/octet-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


def tune_session(session_id: str, req: TuneRequest, allow_outside: bool = False) -> dict[str, Any]:
    """
    Validate a retune against the session state and hand it to the decoder (local or remote).
    With allow_outside, a channel outside the bandwidth is passed on and the session moves
    its centre itself (CW: keeps its offset from the DC spike).
    """
    state = spectrum.load_state(session_id)
    if state is None or not _running(session_id):
        raise ApiError('Session is not running', 409)
    if not state.get('tunable'):
        raise ApiError('This session cannot be retuned', 409)
    centre = req.centre if req.centre is not None else int(state['centre'])
    channel = req.channel if req.channel is not None else int(state.get('channel') or centre)
    if req.centre is not None and req.channel is None and abs(channel - centre) > state['span'] * 0.45:
        channel = centre
    if abs(channel - centre) > state['span'] * 0.45:
        if not allow_outside:
            raise ApiError('Frequency is outside the visible bandwidth — move the centre first', 400)
        offset = state.get('dc_offset')
        centre = channel + (int(offset) if offset is not None else int(state['centre']) - int(state.get('channel') or state['centre']))
    changes: dict[str, Any] = {k: v for k, v in req.model_dump().items()
                               if v is not None and k not in ('squelch_off',)}
    changes['channel'] = channel
    if req.squelch_off:
        changes['squelch_db'] = None
    decoder = session_manager.get_decoder(session_id)
    if decoder is not None and hasattr(decoder, 'tune'):
        decoder.tune(**changes)
    else:
        events.send_control('tune', session_id=session_id, changes=changes)
    return {**state, **{k: v for k, v in changes.items() if k != 'squelch_db'}, 'centre': centre,
            'squelch_db': changes.get('squelch_db', state.get('squelch_db'))}


@spectrum_bp.post('/spectrum/<session_id>/tune')
@api('Retune a waterfall: centre frequency, listening channel, modulation, squelch', tags=['Spectrum'],
     body=TuneRequest, responses={400: 'Outside the bandwidth', 409: 'Session not running'})
def tune_spectrum(session_id: str) -> Response:
    req = parse_body(TuneRequest)
    return jsonify({'status': 'success', 'state': tune_session(session_id, req)})
