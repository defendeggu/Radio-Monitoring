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

# Blueprints are imported from their respective modules
# They will be registered in api_service.py

__all__ = [
    'health_bp',
    'sdr_bp',
    'capture_bp',
    'stats_bp',
    'aprs_bp',
    'pocsag_bp',
    'repeater_bp',
    'streaming_bp'
]
