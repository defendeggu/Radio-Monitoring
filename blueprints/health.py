"""
Health endpoints.

/health        liveness (process is up) — used by the container healthcheck
/health/ready  readiness: Redis, storage backend and SDR lock state
"""

from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify

import config
import redis_client
import sdr_lock
from api_docs import api
from version import __version__

health_bp = Blueprint('health', __name__)


@health_bp.get('/health')
@api('Liveness check', tags=['System'])
def health() -> Response:
    return jsonify({
        'status': 'healthy',
        'service': 'radio-transcription-api',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': __version__,
    })


@health_bp.get('/health/ready')
@api('Readiness check (Redis, storage, SDR)', tags=['System'], responses={503: 'A dependency is down'})
def ready() -> tuple[Response, int]:
    from storage import get_storage

    redis_ok = redis_client.ping()
    try:
        storage = get_storage().health_check()
    except Exception:
        storage = {'status': 'error'}
    storage_ok = storage.get('status') in ('green', 'yellow')
    holder = sdr_lock.current_holder() if redis_ok else None
    ok = redis_ok and storage_ok
    return jsonify({
        'status': 'ready' if ok else 'degraded',
        'version': __version__,
        'checks': {
            'redis': 'ok' if redis_ok else 'down',
            'storage': {'backend': config.STORAGE_BACKEND, **storage},
            'sdr': {'busy': holder is not None, 'holder': holder},
        },
    }), 200 if ok else 503
