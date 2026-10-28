"""
Background jobs that use the SDR: one-shot captures, repeater scans and the
start of streaming sessions.

Each job takes the Redis SDR lease *before* it is queued, so a second request
gets HTTP 409 immediately instead of waiting in a queue. The lease is released
when the job ends (or expires after a crash).
"""

import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import alerts
import config
import events
from redis_client import get_redis
from repeater_activity_analyzer import RepeaterActivityAnalyzer
from scan_session_manager import RepeaterScanSession, get_scan_session_manager
from schemas import CaptureRequest, RepeaterScanRequest
from sdr_hardware import SDRType, detect_sdr, get_sdr_instance
import sdr_lock
from sdr_lock import SdrLease
from services import (ensure_disk_space, get_aprs_decoder, get_pocsag_decoder,
                      get_transcription_service, recording_dir)
from storage import get_storage

logger = logging.getLogger(__name__)

# One worker each: there is one SDR. The lease enforces exclusivity across processes.
capture_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='capture-worker')
scan_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='scan-worker')

CAPTURE_TTL = 3600


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========================================================================== capture
def save_capture_session(capture_id: str, data: dict[str, Any]) -> None:
    get_redis().set(f"capture_session:{capture_id}", json.dumps(data, default=str), ex=CAPTURE_TTL)
    events.publish('capture', {k: data.get(k) for k in ('capture_id', 'status', 'mode', 'error')})


def get_capture_session(capture_id: str) -> Optional[dict[str, Any]]:
    raw = get_redis().get(f"capture_session:{capture_id}")
    return json.loads(raw) if raw else None


def build_capture_doc(req: CaptureRequest, audio_file: str, sdr_type: SDRType, timestamp: str,
                      processing_seconds: Optional[float] = None, **extra: Any) -> dict[str, Any]:
    """Common capture document for all modes."""
    return {
        'uuid': str(uuid.uuid4()),
        'created_at': _utcnow(),
        'frequency': req.frequency,
        'modulation': req.modulation,
        'duration_seconds': req.duration,
        'rf_gain': req.gain,
        'sample_rate': req.sample_rate,
        'audio_file': os.path.basename(audio_file),
        'file_size': os.path.getsize(audio_file) if os.path.exists(audio_file) else None,
        'sdr_type': sdr_type.value,
        'mode': req.mode,
        'transcription_duration': processing_seconds,
        'metadata': {'capture_timestamp': timestamp},
        **extra,
    }


def submit_capture(req: CaptureRequest) -> str:
    """Validate hardware, take the SDR lease and queue the capture. Returns capture_id."""
    ensure_disk_space()
    sdr_type = detect_sdr(preferred_type=req.device_type, device_address=req.device_address_str)
    if sdr_type == SDRType.UNKNOWN:
        raise RuntimeError('No SDR hardware detected')

    # APRS/POCSAG only need a narrow band; RTL-SDR copes better with a low rate.
    if req.mode in ('aprs', 'pocsag') and sdr_type == SDRType.RTLSDR:
        req.sample_rate = min(req.sample_rate, 250_000)
    if sdr_type == SDRType.HACKRF and req.mode == 'pocsag' and req.duration > 60:
        raise ValueError('POCSAG captures with HackRF are limited to 60 seconds (memory)')

    # Validates frequency/sample rate for the detected device (raises ValueError)
    get_sdr_instance(frequency=req.frequency, sample_rate=req.sample_rate, gain=req.gain,
                     sdr_type=sdr_type, device_address=req.device_address_str)

    capture_id = str(uuid.uuid4())
    lease = SdrLease(f"capture:{capture_id}", 'capture',
                     {'mode': req.mode, 'frequency': req.frequency}).acquire()
    save_capture_session(capture_id, {'capture_id': capture_id, 'status': 'queued', 'mode': req.mode,
                                      'created_at': _utcnow(), 'result': None, 'error': None})
    try:
        capture_pool.submit(_capture_worker, capture_id, req, sdr_type, lease)
    except Exception:
        lease.release()
        raise
    return capture_id


