"""
Cross-process SDR lock backed by Redis, one lock per device (radiomoni.devices).

Only one job (capture, stream, scan, VOX, external decoder) may use a device at
a time; jobs on different devices run in parallel. Without a device id the lock
is the one of the default device (the one "auto" picks), so a setup with one
SDR behaves exactly as before. The lock lives in Redis so it holds across
Gunicorn workers, the scheduler and container restarts. Holders keep a short TTL alive with a heartbeat thread,
so a crashed holder frees the SDR within LOCK_TTL seconds.

Some holders only use the SDR while nothing else needs it (the spectrum /
waterfall view). They register a preempt handler; a job that finds such a
holder stops it and takes the SDR instead of failing with "busy".
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Callable, Optional

from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)

LOCK_PREFIX = 'sdr:lock:'
LOCK_TTL = 60          # seconds
HEARTBEAT_EVERY = 20   # seconds
PREEMPT_WAIT = 20      # seconds a job waits for a preempted holder to free the SDR

# kind → handler(holder, by_kind) that stops the holder (see register_preemptible)
_preempt_handlers: dict[str, Callable[[dict[str, Any], str], None]] = {}

# Lua: delete only if the stored owner matches (avoid releasing someone else's lock)
_RELEASE_SCRIPT = """
local v = redis.call('GET', KEYS[1])
if v and cjson.decode(v)['owner'] == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

_REFRESH_SCRIPT = """
local v = redis.call('GET', KEYS[1])
if v and cjson.decode(v)['owner'] == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


class SdrBusyError(RuntimeError):
    """Raised when the SDR is already held by another job."""

    def __init__(self, holder: Optional[dict[str, Any]]):
        self.holder = holder
        what = f"{holder.get('kind')} ({holder.get('owner')})" if holder else 'another job'
        device = f" {holder['device_id']}" if holder and holder.get('device_id') else ''
        super().__init__(f"SDR device{device} is busy — in use by {what}")


def _device(device_id: Optional[str]) -> str:
    if device_id:
        return device_id
    from radiomoni.devices import default_id
    return default_id()


def _key(device_id: Optional[str]) -> str:
    return LOCK_PREFIX + _device(device_id)


def current_holder(device_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Return the holder of a device's lock (default device without an id), or None if it is free."""
    raw = get_redis().get(_key(device_id))
    if not raw:
        return None
    try:
        data: dict[str, Any] = json.loads(raw)
        return data
    except (TypeError, ValueError):
        return {'owner': str(raw), 'kind': 'unknown'}


def holders() -> dict[str, dict[str, Any]]:
    """All held locks: device id → holder."""
    r = get_redis()
    result: dict[str, dict[str, Any]] = {}
    for key in r.scan_iter(match=f'{LOCK_PREFIX}*', count=100):
        raw = r.get(key)
        if not raw:
            continue
        try:
            result[str(key)[len(LOCK_PREFIX):]] = json.loads(raw)
        except (TypeError, ValueError):
            result[str(key)[len(LOCK_PREFIX):]] = {'owner': str(raw), 'kind': 'unknown'}
    return result


def annotate(device_id: str, extra: dict[str, Any]) -> bool:
    """Add facts to the details of a held lock (e.g. the RSPduo master/slave role); keeps its TTL."""
    r = get_redis()
    key = LOCK_PREFIX + device_id
    raw = r.get(key)
    if not raw:
        return False
    holder = json.loads(raw)
    holder['details'] = {**(holder.get('details') or {}), **extra}
    ttl = r.ttl(key)
    r.set(key, json.dumps(holder), ex=ttl if ttl and ttl > 0 else LOCK_TTL)
    return True


def find_holder(owner: str) -> Optional[dict[str, Any]]:
    """The lock held by `owner` on any device."""
    return next((h for h in holders().values() if h.get('owner') == owner), None)


def acquire(owner: str, kind: str, details: Optional[dict[str, Any]] = None,
            device_id: Optional[str] = None) -> bool:
    """Try to take a device's lock. Returns False if another owner holds it."""
    device = _device(device_id)
    payload = json.dumps({
        'owner': owner,
        'kind': kind,
        'device_id': device,
        'since': datetime.now(timezone.utc).isoformat(),
        'details': details or {},
    })
    return bool(get_redis().set(LOCK_PREFIX + device, payload, nx=True, ex=LOCK_TTL))


def release(owner: str, device_id: Optional[str] = None) -> bool:
    """Release a device's lock if (and only if) `owner` holds it."""
    try:
        return bool(_eval(_RELEASE_SCRIPT, _key(device_id), owner))
    except Exception as e:  # never let cleanup crash a worker
        logger.warning(f"SDR lock release failed for {owner}: {e}")
        return False


