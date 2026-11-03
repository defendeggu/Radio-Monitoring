"""
Shared Redis connection.

Production uses a real Redis server and fails loudly when it is unreachable.
Tests set SKIP_REDIS_CHECK=1 (or REDIS_FAKE=1) and get an in-process fakeredis
instance, which supports pub/sub, NX locks and TTLs like the real thing.
"""

import logging
import threading
from typing import Any

import redis

from radiomoni import config

logger = logging.getLogger(__name__)

_client: Any = None
_raw_client: Any = None
_fake_server: Any = None
_lock = threading.Lock()


def _fake(decode: bool) -> Any:
    """fakeredis client; text and binary clients share one in-process server."""
    global _fake_server
    import fakeredis  # dev dependency only
    if _fake_server is None:
        _fake_server = fakeredis.FakeServer()
    return fakeredis.FakeRedis(server=_fake_server, decode_responses=decode)


def _real(decode: bool) -> Any:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD,
        decode_responses=decode,
        socket_connect_timeout=5,
        health_check_interval=30,
    )


def get_redis() -> Any:
    """Return the process-wide Redis client (created lazily)."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                if config.REDIS_FAKE:
                    _client = _fake(decode=True)
                    logger.info("Using in-process fakeredis (test mode)")
                else:
                    _client = _real(decode=True)
    return _client


def get_redis_raw() -> Any:
    """Client that returns bytes instead of str (binary pub/sub, e.g. waterfall frames)."""
    global _raw_client
    if _raw_client is None:
        with _lock:
            if _raw_client is None:
                _raw_client = _fake(decode=False) if config.REDIS_FAKE else _real(decode=False)
    return _raw_client


def ping() -> bool:
    """Return True when Redis answers PING."""
    try:
        return bool(get_redis().ping())
    except redis.RedisError as e:
        logger.warning(f"Redis ping failed: {e}")
        return False
