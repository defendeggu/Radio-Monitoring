"""
SDR hardware endpoints: detection, current status and emergency stop.
"""

import logging
import os
import signal
import time
from typing import Any, Optional

from flask import Blueprint, Response, jsonify, request

from radiomoni import devices
from radiomoni import events
from radiomoni import sdr_lock
from radiomoni.api_docs import api
from radiomoni.errors import ApiError
from radiomoni.sdr_hardware import SDRType, detect_sdr, get_sdr_instance
from radiomoni.session_store import session_manager

logger = logging.getLogger(__name__)
sdr_bp = Blueprint('sdr', __name__)

# Processes that hold the SDR (killed by force-stop)
SDR_PROCESSES = {'hackrf_transfer', 'rtl_sdr', 'rtl_fm', 'airspyhf_rx', 'uhd_rx_cfile', 'multimon-ng',
                 'direwolf', 'rtl_433', 'readsb', 'rtl_ais'}
# the tools that open a device of each type (force-stop of one device)
DEVICE_PROCESSES: dict[SDRType, set[str]] = {
    SDRType.HACKRF: {'hackrf_transfer', 'readsb'},
    SDRType.RTLSDR: {'rtl_sdr', 'rtl_fm', 'rtl_433', 'readsb', 'rtl_ais'},
    SDRType.AIRSPYHF: {'airspyhf_rx'},
    SDRType.USRP: {'uhd_rx_cfile'},
}

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


def _device_states(active: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every connected device with its lock holder and sessions (plus held locks of devices not listed)."""
    held = sdr_lock.holders()
    listed = devices.list_devices()
    if not listed:
        try:
            listed = [devices.resolve('auto')]
        except (ValueError, devices.NoSdrError):
            listed = []
    states = []
    for d in listed:
        holder = held.pop(d.id, None)
        states.append({**d.to_dict(), 'busy': holder is not None, 'holder': holder,
                       'preemptible': holder is not None and sdr_lock.is_preemptible(holder.get('kind')),
                       'sessions': [s['session_id'] for s in active if s.get('device_id') == d.id]})
    for device_id, holder in held.items():          # e.g. a USRP (not on USB)
        states.append({'id': device_id, 'type': device_id.split(':', 1)[0], 'label': device_id, 'busy': True,
                       'holder': holder, 'preemptible': sdr_lock.is_preemptible(holder.get('kind')),
                       'sessions': [s['session_id'] for s in active if s.get('device_id') == device_id]})
    return states


@sdr_bp.get('/sdr/devices')
@api('Connected SDR devices, each with its own lock (who uses it)', tags=['SDR'])
def sdr_devices() -> Response:
    if request.args.get('refresh') in ('1', 'true'):
        devices.clear_cache()
    active = [s.to_dict() for s in session_manager.list_sessions() if s.status in ('starting', 'running')]
    return jsonify({'status': 'success', 'default': devices.default_id(), 'devices': _device_states(active)})


@sdr_bp.get('/sdr/status')
@api('Who is using the SDR right now (busy/holder: default device; devices: all)', tags=['SDR'])
def sdr_status() -> Response:
    session_manager.reap_orphaned_sessions()
    holder = sdr_lock.current_holder()
    active = [s.to_dict() for s in session_manager.list_sessions() if s.status in ('starting', 'running')]
    # a preemptible holder (waterfall) gives way: for starting jobs the SDR counts as free
    preemptible = holder is not None and sdr_lock.is_preemptible(holder.get('kind'))
    return jsonify({'busy': holder is not None, 'preemptible': preemptible, 'holder': holder,
                    'active_sessions': active, 'default_device': devices.default_id(),
                    'devices': _device_states(active)})


@sdr_bp.post('/sdr/force-stop')
@api('Emergency stop: end all sessions and kill SDR processes (?device_id= only that device)', tags=['SDR'])
def sdr_force_stop() -> Response:
    device_id = request.args.get('device_id') or None
    if device_id and len(device_id) > 80:
        raise ApiError('Invalid device_id', 400)
    stopped = stop_all_local_decoders(device_id)
    events.send_control('stop_all', device_id=device_id)
    killed = kill_sdr_processes(device_id)
    sdr_lock.force_release(device_id)
    for session in session_manager.list_sessions():
        if device_id and session.device_id != device_id:
            continue
        if session.status in ('starting', 'running'):
            session.status = 'completed'
            session.error = 'Stopped by force-stop'
            session_manager.save_session(session)
    events.publish('sdr', {'busy': False, 'reason': 'force-stop', 'device_id': device_id})
    return jsonify({'status': 'success',
                    'message': f'SDR {device_id} stopped' if device_id else 'All SDR processes stopped',
                    'sessions_stopped': stopped, 'processes_killed': killed})


def stop_all_local_decoders(device_id: Optional[str] = None) -> int:
    """Stop this process's decoders (only those on `device_id` when given)."""
    decoders = {sid: d for sid, d in session_manager.get_all_active_decoders().items()
                if device_id is None or (getattr(d, 'device', None) is not None and d.device.id == device_id)}
    for sid, decoder in decoders.items():
        try:
            logger.info(f"Force-stopping decoder for session {sid}")
            decoder.stop_stream()
        except Exception as e:
            logger.warning(f"Error stopping decoder {sid}: {e}")
        session_manager.unregister_decoder(sid)
    return len(decoders)


def _matches_device(exe: str, args: list[str], device: Optional[devices.Device]) -> bool:
    if device is None:
        return exe in SDR_PROCESSES
    if exe not in DEVICE_PROCESSES.get(device.type, set()):
        return False
    selector = device.args(exe)
    if device.address:                       # USRP: addr=<ip> in the arguments
        return any(device.address in a for a in args)
    if not selector:
        return True                          # the only device of its type
    return any(args[i:i + len(selector)] == selector for i in range(len(args)))


def kill_sdr_processes(device_id: Optional[str] = None) -> list[str]:
    """SIGKILL SDR-related processes owned by this container (scans /proc); only those that
    open `device_id` when given."""
    device: Optional[devices.Device] = None
    if device_id:
        try:
            device = devices.resolve(device_id=device_id)
        except ValueError:
            return []
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
            args = [a.decode('utf-8', errors='ignore') for a in cmdline[1:] if a]
            if _matches_device(exe, args, device):
                os.kill(int(pid_str), signal.SIGKILL)
                killed.append(exe)
                logger.info(f"Killed SDR process {exe} (PID {pid_str})")
        except (ProcessLookupError, PermissionError, FileNotFoundError):
            pass
    return killed