def refresh(owner: str, device_id: Optional[str] = None) -> bool:
    """Extend the TTL of a lock held by `owner`."""
    try:
        return bool(_eval(_REFRESH_SCRIPT, _key(device_id), owner, str(LOCK_TTL)))
    except Exception as e:
        logger.warning(f"SDR lock refresh failed for {owner}: {e}")
        return False


def force_release(device_id: Optional[str] = None) -> None:
    """Drop a device's lock regardless of owner, or every lock without an id (emergency stop)."""
    r = get_redis()
    if device_id:
        r.delete(LOCK_PREFIX + device_id)
        return
    for key in list(r.scan_iter(match=f'{LOCK_PREFIX}*', count=100)):
        r.delete(key)


def _eval(script: str, key: str, owner: str, *args: str) -> Any:
    r = get_redis()
    try:
        return r.eval(script, 1, key, owner, *args)
    except Exception:
        # fakeredis without Lua support: emulate atomically enough for tests
        raw = r.get(key)
        holder = json.loads(raw) if raw else None
        if not holder or holder.get('owner') != owner:
            return 0
        if script is _RELEASE_SCRIPT:
            return r.delete(key)
        return r.expire(key, int(args[0]))


def register_preemptible(kind: str, handler: Callable[[dict[str, Any], str], None]) -> None:
    """Holders of `kind` give way to other jobs: handler(holder, by_kind) must stop them."""
    _preempt_handlers[kind] = handler


def is_preemptible(kind: Optional[str]) -> bool:
    return kind in _preempt_handlers


def preempt(kind: str, device_id: Optional[str] = None) -> bool:
    """
    If the holder of the device is preemptible (and not of the same kind), stop it
    and wait until the device is free. Returns True when it became free.
    """
    device = _device(device_id)
    holder = current_holder(device)
    if not holder or not is_preemptible(holder.get('kind')) or holder.get('kind') == kind:
        return False
    from radiomoni.sdrplay import dependents
    if dependents(device):
        logger.info(f"Not preempting {holder.get('owner')} on {device}: the other RSPduo tuner depends on it")
        return False
    logger.info(f"Preempting SDR holder {holder.get('owner')} ({holder.get('kind')}) on {device} for {kind}")
    try:
        _preempt_handlers[str(holder['kind'])](holder, kind)
    except Exception as e:
        logger.error(f"Preempt handler for {holder.get('kind')} failed: {e}", exc_info=True)
    return _wait_free(PREEMPT_WAIT, poll=0.25, device_id=device)


class SdrLease:
    """
    Context manager / handle for holding the SDR lock with a heartbeat.

        lease = SdrLease('capture:123', 'capture')
        lease.acquire()          # raises SdrBusyError
        ...
        lease.release()
    """

    def __init__(self, owner: str, kind: str, details: Optional[dict[str, Any]] = None,
                 device_id: Optional[str] = None):
        self.owner = owner
        self.kind = kind
        self.details = details
        self.device_id = _device(device_id)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def acquire(self) -> 'SdrLease':
        if not acquire(self.owner, self.kind, self.details, self.device_id):
            if not (preempt(self.kind, self.device_id)
                    and acquire(self.owner, self.kind, self.details, self.device_id)):
                raise SdrBusyError(current_holder(self.device_id))
        self._thread = threading.Thread(target=self._heartbeat, name=f"sdr-lease-{self.kind}", daemon=True)
        self._thread.start()
        return self

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_EVERY):
            if not refresh(self.owner, self.device_id):
                logger.warning(f"SDR lease {self.owner} lost (expired or force-released)")
                return

    def release(self) -> None:
        self._stop.set()
        release(self.owner, self.device_id)

    def __enter__(self) -> 'SdrLease':
        return self.acquire()

    def __exit__(self, exc_type: Optional[type[BaseException]], exc: Optional[BaseException],
                 tb: Optional[TracebackType]) -> None:
        self.release()


def _wait_free(timeout: float, poll: float = 1.0, device_id: Optional[str] = None) -> bool:
    device = _device(device_id)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if current_holder(device) is None:
            return True
        time.sleep(poll)
    return current_holder(device) is None


def wait_until_free(timeout: float, device_id: Optional[str] = None) -> bool:
    """Block until the device is free or the timeout expires (used by the scheduler).
    A preemptible holder (waterfall) is stopped right away instead of waited for."""
    device = _device(device_id)
    holder = current_holder(device)
    if holder is not None and is_preemptible(holder.get('kind')):
        return preempt('scheduler', device)
    return _wait_free(timeout, device_id=device)
