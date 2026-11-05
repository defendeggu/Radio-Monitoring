"""Leader election across API processes: a Redis key with TTL, renewed by its owner."""

import socket
import uuid

from radiomoni.redis_client import get_redis


class LeaderLock:
    def __init__(self, key: str, ttl: int = 60):
        self.key = key
        self.ttl = ttl
        self.owner = f'{socket.gethostname()}:{uuid.uuid4().hex[:8]}'

    def hold(self) -> bool:
        """Take or renew the lock. True while this process is the leader."""
        r = get_redis()
        if r.set(self.key, self.owner, nx=True, ex=self.ttl):
            return True
        if r.get(self.key) == self.owner:
            r.expire(self.key, self.ttl)
            return True
        return False

    def release(self) -> None:
        try:
            r = get_redis()
            if r.get(self.key) == self.owner:
                r.delete(self.key)
        except Exception:
            pass
