"""
Cross-process SDR lock backed by Redis.

Only one job (capture, stream, scan, VOX, external decoder) may use the SDR at a
time. The lock lives in Redis so it holds across Gunicorn workers, the scheduler
and container restarts. Holders keep a short TTL alive with a heartbeat thread,
so a crashed holder frees the SDR within LOCK_TTL seconds.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Optional

from redis_client import get_redis

logger = logging.getLogger(__name__)

LOCK_KEY = 'sdr:lock'
LOCK_TTL = 60          # seconds
HEARTBEAT_EVERY = 20   # seconds

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
        super().__init__(f"SDR device is busy — in use by {what}")


def current_holder() -> Optional[dict[str, Any]]:
    """Return the current lock holder info, or None if the SDR is free."""
    raw = get_redis().get(LOCK_KEY)
    if not raw:
        return None
    try:
        data: dict[str, Any] = json.loads(raw)
        return data
    except (TypeError, ValueError):
        return {'owner': str(raw), 'kind': 'unknown'}


def acquire(owner: str, kind: str, details: Optional[dict[str, Any]] = None) -> bool:
    """Try to take the lock. Returns False if another owner holds it."""
    payload = json.dumps({
        'owner': owner,
        'kind': kind,
        'since': datetime.now(timezone.utc).isoformat(),
        'details': details or {},
    })
    return bool(get_redis().set(LOCK_KEY, payload, nx=True, ex=LOCK_TTL))


def release(owner: str) -> bool:
    """Release the lock if (and only if) `owner` holds it."""
    try:
        return bool(_eval(_RELEASE_SCRIPT, owner))
    except Exception as e:  # never let cleanup crash a worker
        logger.warning(f"SDR lock release failed for {owner}: {e}")
        return False


def refresh(owner: str) -> bool:
    """Extend the TTL of a lock held by `owner`."""
    try:
        return bool(_eval(_REFRESH_SCRIPT, owner, str(LOCK_TTL)))
    except Exception as e:
        logger.warning(f"SDR lock refresh failed for {owner}: {e}")
        return False


def force_release() -> None:
    """Drop the lock regardless of owner (emergency stop)."""
    get_redis().delete(LOCK_KEY)


def _eval(script: str, owner: str, *args: str) -> Any:
    r = get_redis()
    try:
        return r.eval(script, 1, LOCK_KEY, owner, *args)
    except Exception:
        # fakeredis without Lua support: emulate atomically enough for tests
        holder = current_holder()
        if not holder or holder.get('owner') != owner:
            return 0
        if script is _RELEASE_SCRIPT:
            return r.delete(LOCK_KEY)
        return r.expire(LOCK_KEY, int(args[0]))


class SdrLease:
    """
    Context manager / handle for holding the SDR lock with a heartbeat.

        lease = SdrLease('capture:123', 'capture')
        lease.acquire()          # raises SdrBusyError
        ...
        lease.release()
    """

    def __init__(self, owner: str, kind: str, details: Optional[dict[str, Any]] = None):
        self.owner = owner
        self.kind = kind
        self.details = details
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def acquire(self) -> 'SdrLease':
        if not acquire(self.owner, self.kind, self.details):
            raise SdrBusyError(current_holder())
        self._thread = threading.Thread(target=self._heartbeat, name=f"sdr-lease-{self.kind}", daemon=True)
        self._thread.start()
        return self

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_EVERY):
            if not refresh(self.owner):
                logger.warning(f"SDR lease {self.owner} lost (expired or force-released)")
                return

    def release(self) -> None:
        self._stop.set()
        release(self.owner)

    def __enter__(self) -> 'SdrLease':
        return self.acquire()

    def __exit__(self, exc_type: Optional[type[BaseException]], exc: Optional[BaseException],
                 tb: Optional[TracebackType]) -> None:
        self.release()


def wait_until_free(timeout: float) -> bool:
    """Block until no lock is held or the timeout expires (used by the scheduler)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if current_holder() is None:
            return True
        time.sleep(1)
    return current_holder() is None
