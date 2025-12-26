#!/usr/bin/env python3
"""
Flask API Service for Radio Transcription
Provides REST API endpoints for N8N integration
"""

import os
import json
import time
from datetime import datetime
from typing import TypedDict, Any
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, Histogram, Gauge
from radio_capture import HackRFCapture
from transcription_service import TranscriptionService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class CaptureRequest(TypedDict, total=False):
    """Type definition for capture request parameters"""
    frequency: float
    modulation: str
    duration: int
    gain: int
    sample_rate: int


class TranscribeRequest(TypedDict, total=False):
    """Type definition for transcribe request parameters"""
    audio_file: str
    language: str | None


class RecordingInfo(TypedDict):
    """Type definition for recording file information"""
    filename: str
    path: str
    size: int
    created: str


app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, group_by='endpoint')

# Custom Prometheus metrics
radio_captures_total = Counter(
    'radio_captures_total',
    'Total radio captures',
    ['modulation', 'status']
)

radio_capture_duration = Histogram(
    'radio_capture_duration_seconds',
    'Radio capture duration in seconds',
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

radio_simulation_mode = Gauge(
    'radio_simulation_mode',
    'Whether in simulation mode (1) or real hardware (0)'
)

transcription_requests_total = Counter(
    'transcription_requests_total',
    'Total transcription requests',
    ['status']
)

transcription_duration = Histogram(
    'transcription_duration_seconds',
    'Transcription duration in seconds',
    buckets=[1, 5, 10, 30, 60, 120]
)

# Configuration
RECORDING_DIR = os.getenv('AUDIO_OUTPUT_DIR', './recordings')
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
WHISPER_DEVICE = os.getenv('WHISPER_DEVICE', 'cpu')
WHISPER_COMPUTE_TYPE = os.getenv('WHISPER_COMPUTE_TYPE', 'int8')

# Initialize transcription service
transcription_service: TranscriptionService | None = None


def get_transcription_service() -> TranscriptionService:
    """Lazy load transcription service"""
    global transcription_service
    if transcription_service is None:
        transcription_service = TranscriptionService(
            model=WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE
        )
    return transcription_service


@app.route('/health', methods=['GET'])
def health() -> Response:
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'radio-transcription-api',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/capture', methods=['POST'])
def capture() -> Response | tuple[Response, int]:
    """
    Capture radio signal

    Request body:
    {
        "frequency": 100000000,
        "modulation": "FM",
        "duration": 30,
        "gain": 20,
        "sample_rate": 2000000
    }
    """
    try:
        data = request.get_json()

        # Validate required parameters
        if 'frequency' not in data:
            return jsonify({'error': 'frequency is required'}), 400

        frequency = float(data['frequency'])
        modulation = data.get('modulation', 'FM')
        duration = int(data.get('duration', 30))
        gain = int(data.get('gain', 20))
        sample_rate = int(data.get('sample_rate', 2000000))

        # Generate output filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.wav')

        # Create capture instance
        capture_instance = HackRFCapture(
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain,
            modulation=modulation
        )

        # Perform capture with metrics
        start_time = time.time()
        capture_instance.capture(duration, output_file)
        capture_duration_seconds = time.time() - start_time

        # Record metrics
        radio_captures_total.labels(modulation=modulation, status='success').inc()
        radio_capture_duration.observe(capture_duration_seconds)

        return jsonify({
            'status': 'success',
            'audio_file': output_file,
            'frequency': frequency,
            'modulation': modulation,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        # Record failure metric
        radio_captures_total.labels(modulation=modulation if 'modulation' in locals() else 'unknown', status='failure').inc()
        return jsonify({'error': str(e)}), 500


@app.route('/transcribe', methods=['POST'])
def transcribe() -> Response | tuple[Response, int]:
    """
    Transcribe audio file

    Request body:
    {
        "audio_file": "path/to/audio.wav",
        "language": "en"  # optional
    }
    """
    try:
        data = request.get_json()

        # Validate required parameters
        if 'audio_file' not in data:
            return jsonify({'error': 'audio_file is required'}), 400

        audio_file = data['audio_file']
        language = data.get('language')

        # Get transcription service
        service = get_transcription_service()

        # Transcribe with metrics
        start_time = time.time()
        result = service.transcribe(audio_file, language)
        transcription_duration_seconds = time.time() - start_time

        # Record metrics
        transcription_requests_total.labels(status='success').inc()
        transcription_duration.observe(transcription_duration_seconds)

        return jsonify({
            'status': 'success',
            'result': result
        })

    except FileNotFoundError as e:
        transcription_requests_total.labels(status='failure').inc()
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        transcription_requests_total.labels(status='failure').inc()
        return jsonify({'error': str(e)}), 500


@app.route('/capture-and-transcribe', methods=['POST'])
def capture_and_transcribe() -> Response | tuple[Response, int]:
    """
    Capture radio signal and transcribe in one step

    Request body:
    {
        "frequency": 100000000,
        "modulation": "FM",
        "duration": 30,
        "gain": 20,
        "sample_rate": 2000000,
        "language": "en"  # optional
    }
    """
    try:
        data = request.get_json()

        # Validate required parameters
        if 'frequency' not in data:
            return jsonify({'error': 'frequency is required'}), 400

        frequency = float(data['frequency'])
        modulation = data.get('modulation', 'FM')
        duration = int(data.get('duration', 30))
        gain = int(data.get('gain', 20))
        sample_rate = int(data.get('sample_rate', 2000000))
        language = data.get('language')

        # Generate output filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.wav')
        json_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.json')

        # Step 1: Capture
        capture_instance = HackRFCapture(
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain,
            modulation=modulation
        )
        capture_instance.capture(duration, audio_file)

        # Step 2: Transcribe
        service = get_transcription_service()
        transcription_result = service.transcribe_and_save(
            audio_file,
            json_file,
            language
        )

        return jsonify({
            'status': 'success',
            'capture': {
                'audio_file': audio_file,
                'frequency': frequency,
                'modulation': modulation,
                'duration': duration
            },
            'transcription': transcription_result,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/list-recordings', methods=['GET'])
def list_recordings() -> Response | tuple[Response, int]:
    """List all recordings in the recordings directory"""
    try:
        if not os.path.exists(RECORDING_DIR):
            return jsonify({'recordings': []})

        files = []
        for filename in os.listdir(RECORDING_DIR):
            if filename.endswith('.wav'):
                filepath = os.path.join(RECORDING_DIR, filename)
                stat = os.stat(filepath)
                files.append({
                    'filename': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })

        # Sort by creation time (newest first)
        files.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({'recordings': files})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def main() -> None:
    # Create recordings directory
    os.makedirs(RECORDING_DIR, exist_ok=True)

    # Run Flask app
    port = int(os.getenv('API_PORT', '5000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    # Note: Debug mode disabled by default for Prometheus metrics compatibility
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)


if __name__ == '__main__':
    main()
