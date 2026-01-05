"""
Flask Blueprints for Radio Monitoring System API

This package contains modular blueprints for organizing API endpoints:
- health: Health check and system status
- sdr: SDR hardware detection and management
- capture: Audio capture and transcription
- stats: Statistics and search
- aprs: APRS decoder endpoints
- pocsag: POCSAG decoder endpoints
- repeater: Repeater scanning endpoints
- streaming: Streaming decoder endpoints
"""

from flask import Blueprint

# Import blueprints for type checking
from blueprints.health import health_bp  # type: ignore[import-not-found]
from blueprints.sdr import sdr_bp  # type: ignore[import-not-found]
from blueprints.capture import capture_bp  # type: ignore[import-not-found]
from blueprints.aprs import aprs_bp  # type: ignore[import-not-found]
from blueprints.pocsag import pocsag_bp  # type: ignore[import-not-found]
from blueprints.repeater import repeater_bp  # type: ignore[import-not-found]
from blueprints.streaming import streaming_bp  # type: ignore[import-not-found]

__all__ = [
    'health_bp',
    'sdr_bp',
    'capture_bp',
    'aprs_bp',
    'pocsag_bp',
    'repeater_bp',
    'streaming_bp'
]
