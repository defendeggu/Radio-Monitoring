"""
Uniform error handling.

Endpoints raise ApiError (or let pydantic ValidationError / SdrBusyError
propagate); the handlers here turn them into JSON. Unexpected exceptions are
logged with the correlation ID and answered with a generic message, so stack
details and file paths never reach the client.
"""

import logging
from typing import Any, Callable, Optional, TypeVar

from flask import Flask, Response, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from logging_config import get_correlation_id
from sdr_lock import SdrBusyError

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An error that is safe to show to the client."""

    def __init__(self, message: str, status: int = 400, **extra: Any):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra


def error_response(message: str, status: int, **extra: Any) -> tuple[Response, int]:
    body: dict[str, Any] = {'error': message, 'correlation_id': get_correlation_id()}
    body.update(extra)
    return jsonify(body), status


def _format_validation(e: ValidationError) -> list[dict[str, Any]]:
    return [
        {'field': '.'.join(str(p) for p in err['loc']) or 'body', 'message': err['msg']}
        for err in e.errors(include_url=False, include_input=False)
    ]


def init_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(e: ApiError) -> tuple[Response, int]:
        return error_response(e.message, e.status, **e.extra)

    @app.errorhandler(ValidationError)
    def _validation_error(e: ValidationError) -> tuple[Response, int]:
        details = _format_validation(e)
        first = details[0] if details else {'field': 'body', 'message': 'invalid'}
        return error_response(f"{first['field']}: {first['message']}", 400, details=details)

    @app.errorhandler(SdrBusyError)
    def _busy(e: SdrBusyError) -> tuple[Response, int]:
        return error_response(str(e), 409, holder=e.holder)

    @app.errorhandler(HTTPException)
    def _http_error(e: HTTPException) -> tuple[Response, int]:
        return error_response(e.description or e.name, e.code or 500)

    @app.errorhandler(Exception)
    def _unexpected(e: Exception) -> tuple[Response, int]:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return error_response('Internal server error', 500)


def internal_error(e: Exception, context: Optional[str] = None) -> tuple[Response, int]:
    """Log an unexpected error and return a generic 500 (for explicit try/except blocks)."""
    logger.error(f"{context or 'Request failed'}: {e}", exc_info=True)
    return error_response('Internal server error', 500)


T = TypeVar('T')


def call_action(fn: Callable[..., T], *args: Any) -> T:
    """
    Run an SDR action and map expected failures to client errors:
    busy → 409, bad parameters/disk full → 400, nothing found → 404,
    hardware/tool missing → 503.
    """
    try:
        return fn(*args)
    except SdrBusyError:
        raise
    except LookupError as e:
        raise ApiError(str(e), 404)
    except (ValueError, OSError) as e:
        raise ApiError(str(e), 400)
    except RuntimeError as e:
        raise ApiError(str(e), 503)
