"""
SDR Hardware Blueprint

Provides endpoints for SDR hardware detection and capabilities.
"""

from flask import Blueprint, jsonify, Response
from sdr_hardware import get_sdr_instance, detect_sdr, SDRType

# Create blueprint
sdr_bp = Blueprint('sdr', __name__)


@sdr_bp.route('/sdr/detect', methods=['GET'])
def detect_sdr_hardware() -> Response | tuple[Response, int]:
    """
    Detect available SDR hardware and return capabilities

    Returns:
        JSON response with SDR type and frequency range
    """
    try:
        sdr_type = detect_sdr()

        if sdr_type == SDRType.UNKNOWN:
            return jsonify({
                'error': 'No SDR hardware detected',
                'message': 'Please connect HackRF One or RTL-SDR device'
            }), 404

        # Create temporary instance to get capabilities
        instance = get_sdr_instance(frequency=100_000_000, sdr_type=sdr_type)
        min_freq, max_freq = instance.get_frequency_range()
        max_rate = instance.get_max_sample_rate()

        return jsonify({
            'type': sdr_type.value,
            'frequency_range': {
                'min_hz': min_freq,
                'max_hz': max_freq,
                'min_mhz': min_freq / 1e6,
                'max_mhz': max_freq / 1e6
            },
            'max_sample_rate_hz': max_rate,
            'max_sample_rate_mhz': max_rate / 1e6
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