def _capture_worker(capture_id: str, req: CaptureRequest, sdr_type: SDRType, lease: SdrLease) -> None:
    created_at = _utcnow()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    base = os.path.join(recording_dir(), f"capture_{timestamp}_{capture_id[:8]}")
    audio_file, json_file = base + '.wav', base + '.json'

    def update(status: str, result: Optional[dict[str, Any]] = None, error: Optional[str] = None) -> None:
        save_capture_session(capture_id, {'capture_id': capture_id, 'status': status, 'mode': req.mode,
                                          'created_at': created_at, 'result': result, 'error': error})

    try:
        update('capturing')
        sdr = get_sdr_instance(frequency=req.frequency, sample_rate=req.sample_rate, gain=req.gain,
                               sdr_type=sdr_type, device_address=req.device_address_str)
        sdr.capture_audio(req.duration, audio_file, req.modulation)
        update('processing')
        lease.release()  # the SDR is free again; decoding only needs the file
        capture_info = {'audio_file': os.path.basename(audio_file), 'frequency': req.frequency,
                        'modulation': req.modulation, 'duration': req.duration}
        started = time.time()

        if req.mode == 'raw':
            doc = build_capture_doc(req, audio_file, sdr_type, timestamp)
            _store_capture(doc)
            update('completed', result={'status': 'success', 'mode': 'raw', 'capture': {**capture_info, 'id': doc['uuid']},
                                        'timestamp': _utcnow()})
            return

        if req.mode in ('aprs', 'pocsag'):
            decoder = get_aprs_decoder() if req.mode == 'aprs' else get_pocsag_decoder()
            items: list[dict[str, Any]] = [dict(p) for p in decoder.decode(audio_file)]
            doc = build_capture_doc(req, audio_file, sdr_type, timestamp, time.time() - started)
            doc['metadata']['count'] = len(items)
            _store_capture(doc)
            storage = get_storage()
            for item in items:
                item.update({'uuid': str(uuid.uuid4()), 'capture_id': doc['uuid'],
                             'timestamp': _utcnow(), 'frequency': req.frequency})
                try:
                    if req.mode == 'aprs':
                        storage.index_aprs(item)
                    else:
                        storage.index_pocsag(item)
                except Exception as e:
                    logger.warning(f"Could not store {req.mode} item: {e}")
                events.publish(req.mode, item)
                alerts.evaluate(req.mode, item)
            key, count_key = ('packets', 'packet_count') if req.mode == 'aprs' else ('messages', 'message_count')
            update('completed', result={
                'status': 'success', 'mode': req.mode,
                'capture': {**capture_info, 'id': doc['uuid']},
                req.mode: {count_key: len(items), key: items},
                'timestamp': _utcnow()})
            return

        # voice
        transcription = dict(get_transcription_service().transcribe(
            audio_file=audio_file, language=req.language, task=req.task, beam_size=req.beam_size,
            vad_filter=req.vad_filter, initial_prompt=req.initial_prompt))
        with open(json_file, 'w') as f:
            json.dump(transcription, f, indent=2)
        doc = build_capture_doc(
            req, audio_file, sdr_type, timestamp, time.time() - started,
            json_file=os.path.basename(json_file),
            transcription=transcription.get('text'),
            detected_language=transcription.get('language'),
            confidence_score=transcription.get('language_probability'),
            segments=transcription.get('segments'))
        doc['metadata']['audio_duration'] = transcription.get('duration')
        _store_capture(doc)
        alerts.evaluate('voice', {'transcription': transcription.get('text'), 'frequency': req.frequency})
        result: dict[str, Any] = {'status': 'success', 'mode': 'voice',
                                  'capture': {**capture_info, 'id': doc['uuid']},
                                  'transcription': transcription, 'timestamp': _utcnow()}
        if transcription.get('simulation_mode'):
            result['warning'] = 'Transcription was simulated, not real'
            result['simulation_mode'] = True
        update('completed', result=result)

    except Exception as e:
        logger.error(f"Capture {capture_id} failed: {e}", exc_info=True)
        update('failed', error=_public_error(e))
    finally:
        lease.release()


