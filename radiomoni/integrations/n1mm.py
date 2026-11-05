"""
N1MM+ UDP broadcasts (https://n1mmwp.hamdocs.com/appendices/external-udp-broadcasts/).

- contactinfo / contactreplace  a logged QSO → worked log (radiomoni.contest.worked)
- contactdelete                 remove it again (by ID)
- RadioInfo                     per radio: frequency and IsTransmitting → TX blanking of the skimmer

Frequencies come in units of 10 Hz (1402500 = 14025.00 kHz). IsTransmitting is
only True while N1MM+ itself keys the radio (not for a foot switch or paddle),
so the skimmer also blanks on ADC clipping.

One API process listens (leader lock); the state lives in Redis so every
process (and the skimmer thread) can read it.
"""

import ipaddress
import json
import logging
import socket
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Optional

from radiomoni import config
from radiomoni.contest import worked
from radiomoni.integrations.leader import LeaderLock
from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)

RADIO_KEY = 'n1mm:radio:'          # + station:radio → JSON, short TTL
STATUS_KEY = 'n1mm:status'
RADIO_TTL = 30                     # RadioInfo comes at least every 10 s
TX_STALE = 15.0
MAX_DATAGRAM = 65_535


def _text(root: ET.Element, tag: str) -> str:
    el = root.find(tag)
    return (el.text or '').strip() if el is not None else ''


def _freq_khz(value: str) -> Optional[float]:
    try:
        return int(value) / 100.0
    except ValueError:
        return None


def parse_packet(data: bytes) -> Optional[dict[str, Any]]:
    """One UDP datagram → {'type': 'radio'|'contact'|'delete', …}; None for anything else."""
    if len(data) > MAX_DATAGRAM or b'<!DOCTYPE' in data or b'<!ENTITY' in data:
        return None                     # N1MM+ never sends a DTD: no entity tricks
    try:
        root = ET.fromstring(data.decode('utf-8', errors='replace').strip())  # noqa: S314 - no DTD, see above
    except ET.ParseError:
        return None
    tag = root.tag.lower()
    if tag == 'radioinfo':
        return {'type': 'radio', 'station': _text(root, 'StationName') or 'N1MM',
                'radio': _text(root, 'RadioNr') or '1', 'freq_khz': _freq_khz(_text(root, 'Freq')),
                'tx_freq_khz': _freq_khz(_text(root, 'TXFreq')), 'mode': _text(root, 'Mode'),
                'transmitting': _text(root, 'IsTransmitting').lower() == 'true',
                'running': _text(root, 'IsRunning').lower() == 'true'}
    if tag in ('contactinfo', 'contactreplace'):
        rx = _freq_khz(_text(root, 'rxfreq'))
        band = worked.band_from_khz(rx) if rx else None
        return {'type': 'contact', 'id': _text(root, 'ID'), 'call': _text(root, 'call').upper(),
                'band': band or worked.band_from_text(_text(root, 'band')), 'mode': _text(root, 'mode'),
                'time': _text(root, 'timestamp'), 'contest': _text(root, 'contestname'),
                'station': _text(root, 'StationName')}
    if tag == 'contactdelete':
        return {'type': 'delete', 'id': _text(root, 'ID'), 'call': _text(root, 'call').upper()}
    return None


def handle(packet: dict[str, Any]) -> None:
    """Apply a parsed packet to the shared state."""
    r = get_redis()
    if packet['type'] == 'radio':
        r.set(f"{RADIO_KEY}{packet['station']}:{packet['radio']}", json.dumps({**packet, 'seen': time.time()}),
              ex=RADIO_TTL)
    elif packet['type'] == 'contact' and packet['call']:
        worked.add({'call': packet['call'], 'band': packet['band'], 'mode': packet['mode'], 'time': packet['time'],
                    'source': 'n1mm'}, qso_id=f"n1mm:{packet['id']}" if packet['id'] else None)
    elif packet['type'] == 'delete' and packet['id']:
        worked.delete(f"n1mm:{packet['id']}")


def radios() -> list[dict[str, Any]]:
    r = get_redis()
    result = []
    for key in r.scan_iter(match=f'{RADIO_KEY}*', count=100):
        raw = r.get(key)
        if raw:
            result.append(json.loads(raw))
    return sorted(result, key=lambda x: (x['station'], x['radio']))


def is_transmitting() -> bool:
    """True while any N1MM+ radio reports IsTransmitting (and the report is fresh)."""
    now = time.time()
    return any(x.get('transmitting') and now - x.get('seen', 0) < TX_STALE for x in radios())


def status() -> dict[str, Any]:
    raw = get_redis().get(STATUS_KEY)
    return {'enabled': config.N1MM_ENABLED, 'port': config.N1MM_PORT, 'listening': False,
            **(json.loads(raw) if raw else {}), 'radios': radios()}


def _allowed(address: str, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    if not networks:
        return True
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in n for n in networks)


class N1mmListener:
    def __init__(self, port: int, allowed: Optional[list[str]] = None, host: str = '0.0.0.0'):
        self.port = port
        self.host = host
        self.networks = [ipaddress.ip_network(a, strict=False) for a in (allowed or [])]
        self.lock = LeaderLock('n1mm:leader')
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.packets = 0
        self.bound_port: Optional[int] = None
        self.ready = threading.Event()

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name='n1mm-udp', daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def run(self) -> None:
        while not self.stop_event.is_set():
            if not self.lock.hold():
                self.stop_event.wait(20)
                continue
            try:
                self._serve()
            except OSError as e:
                logger.warning(f"N1MM+ listener on UDP {self.port}: {e}")
                self.stop_event.wait(10)
        self.lock.release()

    def _status(self, **changes: Any) -> None:
        r = get_redis()
        raw = r.get(STATUS_KEY)
        state = json.loads(raw) if raw else {}
        state.update(changes)
        r.set(STATUS_KEY, json.dumps(state), ex=3600)

    def _serve(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.settimeout(1.0)
        self.bound_port = sock.getsockname()[1]
        self.ready.set()
        logger.info(f"N1MM+ listener on UDP {self.bound_port}")
        self._status(listening=True)
        last_lead = time.monotonic()
        try:
            while not self.stop_event.is_set():
                try:
                    data, (address, _) = sock.recvfrom(MAX_DATAGRAM)
                except TimeoutError:
                    data = b''
                    address = ''
                if data and _allowed(address, self.networks):
                    packet = parse_packet(data)
                    if packet:
                        self.packets += 1
                        try:
                            handle(packet)
                        except Exception as e:
                            logger.warning(f"N1MM+ packet not applied: {e}")
                        self._status(last_packet=time.time(), packets=self.packets, last_from=address,
                                     last_type=packet['type'])
                if time.monotonic() - last_lead > self.lock.ttl / 3:
                    last_lead = time.monotonic()
                    if not self.lock.hold():
                        return
        finally:
            sock.close()
            self._status(listening=False)


_listener: Optional[N1mmListener] = None


def start_if_enabled() -> Optional[N1mmListener]:
    global _listener
    if _listener is None and config.N1MM_ENABLED:
        _listener = N1mmListener(config.N1MM_PORT, config.N1MM_ALLOWED)
        _listener.start()
    return _listener
