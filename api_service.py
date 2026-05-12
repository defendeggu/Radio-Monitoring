#!/usr/bin/env python3
"""
Flask API Service for Radio Transcription
Provides REST API endpoints for Radio Monitoring
"""

import os
import json
import time
import threading
import logging
from datetime import datetime, timezone
import uuid
from typing import TypedDict, Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
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
from scan_session_manager import get_scan_session_manager, RepeaterScanSession
from dotenv import load_dotenv
from logging_config import setup_logging, set_correlation_id, clear_correlation_id

# Load environment variables first
load_dotenv()

# Configure structured JSON logging for ELK stack
# Use JSON format in production, plain text for development
json_logging = os.getenv('JSON_LOGGING', 'true').lower() == 'true'
log_level = os.getenv('LOG_LEVEL', 'INFO')
setup_logging(log_level=log_level, json_format=json_logging)
logger = logging.getLogger(__name__)

# Prometheus metrics removed - replaced by Metricbeat
# from prometheus_flask_exporter import PrometheusMetrics
# from prometheus_client import Counter, Histogram, Gauge

# Explicitly export shared utilities for blueprints
__all__ = [
    'app',
    'get_elasticsearch_service',
    'get_aprs_decoder',
    'get_pocsag_decoder',
    'get_transcription_service',
    'session_manager',
    'validate_file_path',
    'RECORDING_DIR',
    'RecordingInfo',
    'scan_thread_pool',
    'has_active_scan',
    '_scan_repeaters_worker',
]


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
# Request Correlation ID Middleware
# ============================================================================

@app.before_request
def setup_request_correlation() -> None:
    """Set correlation ID for request tracing before each request"""
    # Try to get correlation ID from request header
    correlation_id = request.headers.get('X-Correlation-ID')
    if not correlation_id:
        # Generate new correlation ID if not provided
        correlation_id = str(uuid.uuid4())

    # Set correlation ID in context for this request
    set_correlation_id(correlation_id)

    # Log request start with correlation ID
    logger.info(
        'Request started',
        extra={
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        }
    )


@app.after_request
def add_correlation_id_header(response: Response) -> Response:
    """Add correlation ID to response headers and clear from context"""
    from logging_config import get_correlation_id

    # Add correlation ID to response headers for client tracking
    correlation_id = get_correlation_id()
    response.headers['X-Correlation-ID'] = correlation_id

    # Log request completion
    logger.info(
        'Request completed',
        extra={
            'status_code': response.status_code,
            'content_length': response.content_length
        }
    )

    # Clear correlation ID from context
    clear_correlation_id()

    return response


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


