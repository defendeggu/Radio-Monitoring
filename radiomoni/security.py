"""
API authentication, CORS and HTTP hardening.

Rules:
- Every route except PUBLIC_PATHS needs a valid X-API-Key header. Exception: a
  WAV recording with a valid signed link (?sig=, see recording_links), and
  METRICS_API_KEY, which only opens GET /metrics/* (Metricbeat).
- Without configured API keys the API refuses to start, unless ALLOW_INSECURE=true
  is set explicitly (local development / tests).
- Only loopback is trusted by default. Additional networks must be listed in
  TRUSTED_IPS. The Docker bridge network is NOT trusted: every container on it
  (and, depending on the Docker setup, every forwarded host connection) would
  otherwise bypass authentication.
- Behind nginx, the real client address comes from X-Forwarded-For (ProxyFix).
"""

import hmac
import ipaddress
import logging
from typing import Optional

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from radiomoni import config, recording_links

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {'/health', '/health/ready', '/openapi.json'}


class InsecureConfigurationError(RuntimeError):
    """Raised at startup when authentication is not configured."""


def _parse_trusted(entries: list[str]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.warning(f"Ignoring invalid TRUSTED_IPS entry: {entry!r}")
    return networks


def is_trusted_ip(ip_address: Optional[str], trusted: Optional[list[str]] = None) -> bool:
    """True for loopback and for addresses inside an explicitly trusted network."""
    if not ip_address:
        return False
    try:
        ip = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    if ip.is_loopback:
        return True
    networks = _parse_trusted(config.TRUSTED_IPS if trusted is None else trusted)
    return any(ip in net for net in networks)


def is_valid_api_key(candidate: Optional[str], keys: Optional[list[str]] = None) -> bool:
    """Constant-time comparison against every configured key."""
    if not candidate:
        return False
    valid = False
    for key in (config.API_KEYS if keys is None else keys):
        # compare all keys so timing does not reveal which one matched
        if hmac.compare_digest(candidate.encode(), key.encode()):
            valid = True
    return valid


def auth_enabled() -> bool:
    return bool(config.API_KEYS)


def check_startup_security() -> None:
    """Fail closed: no keys and no explicit opt-out means no start."""
    if config.API_KEYS:
        short = [k for k in config.API_KEYS if len(k) < 32]
        if short:
            logger.warning(f"{len(short)} API key(s) shorter than 32 characters — regenerate them")
        return
    if config.ALLOW_INSECURE:
        logger.warning("=" * 70)
        logger.warning("ALLOW_INSECURE=true and no API_KEYS: the API is UNAUTHENTICATED.")
        logger.warning("Use this only for local development.")
        logger.warning("=" * 70)
        return
    raise InsecureConfigurationError(
        "No API_KEYS configured. Generate keys with 'python3 scripts/generate_api_keys.py' "
        "or set ALLOW_INSECURE=true for local development."
    )


def init_security(app: Flask) -> None:
    """Install ProxyFix, CORS, auth check and security headers."""
    if config.PROXY_COUNT > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=config.PROXY_COUNT, x_proto=config.PROXY_COUNT)  # type: ignore[method-assign]

    # The web UI is served same-origin through nginx (/api/), so CORS is off by
    # default. Set CORS_ORIGINS for other origins (e.g. the Vite dev server).
    if config.CORS_ORIGINS:
        CORS(app, origins=config.CORS_ORIGINS, allow_headers=['Content-Type', 'X-API-Key', 'X-Correlation-ID'])

    @app.before_request
    def _check_api_key() -> Optional[tuple[Response, int]]:
        if request.method == 'OPTIONS' or request.path in PUBLIC_PATHS:
            return None
        if not auth_enabled():
            return None
        if is_trusted_ip(request.remote_addr):
            return None
        # signed link to one WAV file (audio player in Kibana, see recording_links)
        if request.method in ('GET', 'HEAD') and recording_links.is_signed_request(request.path,
                                                                                   request.args.get('sig')):
            return None
        api_key = request.headers.get('X-API-Key')
        # read-only metrics key (Metricbeat), valid for /metrics/* only
        if api_key and config.METRICS_API_KEY and request.method == 'GET' and request.path.startswith('/metrics/') \
                and hmac.compare_digest(api_key.encode(), config.METRICS_API_KEY.encode()):
            return None
        if not api_key:
            logger.warning(f"Unauthorized request to {request.path} from {request.remote_addr}: missing API key")
            return jsonify({'error': 'Missing API key', 'message': 'Please provide the X-API-Key header'}), 401
        if not is_valid_api_key(api_key):
            logger.warning(f"Forbidden request to {request.path} from {request.remote_addr}: invalid API key")
            return jsonify({'error': 'Invalid API key', 'message': 'The provided API key is not valid'}), 403
        return None

    @app.after_request
    def _security_headers(response: Response) -> Response:
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Cache-Control', 'no-store')
        return response