def _store_capture(doc: dict[str, Any]) -> None:
    try:
        get_storage().index_capture(doc)
    except Exception as e:
        logger.warning(f"Could not store capture: {e}")


def _public_error(e: Exception) -> str:
    """Error text that is safe to show (no paths, no internals)."""
    if isinstance(e, (ValueError, RuntimeError, FileNotFoundError, OSError, TimeoutError)):
        return str(e).replace(recording_dir(), '<recordings>')[:300]
    return 'Capture failed (see server log)'


# =========================================================================== repeater scan
def submit_repeater_scan(req: RepeaterScanRequest) -> dict[str, Any]:
    """Pick repeaters, take the SDR lease and queue the scan."""
    storage = get_storage()
    if req.repeater_ids:
        repeaters = [r for r in (storage.get_repeater_by_id(rid) for rid in req.repeater_ids) if r]
    else:
        repeaters = storage.get_repeaters(band=req.band, canton=req.canton, mode='FM', status='active',
                                          limit=500)
    if not repeaters:
        raise LookupError('No repeaters found matching criteria')

    manager = get_scan_session_manager()
    session_id = manager.get_next_session_id()
    lease = SdrLease(f"scan:{session_id}", 'repeater_scan', {'repeaters': len(repeaters)}).acquire()
    session = RepeaterScanSession(session_id=session_id, repeaters_total=len(repeaters),
                                  duration_per_repeater=req.duration_per_repeater,
                                  sample_rate=req.sample_rate, gain=req.gain,
                                  total_duration=req.total_duration, until_stopped=req.until_stopped)
    manager.save_session(session)
    try:
        scan_pool.submit(scan_repeaters_worker, session_id, repeaters, req.duration_per_repeater,
                         req.sample_rate, req.gain, lease, req.total_duration, req.until_stopped)
    except Exception:
        lease.release()
        raise
    estimated: Optional[int] = None if req.until_stopped else (
        req.total_duration or len(repeaters) * req.duration_per_repeater)
    return {'session_id': session_id, 'repeaters_count': len(repeaters),
            'estimated_duration_seconds': estimated}


def stop_repeater_scan(session_id: int) -> bool:
    """Ask a running scan to stop and abort its current capture. False if it is not running."""
    manager = get_scan_session_manager()
    session = manager.get_session(session_id)
    if session is None or session.status != 'in_progress':
        return False
    manager.request_stop(session_id)
    holder = sdr_lock.current_holder()
    if holder and holder.get('owner') == f"scan:{session_id}":
        from blueprints.sdr import kill_sdr_processes
        kill_sdr_processes()  # the capture of the current repeater ends now instead of after its duration
    return True


def _measure_repeater(repeater: dict[str, Any], session_id: int, scan_duration: int, sample_rate: int,
                      gain: int, sdr_type: SDRType, analyzer: RepeaterActivityAnalyzer) -> dict[str, Any]:
    """Record one repeater, analyse the carrier activity and store capture and metrics."""
    storage = get_storage()
    frequency = int(repeater['output_frequency'])
    callsign = str(repeater.get('callsign', '?'))
    safe_call = ''.join(c for c in callsign if c.isalnum() or c in '-_')[:20] or 'unknown'
    iq_file = os.path.join(recording_dir(),
                           f"repeater_scan_{safe_call}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.iq")
    try:
        scan_start = datetime.now(timezone.utc)
        sdr = get_sdr_instance(frequency=frequency, sample_rate=sample_rate, gain=gain, sdr_type=sdr_type)
        sdr.capture_iq(scan_duration, iq_file)
        metrics = analyzer.analyze_iq_file(iq_file)
        m = metrics.to_dict()
        capture_uuid = str(uuid.uuid4())
        _store_capture({
            'uuid': capture_uuid, 'created_at': _utcnow(), 'frequency': frequency, 'modulation': 'FM',
            'duration_seconds': scan_duration, 'rf_gain': gain, 'sample_rate': sample_rate,
            'sdr_type': sdr_type.value, 'mode': 'repeater_scan',
            'metadata': {'type': 'repeater_scan', 'session_id': session_id}})
        # metrics are stored flat (summary aggregations) and nested (details)
        storage.index_repeater_activity({
            'uuid': str(uuid.uuid4()), 'created_at': _utcnow(), 'capture_id': capture_uuid,
            'repeater_id': repeater.get('uuid', repeater.get('id')),
            'repeater_callsign': callsign, 'frequency': frequency,
            'band': repeater.get('band'), 'canton': repeater.get('canton'),
            'scan_start_time': scan_start.isoformat(), 'scan_end_time': _utcnow(),
            **{k: v for k, v in m.items() if k != 'transmissions'},
            'metrics': m})
        return m
    finally:
        if os.path.exists(iq_file):
            os.remove(iq_file)


