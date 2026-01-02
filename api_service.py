#!/usr/bin/env python3
"""
Flask API Service for Radio Transcription
Provides REST API endpoints for N8N integration
"""

import os
import json
import time
import threading
import logging
from datetime import datetime
import uuid
from typing import TypedDict, Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from itertools import count
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from sdr_hardware import get_sdr_instance, detect_sdr, SDRType
from transcription_service import TranscriptionService
from aprs_decoder_service import APRSDecoder
from pocsag_decoder_service import POCSAGDecoder
from elasticsearch_service import get_elasticsearch_service
from repeater_activity_analyzer import RepeaterActivityAnalyzer
from streaming_decoder_service import (
    StreamingAPRSDecoder,
    StreamingPOCSAGDecoder,
    SessionManager
)
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics removed - replaced by Metricbeat
# from prometheus_flask_exporter import PrometheusMetrics
# from prometheus_client import Counter, Histogram, Gauge

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

# ============================================================================
# API Security Configuration
# ============================================================================

# Load API keys from environment (comma-separated list)
API_KEYS = set(os.getenv('API_KEYS', '').split(','))
if not API_KEYS or API_KEYS == {''}:
    logger.warning("="*80)
    logger.warning("⚠️  WARNING: No API keys configured! API is UNSECURED!")
    logger.warning("⚠️  Set API_KEYS environment variable to secure the API")
    logger.warning("⚠️  Generate keys with: python3 scripts/generate_api_keys.py")
    logger.warning("="*80)
    API_KEYS = set()

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {'/health'}


def is_trusted_ip(ip_address):
    """
    Check if the request comes from a trusted source.

    Trusted sources:
    - localhost (127.0.0.1, ::1)
    - Docker network (172.16.0.0/12 - includes 172.18.0.0/16)
    - Private networks (10.0.0.0/8, 192.168.0.0/16)

    Args:
        ip_address: IP address string

    Returns:
        bool: True if IP is trusted, False otherwise
    """
    import ipaddress

    if not ip_address:
        return False

    try:
        ip = ipaddress.ip_address(ip_address)

        # Localhost
        if ip.is_loopback:
            return True

        # Docker networks (172.16.0.0/12 covers 172.16-172.31)
        docker_network = ipaddress.ip_network('172.16.0.0/12')
        if ip in docker_network:
            return True

        # Private networks
        private_networks = [
            ipaddress.ip_network('10.0.0.0/8'),
            ipaddress.ip_network('192.168.0.0/16'),
        ]

        for network in private_networks:
            if ip in network:
                return True

        return False
    except ValueError:
        # Invalid IP address
        return False


@app.before_request
def check_api_key():
    """
    Global API key check for all routes except public ones.

    Checks for X-API-Key header and validates it against configured API keys.
    Exempts requests from trusted sources (localhost, Docker network, private networks).
    Returns 401 if key is missing, 403 if key is invalid.
    """
    # Skip authentication for public endpoints
    if request.path in PUBLIC_ENDPOINTS:
        return None

    # Skip authentication if no API keys are configured (development mode)
    if not API_KEYS:
        return None

    # Skip authentication for trusted sources (localhost, Docker network, private networks)
    if is_trusted_ip(request.remote_addr):
        logger.debug(f"Allowing trusted request from {request.remote_addr} to {request.path}")
        return None

    # Check for API key in header
    api_key = request.headers.get('X-API-Key')

    if not api_key:
        logger.warning(f"Unauthorized request to {request.path} from {request.remote_addr}: Missing API key")
        return jsonify({
            'error': 'Missing API key',
            'message': 'Please provide X-API-Key header'
        }), 401

    if api_key not in API_KEYS:
        logger.warning(f"Forbidden request to {request.path} from {request.remote_addr}: Invalid API key")
        return jsonify({
            'error': 'Invalid API key',
            'message': 'The provided API key is not valid'
        }), 403

    # API key is valid - allow request to proceed
    return None

# ============================================================================

# Prometheus metrics removed - replaced by Metricbeat for system/container metrics
# Application metrics now tracked in Elasticsearch via elasticsearch_service.py
# metrics = PrometheusMetrics(app, group_by='endpoint')
# radio_captures_total = Counter(...)
# radio_capture_duration = Histogram(...)
# transcription_requests_total = Counter(...)
# transcription_duration = Histogram(...)
# aprs_decodes_total = Counter(...)
# aprs_packets_decoded = Counter(...)

# POCSAG and Repeater metrics removed - replaced by Metricbeat
# pocsag_decodes_total = Counter(...)
# pocsag_messages_decoded = Counter(...)
# repeater_scans_total = Counter(...)
# repeater_scans_duration = Histogram(...)
# repeater_activity_detected = Counter(...)
# repeater_transmissions_total = Counter(...)
# repeater_activity_percentage = Histogram(...)
# repeater_scan_progress = Gauge(...)

# Configuration
RECORDING_DIR = os.getenv('AUDIO_OUTPUT_DIR', './recordings')
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
WHISPER_DEVICE = os.getenv('WHISPER_DEVICE', 'cpu')
WHISPER_COMPUTE_TYPE = os.getenv('WHISPER_COMPUTE_TYPE', 'int8')

# Repeater scan sessions tracking
scan_sessions: Dict[int, Dict[str, Any]] = {}
scan_sessions_lock = threading.Lock()

# Thread pool for scan operations (max 1 worker - only 1 SDR device)
scan_thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-worker")

# Atomic session ID counter (thread-safe)
_session_id_counter = count(1)

# Session cleanup configuration
MAX_SESSIONS = 100  # Maximum number of sessions to keep in memory
SESSION_MAX_AGE_HOURS = 24  # Remove sessions older than 24 hours