def is_trusted_ip(ip_address: str) -> bool:
    """
    Check if the request comes from a trusted source.

    Default trusted sources (always included):
    - localhost (127.0.0.1, ::1)
    - Docker internal network (172.16.0.0/12 - covers 172.16–172.31, includes 172.18.x used by Compose)

    Broad private ranges (10.0.0.0/8, 192.168.0.0/16) are NOT trusted by default because
    any host on the local network would bypass API key authentication entirely.
    To opt in, set TRUSTED_IPS to the specific subnet you control:
      TRUSTED_IPS=192.168.1.0/24,10.0.1.5

    Additional trusted sources can be configured via TRUSTED_IPS environment variable:
    - Supports individual IPs: TRUSTED_IPS=192.168.1.100,10.0.0.50
    - Supports CIDR networks: TRUSTED_IPS=192.168.1.0/24,10.0.0.0/8

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

        # Localhost (always trusted)
        if ip.is_loopback:
            return True

        # Docker networks (172.16.0.0/12 covers 172.16-172.31)
        docker_network = ipaddress.ip_network('172.16.0.0/12')
        if ip in docker_network:
            return True

        # Check custom trusted IPs from environment variable
        trusted_ips_str = os.getenv('TRUSTED_IPS', '')
        if trusted_ips_str:
            for trusted_ip in trusted_ips_str.split(','):
                trusted_ip = trusted_ip.strip()
                if not trusted_ip:
                    continue

                try:
                    # Check if it's a network (CIDR notation)
                    if '/' in trusted_ip:
                        trusted_network = ipaddress.ip_network(trusted_ip)
                        if ip in trusted_network:
                            return True
                    else:
                        # Single IP address
                        if ip == ipaddress.ip_address(trusted_ip):
                            return True
                except ValueError:
                    logger.warning(f"Invalid TRUSTED_IP entry: {trusted_ip}")
                    continue

        return False
    except ValueError:
        # Invalid IP address
        return False


@app.before_request
def check_api_key() -> None | tuple[Response, int]:
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
    if request.remote_addr and is_trusted_ip(request.remote_addr):
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

# Repeater scan sessions tracking (Redis-based)
scan_session_manager = get_scan_session_manager()

# Thread pool for scan operations (max 1 worker - only 1 SDR device)
scan_thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-worker")

# Thread pool for async capture operations (max 1 worker - same SDR device constraint)
capture_thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capture-worker")
_capture_busy = threading.Event()  # set while a capture worker is executing

# Session cleanup configuration
MAX_SESSIONS = 100  # Maximum number of concurrent scan sessions
SESSION_MAX_AGE_HOURS = 24  # Remove sessions older than 24 hours


def has_active_scan() -> bool:
    """
    Check if there's currently an active scan in progress.

    Returns:
        True if a scan is in progress, False otherwise
    """
    active_sessions = scan_session_manager.get_active_sessions()
    return len(active_sessions) > 0


def cleanup_old_sessions() -> int:
    """
    Remove old scan sessions from Redis

    Removes sessions older than SESSION_MAX_AGE_HOURS.
    Note: Redis TTL (24h) provides automatic cleanup, this is for explicit cleanup.

    Returns:
        Number of sessions removed
    """
    removed_count = scan_session_manager.cleanup_old_sessions(SESSION_MAX_AGE_HOURS)

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old scan sessions from Redis")

    return removed_count


def session_cleanup_background() -> None:
    """Background thread that periodically cleans up old sessions"""
    while True:
        time.sleep(3600)  # Run every hour
        removed = cleanup_old_sessions()
        if removed > 0:
            logger.info(f"Session cleanup: Removed {removed} old sessions")


# Start background cleanup thread
cleanup_thread = threading.Thread(target=session_cleanup_background, daemon=True)
cleanup_thread.start()


# ============================================================================
# Capture Session Store (Redis, 1-hour TTL)
# ============================================================================

def _save_capture_session(capture_id: str, data: Dict[str, Any]) -> None:
    key = f"capture_session:{capture_id}"
    scan_session_manager.redis.set(key, json.dumps(data))
    scan_session_manager.redis.expire(key, 3600)


def _get_capture_session(capture_id: str) -> Optional[Dict[str, Any]]:
    key = f"capture_session:{capture_id}"
    raw = scan_session_manager.redis.get(key)
    return json.loads(str(raw)) if raw else None


def _capture_worker(
    capture_id: str,
    frequency: int,
    modulation: str,
    duration: int,
    gain: int,
    sample_rate: int,
    mode: str,
    language: Optional[str],
    sdr_type_val: SDRType,
    timestamp: str,
    audio_file: str,
    json_file: str,
) -> None:
    """Background capture worker: runs SDR capture + decode/transcribe, stores result in Redis."""
    _capture_busy.set()
    created_at = datetime.now(timezone.utc).isoformat()

    def _update(status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
        _save_capture_session(capture_id, {
            'capture_id': capture_id,
            'status': status,
            'mode': mode,
            'created_at': created_at,
            'result': result,
            'error': error,
        })

    try:
        _update('capturing')

        capture_instance = get_sdr_instance(
            frequency=frequency,
            sample_rate=sample_rate,
            gain=gain
        )
        capture_instance.capture_audio(duration, audio_file, modulation)

        _update('processing')

        if mode == 'aprs':
            decode_start = time.time()
            aprs_decoder_instance = get_aprs_decoder()
            packets = aprs_decoder_instance.decode(audio_file)
            decode_duration = time.time() - decode_start

            es = get_elasticsearch_service()
            file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else None
            capture_uuid = str(uuid.uuid4())
            capture_doc: Dict[str, Any] = {
                'uuid': capture_uuid,
                'created_at': datetime.now(timezone.utc).isoformat(),
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
                'metadata': {'packet_count': len(packets), 'capture_timestamp': timestamp}
            }
            cap_id = es.index_capture(capture_doc)
            for packet in packets:
                es.index_aprs({
                    'uuid': str(uuid.uuid4()),
                    'capture_id': capture_uuid,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'frequency': frequency,
                    **packet
                })

            _update('completed', result={
                'status': 'success',
                'mode': 'aprs',
                'capture': {'id': cap_id, 'audio_file': audio_file, 'frequency': frequency,
                            'modulation': modulation, 'duration': duration},
                'aprs': {'packet_count': len(packets), 'packets': packets},
                'timestamp': datetime.now().isoformat(),
            })

        elif mode == 'pocsag':
            decode_start = time.time()
            pocsag_decoder_instance = get_pocsag_decoder()
            messages = pocsag_decoder_instance.decode(audio_file)
            decode_duration = time.time() - decode_start

            es = get_elasticsearch_service()
            file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else None
            capture_uuid = str(uuid.uuid4())
            capture_doc = {
                'uuid': capture_uuid,
                'created_at': datetime.now(timezone.utc).isoformat(),
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
                'metadata': {'message_count': len(messages), 'capture_timestamp': timestamp}
            }
            cap_id = es.index_capture(capture_doc)
            for message in messages:
                es.index_pocsag({
                    'uuid': str(uuid.uuid4()),
                    'capture_id': capture_uuid,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'frequency': frequency,
                    **message
                })

            _update('completed', result={
                'status': 'success',
                'mode': 'pocsag',
                'capture': {'id': cap_id, 'audio_file': audio_file, 'frequency': frequency,
                            'modulation': modulation, 'duration': duration},
                'pocsag': {'message_count': len(messages), 'messages': messages},
                'timestamp': datetime.now().isoformat(),
            })

        else:
            transcribe_start = time.time()
            service = get_transcription_service()
            transcription_result = service.transcribe(audio_file=audio_file, language=language)
            with open(json_file, 'w') as f:
                json.dump(transcription_result, f, indent=2)
            transcribe_duration = time.time() - transcribe_start

            try:
                es = get_elasticsearch_service()
                file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else None
                es.index_capture({
                    'uuid': str(uuid.uuid4()),
                    'created_at': datetime.now(timezone.utc).isoformat(),
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
                    'metadata': {'capture_timestamp': timestamp,
                                 'audio_duration': transcription_result.get('duration')}
                })
            except Exception as es_error:
                logger.warning(f"Could not index to Elasticsearch: {es_error}")

            result_data: Dict[str, Any] = {
                'status': 'success',
                'mode': 'voice',
                'capture': {'audio_file': audio_file, 'frequency': frequency,
                            'modulation': modulation, 'duration': duration},
                'transcription': transcription_result,
                'timestamp': datetime.now().isoformat(),
            }
            if transcription_result.get('simulation_mode'):
                result_data['warning'] = 'Transcription was simulated, not real'
                result_data['simulation_mode'] = True

            _update('completed', result=result_data)

    except Exception as e:
        logger.error(f"Capture worker {capture_id} failed: {e}", exc_info=True)
        _update('failed', error=str(e))
    finally:
        _capture_busy.clear()


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


# ============================================================================
# Blueprint Registration
# ============================================================================

# Import blueprints
from blueprints.health import health_bp
from blueprints.sdr import sdr_bp
from blueprints.capture import capture_bp
from blueprints.aprs import aprs_bp
from blueprints.pocsag import pocsag_bp
from blueprints.repeater import repeater_bp
from blueprints.streaming import streaming_bp

# Register blueprints
app.register_blueprint(health_bp)
app.register_blueprint(sdr_bp)
app.register_blueprint(capture_bp)
app.register_blueprint(aprs_bp)
app.register_blueprint(pocsag_bp)
app.register_blueprint(repeater_bp)
app.register_blueprint(streaming_bp)


# ============================================================================
# API Endpoints (Legacy - being migrated to blueprints)
# ============================================================================

@app.route('/capture-and-transcribe', methods=['POST'])
def capture_and_transcribe() -> Response | tuple[Response, int]:
    """
    Start an async radio capture + decode/transcribe job.

    Returns HTTP 202 immediately with a capture_id. Poll
    GET /capture-status/<capture_id> for progress and result.

    Request body:
    {
        "frequency": 100000000,
        "modulation": "FM",
        "duration": 30,
        "gain": 20,
        "sample_rate": 2000000,
        "mode": "voice",       # "voice", "aprs", or "pocsag"
        "language": "en"       # optional (voice mode only)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON body'}), 400

        if 'frequency' not in data:
            return jsonify({'error': 'frequency is required'}), 400

        frequency = int(float(data['frequency']))
        modulation = data.get('modulation', 'FM')
        duration = int(data.get('duration', 30))
        gain = int(data.get('gain', 20))
        sample_rate = int(data.get('sample_rate', 2000000))
        mode = data.get('mode', 'voice')
        language = data.get('language')

        if mode not in ['voice', 'aprs', 'pocsag']:
            return jsonify({'error': 'mode must be "voice", "aprs", or "pocsag"'}), 400

        sdr_type_val = detect_sdr()
        if mode in ['pocsag', 'aprs']:
            if sdr_type_val == SDRType.RTLSDR:
                original_sample_rate = sample_rate
                sample_rate = min(sample_rate, 250000)
                if original_sample_rate != sample_rate:
                    logger.info(f"Sample rate reduced for {mode} mode: {original_sample_rate/1e6:.1f} MHz -> {sample_rate/1e3:.0f} kHz")
            else:
                logger.info(f"HackRF detected: keeping sample rate at {sample_rate/1e6:.1f} MHz (hardware minimum: 2 MHz)")

        if sdr_type_val == SDRType.HACKRF and mode == 'pocsag':
            MAX_DURATIONS: Dict[str, int] = {'pocsag': 60, 'aprs': 180, 'voice': 600}
        else:
            MAX_DURATIONS = {'pocsag': 120, 'aprs': 300, 'voice': 600}

        max_duration = MAX_DURATIONS.get(mode, 600)
        if duration > max_duration:
            return jsonify({
                'error': f'{mode.upper()} captures are limited to {max_duration} seconds to prevent memory issues',
                'max_duration': max_duration,
                'requested_duration': duration
            }), 400

        # Reject if SDR is already in use
        if has_active_scan() or _capture_busy.is_set():
            return jsonify({'error': 'SDR device is busy — another capture or scan is in progress'}), 409

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.wav')
        json_file = os.path.join(RECORDING_DIR, f'capture_{timestamp}.json')

        capture_id = str(uuid.uuid4())
        _save_capture_session(capture_id, {
            'capture_id': capture_id,
            'status': 'queued',
            'mode': mode,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'result': None,
            'error': None,
        })

        capture_thread_pool.submit(
            _capture_worker,
            capture_id, frequency, modulation, duration, gain,
            sample_rate, mode, language, sdr_type_val, timestamp,
            audio_file, json_file,
        )

        return jsonify({'capture_id': capture_id, 'status': 'queued'}), 202

    except Exception as e:
        logger.error(f"Capture and Transcribe error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/capture-status/<capture_id>', methods=['GET'])
def get_capture_status(capture_id: str) -> Response | tuple[Response, int]:
    """Poll the status of an async capture job started by POST /capture-and-transcribe."""
    session = _get_capture_session(capture_id)
    if not session:
        return jsonify({'error': 'Capture session not found or expired'}), 404
    return jsonify(session)


@app.route('/captures/<int:capture_id>', methods=['GET'])
def get_capture(capture_id: int) -> Response | tuple[Response, int]:
    """Get a single capture by ID"""
    try:
        es = get_elasticsearch_service()
        result = es.get_capture_by_id(str(capture_id))

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


# ============================================================================
# Repeater Scanning Endpoints
# ============================================================================

def _scan_repeaters_worker(
    session_id: int,
    repeaters: list[Dict[str, Any]],
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
            # Update progress in Redis
            session_obj = scan_session_manager.get_session(session_id)
            if session_obj:
                elapsed_seconds = (datetime.now(timezone.utc) - session_obj.start_time).total_seconds()
                session_obj.update_progress(
                    current_index=idx,
                    current_repeater=repeater['callsign'],
                    elapsed_time=elapsed_seconds
                )
                scan_session_manager.save_session(session_obj)

            frequency = repeater['output_frequency']
            callsign = repeater['callsign']

            logger.info(f"Scanning repeater {idx+1}/{len(repeaters)}: {callsign} ({frequency/1e6:.4f} MHz)")

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
                    'created_at': datetime.now(timezone.utc).isoformat(),
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
                    'created_at': datetime.now(timezone.utc).isoformat(),
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

                # Update session with partial results in Redis
                session_obj = scan_session_manager.get_session(session_id)
                if session_obj:
                    session_obj.results = results
                    session_obj.repeaters_scanned = repeaters_scanned
                    session_obj.repeaters_with_activity = repeaters_with_activity
                    scan_session_manager.save_session(session_obj)

                # Clean up IQ file to save disk space (prevents disk filling)
                try:
                    if os.path.exists(iq_file):
                        os.remove(iq_file)
                        logger.debug(f"Cleaned up IQ file: {iq_file}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup IQ file {iq_file}: {cleanup_error}")

            except Exception as e:
                logger.error(f"Error scanning {callsign}: {e}")
                results.append({
                    'repeater_id': repeater.get('uuid', repeater.get('id')),
                    'callsign': callsign,
                    'frequency': frequency,
                    'error': str(e)
                })

        # Mark session as completed in Redis
        session_obj = scan_session_manager.get_session(session_id)
        if session_obj:
            session_obj.complete(results)
            scan_session_manager.save_session(session_obj)

        # Update database
        # Scan sessions are in-memory only
        # # REMOVED: db.update_scan_session() - using in-memory scan_sessions dict instead

        # Record completion metrics
        logger.info(f"Scan session {session_id} completed: {repeaters_scanned} scanned, {repeaters_with_activity} with activity")

    except Exception as e:
        logger.exception(f"Scan session {session_id} failed: {e}")
        # Mark session as failed in Redis
        session_obj = scan_session_manager.get_session(session_id)
        if session_obj:
            session_obj.fail(str(e))
            scan_session_manager.save_session(session_obj)

        # Scan sessions are in-memory only (removed db.update_scan_session)


# ===========================================================================
# Session Manager Initialization
# ===========================================================================

# session_manager is defined in session_store.py to avoid circular imports
# with blueprints/streaming.py
from session_store import session_manager


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
