"""
Jetvision Air!Squitter / Radarcape as a network ADS-B source.

The device decodes ADS-B, takes part in MLAT and (with the option) receives
FLARM; it publishes the decoded aircraft as http://<device>/aircraftlist.json,
the interface Jetvision recommends for other programs
(https://wiki.jetvision.de/wiki/Radarcape:User_Services_and_Interfaces).

RadioMoni polls that list in the background (one API process, leader lock),
publishes it live, stores one position per aircraft at most every
AIRSQUITTER_STORE_SECONDS into radio-adsb-* and checks the alert rules. Every
document carries `receiver` (the device's name; own readsb sessions: radiomoni)
and `position_source` (adsb, mlat, flarm, tisb). No SDR and no SDR lock.
"""

import json
import logging
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from radiomoni import alerts, config, events
from radiomoni.integrations.leader import LeaderLock
from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)

STATUS_KEY = 'airsquitter:status'
STALE_POSITION_S = 60          # older positions (lla) are shown, not stored
SOURCES = {'A': 'adsb', 'M': 'mlat', 'F': 'flarm'}


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def position_source(item: dict[str, Any]) -> Optional[str]:
    """adsb / mlat / flarm from `src`; tisb when the ground/air flag is lower case (TIS-B)."""
    src = SOURCES.get(str(item.get('src') or '').upper())
    gda = str(item.get('gda') or '')
    if src == 'adsb' and gda and gda.islower():
        return 'tisb'
    return src


def parse_aircraft(item: dict[str, Any], receiver: Optional[str] = None) -> Optional[dict[str, Any]]:
    """One entry of aircraftlist.json -> the fields RadioMoni uses for ADS-B (readsb names where they exist)."""
    if not isinstance(item, dict) or not item.get('hex'):
        return None
    uti = _num(item.get('uti'))
    when = datetime.fromtimestamp(uti + (_num(item.get('ns')) or 0) / 1e9, timezone.utc) if uti else None
    doc: dict[str, Any] = {
        'icao': str(item['hex']).upper(),
        'flight': _text(item.get('fli')),
        'altitude_ft': _num(item.get('alt')),
        'gnss_altitude_ft': _num(item.get('altg')),
        'ground_speed_kt': _num(item.get('spd')),
        'track': _num(item.get('trk')),
        'vertical_rate': _num(item.get('vrt')),
        'squawk': _text(item.get('squ')),
        'category': _text(item.get('cat')),
        'registration': _text(item.get('reg')),
        'aircraft_type': _text(item.get('typ')),
        'operator': _text(item.get('opr')),
        'origin': _text(item.get('org')),
        'destination': _text(item.get('dst')),
        'country': _text(item.get('cou')),
        'distance_km': _num(item.get('dis')),
        'rssi': _num(item.get('dbm')),
        'position_source': position_source(item),
        'available_sources': ','.join(SOURCES.get(c.upper(), c.lower()) for c in str(item.get('ava') or '')) or None,
        'position_age_s': _num(item.get('lla')),
        'air_temperature_c': _num(item.get('tmp')),
        'wind_speed_kt': _num(item.get('wsp')),
        'wind_direction': _num(item.get('wdi')),
        'receiver': receiver or config.AIRSQUITTER_NAME,
    }
    if item.get('alr'):
        doc['alert_flag'] = True
    if item.get('spi'):
        doc['spi'] = True
    lat, lon = _num(item.get('lat')), _num(item.get('lon'))
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0, 0):
        doc['latitude'], doc['longitude'] = lat, lon
    if when:
        doc['timestamp'] = when.isoformat()
    return {k: v for k, v in doc.items() if v is not None}


def parse_aircraftlist(payload: Any, receiver: Optional[str] = None) -> list[dict[str, Any]]:
    items = payload if isinstance(payload, list) else (payload or {}).get('aircraft', []) if isinstance(payload, dict) else []
    return [a for a in (parse_aircraft(i, receiver) for i in items) if a]


def storable(ac: dict[str, Any]) -> bool:
    """Stored with its position only when the position is current."""
    return 'latitude' in ac and (ac.get('position_age_s') or 0) <= STALE_POSITION_S


class Poller:
    def __init__(self, url: Optional[str] = None, http: Optional[requests.Session] = None):
        self.url = (url if url is not None else config.AIRSQUITTER_URL).rstrip('/')
        self.http = http or requests.Session()
        self.last_stored: dict[str, float] = {}
        self.failures = 0

    def fetch(self) -> list[dict[str, Any]]:
        r = self.http.get(f"{self.url}/aircraftlist.json", timeout=10)
        r.raise_for_status()
        return parse_aircraftlist(r.json())

    def poll_once(self) -> dict[str, Any]:
        """Fetch, publish, store and check alerts. Returns the status that is saved."""
        from radiomoni.storage.base import get_storage
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            aircraft = self.fetch()
        except (requests.RequestException, ValueError) as e:
            self.failures += 1
            if self.failures in (1, 10) or self.failures % 360 == 0:
                logger.warning(f"AirSquitter not reachable ({self.failures}x): {e}")
            status = {'ok': False, 'time': now_iso, 'error': str(e)[:300], 'failures': self.failures}
            _save_status(status)
            return status
        self.failures = 0
        receiver = config.AIRSQUITTER_NAME
        events.publish('adsb_snapshot', {'receiver': receiver, 'aircraft': aircraft})
        now = time.time()
        stored = 0
        storage = get_storage()
        for ac in aircraft:
            if not storable(ac) or now - self.last_stored.get(ac['icao'], 0) < config.AIRSQUITTER_STORE_SECONDS:
                continue
            self.last_stored[ac['icao']] = now
            doc = {'uuid': str(uuid.uuid4()), **ac}
            doc.setdefault('timestamp', now_iso)
            try:
                storage.index_event('adsb', doc)
                stored += 1
            except Exception as e:
                logger.warning(f"Could not store AirSquitter aircraft: {e}")
            alerts.evaluate('adsb', doc)
        # forget aircraft not seen for an hour
        self.last_stored = {k: v for k, v in self.last_stored.items() if now - v < 3600}
        by_source = Counter(a.get('position_source') or 'none' for a in aircraft)
        status = {'ok': True, 'time': now_iso, 'error': None, 'aircraft': len(aircraft),
                  'with_position': sum(1 for a in aircraft if 'latitude' in a), 'by_source': dict(by_source),
                  'stored': stored, 'receiver': receiver}
        _save_status(status)
        return status


def _save_status(status: dict[str, Any]) -> None:
    try:
        get_redis().set(STATUS_KEY, json.dumps(status), ex=3600)
    except Exception:
        pass


def status() -> dict[str, Any]:
    raw = get_redis().get(STATUS_KEY)
    return {'enabled': bool(config.AIRSQUITTER_URL), 'name': config.AIRSQUITTER_NAME,
            **(json.loads(raw) if raw else {})}


_started = False


def start() -> None:
    """Poll in the background, in the API process that holds the leader lock."""
    global _started
    if _started or not config.AIRSQUITTER_URL:
        return
    _started = True
    lock = LeaderLock('airsquitter:leader', ttl=max(60, config.AIRSQUITTER_POLL_SECONDS * 6))

    def loop() -> None:
        poller = Poller()
        while True:
            try:
                if lock.hold():
                    poller.poll_once()
            except Exception as e:      # never let the thread die
                logger.warning(f"AirSquitter poll failed: {e}", exc_info=True)
            time.sleep(config.AIRSQUITTER_POLL_SECONDS)

    threading.Thread(target=loop, name='airsquitter', daemon=True).start()