def has_active_scan() -> bool:
    """
    Check if there's currently an active scan in progress.

    Returns:
        True if a scan is in progress, False otherwise
    """
    with scan_sessions_lock:
        return any(
            session.get('status') == 'in_progress'
            for session in scan_sessions.values()
        )


def cleanup_old_sessions() -> int:
    """
    Remove old and excess scan sessions to prevent memory leak

    Removes:
    1. Sessions older than SESSION_MAX_AGE_HOURS
    2. Oldest sessions if total exceeds MAX_SESSIONS

    Returns:
        Number of sessions removed
    """
    removed_count = 0
    current_time = time.time()
    max_age_seconds = SESSION_MAX_AGE_HOURS * 3600

    with scan_sessions_lock:
        # Phase 1: Remove sessions older than max age
        sessions_to_remove = []
        for session_id, session in scan_sessions.items():
            session_age = current_time - session.get('start_time', current_time)
            if session_age > max_age_seconds:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del scan_sessions[session_id]
            removed_count += 1

        # Phase 2: If still too many sessions, remove oldest completed/failed ones
        if len(scan_sessions) > MAX_SESSIONS:
            # Separate completed/failed sessions from in-progress
            completed_sessions = [
                (sid, s) for sid, s in scan_sessions.items()
                if s.get('status') in ['completed', 'failed']
            ]

            if completed_sessions:
                # Sort by start time (oldest first)
                completed_sessions.sort(key=lambda x: x[1].get('start_time', 0))

                # Remove oldest until we're under the limit
                sessions_to_keep = MAX_SESSIONS - sum(
                    1 for s in scan_sessions.values()
                    if s.get('status') == 'in_progress'
                )

                for i in range(len(completed_sessions) - sessions_to_keep):
                    session_id = completed_sessions[i][0]
                    if session_id in scan_sessions:
                        del scan_sessions[session_id]
                        removed_count += 1

    return removed_count


def session_cleanup_background():
    """Background thread that periodically cleans up old sessions"""
    while True:
        time.sleep(3600)  # Run every hour
        removed = cleanup_old_sessions()
        if removed > 0:
            print(f"Session cleanup: Removed {removed} old sessions")


# Start background cleanup thread
cleanup_thread = threading.Thread(target=session_cleanup_background, daemon=True)
cleanup_thread.start()


def validate_file_path(file_path: str, base_dir: str = RECORDING_DIR) -> str:
    """
    Validate file path to prevent path traversal attacks

    Args:
        file_path: User-provided file path
        base_dir: Base directory to restrict access to

    Returns:
        Validated absolute file path

    Raises:
        ValueError: If path attempts to escape base directory
    """
    # Convert to absolute paths
    base_dir_abs = os.path.abspath(base_dir)

    # Handle both absolute and relative paths from user
    if os.path.isabs(file_path):
        # If user provides absolute path, check if it's within base_dir
        file_path_abs = os.path.abspath(file_path)
    else:
        # If relative, join with base_dir
        file_path_abs = os.path.abspath(os.path.join(base_dir_abs, file_path))

    # Ensure the resolved path is within base_dir
    try:
        common_path = os.path.commonpath([base_dir_abs, file_path_abs])
    except ValueError:
        # Paths on different drives on Windows
        raise ValueError(f"Invalid file path: path traversal detected")

    if common_path != base_dir_abs:
        raise ValueError(f"Invalid file path: access denied outside {base_dir}")

    return file_path_abs

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


# Initialize APRS decoder
aprs_decoder: APRSDecoder | None = None


def get_aprs_decoder() -> APRSDecoder:
    """Lazy load APRS decoder service"""
    global aprs_decoder
    if aprs_decoder is None:
        aprs_decoder = APRSDecoder()
    return aprs_decoder


# Initialize POCSAG decoder
pocsag_decoder: POCSAGDecoder | None = None


def get_pocsag_decoder() -> POCSAGDecoder:
    """Lazy load POCSAG decoder service"""
    global pocsag_decoder
    if pocsag_decoder is None:
        pocsag_decoder = POCSAGDecoder()
    return pocsag_decoder


@app.route('/health', methods=['GET'])
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
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0.0',  # Incremented for Gunicorn migration
    })


