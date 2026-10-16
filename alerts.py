"""
Alerts / watchlists (N3).

Rules are stored in Redis. Every decoded packet, transcription and sensor
reading is passed to evaluate(); matching rules record an alert, publish it on
the live event bus and send notifications through the channels configured in
the environment (ntfy, Telegram, webhook, e-mail).

Notification targets come only from server-side configuration, never from
rule data, so rules cannot be used to make the server call arbitrary URLs.
"""

import json
import logging
import re
import smtplib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Optional

import requests

import config
import events
from redis_client import get_redis

logger = logging.getLogger(__name__)

RULES_KEY = 'alert_rules'
RECENT_KEY = 'alerts:recent'
RECENT_MAX = 200
_CACHE_TTL = 5.0

# Which document fields each logical field maps to
FIELD_MAP: dict[str, tuple[str, ...]] = {
    'callsign': ('source_callsign', 'callsign', 'flight', 'shipname'),
    'address': ('address',),
    'text': ('message_text', 'transcription', 'text'),
    'icao': ('icao', 'hex'),
    'mmsi': ('mmsi',),
    'model': ('model',),
}

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='alert-notify')
_cache_lock = threading.Lock()
_cache: tuple[float, list[dict[str, Any]]] = (0.0, [])


# ----------------------------------------------------------------- rule storage
def list_rules() -> list[dict[str, Any]]:
    raw = get_redis().hgetall(RULES_KEY)
    rules = [json.loads(v) for v in raw.values()]
    rules.sort(key=lambda r: r.get('created_at', ''))
    return rules


def get_rule(rule_id: str) -> Optional[dict[str, Any]]:
    raw = get_redis().hget(RULES_KEY, rule_id)
    return json.loads(raw) if raw else None


def save_rule(data: dict[str, Any], rule_id: Optional[str] = None) -> dict[str, Any]:
    existing = get_rule(rule_id) if rule_id else None
    rule = {**data, 'id': rule_id or str(uuid.uuid4()),
            'created_at': (existing or {}).get('created_at') or datetime.now(timezone.utc).isoformat()}
    get_redis().hset(RULES_KEY, rule['id'], json.dumps(rule))
    _invalidate()
    return rule


def delete_rule(rule_id: str) -> bool:
    removed = bool(get_redis().hdel(RULES_KEY, rule_id))
    _invalidate()
    return removed


def recent_alerts(limit: int = 50) -> list[dict[str, Any]]:
    return [json.loads(x) for x in get_redis().lrange(RECENT_KEY, 0, max(0, limit - 1))]


def _invalidate() -> None:
    global _cache
    with _cache_lock:
        _cache = (0.0, [])


def _active_rules() -> list[dict[str, Any]]:
    global _cache
    with _cache_lock:
        ts, rules = _cache
        if time.time() - ts < _CACHE_TTL and ts:
            return rules
    rules = [r for r in list_rules() if r.get('enabled', True)]
    with _cache_lock:
        _cache = (time.time(), rules)
    return rules


# ----------------------------------------------------------------- matching
def _values(rule_field: str, doc: dict[str, Any]) -> list[str]:
    if rule_field == 'any':
        keys = tuple(k for keys in FIELD_MAP.values() for k in keys)
    else:
        keys = FIELD_MAP.get(rule_field, ())
    return [str(doc[k]) for k in keys if doc.get(k) not in (None, '')]


def matches(rule: dict[str, Any], source: str, doc: dict[str, Any]) -> bool:
    """True when `doc` from `source` triggers `rule`."""
    if rule.get('source', 'any') not in ('any', source):
        return False
    pattern = str(rule.get('pattern', ''))
    if not pattern:
        return False
    case = bool(rule.get('case_sensitive', False))
    match_type = rule.get('match_type', 'contains')
    for value in _values(rule.get('field', 'any'), doc):
        if match_type == 'regex':
            if re.search(pattern, value, 0 if case else re.IGNORECASE):
                return True
            continue
        a, b = (value, pattern) if case else (value.lower(), pattern.lower())
        if (match_type == 'equals' and a == b) or (match_type == 'contains' and b in a):
            return True
    return False


