"""Thin client for aprs-stats' API. Only the paths below can be called (no stations, beacons, imports)."""

import logging
from typing import Any, Optional

import requests

from radiomoni import config

logger = logging.getLogger(__name__)

TIMEOUT = 15.0

ALLOWED_GET = frozenset({'version', 'status', 'stations', 'stats/summary', 'stats/trips', 'stats/places',
                         'feed/packets', 'feed/positions'})
ALLOWED_POST = frozenset({'ingest'})


class AprsStatsError(RuntimeError):
    """aprs-stats is not configured, not reachable or refused a request."""


def enabled() -> bool:
    return bool(config.APRSSTATS_URL)


def _check(path: str, allowed: frozenset[str]) -> str:
    clean = path.strip('/')
    if clean not in allowed:
        raise AprsStatsError(f"aprs-stats path not allowed: {path!r}")
    return clean


class AprsStatsClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None,
                 timeout: float = TIMEOUT, session: Optional[requests.Session] = None):
        self.base_url = (base_url if base_url is not None else config.APRSSTATS_URL).rstrip('/')
        self.token = token if token is not None else config.APRSSTATS_TOKEN
        self.timeout = timeout
        self.http = session or requests.Session()

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise AprsStatsError('aprs-stats is not configured (APRSSTATS_URL)')
        return f"{self.base_url}/api/{path}"

    def _headers(self) -> dict[str, str]:
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    @staticmethod
    def _answer(r: requests.Response) -> Any:
        try:
            data = r.json()
        except ValueError:
            data = None
        if r.status_code >= 400:
            msg = data.get('detail') if isinstance(data, dict) else r.text[:200]
            raise AprsStatsError(f"aprs-stats {r.status_code}: {msg or r.reason}")
        return data

    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        clean = _check(path, ALLOWED_GET)
        try:
            r = self.http.get(self._url(clean), params=params, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as e:
            raise AprsStatsError(f"aprs-stats not reachable: {e}") from e
        return self._answer(r)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        clean = _check(path, ALLOWED_POST)
        try:
            r = self.http.post(self._url(clean), json=body, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as e:
            raise AprsStatsError(f"aprs-stats not reachable: {e}") from e
        return self._answer(r)
