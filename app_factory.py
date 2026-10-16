"""
Flask application factory.

    app = create_app()

Wires up logging, security (auth/CORS/headers), error handlers, blueprints,
the OpenAPI document, the control-channel listener and the scheduler.
"""

import logging
import os
import threading
import uuid
from typing import Any

from flask import Flask, Response, jsonify, request

import config
from logging_config import clear_correlation_id, get_correlation_id, set_correlation_id, setup_logging

logger = logging.getLogger(__name__)

_background_started = False
_background_lock = threading.Lock()


def _handle_control(message: dict[str, Any]) -> None:
    """Commands broadcast by other API processes (see events.send_control)."""
    from blueprints.sdr import stop_all_local_decoders
    from blueprints.streaming import stop_session

    command = message.get('command')
    if command == 'stop' and message.get('session_id'):
        stop_session(str(message['session_id']))
    elif command == 'stop_all':
        stop_all_local_decoders()


def start_background_services() -> None:
    """Scheduler and control listener — once per process, never in tests."""
    global _background_started
    with _background_lock:
        if _background_started:
            return
        _background_started = True
    import events
    import scheduler
    events.start_control_listener(_handle_control)
    try:
        scheduler.start()
    except Exception as e:
        logger.error(f"Scheduler could not start: {e}", exc_info=True)


def create_app(start_background: bool = True) -> Flask:
    setup_logging(log_level=os.getenv('LOG_LEVEL', 'INFO'),
                  json_format=os.getenv('JSON_LOGGING', 'true').lower() == 'true')

    from security import check_startup_security, init_security
    check_startup_security()

    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024   # JSON bodies only
    app.json.sort_keys = False  # type: ignore[attr-defined]

    @app.before_request
    def _correlation() -> None:
        incoming = request.headers.get('X-Correlation-ID', '')
        cid = incoming if 0 < len(incoming) <= 64 and incoming.replace('-', '').isalnum() else str(uuid.uuid4())
        set_correlation_id(cid)
        if request.path != '/health':
            logger.info('Request started', extra={'method': request.method, 'path': request.path,
                                                  'remote_addr': request.remote_addr})

    @app.after_request
    def _correlation_header(response: Response) -> Response:
        response.headers['X-Correlation-ID'] = get_correlation_id()
        if request.path != '/health':
            logger.info('Request completed', extra={'status_code': response.status_code})
        clear_correlation_id()
        return response

    init_security(app)

    from errors import init_error_handlers
    init_error_handlers(app)

    from blueprints import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    from api_docs import api, build_openapi

    @app.get('/openapi.json')
    @api('OpenAPI document of this API', tags=['System'])
    def openapi() -> Response:
        return jsonify(build_openapi(app))

    os.makedirs(config.RECORDING_DIR, exist_ok=True)
    if start_background and not config.REDIS_FAKE:
        start_background_services()
    logger.info("Application initialization complete")
    return app
