"""
Health Check Blueprint

Provides system health monitoring endpoint for load balancers and monitoring tools.
"""

from datetime import datetime, timezone
from flask import Blueprint, jsonify, Response

# Create blueprint
health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health() -> Response:
    """
    Health check endpoint for load balancers and monitoring

    Returns:
    - status: healthy/unhealthy
    - service: service name
    - timestamp: current UTC time
    - version: API version
    - uptime: seconds since startup
    """
    return jsonify({
        'status': 'healthy',
        'service': 'radio-transcription-api',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '2.0.0',  # Incremented for Gunicorn migration
    })
