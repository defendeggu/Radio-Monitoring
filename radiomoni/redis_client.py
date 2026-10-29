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
_lock = threading.Lock()


def get_redis() -> Any:
    """Return the process-wide Redis client (created lazily)."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                if config.REDIS_FAKE:
                    import fakeredis  # dev dependency only
                    _client = fakeredis.FakeRedis(decode_responses=True)
                    logger.info("Using in-process fakeredis (test mode)")
                else:
                    _client = redis.Redis(
                        host=config.REDIS_HOST,
                        port=config.REDIS_PORT,
                        db=config.REDIS_DB,
                        password=config.REDIS_PASSWORD,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        health_check_interval=30,
                    )
    return _client


def ping() -> bool:
    """Return True when Redis answers PING."""
    try:
        return bool(get_redis().ping())
    except redis.RedisError as e:
        logger.warning(f"Redis ping failed: {e}")
        return False