@app.route('/sdr/detect', methods=['GET'])
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

        # Create capture instance (auto-detect SDR hardware)
        capture_instance = get_sdr_instance(
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )

        # Perform capture with metrics
        start_time = time.time()
        capture_instance.capture_audio(duration, output_file, modulation)
        capture_duration_seconds = time.time() - start_time

        # Record metrics
        return jsonify({
            'status': 'success',
            'audio_file': output_file,
            'frequency': frequency,
            'modulation': modulation,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
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

        # Validate file path to prevent path traversal
        try:
            audio_file = validate_file_path(data['audio_file'])
        except ValueError as e:
            return jsonify({'error': str(e)}), 403

        language = data.get('language')

        # Get transcription service
        service = get_transcription_service()

        # Transcribe with metrics
        start_time = time.time()
        result = service.transcribe(audio_file, language)
        transcription_duration_seconds = time.time() - start_time

        # Record metrics
        return jsonify({
            'status': 'success',
            'result': result
        })

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/capture-and-transcribe', methods=['POST'])
def capture_and_transcribe() -> Response | tuple[Response, int]:
    """
    Capture radio signal and transcribe or decode APRS in one step

    Request body:
    {
        "frequency": 100000000,
        "modulation": "FM",
        "duration": 30,
        "gain": 20,
        "sample_rate": 2000000,
        "mode": "voice",  # "voice" or "aprs" (optional, default: "voice")
        "language": "en"  # optional (only for voice mode)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON body'}), 400

        # Validate required parameters
        if 'frequency' not in data:
            return jsonify({'error': 'frequency is required'}), 400

        frequency = int(float(data['frequency']))
        modulation = data.get('modulation', 'FM')
        duration = int(data.get('duration', 30))
        gain = int(data.get('gain', 20))
        sample_rate = int(data.get('sample_rate', 2000000))
        mode = data.get('mode', 'voice')  # NEW: mode parameter
        language = data.get('language')

        # Validate mode
        if mode not in ['voice', 'aprs', 'pocsag']:
            return jsonify({'error': 'mode must be "voice", "aprs", or "pocsag"'}), 400

        # Optimize sample rate for POCSAG/APRS (reduces memory usage by 8-10x)
        # POCSAG/APRS only need ~25 kHz bandwidth, not 2 MHz
        # NOTE: HackRF minimum is 2 MHz, RTL-SDR can go lower
        sdr_type_val = detect_sdr()
        if mode in ['pocsag', 'aprs']:
            if sdr_type_val == SDRType.RTLSDR:
                # RTL-SDR can use lower sample rates
                original_sample_rate = sample_rate
                sample_rate = min(sample_rate, 250000)  # Max 250 kHz for digital modes
                if original_sample_rate != sample_rate:
                    logger.info(f"Sample rate reduced for {mode} mode: {original_sample_rate/1e6:.1f} MHz -> {sample_rate/1e3:.0f} kHz")
            else:
                # HackRF minimum is 2 MHz - cannot reduce sample rate
                logger.info(f"HackRF detected: keeping sample rate at {sample_rate/1e6:.1f} MHz (hardware minimum: 2 MHz)")

        # Enforce duration limits to prevent OOM crashes
        # HackRF uses 2 MHz (can't reduce), RTL-SDR uses 250 kHz (8x less memory)
        if sdr_type_val == SDRType.HACKRF and mode == 'pocsag':
            # HackRF POCSAG: 2 MHz sample rate = high memory usage
            # Limit to 60s to prevent OOM (2 MHz * 2 bytes * 60s = 240 MB raw IQ)
            MAX_DURATIONS: Dict[str, int] = {
                'pocsag': 60,    # Max 1 minute for POCSAG with HackRF (2 MHz sample rate)
                'aprs': 180,     # Max 3 minutes for APRS with HackRF
                'voice': 600,    # Max 10 minutes for voice transcription
            }
        else:
            # RTL-SDR POCSAG: 250 kHz sample rate = low memory usage
            # Can handle longer durations
            MAX_DURATIONS = {
                'pocsag': 120,   # Max 2 minutes for POCSAG with RTL-SDR (250 kHz sample rate)
                'aprs': 300,     # Max 5 minutes for APRS
                'voice': 600,    # Max 10 minutes for voice transcription
            }
        max_duration = MAX_DURATIONS.get(mode, 600)
        if duration > max_duration:
            return jsonify({
                'error': f'{mode.upper()} captures are limited to {max_duration} seconds to prevent memory issues',
                'max_duration': max_duration,
                'requested_duration': duration
            }), 400

        # Generate output filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.wav')
        json_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.json')

        # Step 1: Capture (same for both modes)
        capture_start = time.time()
        capture_instance = get_sdr_instance(
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )
        capture_instance.capture_audio(duration, audio_file, modulation)

        # Step 2: Process based on mode
        if mode == 'aprs':
            # APRS decoding
            try:
                decode_start = time.time()
                decoder = get_aprs_decoder()
                packets = decoder.decode(audio_file)
                decode_duration = time.time() - decode_start

                # Save to database
                es = get_elasticsearch_service()
                file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else None

                # Index capture to Elasticsearch
                capture_uuid = str(uuid.uuid4())
                capture_doc: Dict[str, Any] = {
                    'uuid': capture_uuid,
                    'created_at': datetime.utcnow().isoformat(),
                    'frequency': frequency,
                    'modulation': modulation,
                    'duration_seconds': duration,
                    'rf_gain': gain,
                    'sample_rate': sample_rate,
                    'audio_file': audio_file,
                    'file_size': file_size,
                    'sdr_type': sdr_type_val.value,
                    'mode': 'aprs',
                    'transcription_duration': decode_duration,
                    'metadata': {
                        'packet_count': len(packets),
                        'capture_timestamp': timestamp
                    }
                }
                capture_id = es.index_capture(capture_doc)

                # Index APRS packets
                for packet in packets:
                    packet_doc: Dict[str, Any] = {
                        'uuid': str(uuid.uuid4()),
                        'capture_id': capture_uuid,
                        'timestamp': datetime.utcnow().isoformat(),
                        'frequency': frequency,
                        **packet
                    }
                    es.index_aprs(packet_doc)
                logger.info(f"Indexed {len(packets)} APRS packets to Elasticsearch")

                # Metrics
                return jsonify({
                    'status': 'success',
                    'mode': 'aprs',
                    'capture': {
                        'id': capture_id,
                        'audio_file': audio_file,
                        'frequency': frequency,
                        'modulation': modulation,
                        'duration': duration
                    },
                    'aprs': {
                        'packet_count': len(packets),
                        'packets': packets
                    },
                    'timestamp': datetime.now().isoformat()
                })

            except Exception as e:
                logger.error(f"APRS decode error: {e}", exc_info=True)
                return jsonify({'error': f'APRS decode error: {str(e)}'}), 500

        elif mode == 'pocsag':
            # POCSAG decoding
            try:
                decode_start = time.time()
                decoder = get_pocsag_decoder()
                messages = decoder.decode(audio_file)
                decode_duration = time.time() - decode_start

                # Save to database
                es = get_elasticsearch_service()
                file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else None

                # Index capture to Elasticsearch
                capture_uuid = str(uuid.uuid4())
                capture_doc = {
                    'uuid': capture_uuid,
                    'created_at': datetime.utcnow().isoformat(),
                    'frequency': frequency,
                    'modulation': modulation,
                    'duration_seconds': duration,
                    'rf_gain': gain,
                    'sample_rate': sample_rate,
                    'audio_file': audio_file,
                    'file_size': file_size,
                    'sdr_type': sdr_type_val.value,
                    'mode': 'pocsag',
                    'transcription_duration': decode_duration,
                    'metadata': {
                        'message_count': len(messages),
                        'capture_timestamp': timestamp
                    }
                }
                capture_id = es.index_capture(capture_doc)

                # Index POCSAG messages
                for message in messages:
                    message_doc: Dict[str, Any] = {
                        'uuid': str(uuid.uuid4()),
                        'capture_id': capture_uuid,
                        'timestamp': datetime.utcnow().isoformat(),
                        'frequency': frequency,
                        **message
                    }
                    es.index_pocsag(message_doc)
                logger.info(f"Indexed {len(messages)} POCSAG messages to Elasticsearch")

                # Metrics
                return jsonify({
                    'status': 'success',
                    'mode': 'pocsag',
                    'capture': {
                        'id': capture_id,
                        'audio_file': audio_file,
                        'frequency': frequency,
                        'modulation': modulation,
                        'duration': duration
                    },
                    'pocsag': {
                        'message_count': len(messages),
                        'messages': messages
                    },
                    'timestamp': datetime.now().isoformat()
                })

            except Exception as e:
                logger.error(f"POCSAG decode error: {e}", exc_info=True)
                return jsonify({'error': f'POCSAG decode error: {str(e)}'}), 500

        else:
            # Voice transcription (existing logic)
            transcribe_start = time.time()
            service = get_transcription_service()
            transcription_result = service.transcribe_and_save(
                audio_file,
                json_file,
                language
            )
            transcribe_duration = time.time() - transcribe_start

            # Save to Elasticsearch
            try:
                es = get_elasticsearch_service()
                file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else None

                capture_doc = {
                    'uuid': str(uuid.uuid4()),
                    'created_at': datetime.utcnow().isoformat(),
                    'frequency': frequency,
                    'modulation': modulation,
                    'duration_seconds': duration,
                    'rf_gain': gain,
                    'sample_rate': sample_rate,
                    'audio_file': audio_file,
                    'json_file': json_file,
                    'file_size': file_size,
                    'sdr_type': sdr_type_val.value,
                    'transcription': transcription_result.get('text'),
                    'detected_language': transcription_result.get('language'),
                    'confidence_score': transcription_result.get('language_probability'),
                    'segments': transcription_result.get('segments'),
                    'transcription_duration': transcribe_duration,
                    'mode': 'voice',
                    'metadata': {
                        'capture_timestamp': timestamp,
                        'audio_duration': transcription_result.get('duration')
                    }
                }
                es.index_capture(capture_doc)
            except Exception as es_error:
                logger.warning(f"Warning: Could not index to Elasticsearch: {es_error}")

            response_data: Dict[str, Any] = {
                'status': 'success',
                'mode': 'voice',
                'capture': {
                    'audio_file': audio_file,
                    'frequency': frequency,
                    'modulation': modulation,
                    'duration': duration
                },
                'transcription': transcription_result,
                'timestamp': datetime.now().isoformat()
            }

            # Add simulation warning if present
            if transcription_result.get('simulation_mode'):
                response_data['warning'] = 'Transcription was simulated, not real'
                response_data['simulation_mode'] = True

            return jsonify(response_data)

    except Exception as e:
        logger.error(f"Capture and Transcribe error: {e}", exc_info=True)
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


@app.route('/search', methods=['GET'])
def search_captures() -> Response | tuple[Response, int]:
    """
    Search captures in database

    Query parameters:
    - query: Full-text search query
    - freq_min: Filter by minimum frequency
    - freq_max: Filter by maximum frequency
    - modulation: Filter by modulation (FM, AM, USB, LSB)
    - language: Filter by language
    - sdr_type: Filter by SDR type
    - hours: Time range in hours (default 24)
    - limit: Maximum results (default 100)
    - offset: Offset for pagination (default 0)
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        query = request.args.get('query')
        freq_min = request.args.get('freq_min', type=int)
        freq_max = request.args.get('freq_max', type=int)
        modulation = request.args.get('modulation')
        language = request.args.get('language')
        sdr_type = request.args.get('sdr_type')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        # Search
        results = es.search_captures(
            query=query,
            frequency_min=freq_min,
            frequency_max=freq_max,
            modulation=modulation,
            language=language,
            sdr_type=sdr_type,
            hours=hours,
            limit=limit,
            offset=offset
        )

        return jsonify({
            'status': 'success',
            'count': results['total'],
            'results': results['hits']
        })

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/captures/<int:capture_id>', methods=['GET'])
def get_capture(capture_id: int) -> Response | tuple[Response, int]:
    """Get a single capture by ID"""
    try:
        es = get_elasticsearch_service()
        result = es.get_capture_by_id(capture_id)

        if result is None:
            return jsonify({'error': 'Capture not found'}), 404

        return jsonify({
            'status': 'success',
            'capture': result
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_statistics() -> Response | tuple[Response, int]:
    """Get database statistics"""
    try:
        es = get_elasticsearch_service()
        stats = es.get_overall_stats()

        return jsonify({
            'status': 'success',
            'statistics': stats
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stats/frequencies', methods=['GET'])
def get_frequency_stats() -> Response | tuple[Response, int]:
    """Get frequency usage statistics"""
    try:
        es = get_elasticsearch_service()
        limit = request.args.get('limit', 10, type=int)
        frequencies = es.get_frequency_usage(limit=limit)

        return jsonify({
            'status': 'success',
            'frequencies': frequencies
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aprs/search', methods=['GET'])
def search_aprs() -> Response | tuple[Response, int]:
    """
    Search APRS messages in database

    Query parameters:
    - callsign: Filter by source callsign
    - type: Filter by APRS type (position, message, weather, telemetry)
    - hours: Time window in hours (default 24)
    - limit: Maximum results (default 100)
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        callsign = request.args.get('callsign')
        packet_type = request.args.get('type')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)

        # Search
        results = es.search_aprs(
            callsign=callsign,
            packet_type=packet_type,
            hours=hours,
            limit=limit
        )

        return jsonify({
            'status': 'success',
            'count': results['total'],
            'results': results['hits']
        })

    except Exception as e:
        logger.error(f"APRS search failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/aprs/stats', methods=['GET'])
def get_aprs_stats() -> Response | tuple[Response, int]:
    """Get APRS statistics"""
    try:
        es = get_elasticsearch_service()
        stats = es.get_aprs_stats()

        return jsonify({
            'status': 'success',
            'statistics': stats
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aprs/map', methods=['GET'])
def get_aprs_map_data() -> Response | tuple[Response, int]:
    """
    Get APRS position data for map display (GeoJSON format)

    Returns recent APRS packets with position data in GeoJSON format
    suitable for map visualization (Grafana, Leaflet, etc.)
    """
    try:
        es = get_elasticsearch_service()

        # Get recent packets with position data (last 24 hours by default)
        hours = request.args.get('hours', 24, type=int)

        results = es.search_aprs(
            start_date=datetime.now().replace(hour=0, minute=0, second=0) if hours == 24 else None,
            limit=1000
        )

        # Filter for packets with position data and convert to GeoJSON
        features = []
        for packet in results:
            if packet.get('latitude') and packet.get('longitude'):
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [packet['longitude'], packet['latitude']]
                    },
                    'properties': {
                        'callsign': packet['source_callsign'],
                        'message': packet.get('message_text', ''),
                        'type': packet.get('aprs_type', 'unknown'),
                        'timestamp': packet['created_at'].isoformat() if hasattr(packet['created_at'], 'isoformat') else str(packet['created_at']),
                        'altitude': packet.get('altitude_meters'),
                        'speed': packet.get('speed_kmh'),
                        'frequency': packet.get('frequency')
                    }
                })

        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }

        return jsonify(geojson)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/pocsag/search', methods=['GET'])
def search_pocsag() -> Response | tuple[Response, int]:
    """
    Search POCSAG messages in database

    Query parameters:
    - address: Filter by pager address
    - type: Filter by message type (alphanumeric, numeric, tone)
    - hours: Time window in hours (default 24)
    - limit: Maximum results (default 100)
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        address = request.args.get('address', type=int)
        message_type = request.args.get('type')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)

        # Search
        results = es.search_pocsag(
            address=address,
            message_type=message_type,
            hours=hours,
            limit=limit
        )

        return jsonify({
            'status': 'success',
            'count': results['total'],
            'results': results['hits']
        })

    except Exception as e:
        logger.error(f"POCSAG search failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/pocsag/stats', methods=['GET'])
def get_pocsag_stats() -> Response | tuple[Response, int]:
    """Get POCSAG statistics"""
    try:
        es = get_elasticsearch_service()
        stats = es.get_pocsag_stats()

        return jsonify({
            'status': 'success',
            'statistics': stats
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/pocsag/messages', methods=['GET'])
def get_pocsag_messages() -> Response | tuple[Response, int]:
    """
    Get recent POCSAG messages

    Query parameters:
    - limit: Maximum results (default 50)
    - offset: Offset for pagination (default 0)
    """
    try:
        es = get_elasticsearch_service()
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        results = es.search_pocsag(limit=limit, offset=offset)

        return jsonify({
            'status': 'success',
            'count': len(results),
            'messages': results
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Repeater Scanning Endpoints
# ============================================================================

def _scan_repeaters_worker(
    session_id: int,
    repeaters: list,
    scan_duration: int,
    sample_rate: int,
    gain: int
) -> None:
    """
    Background worker thread for scanning repeaters.

    Args:
        session_id: Scan session ID
        repeaters: List of repeater dictionaries
        scan_duration: Duration to scan each repeater (seconds)
        sample_rate: IQ sample rate
        gain: RF gain
    """
    es = get_elasticsearch_service()
    analyzer = RepeaterActivityAnalyzer(sample_rate=sample_rate)

    results = []
    repeaters_scanned = 0
    repeaters_with_activity = 0

    try:
        for idx, repeater in enumerate(repeaters):
            # Update progress
            with scan_sessions_lock:
                if session_id in scan_sessions:
                    scan_sessions[session_id]['current_index'] = idx
                    scan_sessions[session_id]['current_repeater'] = repeater['callsign']
                    scan_sessions[session_id]['elapsed_time'] = time.time() - scan_sessions[session_id]['start_time']

            frequency = repeater['output_frequency']
            callsign = repeater['callsign']

            print(f"Scanning repeater {idx+1}/{len(repeaters)}: {callsign} ({frequency/1e6:.4f} MHz)")

            try:
                # Generate output filename for IQ samples
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                iq_file = os.path.join(RECORDING_DIR, f'repeater_scan_{callsign}_{timestamp}.iq')

                # Capture IQ samples
                scan_start_time = datetime.now()
                capture_instance = get_sdr_instance(
                    frequency=frequency,
                    sample_rate=sample_rate,
                    gain=gain
                )

                # Capture to IQ file (complex64 format)
                capture_instance.capture_iq(scan_duration, iq_file)

                # Create capture record for Elasticsearch
                capture_uuid = str(uuid.uuid4())
                capture_doc = {
                    'uuid': capture_uuid,
                    'created_at': datetime.utcnow().isoformat(),
                    'frequency': frequency,
                    'modulation': 'FM',
                    'duration_seconds': scan_duration,
                    'rf_gain': gain,
                    'audio_file': iq_file,
                    'sample_rate': sample_rate,
                    'sdr_type': detect_sdr().value,
                    'mode': 'repeater_scan',
                    'metadata': {'type': 'repeater_scan', 'session_id': session_id}
                }
                es.index_capture(capture_doc)

                # Analyze IQ samples
                metrics = analyzer.analyze_iq_file(iq_file)
                scan_end_time = datetime.now()

                # Index repeater activity
                activity_doc = {
                    'uuid': str(uuid.uuid4()),
                    'created_at': datetime.utcnow().isoformat(),
                    'capture_id': capture_uuid,
                    'repeater_id': repeater.get('uuid', repeater.get('id')),
                    'repeater_callsign': repeater.get('callsign'),
                    'frequency': frequency,
                    'frequency_mhz': repeater.get('frequency_mhz'),
                    'band': repeater.get('band'),
                    'canton': repeater.get('canton'),
                    'scan_start_time': scan_start_time.isoformat(),
                    'scan_end_time': scan_end_time.isoformat(),
                    'metrics': metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics
                }
                # Merge with analysis results if they exist
                if 'analysis_result' in locals():
                    activity_doc.update(analysis_result)
                activity_id = es.index_repeater_activity(activity_doc)

                repeaters_scanned += 1
                if metrics.carrier_detected:
                    repeaters_with_activity += 1

                # Record Prometheus metrics
                if metrics.carrier_detected:
                    band = repeater.get('band', 'unknown')
                    canton = repeater.get('canton', 'unknown')
                result = {
                    'repeater_id': repeater.get('uuid', repeater.get('id')),
                    'callsign': callsign,
                    'frequency': frequency,
                    'activity': metrics.to_dict()
                }
                results.append(result)

                # Update session with partial results
                with scan_sessions_lock:
                    if session_id in scan_sessions:
                        scan_sessions[session_id]['results'] = results
                        scan_sessions[session_id]['repeaters_scanned'] = repeaters_scanned
                        scan_sessions[session_id]['repeaters_with_activity'] = repeaters_with_activity

                # Clean up IQ file to save disk space (prevents disk filling)
                try:
                    if os.path.exists(iq_file):
                        os.remove(iq_file)
                        print(f"Cleaned up IQ file: {iq_file}")
                except Exception as cleanup_error:
                    print(f"Warning: Failed to cleanup IQ file {iq_file}: {cleanup_error}")

            except Exception as e:
                print(f"Error scanning {callsign}: {e}")
                results.append({
                    'repeater_id': repeater.get('uuid', repeater.get('id')),
                    'callsign': callsign,
                    'frequency': frequency,
                    'error': str(e)
                })

        # Mark session as completed
        with scan_sessions_lock:
            if session_id in scan_sessions:
                scan_sessions[session_id]['status'] = 'completed'
                scan_sessions[session_id]['end_time'] = time.time()
                scan_sessions[session_id]['results'] = results

        # Update database
        # Scan sessions are in-memory only
        # # REMOVED: db.update_scan_session() - using in-memory scan_sessions dict instead

        # Record completion metrics
        print(f"Scan session {session_id} completed: {repeaters_scanned} scanned, {repeaters_with_activity} with activity")

    except Exception as e:
        import traceback
        print(f"Scan session {session_id} failed: {e}")
        print("Full traceback:")
        traceback.print_exc()
        with scan_sessions_lock:
            if session_id in scan_sessions:
                scan_sessions[session_id]['status'] = 'failed'
                scan_sessions[session_id]['error'] = str(e)

        # Scan sessions are in-memory only (removed db.update_scan_session)


@app.route('/scan-repeaters', methods=['POST'])
def scan_repeaters() -> Response | tuple[Response, int]:
    """
    Start a repeater activity scan.

    Request body:
    {
        "duration_per_repeater": 120,    // Seconds (default: 120)
        "band": "2m",                     // optional: "2m", "70cm", "all"
        "canton": "ZH",                   // optional: Filter by canton
        "repeater_ids": [1, 2, 3],       // optional: Specific repeater IDs
        "sample_rate": 2000000,           // optional: IQ sample rate
        "gain": 20                        // optional: RF gain
    }

    Response:
    {
        "status": "success",
        "session_id": 1,
        "message": "Scan started",
        "repeaters_count": 10,
        "estimated_duration_seconds": 1200
    }
    """
    try:
        # Check if a scan is already in progress
        if has_active_scan():
            return jsonify({
                'status': 'error',
                'message': 'A scan is already in progress. Please wait for it to complete.',
                'code': 'SCAN_IN_PROGRESS'
            }), 409

        data = request.get_json() or {}

        # Parse parameters
        duration_per_repeater = data.get('duration_per_repeater', 120)
        band = data.get('band')
        canton = data.get('canton')
        repeater_ids = data.get('repeater_ids')
        sample_rate = data.get('sample_rate', 2000000)
        gain = data.get('gain', 20)

        es = get_elasticsearch_service()

        # Get repeaters to scan
        if repeater_ids:
            # Specific repeaters by ID
            repeaters = []
            for rid in repeater_ids:
                repeater = es.get_repeater_by_id(rid)
                if repeater:
                    repeaters.append(repeater)
        else:
            # Filter by band/canton
            repeaters = es.get_repeaters(
                band=band,
                canton=canton,
                mode='FM',
                status='active'
            )

        if not repeaters:
            return jsonify({
                'status': 'error',
                'message': 'No repeaters found matching criteria'
            }), 404

        # Generate thread-safe session ID using atomic counter
        session_id = next(_session_id_counter)

        # Initialize session tracking
        with scan_sessions_lock:
            scan_sessions[session_id] = {
                'status': 'in_progress',
                'start_time': time.time(),
                'repeaters_total': len(repeaters),
                'repeaters_scanned': 0,
                'repeaters_with_activity': 0,
                'current_index': 0,
                'current_repeater': None,
                'elapsed_time': 0,
                'results': []
            }

        # Submit scan to thread pool (max 1 concurrent scan)
        scan_thread_pool.submit(
            _scan_repeaters_worker,
            session_id,
            repeaters,
            duration_per_repeater,
            sample_rate,
            gain
        )

        estimated_duration = len(repeaters) * duration_per_repeater

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'Scan started',
            'repeaters_count': len(repeaters),
            'estimated_duration_seconds': estimated_duration
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/scan-repeaters/<int:session_id>/progress', methods=['GET'])
def get_scan_progress(session_id: int) -> Response | tuple[Response, int]:
    """
    Get progress of a repeater scan session.

    Response:
    {
        "status": "in_progress",
        "session_id": 1,
        "progress": {
            "current_repeater": 5,
            "total_repeaters": 10,
            "current_callsign": "HB9AB",
            "elapsed_seconds": 600,
            "estimated_remaining_seconds": 600,
            "repeaters_scanned": 4,
            "repeaters_with_activity": 2
        },
        "results": [...]  // Partial or complete results
    }
    """
    try:
        with scan_sessions_lock:
            if session_id not in scan_sessions:
                return jsonify({
                    'status': 'error',
                    'message': 'Scan session not found'
                }), 404

            session = scan_sessions[session_id].copy()

        # Calculate progress
        current = session.get('current_index', 0)
        total = session.get('repeaters_total', 0)
        elapsed = session.get('elapsed_time', 0)

        # Estimate remaining time
        if current > 0 and elapsed > 0:
            avg_time_per_repeater = elapsed / current
            remaining_repeaters = total - current
            estimated_remaining = int(avg_time_per_repeater * remaining_repeaters)
        else:
            estimated_remaining = 0

        response = {
            'status': session.get('status', 'unknown'),
            'session_id': session_id,
            'progress': {
                'current_repeater': current + 1,  # 1-indexed for display
                'total_repeaters': total,
                'current_callsign': session.get('current_repeater'),
                'elapsed_seconds': int(elapsed),
                'estimated_remaining_seconds': estimated_remaining,
                'repeaters_scanned': session.get('repeaters_scanned', 0),
                'repeaters_with_activity': session.get('repeaters_with_activity', 0)
            },
            'results': session.get('results', [])
        }

        if session.get('status') == 'failed':
            response['error'] = session.get('error')

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/scan-repeaters/<int:session_id>', methods=['GET'])
def get_scan_session_details(session_id: int) -> Response | tuple[Response, int]:
    """
    Get complete details of a scan session from database.

    Response:
    {
        "status": "success",
        "session": {...}
    }
    """
    try:
        es = get_elasticsearch_service()
        # Get session from in-memory dict (removed db.get_scan_session)
        session = scan_sessions.get(session_id)

        if not session:
            return jsonify({
                'status': 'error',
                'message': 'Scan session not found'
            }), 404

        return jsonify({
            'status': 'success',
            'session': session
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/repeaters', methods=['GET'])
def get_repeaters_endpoint() -> Response | tuple[Response, int]:
    """
    Get list of repeaters with optional filters.

    Query parameters:
    - band: Filter by band (2m, 70cm, 23cm)
    - canton: Filter by canton (ZH, BE, etc.)
    - mode: Filter by mode (FM, DMR, etc.) - default: FM
    - status: Filter by status (active, inactive, testing) - default: active
    - limit: Maximum results (default 1000)

    Response:
    {
        "status": "success",
        "count": 10,
        "repeaters": [...]
    }
    """
    try:
        es = get_elasticsearch_service()

        # Get query parameters
        band = request.args.get('band')
        canton = request.args.get('canton')
        mode = request.args.get('mode', 'FM')
        status = request.args.get('status', 'active')
        limit = request.args.get('limit', 1000, type=int)

        repeaters = es.get_repeaters(
            band=band,
            canton=canton,
            mode=mode,
            status=status,
            limit=limit
        )

        return jsonify({
            'status': 'success',
            'count': len(repeaters),
            'repeaters': repeaters
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/repeater-activity/summary', methods=['GET'])
def get_repeater_activity_summary_endpoint() -> Response | tuple[Response, int]:
    """
    Get summary of most active repeaters.

    Query parameters:
    - hours: Time window in hours (default 24)
    - limit: Maximum results (default 10)

    Response:
    {
        "status": "success",
        "summary": [...]
    }
    """
    try:
        es = get_elasticsearch_service()

        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 10, type=int)

        summary = es.get_repeater_activity_summary(hours=hours, limit=limit)

        return jsonify({
            'status': 'success',
            'summary': summary
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===========================================================================
# Streaming Decode Endpoints (NEW)
# ===========================================================================

# Initialize session manager (Redis connection)
session_manager = SessionManager(
    redis_host=os.getenv('REDIS_HOST', 'localhost'),
    redis_port=int(os.getenv('REDIS_PORT', 6379)),
    redis_db=int(os.getenv('REDIS_DB', 0))
)

# Track active decoders in memory
active_decoders = {}  # session_id -> decoder instance


@app.route('/stream-decode', methods=['POST'])
def start_stream_decode():
    """
    Start continuous streaming decode session (APRS/POCSAG)

    Request body:
    {
        "mode": "aprs|pocsag",
        "frequency": 144800000,
        "duration": 3600,
        "gain": 20,
        "sample_rate": 2000000  # optional
    }

    Returns:
    {
        "status": "started",
        "session_id": "uuid",
        "mode": "aprs",
        "frequency": 144800000,
        "duration": 3600
    }
    """
    try:
        data = request.get_json()

        mode = data.get('mode')
        frequency = float(data['frequency'])
        duration = int(data.get('duration', 3600))  # Default 1 hour
        gain = int(data.get('gain', 20))
        sample_rate = int(data.get('sample_rate', 2000000))

        # Validate mode
        if mode not in ['aprs', 'pocsag']:
            return jsonify({'error': 'mode must be "aprs" or "pocsag"'}), 400

        # Check if user already has an active session (max 1 per user)
        existing_session = session_manager.get_user_active_session()
        if existing_session:
            return jsonify({
                'error': 'Active streaming session already exists',
                'active_session_id': existing_session.session_id,
                'message': 'Stop the active session before starting a new one'
            }), 409  # Conflict

        # Create decoder instance
        if mode == 'aprs':
            decoder = StreamingAPRSDecoder(frequency, duration, gain, sample_rate)
        elif mode == 'pocsag':
            decoder = StreamingPOCSAGDecoder(frequency, duration, gain, sample_rate)
        else:
            return jsonify({'error': 'Invalid mode'}), 400

        # Start streaming
        session_id = decoder.start_stream(session_manager)
        active_decoders[session_id] = decoder

        logger.info(f"Started streaming session {session_id}: {mode} @ {frequency/1e6:.3f} MHz")

        return jsonify({
            'status': 'started',
            'session_id': session_id,
            'mode': mode,
            'frequency': frequency,
            'duration': duration,
            'message': 'Streaming session started. Check /stream-decode/<session_id> for status.'
        })

    except KeyError as e:
        return jsonify({'error': f'Missing required parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/stream-decode/<session_id>', methods=['GET'])
def get_stream_status(session_id):
    """
    Get streaming session status and stats

    Returns:
    {
        "session_id": "uuid",
        "mode": "aprs",
        "frequency": 144800000,
        "status": "running",  # starting, running, stopping, completed, failed
        "start_time": "2025-01-01T12:00:00",
        "duration": 3600,
        "stats": {
            "packet_count": 42,
            "last_packet_time": "2025-01-01T12:05:30",
            "elapsed_seconds": 330
        }
    }
    """
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        # Calculate elapsed time (use end_time if session completed)
        if session.end_time:
            elapsed = (session.end_time - session.start_time).total_seconds()
        else:
            elapsed = (datetime.utcnow() - session.start_time).total_seconds()

        return jsonify({
            'session_id': session.session_id,
            'mode': session.mode,
            'frequency': session.frequency,
            'status': session.status,
            'start_time': session.start_time.isoformat(),
            'end_time': session.end_time.isoformat() if session.end_time else None,
            'duration': session.duration,
            'stats': {
                'packet_count': session.packet_count,
                'last_packet_time': session.last_packet_time.isoformat() if session.last_packet_time else None,
                'elapsed_seconds': int(elapsed),
                'error': session.error
            }
        })

    except Exception as e:
        logger.error(f"Failed to get session status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/stream-decode/<session_id>', methods=['DELETE'])
def stop_stream_decode(session_id):
    """
    Stop streaming session gracefully

    Returns:
    {
        "status": "stopping",
        "session_id": "uuid",
        "message": "Session is being stopped..."
    }
    """
    try:
        decoder = active_decoders.get(session_id)
        if not decoder:
            # Session might be already completed
            session = session_manager.get_session(session_id)
            if not session:
                return jsonify({'error': 'Session not found'}), 404

            return jsonify({
                'status': session.status,
                'session_id': session_id,
                'message': f'Session already {session.status}'
            })

        # Stop decoder
        decoder.stop_stream()

        # Remove from active decoders
        del active_decoders[session_id]

        logger.info(f"Stopped streaming session {session_id}")

        return jsonify({
            'status': 'stopping',
            'session_id': session_id,
            'message': 'Session is being stopped. Check status in a few seconds.'
        })

    except Exception as e:
        logger.error(f"Failed to stop session: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/stream-decode', methods=['GET'])
def list_stream_sessions():
    """
    List all streaming sessions (active and recent)

    Returns:
    {
        "sessions": [
            {
                "session_id": "uuid",
                "mode": "aprs",
                "status": "running",
                "packet_count": 42,
                "start_time": "2025-01-01T12:00:00"
            }
        ]
    }
    """
    try:
        sessions = session_manager.list_sessions()

        sessions_data = []
        for session in sessions:
            sessions_data.append({
                'session_id': session.session_id,
                'mode': session.mode,
                'frequency': session.frequency,
                'status': session.status,
                'packet_count': session.packet_count,
                'start_time': session.start_time.isoformat(),
                'duration': session.duration
            })

        return jsonify({'sessions': sessions_data})

    except Exception as e:
        logger.error(f"Failed to list sessions: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def main() -> None:
    """
    Initialize application directories and resources.
    Called by both Gunicorn (production) and Flask dev server (development).
    """
    # Create recordings directory
    os.makedirs(RECORDING_DIR, exist_ok=True)
    logger.info("Application initialization complete")


# Initialize app on module import (Gunicorn imports this module)
main()


if __name__ == '__main__':
    # Local development mode using Flask's built-in server
    # For production, use: gunicorn --config gunicorn_config.py api_service:app
    port = int(os.getenv('API_PORT', '5000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    logger.warning("=" * 70)
    logger.warning("⚠️  DEVELOPMENT MODE - Flask built-in server")
    logger.warning("   This server is NOT suitable for production deployment!")
    logger.warning("")
    logger.warning("   For production, use:")
    logger.warning("   gunicorn --config gunicorn_config.py api_service:app")
    logger.warning("=" * 70)

    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