def evaluate(source: str, doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Check `doc` against all active rules. Never raises."""
    fired: list[dict[str, Any]] = []
    try:
        for rule in _active_rules():
            if not matches(rule, source, doc):
                continue
            cooldown = int(rule.get('cooldown_seconds', 300))
            if cooldown and not get_redis().set(f"alert_cooldown:{rule['id']}", '1', nx=True, ex=cooldown):
                continue
            fired.append(_fire(rule, source, doc))
    except Exception as e:
        logger.error(f"Alert evaluation failed: {e}", exc_info=True)
    return fired


def _summary(source: str, doc: dict[str, Any]) -> str:
    who = doc.get('source_callsign') or doc.get('address') or doc.get('flight') or doc.get('icao') \
        or doc.get('mmsi') or doc.get('model') or ''
    text = doc.get('message_text') or doc.get('transcription') or doc.get('text') or ''
    freq = doc.get('frequency')
    freq_str = f" @ {freq / 1e6:.4f} MHz" if isinstance(freq, (int, float)) and freq else ''
    return f"[{source.upper()}] {who}{freq_str}: {str(text)[:300]}".strip()


def _fire(rule: dict[str, Any], source: str, doc: dict[str, Any]) -> dict[str, Any]:
    alert = {
        'uuid': str(uuid.uuid4()),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'rule_id': rule['id'],
        'rule_name': rule.get('name'),
        'source': source,
        'summary': _summary(source, doc),
        'document': {k: v for k, v in doc.items() if k not in ('raw_packet', 'segments')},
    }
    r = get_redis()
    r.lpush(RECENT_KEY, json.dumps(alert, default=str))
    r.ltrim(RECENT_KEY, 0, RECENT_MAX - 1)
    events.publish('alert', alert)
    try:
        from storage import get_storage
        get_storage().index_event('alerts', dict(alert))
    except Exception as e:
        logger.warning(f"Could not store alert: {e}")
    channels = list(rule.get('channels') or [])
    if channels:
        _executor.submit(notify, channels, f"RadioMoni: {rule.get('name')}", alert['summary'], alert)
    logger.info(f"Alert fired: {rule.get('name')} — {alert['summary'][:120]}")
    return alert


# ----------------------------------------------------------------- notifications
def configured_channels() -> dict[str, bool]:
    return {
        'ntfy': bool(config.NTFY_URL),
        'telegram': bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID),
        'webhook': bool(config.ALERT_WEBHOOK_URL),
        'email': bool(config.SMTP_HOST and config.ALERT_EMAIL_TO and config.SMTP_FROM),
    }


def notify(channels: list[str], title: str, message: str, payload: Optional[dict[str, Any]] = None) -> dict[str, str]:
    """Send a notification to each channel; returns per-channel status."""
    results: dict[str, str] = {}
    available = configured_channels()
    for channel in channels:
        if not available.get(channel):
            results[channel] = 'not configured'
            continue
        try:
            if channel == 'ntfy':
                headers = {'Title': title, 'Tags': 'radio'}
                if config.NTFY_TOKEN:
                    headers['Authorization'] = f'Bearer {config.NTFY_TOKEN}'
                requests.post(str(config.NTFY_URL), data=message.encode(), headers=headers,
                              timeout=10).raise_for_status()
            elif channel == 'telegram':
                requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                              json={'chat_id': config.TELEGRAM_CHAT_ID, 'text': f"{title}\n{message}"},
                              timeout=10).raise_for_status()
            elif channel == 'webhook':
                requests.post(str(config.ALERT_WEBHOOK_URL),
                              json={'title': title, 'message': message, 'alert': payload},
                              timeout=10).raise_for_status()
            elif channel == 'email':
                mail = EmailMessage()
                mail['Subject'] = title
                mail['From'] = str(config.SMTP_FROM)
                mail['To'] = str(config.ALERT_EMAIL_TO)
                mail.set_content(message)
                with smtplib.SMTP(str(config.SMTP_HOST), config.SMTP_PORT, timeout=15) as smtp:
                    smtp.starttls()
                    if config.SMTP_USER and config.SMTP_PASSWORD:
                        smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
                    smtp.send_message(mail)
            results[channel] = 'sent'
        except Exception as e:
            logger.warning(f"Alert notification via {channel} failed: {e}")
            results[channel] = 'failed'
    return results
