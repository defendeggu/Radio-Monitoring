"""
An OnAir session: RadioMoni holds the SDR lock, OnAir has the radio open.

    lock taken (jobs.start_stream_session) -> /stop, /mode, /frequency, /gain, /start
    -> read the JSON lines OnAir writes -> store, publish, alerts
    -> /stop -> lock released

onair-server opens the radio only between /start and /stop (checked at the
device: RadioMoni gets "Resource busy" while it runs and the radio right after
the stop). Its settings file has autostart=0, so it never opens the radio on
its own; recover() stops it when no OnAir session holds a lock (after a crash).
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

from radiomoni import alerts, config, devices, events, sdr_lock
from radiomoni.decoders.streaming import BaseStreamingDecoder, SessionManager
from radiomoni.devices import Device
from radiomoni.onair import mapping
from radiomoni.onair.client import OnAirClient, OnAirError, find_device_index
from radiomoni.sdr_hardware import SDRType

logger = logging.getLogger(__name__)

KIND = 'onair'
SUPPORTED = (SDRType.HACKRF, SDRType.RTLSDR)
STATUS_EVERY = 5.0


def events_file() -> str:
    return os.path.join(config.ONAIR_DATA_DIR, 'events', 'onair-events.jsonl')


class JsonlTail:
    """Read the lines appended to a file from now on; follows OnAir's rotation (file -> file.1)."""

    def __init__(self, path: str):
        self.path = path
        self._buf = b''
        self._inode: Optional[int] = None
        self._offset = 0
        try:
            st = os.stat(path)
            self._inode, self._offset = st.st_ino, st.st_size
        except OSError:
            pass

    def _read_from(self, path: str, offset: int) -> tuple[bytes, int]:
        try:
            with open(path, 'rb') as f:
                f.seek(offset)
                data = f.read(4 * 1024 * 1024)
                return data, offset + len(data)
        except OSError:
            return b'', offset

    def read(self) -> list[str]:
        try:
            st = os.stat(self.path)
        except OSError:
            return []
        data = b''
        if self._inode is not None and (st.st_ino != self._inode or st.st_size < self._offset):
            rotated = self.path + '.1'
            try:
                if os.stat(rotated).st_ino == self._inode:
                    data, _ = self._read_from(rotated, self._offset)
            except OSError:
                pass
            self._offset = 0
        self._inode = st.st_ino
        more, self._offset = self._read_from(self.path, self._offset)
        data = self._buf + data + more
        *lines, self._buf = data.split(b'\n')
        return [ln.decode('utf-8', errors='replace') for ln in lines if ln.strip()]


def pick_device(device_id: Optional[str]) -> Device:
    """The requested SDR, else the first free HackRF / RTL-SDR, else the first one."""
    if device_id:
        device = devices.resolve(device_id=device_id)
        if device.type not in SUPPORTED:
            raise ValueError(f"OnAir runs on a HackRF or RTL-SDR here, not on {device.label}")
        return device
    candidates = [d for d in devices.list_devices() if d.type in SUPPORTED]
    if not candidates:
        raise ValueError('OnAir needs a HackRF or RTL-SDR')
    return next((d for d in candidates if sdr_lock.current_holder(d.id) is None), candidates[0])


