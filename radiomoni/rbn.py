"""
Reverse Beacon Network (RBN): live CW spots from skimmers around the world.

https://www.reversebeacon.net/ — the spots come over telnet
(telnet.reversebeacon.net:7000 for CW/RTTY), the login asks for a callsign.
RBN asks end users to prefer a DX cluster that relays its spots, so host and
port are configurable (RBN_HOST, RBN_PORT). Most clusters only send skimmer
spots after a command such as SET/SKIMMER (RBN_LOGIN_COMMANDS).

One API process (leader lock in Redis) holds the single connection, filters
the spots (CW, HF, optionally skimmers with given prefixes), merges duplicates
and writes a snapshot of the last 30 minutes to Redis. Every process serves
GET /rbn/spots from that snapshot. Nothing goes to Elasticsearch: worldwide
RBN carries dozens of spots per second at peak times.

    telnet ─► parse_spot ─► accept (filter) ─► SpotBook.add (merge) ─► Redis snapshot ─► /rbn/spots
                                                    └─► alerts.evaluate('rbn', …)
"""

import json
import logging
import re
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from radiomoni import config
from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)

SNAPSHOT_KEY = 'rbn:spots'
STATUS_KEY = 'rbn:status'
LEADER_KEY = 'rbn:leader'
LEADER_TTL = 60
MAX_AGE = 30 * 60          # s: spots older than this are dropped
MAX_SPOTS = 5000
MERGE_WINDOW = 120         # s: same callsign on (nearly) the same frequency → one entry
MERGE_KHZ = 0.5
SILENCE_TIMEOUT = 300      # s without a line → reconnect

# Example: "DX de EA5WU-#:   14014.0  OH6BG          CW    22 dB  27 WPM  CQ      1234Z"
# Skimmer suffixes may be digits or letters: KM3T-2-#, DF4UE-RP-#. Clusters (CC Cluster) drop the
# blank after long skimmer calls ("DX de DL8LAS-3-#:21020.6") and write beacons as "NCDXF BCN".
SPOT_RE = re.compile(
    r'^DX de (?P<spotter>[A-Z0-9/]+(?:-[A-Z0-9]+)?)(?:-#)?:\s*(?P<khz>\d+(?:\.\d+)?)\s+(?P<dx>[A-Z0-9/]+)\s+'
    r'(?P<mode>[A-Z0-9]+)\s+(?P<snr>-?\d+)\s*dB\s+(?P<speed>\d+)\s*(?P<unit>WPM|BPS)\s+'
    r'(?P<type>NCDXF B(?:CN)?|BEACON|CQ|DX)\s+(?P<time>\d{4})Z')

HF_MIN_KHZ, HF_MAX_KHZ = 1800.0, 30000.0

HF_BANDS: dict[str, tuple[float, float]] = {    # amateur bands in kHz (whole band, not only CW)
    '160m': (1800, 2000), '80m': (3500, 3800), '60m': (5350, 5367), '40m': (7000, 7200),
    '30m': (10100, 10150), '20m': (14000, 14350), '17m': (18068, 18168), '15m': (21000, 21450),
    '12m': (24890, 24990), '10m': (28000, 29700),
}


# VHF/UHF bands of IARU Region 1 (contest skimmer on 6 m … 23 cm; RBN itself is HF only)
VHF_BANDS: dict[str, tuple[float, float]] = {
    '6m': (50000, 52000), '2m': (144000, 146000), '70cm': (430000, 440000), '23cm': (1240000, 1300000),
}


def band_of(khz: float) -> Optional[str]:
    for name, (low, high) in (HF_BANDS | VHF_BANDS).items():
        if low <= khz <= high:
            return name
    return None


def parse_spot(line: str) -> Optional[dict[str, Any]]:
    """Parse one RBN telnet line; None for prompts, banners and unknown lines."""
    m = SPOT_RE.match(line.strip())
    if not m:
        return None
    khz = float(m['khz'])
    return {
        'spotter': m['spotter'], 'callsign': m['dx'], 'frequency': int(round(khz * 1000)), 'khz': khz,
        'mode': m['mode'], 'snr_db': int(m['snr']), 'wpm': int(m['speed']) if m['unit'] == 'WPM' else None,
        'type': 'NCDXF B' if m['type'].startswith('NCDXF') else m['type'], 'utc': m['time'], 'band': band_of(khz),
    }


def accept(spot: dict[str, Any], prefixes: list[str]) -> bool:
    """CW on HF from a wanted skimmer."""
    if spot['mode'] != 'CW' or not HF_MIN_KHZ <= spot['khz'] <= HF_MAX_KHZ:
        return False
    return not prefixes or any(spot['spotter'].startswith(p) for p in prefixes)


