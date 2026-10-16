"""
Recording files: list, download/stream (for the audio player), delete.

Only file names are exposed — never server paths.
"""

import os
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, send_file

from api_docs import api
from errors import ApiError
from jobs import cleanup_recordings, recordings_stats
from services import recording_dir, safe_recording_path

recordings_bp = Blueprint('recordings', __name__)

AUDIO_TYPES = {'.wav': 'audio/wav', '.json': 'application/json'}


def _list(extensions: tuple[str, ...] = ('.wav',)) -> list[dict[str, object]]:
    directory = recording_dir()
    if not os.path.isdir(directory):
        return []
    files = []
    for name in os.listdir(directory):
        if not name.endswith(extensions):
            continue
        stat = os.stat(os.path.join(directory, name))
        base = name.rsplit('.', 1)[0]
        files.append({
            'filename': name,
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            'has_transcript': os.path.exists(os.path.join(directory, base + '.json')),
        })
    files.sort(key=lambda f: str(f['created']), reverse=True)
    return files


@recordings_bp.get('/recordings')
@api('List recordings', tags=['Recordings'])
def list_recordings() -> Response:
    return jsonify({'recordings': _list(), 'stats': recordings_stats()})


@recordings_bp.get('/list-recordings')
@api('List recordings (legacy alias of /recordings)', tags=['Recordings'], deprecated=True)
def list_recordings_legacy() -> Response:
    return jsonify({'recordings': _list()})


@recordings_bp.get('/recordings/<filename>')
@api('Download a recording (WAV) or its transcript (JSON)', tags=['Recordings'], responses={404: 'Not found'})
def get_recording(filename: str) -> Response:
    try:
        path = safe_recording_path(filename)
    except ValueError as e:
        raise ApiError(str(e), 400)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in AUDIO_TYPES or not os.path.isfile(path):
        raise ApiError('Recording not found', 404)
    response = send_file(path, mimetype=AUDIO_TYPES[ext], conditional=True, download_name=filename)
    response.headers['Cache-Control'] = 'private, max-age=3600'
    return response


@recordings_bp.delete('/recordings/<filename>')
@api('Delete a recording and its transcript', tags=['Recordings'], responses={404: 'Not found'})
def delete_recording(filename: str) -> Response:
    try:
        path = safe_recording_path(filename)
    except ValueError as e:
        raise ApiError(str(e), 400)
    if not os.path.isfile(path):
        raise ApiError('Recording not found', 404)
    os.remove(path)
    transcript = path.rsplit('.', 1)[0] + '.json'
    if os.path.isfile(transcript):
        os.remove(transcript)
    return jsonify({'status': 'deleted', 'filename': filename})


@recordings_bp.post('/recordings/cleanup')
@api('Apply the retention policy now', tags=['Recordings'])
def run_cleanup() -> Response:
    return jsonify({'removed': cleanup_recordings()})