def _add_to_summary(summary: dict[str, dict[str, Any]], repeater: dict[str, Any],
                    metrics: Optional[dict[str, Any]], error: Optional[str]) -> None:
    """Aggregate the measurements of all rounds per repeater (bounded result list for long scans)."""
    key = str(repeater.get('uuid', repeater.get('id')))
    entry = summary.setdefault(key, {
        'repeater_id': repeater.get('uuid', repeater.get('id')), 'callsign': str(repeater.get('callsign', '?')),
        'frequency': int(repeater['output_frequency']), 'location': repeater.get('location_name'),
        'band': repeater.get('band'), 'rounds': 0, 'active_rounds': 0, 'errors': 0, 'transmission_count': 0,
        'activity_percentage': 0.0, 'average_signal_strength': None, 'activity_detected': False,
        'activity': None, 'error': None, 'last_scan': None})
    entry['last_scan'] = _utcnow()
    if metrics is None:
        entry['errors'] += 1
        entry['error'] = error
        return
    entry['rounds'] += 1
    n = entry['rounds']
    carrier = bool(metrics.get('carrier_detected'))
    entry['active_rounds'] += int(carrier)
    entry['activity_detected'] = entry['active_rounds'] > 0
    entry['transmission_count'] += int(metrics.get('transmission_count') or 0)
    pct = float(metrics.get('activity_percentage') or 0.0)
    entry['activity_percentage'] = round(entry['activity_percentage'] + (pct - entry['activity_percentage']) / n, 2)
    if metrics.get('average_signal_strength') is not None:
        entry['average_signal_strength'] = metrics['average_signal_strength']
    entry['activity'] = {k: v for k, v in metrics.items() if k != 'transmissions'}
    entry['error'] = None