@dataclass
class SpotBook:
    """Merged spots of the last MAX_AGE seconds, keyed by callsign and ~0.5 kHz frequency bucket."""
    entries: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)

    def add(self, spot: dict[str, Any], now: float) -> dict[str, Any]:
        key = (spot['callsign'], int(round(spot['khz'] / MERGE_KHZ)))
        entry = self.entries.get(key)
        if entry and now - entry['last_seen'] <= MERGE_WINDOW:
            entry['skimmers'] = sorted(set(entry['skimmers']) | {spot['spotter']})[:20]
            entry['skimmer_count'] = len(entry['skimmers'])
            if spot['snr_db'] > entry['snr_db']:
                entry['snr_db'], entry['best_skimmer'] = spot['snr_db'], spot['spotter']
            entry.update(last_seen=now, wpm=spot['wpm'] or entry['wpm'], type=spot['type'],
                         frequency=spot['frequency'], khz=spot['khz'])
            return entry
        entry = {
            'callsign': spot['callsign'], 'frequency': spot['frequency'], 'khz': spot['khz'],
            'band': spot['band'], 'mode': spot['mode'], 'snr_db': spot['snr_db'], 'wpm': spot['wpm'],
            'type': spot['type'], 'skimmers': [spot['spotter']], 'skimmer_count': 1,
            'best_skimmer': spot['spotter'], 'first_seen': now, 'last_seen': now,
        }
        self.entries[key] = entry
        return entry

    def prune(self, now: float) -> None:
        old = [k for k, e in self.entries.items() if now - e['last_seen'] > MAX_AGE]
        for k in old:
            del self.entries[k]
        if len(self.entries) > MAX_SPOTS:
            newest = sorted(self.entries.items(), key=lambda kv: kv[1]['last_seen'], reverse=True)[:MAX_SPOTS]
            self.entries = dict(newest)

    def snapshot(self) -> list[dict[str, Any]]:
        return sorted(self.entries.values(), key=lambda e: e['last_seen'], reverse=True)


# ------------------------------------------------------------------ reading (any process)
def load_spots() -> list[dict[str, Any]]:
    raw = get_redis().get(SNAPSHOT_KEY)
    return json.loads(raw) if raw else []


def query(spots: list[dict[str, Any]], band: Optional[str] = None, freq_min: Optional[int] = None,
          freq_max: Optional[int] = None, call: Optional[str] = None, max_age: int = 30 * 60,
          cq_only: bool = False, limit: int = 200, now: Optional[float] = None) -> list[dict[str, Any]]:
    """Filter the snapshot for the API."""
    now = time.time() if now is None else now
    result = []
    for s in spots:
        if now - s['last_seen'] > max_age:
            continue
        if band and s.get('band') != band:
            continue
        if freq_min is not None and s['frequency'] < freq_min:
            continue
        if freq_max is not None and s['frequency'] > freq_max:
            continue
        if call and call.upper() not in s['callsign']:
            continue
        if cq_only and s['type'] != 'CQ':
            continue
        result.append({**s, 'age_seconds': int(now - s['last_seen'])})
        if len(result) >= limit:
            break
    return result


def status() -> dict[str, Any]:
    raw = get_redis().get(STATUS_KEY)
    state = json.loads(raw) if raw else {}
    return {'enabled': config.RBN_ENABLED, 'configured': bool(config.RBN_CALLSIGN),
            'host': config.RBN_HOST, 'port': config.RBN_PORT, 'connected': False, **state}


