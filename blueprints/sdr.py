"""
SDR hardware endpoints: detection, current status and emergency stop.
"""

import logging
import os
import signal
import time
from typing import Any

from flask import Blueprint, Response, jsonify

import events
import sdr_lock
from api_docs import api
from sdr_hardware import SDRType, detect_sdr, get_sdr_instance
from session_store import session_manager

logger = logging.getLogger(__name__)
sdr_bp = Blueprint('sdr', __name__)

# Processes that hold the SDR (killed by force-stop)
SDR_PROCESSES = {'hackrf_transfer', 'rtl_sdr', 'rtl_fm', 'airspyhf_rx', 'uhd_rx_cfile', 'multimon-ng',
                 'direwolf', 'rtl_433', 'readsb', 'rtl_ais'}

_detect_cache: tuple[float, dict[str, Any]] = (0.0, {})
DETECT_CACHE_SECONDS = 10


def _detect() -> dict[str, Any]:
    global _detect_cache
    ts, cached = _detect_cache
    if cached and time.time() - ts < DETECT_CACHE_SECONDS:
        return cached
    sdr_type = detect_sdr()
    if sdr_type == SDRType.UNKNOWN:
        result: dict[str, Any] = {'detected': False, 'type': 'unknown',
                                  'message': 'No SDR detected. Connect a HackRF One, RTL-SDR or Airspy HF+ '
                                             '(USRP N200 is selected by IP address).'}
    else:
        instance = get_sdr_instance(frequency=100_000_000, sdr_type=sdr_type)
        min_freq, max_freq = instance.get_frequency_range()
        max_rate = instance.get_max_sample_rate()
        result = {
            'detected': True,
            'type': sdr_type.value,
            'frequency_range': {'min_hz': min_freq, 'max_hz': max_freq,
                                'min_mhz': min_freq / 1e6, 'max_mhz': max_freq / 1e6},
            'max_sample_rate_hz': max_rate,
            'max_sample_rate_mhz': max_rate / 1e6,
        }
    _detect_cache = (time.time(), result)
    return result


@sdr_bp.get('/sdr/detect')
@api('Detect connected SDR hardware and its capabilities', tags=['SDR'])
def detect_sdr_hardware() -> Response:
    """Returns detected=false (HTTP 200) when no device is connected."""
    return jsonify(_detect())


@sdr_bp.get('/sdr/status')
@api('Who is using the SDR right now', tags=['SDR'])
def sdr_status() -> Response:
    holder = sdr_lock.current_holder()
    active = [s.to_dict() for s in session_manager.list_sessions() if s.status in ('starting', 'running')]
    return jsonify({'busy': holder is not None, 'holder': holder, 'active_sessions': active})


@sdr_bp.post('/sdr/force-stop')
@api('Emergency stop: end all sessions and kill SDR processes', tags=['SDR'])
def sdr_force_stop() -> Response:
    stopped = stop_all_local_decoders()
    events.send_control('stop_all')
    killed = kill_sdr_processes()
    sdr_lock.force_release()
    for session in session_manager.list_sessions():
        if session.status in ('starting', 'running'):
            session.status = 'completed'
            session.error = 'Stopped by force-stop'
            session_manager.save_session(session)
    events.publish('sdr', {'busy': False, 'reason': 'force-stop'})
    return jsonify({'status': 'success', 'message': 'All SDR processes stopped',
                    'sessions_stopped': stopped, 'processes_killed': killed})


def stop_all_local_decoders() -> int:
    decoders = session_manager.get_all_active_decoders()
    for sid, decoder in decoders.items():
        try:
            logger.info(f"Force-stopping decoder for session {sid}")
            decoder.stop_stream()
        except Exception as e:
            logger.warning(f"Error stopping decoder {sid}: {e}")
        session_manager.unregister_decoder(sid)
    return len(decoders)


def kill_sdr_processes() -> list[str]:
    """SIGKILL SDR-related processes owned by this container (scans /proc)."""
    killed: list[str] = []
    for pid_str in os.listdir('/proc'):
        if not pid_str.isdigit():
            continue
        try:
            with open(f'/proc/{pid_str}/cmdline', 'rb') as f:
                cmdline = f.read().split(b'\x00')
            if not cmdline or not cmdline[0]:
                continue
            exe = os.path.basename(cmdline[0].decode('utf-8', errors='ignore'))
            if exe in SDR_PROCESSES:
                os.kill(int(pid_str), signal.SIGKILL)
                killed.append(exe)
                logger.info(f"Killed SDR process {exe} (PID {pid_str})")
        except (ProcessLookupError, PermissionError, FileNotFoundError):
            pass
    return killed
