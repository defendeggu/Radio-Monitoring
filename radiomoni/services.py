"""
Shared service singletons and file helpers used by blueprints and jobs.

Kept separate from the Flask app so that blueprints, background jobs and the
scheduler can import them without circular imports.
"""

import os
import re
import shutil
import threading
from typing import Optional

from radiomoni import config
from radiomoni.decoders.aprs import APRSDecoder
from radiomoni.decoders.pocsag import POCSAGDecoder
from radiomoni.transcription_service import TranscriptionService

RECORDING_DIR = config.RECORDING_DIR

_lock = threading.Lock()
_transcription: Optional[TranscriptionService] = None
_aprs: Optional[APRSDecoder] = None
_pocsag: Optional[POCSAGDecoder] = None

SAFE_FILENAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$')


def get_transcription_service() -> TranscriptionService:
    """Lazy-load the Whisper model (it is large)."""
    global _transcription
    if _transcription is None:
        with _lock:
            if _transcription is None:
                _transcription = TranscriptionService(
                    model=config.WHISPER_MODEL,
                    device=config.WHISPER_DEVICE,
                    compute_type=config.WHISPER_COMPUTE_TYPE,
                )
    return _transcription


def whisper_status() -> dict[str, object]:
    """Device actually used by Whisper (the model is loaded on first use)."""
    if _transcription is None:
        return {'loaded': False, 'requested_device': config.WHISPER_DEVICE, 'model': config.WHISPER_MODEL}
    return {'loaded': True, 'model': _transcription.model_name, 'device': _transcription.device,
            'compute_type': _transcription.compute_type, 'requested_device': config.WHISPER_DEVICE,
            'fallback_reason': _transcription.fallback_reason}


def get_aprs_decoder() -> APRSDecoder:
    global _aprs
    if _aprs is None:
        _aprs = APRSDecoder()
    return _aprs


def get_pocsag_decoder() -> POCSAGDecoder:
    global _pocsag
    if _pocsag is None:
        _pocsag = POCSAGDecoder()
    return _pocsag


def recording_dir() -> str:
    """Current recording directory (read at call time so tests can override it)."""
    return os.getenv('AUDIO_OUTPUT_DIR', RECORDING_DIR)


def validate_file_path(file_path: str, base_dir: Optional[str] = None) -> str:
    """
    Resolve a user-supplied path and make sure it stays inside base_dir.

    Symlinks are resolved, so a link pointing outside the directory is rejected.
    Raises ValueError on traversal attempts.
    """
    base = os.path.realpath(base_dir or recording_dir())
    candidate = file_path if os.path.isabs(file_path) else os.path.join(base, file_path)
    resolved = os.path.realpath(candidate)
    try:
        common = os.path.commonpath([base, resolved])
    except ValueError:
        raise ValueError("Invalid file path: path traversal detected")
    if common != base:
        raise ValueError("Invalid file path: access outside the recordings directory is not allowed")
    return resolved


def safe_recording_path(filename: str) -> str:
    """Path of a recording given only its file name (no directories allowed)."""
    if not SAFE_FILENAME.match(filename):
        raise ValueError("Invalid file name")
    return validate_file_path(filename)


def ensure_disk_space(path: Optional[str] = None) -> None:
    """Refuse new recordings when the disk is nearly full."""
    target = path or recording_dir()
    os.makedirs(target, exist_ok=True)
    free_mb = shutil.disk_usage(target).free / (1024 * 1024)
    if free_mb < config.MIN_FREE_DISK_MB:
        raise OSError(f"Not enough free disk space ({free_mb:.0f} MB < {config.MIN_FREE_DISK_MB} MB)")
