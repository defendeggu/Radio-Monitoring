"""
Thin client for onair-server's remote-control API (docs/REMOTE-API.md of OnAir).

Only the receive paths below can be called. Everything else - above all
transmitting (/tx), live RDS, recordings, the rotator - is refused here, before
a request leaves the process: the HackRF can transmit, RadioMoni never does.
"""

import logging
from typing import Any, Optional

import requests

from radiomoni import config

logger = logging.getLogger(__name__)

TIMEOUT = 8.0

ALLOWED_GET = frozenset({'', 'status', 'devices', 'modes', 'telemetry', 'metrics', 'x/server'})
ALLOWED_POST = frozenset({'start', 'stop', 'mode', 'frequency', 'samplerate', 'gain', 'autogain',
                          'bandwidth', 'squelch'})


class OnAirError(RuntimeError):
    """OnAir is not configured, not reachable or refused a request."""


def enabled() -> bool:
    return bool(config.ONAIR_URL)


def _check_path(path: str, allowed: frozenset[str]) -> str:
    clean = path.strip('/')
    if clean not in allowed or '..' in clean:
        raise OnAirError(f"OnAir path not allowed: {path!r}")
    return clean


class OnAirClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None,
                 timeout: float = TIMEOUT, session: Optional[requests.Session] = None):
        self.base_url = (base_url if base_url is not None else config.ONAIR_URL).rstrip('/')
        self.token = token if token is not None else config.ONAIR_TOKEN
        self.timeout = timeout
        self.http = session or requests.Session()

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise OnAirError('OnAir is not configured (ONAIR_URL)')
        return f"{self.base_url}/api/v1/{path}" if path else f"{self.base_url}/api/v1"

    def _headers(self) -> dict[str, str]:
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    @staticmethod
    def _answer(r: requests.Response) -> Any:
        try:
            data = r.json()
        except ValueError:
            data = None
        if r.status_code >= 400:
            msg = data.get('error') if isinstance(data, dict) else r.text[:200]
            raise OnAirError(f"OnAir {r.status_code}: {msg or r.reason}")
        return data

    def get(self, path: str) -> Any:
        clean = _check_path(path, ALLOWED_GET)
        try:
            r = self.http.get(self._url(clean), headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as e:
            raise OnAirError(f"OnAir not reachable: {e}") from e
        if clean == 'metrics':
            if r.status_code >= 400:
                raise OnAirError(f"OnAir {r.status_code}")
            return r.text
        return self._answer(r)

    def post(self, path: str, body: Optional[dict[str, Any]] = None) -> Any:
        clean = _check_path(path, ALLOWED_POST)
        try:
            r = self.http.post(self._url(clean), json=body or {}, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as e:
            raise OnAirError(f"OnAir not reachable: {e}") from e
        return self._answer(r)

    # ------------------------------------------------------------------ helpers
    def status(self) -> dict[str, Any]:
        return dict(self.get('status') or {})

    def devices(self) -> list[dict[str, Any]]:
        return list(self.get('devices') or [])

    def modes(self) -> list[dict[str, Any]]:
        return list(self.get('modes') or [])

    def telemetry(self) -> dict[str, Any]:
        return dict(self.get('telemetry') or {})

    def stop(self) -> None:
        self.post('stop')

    def tune(self, family: int, sub: Optional[str], frequency: Optional[int], gain: Optional[float],
             sample_rate: Optional[int] = None) -> None:
        """Set mode, frequency, gain and rate (the receiver is stopped first: /mode needs that)."""
        self.post('stop')
        body: dict[str, Any] = {'family': family}
        if sub:
            body['sub'] = sub
        self.post('mode', body)
        if frequency:
            self.post('frequency', {'hz': int(frequency)})
        if sample_rate is not None:
            self.post('samplerate', {'hz': int(sample_rate)})
        if gain is None:
            self.post('autogain', {'on': True})
        else:
            self.post('gain', {'db': float(gain)})

    def start(self, device_index: int) -> None:
        self.post('start', {'device': int(device_index)})


def find_device_index(onair_devices: list[dict[str, Any]], sdr_type: str, serial: Optional[str] = None) -> int:
    """OnAir's index of the radio RadioMoni holds the lock for (by kind, then serial)."""
    kind = {'hackrf': 'hackrf', 'rtlsdr': 'rtlsdr', 'airspy': 'airspy', 'sdrplay': 'sdrplay'}.get(sdr_type, sdr_type)
    matches = [d for d in onair_devices if str(d.get('kind', '')).lower() == kind]
    if serial:
        exact = [d for d in matches if serial and serial in str(d.get('serial') or '')]
        matches = exact or matches
    usable = [d for d in matches if 'ERROR' not in str(d.get('name', ''))]
    if not usable:
        names = ', '.join(str(d.get('name')) for d in onair_devices) or 'none'
        raise OnAirError(f"OnAir does not see the {sdr_type} (its radios: {names})")
    return int(usable[0]['index'])