class OnAirSession(BaseStreamingDecoder):
    """Runs one OnAir mode for the session duration."""

    def __init__(self, mode: dict[str, Any], duration: int, frequency: Optional[int] = None,
                 gain: Optional[float] = None, sample_rate: Optional[int] = None,
                 device_id: Optional[str] = None, client: Optional[OnAirClient] = None):
        freq = int(frequency or mode.get('default_frequency') or 0)
        super().__init__(frequency=freq, duration=duration, gain=int(gain) if gain is not None else -1,
                         sample_rate=int(sample_rate or 0))
        self.mode = mode
        self.requested_gain = gain
        self.requested_rate = sample_rate
        self.client = client or OnAirClient()
        self.device = pick_device(device_id)
        self.sdr_type = self.device.type
        self.telemetry: dict[str, Any] = {}

    # BaseStreamingDecoder's pipeline hooks are not used: OnAir does the decoding
    def _get_mode(self) -> str:
        return KIND

    def _start_decoder(self) -> Any:  # pragma: no cover - not used
        raise NotImplementedError

    def _parse_decoder_line(self, line: str) -> Optional[dict[str, Any]]:
        return mapping.to_document(line)

    def _index_packet(self, packet: dict[str, Any]) -> None:
        try:
            from radiomoni.storage.base import get_storage
            get_storage().index_event(KIND, packet)
        except Exception as e:
            logger.warning(f"Could not store OnAir document: {e}")

    def state(self) -> dict[str, Any]:
        return {'onair_mode': self.mode.get('id'), 'onair_mode_name': self.mode.get('name'),
                'group': self.mode.get('group')}

    # ------------------------------------------------------------------ worker
    def _stream_worker_simple(self, session_manager: SessionManager) -> None:
        assert self.session is not None and self.device is not None
        started_receiver = False
        try:
            self.session.status = 'running'
            session_manager.save_session(self.session)
            tail = JsonlTail(events_file())
            self.client.tune(int(self.mode['family']), self.mode.get('sub'), self.frequency or None,
                             self.requested_gain, self.requested_rate)
            index = find_device_index(self.client.devices(), self.sdr_type.value, self.device.serial)
            started_receiver = True
            self.client.start(index)
            status = self.client.status()
            if not status.get('running'):
                raise OnAirError(status.get('error') or 'OnAir did not start the receiver')
            self.frequency = int(status.get('frequencyHz') or self.frequency)
            self.sample_rate = int(status.get('sampleRateHz') or self.sample_rate)
            self.session.frequency, self.session.sample_rate = self.frequency, self.sample_rate
            session_manager.save_session(self.session)
            sdr_lock.annotate(self.device.id, {'frequency': self.frequency, 'onair_mode': self.mode.get('id'),
                                               'onair_mode_name': self.mode.get('name')})
            logger.info(f"OnAir {self.mode.get('id')} on {self.device.label} at {self.frequency} Hz "
                        f"(session {self.session.session_id})")
            self._run(tail, session_manager)
        except Exception as e:
            logger.error(f"OnAir session failed: {e}", exc_info=not isinstance(e, OnAirError))
            self.session.status = 'failed'
            self.session.error = str(e)
            session_manager.save_session(self.session)
        finally:
            if started_receiver:
                self._stop_receiver()
            self._finish_session(session_manager)

    def _run(self, tail: JsonlTail, session_manager: SessionManager) -> None:
        assert self.session is not None
        started = last_status = time.time()
        while not self.stop_event.wait(1.0):
            for line in tail.read():
                doc = mapping.to_document(line)
                if doc is not None:
                    self._handle(doc)
            now = time.time()
            if self.duration and now - started >= self.duration:
                break
            if now - last_status >= STATUS_EVERY:
                last_status = now
                self._check_receiver()
                session_manager.save_session(self.session)
        for line in tail.read():  # what came in during the last second
            doc = mapping.to_document(line)
            if doc is not None:
                self._handle(doc)

    def _check_receiver(self) -> None:
        assert self.session is not None
        status = self.client.status()
        if not status.get('running'):
            raise OnAirError(status.get('error') or 'OnAir stopped the receiver')
        try:
            self.telemetry = self.client.telemetry()
        except OnAirError:
            self.telemetry = {}
        events.publish('onair_status', {'session_id': self.session.session_id, 'status': status,
                                        'telemetry': self.telemetry})

    def _handle(self, doc: dict[str, Any]) -> None:
        assert self.session is not None and self.device is not None
        doc['session_id'] = self.session.session_id
        doc['device_id'] = self.device.id
        doc.setdefault('frequency', int(self.frequency))
        self._index_packet(doc)
        events.publish(KIND, doc)
        alerts.evaluate(KIND, doc)
        self.session.packet_count += 1
        self.session.last_packet_time = datetime.now(timezone.utc)

    def _stop_receiver(self) -> None:
        for attempt in range(3):
            try:
                self.client.stop()
                if not self.client.status().get('running'):
                    return
            except OnAirError as e:
                logger.warning(f"OnAir stop failed (attempt {attempt + 1}): {e}")
            time.sleep(1.0)
        logger.error('OnAir did not stop the receiver; the SDR lock is released anyway')

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=20)


def recover(client: Optional[OnAirClient] = None) -> bool:
    """Stop OnAir's receiver when no OnAir session holds an SDR lock (API restart, crash).
    Returns True when it had to stop it."""
    from radiomoni.onair.client import enabled
    if not enabled():
        return False
    if any(h.get('kind') == KIND for h in sdr_lock.holders().values()):
        return False
    c = client or OnAirClient(timeout=3.0)
    try:
        status = c.status()
        if status.get('running') or status.get('wanted'):
            c.stop()
            logger.warning('OnAir was running without an SDR lock: stopped it')
            return True
    except OnAirError as e:
        logger.debug(f"OnAir recover: {e}")
    return False


_watchdog_started = False


def start_watchdog(every: float = 30.0) -> None:
    """Background check: OnAir never keeps the radio open without an OnAir session's lock."""
    global _watchdog_started
    from radiomoni.onair.client import enabled
    if _watchdog_started or not enabled():
        return
    _watchdog_started = True
    import threading

    def loop() -> None:
        stop = threading.Event()
        while True:
            try:
                recover()
            except Exception as e:  # never let the watchdog die
                logger.debug(f"OnAir watchdog: {e}")
            stop.wait(every)

    threading.Thread(target=loop, name='onair-watchdog', daemon=True).start()
