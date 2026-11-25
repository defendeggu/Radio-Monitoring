"""
OnAir's decoded-message JSON lines -> RadioMoni documents (index radio-onair-*).

A line (docs/INTEGRATIONS.md of OnAir):
    {"source":"OnAir","type":"acars.message","mode":"ACARS","freq_hz":131725000,
     "time":1795602455.31,"ident":"MU0218","fields":{"flight":"MU0218","text":"POS ..."}}
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from radiomoni import config

# events that describe OnAir itself, not something heard
SKIP_TYPES = frozenset({'receiver.state', 'time.minute', 'session.digest'})

_LAT_KEYS = ('lat', 'latitude')
_LON_KEYS = ('lon', 'lng', 'longitude')
_TEXT_KEYS = ('summary', 'text', 'title', 'detail', 'phase')
_MAX_TEXT = 2000


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _position(fields: dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    lat = next((_number(fields[k]) for k in _LAT_KEYS if k in fields), None)
    lon = next((_number(fields[k]) for k in _LON_KEYS if k in fields), None)
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None, None
    return lat, lon


def _clean_fields(fields: Any) -> dict[str, Any]:
    """Flat scalars only (ES: flattened field); nested values become JSON text."""
    out: dict[str, Any] = {}
    if not isinstance(fields, dict):
        return out
    for key, value in fields.items():
        k = str(key)[:64]
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[k] = value[:_MAX_TEXT] if isinstance(value, str) else value
        else:
            out[k] = json.dumps(value, ensure_ascii=False)[:_MAX_TEXT]
    return out


def summary(event_type: str, mode: str, ident: str, fields: dict[str, Any]) -> str:
    """One readable line for the table and the alert rules ("text")."""
    parts: list[str] = []
    if event_type == 'acars.message' or event_type in ('vdl2.message', 'hfdl.message'):
        who = ' '.join(p for p in (fields.get('flight'), fields.get('tail')) if p)
        if who:
            parts.append(who)
        if fields.get('label'):
            parts.append(f"label {fields['label']}")
    elif event_type.startswith('sonde.'):
        parts.append(' '.join(str(p) for p in (fields.get('type'), fields.get('serial')) if p))
        if fields.get('alt_m') is not None:
            parts.append(f"{float(fields['alt_m']):.0f} m")
        if event_type == 'sonde.landed':
            parts.append('landed')
    elif event_type.startswith('session.'):
        verdict = fields.get('verdict')
        if verdict and verdict != 'clear':
            parts.append(str(verdict))
    elif event_type == 'image.done':
        parts.append(' '.join(str(p) for p in (fields.get('satellite') or fields.get('source'),
                                                fields.get('detail')) if p))
    text = next((str(fields[k]) for k in _TEXT_KEYS if fields.get(k) not in (None, '')), '')
    if text and not any(text in p for p in parts):
        parts.append(text)
    if not parts and ident:
        parts.append(ident)
    line = ' · '.join(p.replace('\n', ' ').strip() for p in parts if p and p.strip())
    return (line or event_type)[:_MAX_TEXT]


def to_document(line: str, store_insights: Optional[bool] = None) -> Optional[dict[str, Any]]:
    """One JSON line -> a document, or None for a line that is not stored."""
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if not isinstance(event, dict) or not isinstance(event.get('type'), str):
        return None
    event_type = event['type']
    insights = config.ONAIR_STORE_INSIGHTS if store_insights is None else store_insights
    if event_type in SKIP_TYPES or (event_type.startswith('insight.') and not insights):
        return None
    fields = _clean_fields(event.get('fields'))
    ident = str(event.get('ident') or '')[:128]
    mode = str(event.get('mode') or '')[:64]
    ts = _number(event.get('time'))
    when = datetime.fromtimestamp(ts, timezone.utc) if ts else datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        'uuid': str(uuid.uuid4()),
        'timestamp': when.isoformat(),
        '@timestamp': when.isoformat(),
        'event_type': event_type,
        'family': event_type.split('.', 1)[0],
        'mode': mode,
        'ident': ident or None,
        'text': summary(event_type, mode, ident, fields),
        'fields': fields,
        'truncated': bool(event.get('truncated')),
    }
    freq = _number(event.get('freq_hz'))
    if freq:
        doc['frequency'] = int(freq)
    lat, lon = _position(fields)
    if lat is not None and lon is not None:
        doc['latitude'], doc['longitude'] = lat, lon
    alt = _number(fields.get('alt_m'))
    if alt is not None:
        doc['altitude'] = alt
    if event_type == 'image.done' and fields.get('path'):
        doc['image_path'] = local_path(str(fields['path']))
    return doc


def local_path(container_path: str) -> Optional[str]:
    """A path inside the OnAir container -> the same file in the read-only mount here (None if outside)."""
    prefix = config.ONAIR_CONTAINER_DATA_DIR.rstrip('/') + '/'
    if not container_path.startswith(prefix):
        return None
    rel = os.path.normpath(container_path[len(prefix):])
    if rel.startswith('..') or os.path.isabs(rel):
        return None
    return os.path.join(config.ONAIR_DATA_DIR, rel)