# ------------------------------------------------------------------ client (leader process)
class RbnClient:
    """Keeps one telnet connection to RBN (or a DX cluster) open and feeds the SpotBook."""

    def __init__(self, callsign: str, host: str, port: int, prefixes: list[str],
                 connect: Optional[Callable[[str, int], socket.socket]] = None,
                 on_spot: Optional[Callable[[dict[str, Any]], None]] = None,
                 login_commands: Optional[list[str]] = None):
        self.callsign = callsign
        self.login_commands = login_commands or []   # sent after the callsign, e.g. SET/SKIMMER
        self.host = host
        self.port = port
        self.prefixes = prefixes
        self._connect = connect or (lambda h, p: socket.create_connection((h, p), timeout=30))
        self.on_spot = on_spot
        self.book = SpotBook()
        self.stop_event = threading.Event()
        self.owner = f'{socket.gethostname()}:{uuid.uuid4().hex[:8]}'
        self.thread: Optional[threading.Thread] = None
        self._recent: list[float] = []       # accepted spot times of the last minute
        self._last_snapshot = 0.0
        self._last_unknown_log = 0.0
        self.total = 0

    # leader election: only one API process connects
    def _lead(self) -> bool:
        r = get_redis()
        if r.set(LEADER_KEY, self.owner, nx=True, ex=LEADER_TTL):
            return True
        if r.get(LEADER_KEY) == self.owner:
            r.expire(LEADER_KEY, LEADER_TTL)
            return True
        return False

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name='rbn-client', daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)

    def run(self) -> None:
        delay = 5.0
        while not self.stop_event.is_set():
            if not self._lead():
                self.stop_event.wait(30)
                continue
            try:
                self._session()
                delay = 5.0
            except Exception as e:
                logger.warning(f"RBN connection to {self.host}:{self.port} failed: {e}")
                self._status(connected=False, error=str(e)[:200])
            if self.stop_event.wait(delay):
                break
            delay = min(delay * 2, 300.0)
        try:
            if get_redis().get(LEADER_KEY) == self.owner:
                get_redis().delete(LEADER_KEY)
        except Exception:
            pass

    def _session(self) -> None:
        sock = self._connect(self.host, self.port)
        sock.settimeout(5.0)
        logger.info(f"RBN: connected to {self.host}:{self.port}")
        buffer = b''
        logged_in = False
        last_line = time.monotonic()
        last_lead = time.monotonic()
        self._status(connected=True, error=None, since=datetime.now(timezone.utc).isoformat())
        try:
            while not self.stop_event.is_set():
                try:
                    data = sock.recv(4096)
                except TimeoutError:
                    data = None
                if data == b'':
                    raise ConnectionError('connection closed by the server')
                now = time.monotonic()
                if data:
                    buffer += data
                    if not logged_in and b'call' in buffer.lower() and b':' in buffer:
                        sock.sendall(self.callsign.encode() + b'\r\n')
                        for command in self.login_commands:
                            sock.sendall(command.encode() + b'\r\n')
                        logged_in = True
                        buffer = b''
                        continue
                    *lines, buffer = buffer.split(b'\n')
                    for raw in lines:
                        last_line = now
                        self.handle_line(raw.decode('ascii', errors='replace'))
                if now - last_line > SILENCE_TIMEOUT:
                    raise ConnectionError(f'no data for {SILENCE_TIMEOUT} s')
                if now - last_lead > LEADER_TTL / 3:
                    last_lead = now
                    if not self._lead():
                        raise ConnectionError('lost the RBN leader lock')
                self._flush()
        finally:
            sock.close()
            self._status(connected=False)

    def handle_line(self, line: str) -> Optional[dict[str, Any]]:
        """Parse, filter and store one line. Returns the merged entry for accepted spots."""
        spot = parse_spot(line)
        if spot is None:
            # warn only for skimmer lines; clusters also relay human spots, which are not RBN data
            if line.startswith('DX de') and '-#:' in line and time.time() - self._last_unknown_log > 60:
                self._last_unknown_log = time.time()
                logger.warning(f"RBN: unknown spot format: {line.strip()[:120]}")
            return None
        if not accept(spot, self.prefixes):
            return None
        now = time.time()
        entry = self.book.add(spot, now)
        self.total += 1
        self._recent.append(now)
        if self.on_spot:
            self.on_spot(entry)
        if entry['skimmer_count'] == 1 and entry['first_seen'] == now:
            # only new entries reach the alert rules (merged repeats would flood them)
            from radiomoni import alerts
            alerts.evaluate('rbn', {'callsign': spot['callsign'], 'text': spot['type'],
                                    'frequency': spot['frequency'], 'snr_db': spot['snr_db'],
                                    'wpm': spot['wpm'], 'skimmer': spot['spotter']})
        return entry

    def _flush(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_snapshot < 2.0:
            return
        self._last_snapshot = now
        self.book.prune(now)
        self._recent = [t for t in self._recent if now - t <= 60]
        r = get_redis()
        r.set(SNAPSHOT_KEY, json.dumps(self.book.snapshot()), ex=MAX_AGE)
        self._status(spots_per_minute=len(self._recent), total=self.total, entries=len(self.book.entries),
                     last_spot=max((e['last_seen'] for e in self.book.entries.values()), default=None))

    def _status(self, **changes: Any) -> None:
        try:
            r = get_redis()
            raw = r.get(STATUS_KEY)
            state = json.loads(raw) if raw else {}
            state.update(changes)
            r.set(STATUS_KEY, json.dumps(state), ex=3600)
        except Exception as e:
            logger.debug(f"RBN status not saved: {e}")


_client: Optional[RbnClient] = None


def start_if_enabled() -> Optional[RbnClient]:
    """Start the client when RBN_ENABLED and RBN_CALLSIGN are set (once per process)."""
    global _client
    if _client is not None or not config.RBN_ENABLED:
        return _client
    if not config.RBN_CALLSIGN:
        logger.warning("RBN_ENABLED is set but RBN_CALLSIGN is empty — RBN spots stay off")
        return None
    _client = RbnClient(config.RBN_CALLSIGN, config.RBN_HOST, config.RBN_PORT, config.RBN_SPOTTER_PREFIXES,
                        login_commands=config.RBN_LOGIN_COMMANDS)
    _client.start()
    logger.info(f"RBN client started ({config.RBN_HOST}:{config.RBN_PORT} as {config.RBN_CALLSIGN})")
    return _client
