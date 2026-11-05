"""
DX cluster telnet server: the skimmer's spots for N1MM+ (bandmap, click to QSY)
and any other logger that talks to a DX cluster.

    login: HB9XYZ
    Hello HB9XYZ, this is the RadioMoni contest skimmer
    DX de HB9XYZ-#:   14025.0  DL1ABC       CW 18 dB 24 WPM CQ MULT        1203Z

The lines follow the DX cluster / RBN layout, so loggers parse them like RBN
spots. Spots are published from any API process over Redis (publish_spot);
one process (leader lock) runs the server and fans them out. Read-only: client
commands are ignored, except bye/quit.
"""

import json
import logging
import queue
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from radiomoni import config
from radiomoni.integrations.leader import LeaderLock
from radiomoni.redis_client import get_redis

logger = logging.getLogger(__name__)

CHANNEL = 'radiomoni:cluster'
RECENT_KEY = 'cluster:recent'
STATUS_KEY = 'cluster:status'
RECENT = 30                 # spots a new client gets right after login


def format_spot(spotter: str, khz: float, call: str, comment: str, when: Optional[datetime] = None) -> str:
    when = when or datetime.now(timezone.utc)
    head = f'DX de {spotter}:'
    return f'{head:<16}{khz:>9.1f}  {call:<12} {comment[:30]:<30} {when:%H%M}Z'


def spot_comment(spot: dict[str, Any]) -> str:
    """'CW 18 dB 24 WPM CQ' plus MULT / RARE / DUPE."""
    parts = [spot.get('mode') or 'CW']
    if spot.get('snr_db') is not None:
        parts.append(f"{int(round(spot['snr_db']))} dB")
    if spot.get('wpm'):
        parts.append(f"{int(round(spot['wpm']))} WPM")
    parts.append(spot.get('type') or 'CQ')
    priority = spot.get('priority')
    if spot.get('new_mults'):
        parts.append('MULT')
    elif spot.get('rare'):
        parts.append('RARE')
    elif priority == 'dupe':
        parts.append('DUPE')
    return ' '.join(parts)


def publish_spot(spot: dict[str, Any], spotter: Optional[str] = None) -> str:
    """Send a spot to every connected cluster client (any process)."""
    line = format_spot(f"{spotter or config.SKIMMER_CALLSIGN}-#", spot['frequency'] / 1000.0, spot['callsign'],
                       spot_comment(spot))
    r = get_redis()
    r.lpush(RECENT_KEY, line)
    r.ltrim(RECENT_KEY, 0, RECENT - 1)
    r.publish(CHANNEL, line)
    return line


def status() -> dict[str, Any]:
    raw = get_redis().get(STATUS_KEY)
    return {'enabled': config.CLUSTER_ENABLED, 'port': config.CLUSTER_PORT, 'listening': False, 'clients': [],
            **(json.loads(raw) if raw else {})}


class _Client:
    def __init__(self, sock: socket.socket, address: str):
        self.sock = sock
        self.address = address
        self.call = ''
        self.lines: queue.Queue[str] = queue.Queue(maxsize=500)
        self.closed = threading.Event()

    def send(self, text: str) -> None:
        self.sock.sendall(text.encode('ascii', errors='replace'))


class ClusterServer:
    def __init__(self, port: int, max_clients: int = 20, host: str = '0.0.0.0'):
        self.port = port
        self.host = host
        self.max_clients = max_clients
        self.lock = LeaderLock('cluster:leader')
        self.stop_event = threading.Event()
        self.clients: list[_Client] = []
        self._clients_lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.bound_port: Optional[int] = None
        self.ready = threading.Event()

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name='dx-cluster', daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        with self._clients_lock:
            for c in self.clients:
                c.closed.set()
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
                logger.warning(f"DX cluster server on TCP {self.port}: {e}")
                self.stop_event.wait(10)
        self.lock.release()

    def _status(self) -> None:
        with self._clients_lock:
            clients = [{'call': c.call, 'address': c.address} for c in self.clients]
        try:
            get_redis().set(STATUS_KEY, json.dumps({'listening': not self.stop_event.is_set(), 'clients': clients}),
                            ex=120)
        except Exception:
            pass

    def _serve(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        server.settimeout(1.0)
        self.bound_port = server.getsockname()[1]
        logger.info(f"DX cluster server on TCP {self.bound_port}")
        fanout = threading.Thread(target=self._fanout, name='dx-cluster-fanout', daemon=True)
        fanout.start()
        self.ready.set()
        last_lead = time.monotonic()
        try:
            while not self.stop_event.is_set():
                self._status()
                try:
                    sock, (address, _) = server.accept()
                except TimeoutError:
                    sock = None
                if sock is not None:
                    with self._clients_lock:
                        full = len(self.clients) >= self.max_clients
                    if full:
                        sock.sendall(b'Too many connections, try later\r\n')
                        sock.close()
                    else:
                        client = _Client(sock, address)
                        threading.Thread(target=self._client, args=(client,), daemon=True).start()
                if time.monotonic() - last_lead > self.lock.ttl / 3:
                    last_lead = time.monotonic()
                    if not self.lock.hold():
                        return
        finally:
            server.close()
            with self._clients_lock:
                for c in self.clients:
                    c.closed.set()
            try:
                get_redis().delete(STATUS_KEY)
            except Exception:
                pass

    def _fanout(self) -> None:
        pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(CHANNEL)
        try:
            while not self.stop_event.is_set():
                message = pubsub.get_message(timeout=1.0)
                if not message:
                    continue
                line = message['data']
                with self._clients_lock:
                    for c in self.clients:
                        try:
                            c.lines.put_nowait(line)
                        except queue.Full:
                            pass
        finally:
            pubsub.close()

    def _client(self, client: _Client) -> None:
        sock = client.sock
        sock.settimeout(1.0)
        try:
            client.send('login: ')
            buffer = b''
            deadline = time.monotonic() + 60
            while b'\n' not in buffer:
                if time.monotonic() > deadline or self.stop_event.is_set():
                    return
                try:
                    data = sock.recv(256)
                except TimeoutError:
                    continue
                if not data:
                    return
                buffer += data
            client.call = buffer.split(b'\n')[0].decode('ascii', 'replace').strip().upper()[:20] or 'GUEST'
            client.send(f'Hello {client.call}, this is the RadioMoni contest skimmer\r\n')
            with self._clients_lock:
                self.clients.append(client)
            self._status()
            for line in reversed(get_redis().lrange(RECENT_KEY, 0, RECENT - 1)):
                client.send(line + '\r\n')
            client.send(f'{config.SKIMMER_CALLSIGN} de RADIOMONI >\r\n')
            sock.settimeout(0.05)              # poll for bye/quit between spots
            while not client.closed.is_set() and not self.stop_event.is_set():
                try:
                    line = client.lines.get(timeout=0.5)
                    client.send(line + '\r\n')
                except queue.Empty:
                    pass
                try:
                    data = sock.recv(256)
                    if data == b'' or data.strip().lower() in (b'bye', b'quit', b'q'):
                        return
                except (TimeoutError, BlockingIOError):
                    pass
        except OSError:
            pass
        finally:
            with self._clients_lock:
                if client in self.clients:
                    self.clients.remove(client)
            self._status()
            try:
                sock.close()
            except OSError:
                pass


_server: Optional[ClusterServer] = None


def start_if_enabled() -> Optional[ClusterServer]:
    global _server
    if _server is None and config.CLUSTER_ENABLED:
        _server = ClusterServer(config.CLUSTER_PORT, config.CLUSTER_MAX_CLIENTS)
        _server.start()
    return _server