def scan_repeaters_worker(session_id: int, repeaters: list[dict[str, Any]], scan_duration: int,
                          sample_rate: int, gain: int, lease: Optional[SdrLease] = None,
                          total_duration: Optional[int] = None, until_stopped: bool = False) -> None:
    """Scan the repeaters in rounds: once, until total_duration has passed, or until stopped."""
    manager = get_scan_session_manager()
    analyzer = RepeaterActivityAnalyzer(sample_rate=sample_rate)
    sdr_type = detect_sdr()
    started = time.monotonic()
    deadline = started + total_duration if total_duration else None
    looping = until_stopped or deadline is not None
    summary: dict[str, dict[str, Any]] = {}
    stopped = False

    def save(**changes: Any) -> None:
        session = manager.get_session(session_id)
        if session:
            for name, value in changes.items():
                setattr(session, name, value)
            session.results = list(summary.values())
            session.repeaters_scanned = sum(1 for e in summary.values() if e['rounds'])
            session.repeaters_with_activity = sum(1 for e in summary.values() if e['activity_detected'])
            session.elapsed_time = time.monotonic() - started
            manager.save_session(session)

    try:
        round_no = 0
        while not stopped:
            round_no += 1
            for idx, repeater in enumerate(repeaters):
                if manager.stop_requested(session_id):
                    stopped = True
                    break
                # with a total duration, start a repeater only if it ends in time (the first one always runs)
                if deadline is not None and (round_no, idx) != (1, 0) and time.monotonic() + scan_duration > deadline:
                    break
                callsign = str(repeater.get('callsign', '?'))
                save(current_index=idx, current_repeater=callsign, current_round=round_no)
                events.publish('scan', {'session_id': session_id, 'index': idx, 'total': len(repeaters),
                                        'round': round_no, 'callsign': callsign})
                try:
                    metrics = _measure_repeater(repeater, session_id, scan_duration, sample_rate, gain,
                                                sdr_type, analyzer)
                    _add_to_summary(summary, repeater, metrics, None)
                except Exception as e:
                    if manager.stop_requested(session_id):  # capture aborted by the stop request
                        stopped = True
                        break
                    logger.error(f"Error scanning {callsign}: {e}")
                    _add_to_summary(summary, repeater, None, _public_error(e))
                save()
            else:
                save(rounds_completed=round_no)
                if looping and (deadline is None or time.monotonic() + scan_duration <= deadline):
                    continue
            break

        session = manager.get_session(session_id)
        if session:
            session.results = list(summary.values())
            if stopped:
                session.stop()
                session.repeaters_scanned = sum(1 for e in summary.values() if e['rounds'])
                session.repeaters_with_activity = sum(1 for e in summary.values() if e['activity_detected'])
            else:
                session.complete(session.results)
            session.elapsed_time = time.monotonic() - started
            manager.save_session(session)
        logger.info(f"Scan session {session_id} {'stopped' if stopped else 'completed'} after {round_no} "
                    f"round(s): {len(summary)} repeaters")
    except Exception as e:
        logger.exception(f"Scan session {session_id} failed: {e}")
        session = manager.get_session(session_id)
        if session:
            session.fail(_public_error(e))
            manager.save_session(session)
    finally:
        events.publish('scan', {'session_id': session_id, 'finished': True})
        if lease:
            lease.release()


# =========================================================================== streaming
def start_stream_session(decoder: Any, mode: str, frequency: int, sample_rate: int, gain: int,
                         configure: Optional[Callable[[Any], None]] = None) -> str:
    """Take the SDR lease, create the session and start the decoder thread."""
    from session_store import session_manager

    lease = SdrLease(f"stream:{uuid.uuid4()}", mode, {'frequency': frequency}).acquire()
    try:
        session_id: str = session_manager.create_session(decoder_type=mode, decoder=decoder, frequency=frequency,
                                                         sample_rate=sample_rate, gain=gain)
        decoder.lease = lease
        if configure:
            configure(session_manager.get_session(session_id))
        decoder.start(session_manager)
        events.publish('session', {'session_id': session_id, 'mode': mode, 'status': 'starting',
                                   'frequency': frequency})
        return session_id
    except Exception:
        lease.release()
        raise


# =========================================================================== housekeeping
def cleanup_recordings(max_age_days: Optional[int] = None) -> int:
    """Delete recordings older than RECORDING_RETENTION_DAYS. Returns number of files removed."""
    days = config.RECORDING_RETENTION_DAYS if max_age_days is None else max_age_days
    if days <= 0:
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    directory = recording_dir()
    if not os.path.isdir(directory):
        return 0
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
            try:
                os.remove(path)
                removed += 1
            except OSError as e:
                logger.warning(f"Could not remove {name}: {e}")
    if removed:
        logger.info(f"Retention: removed {removed} recordings older than {days} days")
    return removed


def cleanup_scan_sessions() -> int:
    return get_scan_session_manager().cleanup_old_sessions(config.SCAN_SESSION_MAX_AGE_HOURS)


def recordings_stats() -> dict[str, Any]:
    directory = recording_dir()
    files = [os.path.join(directory, n) for n in os.listdir(directory)] if os.path.isdir(directory) else []
    sizes = [os.path.getsize(f) for f in files if os.path.isfile(f)]
    import shutil
    usage = shutil.disk_usage(directory) if os.path.isdir(directory) else None
    return {
        'count': len(sizes), 'total_bytes': sum(sizes),
        'retention_days': config.RECORDING_RETENTION_DAYS,
        'disk_free_bytes': usage.free if usage else None,
        'oldest_allowed': (datetime.now(timezone.utc) - timedelta(days=config.RECORDING_RETENTION_DAYS)).isoformat(),
    }
