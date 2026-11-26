"""
RF -> aprs-stats: every APRS packet RadioMoni decodes over the air goes to
aprs-stats (POST /api/ingest, source 'rf'). aprs-stats keeps only packets of
its stations and recognises a position that also came over APRS-IS.

A background thread sends them; the decoders only put packets in a bounded
queue and never wait for the network.
"""

import logging
import queue
import re
import threading
import time
from typing import Any, Optional

from radiomoni import config
from radiomoni.aprs_parse import unescape
from radiomoni.aprsstats.client import AprsStatsClient, AprsStatsError, enabled

logger = logging.getLogger(__name__)

QUEUE_MAX = 2000
RETRIES = 5
_CHANNEL_RE = re.compile(r'^\s*\[[^\]]*\]\s*')

_queue: 'queue.Queue[dict[str, Any]]' = queue.Queue(maxsize=QUEUE_MAX)
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()
stats = {'sent': 0, 'kept': 0, 'failed': 0, 'dropped': 0}


def tnc2(raw_packet: str) -> Optional[str]:
    """direwolf line ('[0.1] SRC>DST,PATH:info' with <0xNN> escapes) -> TNC2 'SRC>DST,PATH:info'."""
    line = _CHANNEL_RE.sub('', raw_packet or '').strip()
    head, sep, info = line.partition(':')
    if not sep or '>' not in head:
        return None
    return f"{head}:{unescape(info)}".rstrip('\r\n')


def submit(doc: dict[str, Any]) -> bool:
    """Queue an RF packet document (after it was stored). False when it is not sent."""
    if not (enabled() and config.APRSSTATS_FEED_RF) or doc.get('reception', 'rf') != 'rf':
        return False
    raw = tnc2(str(doc.get('raw_packet') or ''))
    if not raw:
        return False
    item = {'raw': raw, 'received_at': doc.get('@timestamp') or doc.get('timestamp'),
            'ext_ref': doc.get('uuid'), 'tries': 0}
    try:
        _queue.put_nowait(item)
    except queue.Full:
        stats['dropped'] += 1
        return False
    _ensure_thread()
    return True


def _ensure_thread() -> None:
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, name='aprsstats-feed', daemon=True)
            _thread.start()


def send(item: dict[str, Any], client: Optional[AprsStatsClient] = None) -> dict[str, Any]:
    body = {k: item[k] for k in ('raw', 'received_at', 'ext_ref') if item.get(k)}
    return dict((client or AprsStatsClient(timeout=10.0)).post('ingest', body) or {})


def _run() -> None:
    while True:
        item = _queue.get()
        try:
            result = send(item, AprsStatsClient(timeout=10.0))   # per packet: follows changed settings
            stats['sent'] += 1
            if result.get('stored'):
                stats['kept'] += 1
        except AprsStatsError as e:
            item['tries'] += 1
            if item['tries'] < RETRIES and '422' not in str(e):
                time.sleep(min(30, 2 ** item['tries']))
                try:
                    _queue.put_nowait(item)
                except queue.Full:
                    stats['dropped'] += 1
            else:
                stats['failed'] += 1
                logger.warning(f"aprs-stats did not take an RF packet: {e}")
        finally:
            _queue.task_done()


def drain(timeout: float = 5.0) -> None:
    """Wait until the queue is empty (tests)."""
    end = time.time() + timeout
    while _queue.unfinished_tasks and time.time() < end:
        time.sleep(0.02)
