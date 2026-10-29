"""
Capture and transcription endpoints.

POST /capture-and-transcribe   capture + decode/transcribe (async, HTTP 202)
POST /capture                  capture audio only (async, HTTP 202)
GET  /capture-status/<id>      poll a capture job
POST /transcribe               transcribe an existing recording
GET  /captures/<uuid>          one stored capture
GET  /search                   search stored captures
"""

import logging
import os
import re

from flask import Blueprint, Response, jsonify

from radiomoni import actions
from radiomoni.api_docs import api, parse_body, parse_query
from radiomoni.errors import ApiError, call_action
from radiomoni.jobs import get_capture_session
from radiomoni.schemas import CaptureRequest, RawCaptureRequest, SearchQuery, TranscribeRequest
from radiomoni.services import get_transcription_service, validate_file_path
from radiomoni.storage import get_storage

logger = logging.getLogger(__name__)
capture_bp = Blueprint('capture', __name__)

UUID_RE = re.compile(r'^[0-9a-fA-F-]{8,64}$')


@capture_bp.post('/capture-and-transcribe')
@api('Capture and decode (voice/aprs/pocsag) — returns a job id', tags=['Capture'], body=CaptureRequest,
     responses={202: 'Job queued', 409: 'SDR busy'})
def capture_and_transcribe() -> tuple[Response, int]:
    """Poll GET /capture-status/{capture_id} for progress and result."""
    req = parse_body(CaptureRequest)
    return jsonify(call_action(actions.start_capture, req)), 202


@capture_bp.post('/capture')
@api('Capture audio without decoding — returns a job id', tags=['Capture'], body=RawCaptureRequest,
     responses={202: 'Job queued', 409: 'SDR busy'})
def capture() -> tuple[Response, int]:
    raw = parse_body(RawCaptureRequest)
    req = CaptureRequest.model_validate({**raw.model_dump(), 'mode': 'raw'})
    return jsonify(call_action(actions.start_capture, req)), 202


@capture_bp.get('/capture-status/<capture_id>')
@api('Status and result of a capture job', tags=['Capture'], responses={404: 'Unknown or expired'})
def get_capture_status(capture_id: str) -> Response:
    if not UUID_RE.match(capture_id):
        raise ApiError('Invalid capture id', 400)
    session = get_capture_session(capture_id)
    if not session:
        raise ApiError('Capture session not found or expired', 404)
    return jsonify(session)


@capture_bp.post('/transcribe')
@api('Transcribe an existing recording', tags=['Capture'], body=TranscribeRequest)
def transcribe() -> Response:
    req = parse_body(TranscribeRequest)
    try:
        audio_file = validate_file_path(req.audio_file)
    except ValueError as e:
        raise ApiError(str(e), 403)
    if not os.path.isfile(audio_file):
        raise ApiError('Audio file not found', 404)
    result = get_transcription_service().transcribe(audio_file, req.language, task=req.task,
                                                    beam_size=req.beam_size, vad_filter=req.vad_filter,
                                                    initial_prompt=req.initial_prompt)
    return jsonify({'status': 'success', 'result': result})


@capture_bp.get('/captures/<capture_id>')
@api('A stored capture by UUID', tags=['Capture'], responses={404: 'Not found'})
def get_capture(capture_id: str) -> Response:
    if not UUID_RE.match(capture_id):
        raise ApiError('Invalid capture id', 400)
    result = get_storage().get_capture_by_id(capture_id)
    if result is None:
        raise ApiError('Capture not found', 404)
    return jsonify({'status': 'success', 'capture': result})


@capture_bp.get('/search')
@api('Search stored captures (full text and filters)', tags=['Capture'], query=SearchQuery)
def search_captures() -> Response:
    q = parse_query(SearchQuery)
    results = get_storage().search_captures(
        query=q.query, frequency_min=q.freq_min, frequency_max=q.freq_max, modulation=q.modulation,
        language=q.language, sdr_type=q.sdr_type, hours=q.hours, limit=q.limit, offset=q.offset, mode=q.mode)
    return jsonify({'status': 'success', 'count': results['total'], 'results': results['hits']})
