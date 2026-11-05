"""
Worked log of the contest station: who was worked on which band and mode.

QSOs come from an ADIF or Cabrillo import (start of the contest, after a
restart) and live from N1MM+ (contactinfo / contactreplace / contactdelete,
see radiomoni.integrations.n1mm). They live in Redis (hash contest:qsos), so
every API process sees the same log; a version counter tells the cached index
when to rebuild.
"""

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from radiomoni.contest import callsign as cs
from radiomoni.contest.refdata import RefData
from radiomoni.rbn import band_of
from radiomoni.redis_client import get_redis

QSOS_KEY = 'contest:qsos'
VERSION_KEY = 'contest:qsos:version'
MAX_QSOS = 50_000

N1MM_BANDS = {'1.8': '160m', '3.5': '80m', '5': '60m', '7': '40m', '10': '30m', '14': '20m', '18': '17m',
              '21': '15m', '24': '12m', '28': '10m', '50': '6m', '144': '2m', '432': '70cm', '1296': '23cm'}
# Cabrillo writes VHF/UHF bands as designators instead of kHz
CABRILLO_BANDS = {'50': '6m', '144': '2m', '432': '70cm', '1.2G': '23cm', '1296': '23cm'}
PHONE = {'SSB', 'USB', 'LSB', 'PH', 'AM', 'FM', 'PHONE'}
DIGITAL = {'RTTY', 'RY', 'DG', 'FT8', 'FT4', 'PSK', 'PSK31', 'DIGI', 'DATA'}


def normalize_mode(mode: str) -> str:
    mode = (mode or '').strip().upper()
    if mode in PHONE:
        return 'SSB'
    if mode in DIGITAL:
        return 'DIGI'
    return 'CW' if mode == 'CW' else mode or 'CW'


def band_from_khz(khz: float) -> Optional[str]:
    return band_of(khz)


def band_from_text(text: str) -> Optional[str]:
    """ADIF '20m' / '20M', N1MM '14' or '3,5' (MHz)."""
    text = (text or '').strip().lower().replace(',', '.')
    if re.fullmatch(r'\d+c?m', text):
        return text
    if text in N1MM_BANDS:
        return N1MM_BANDS[text]
    try:
        mhz = float(text)
    except ValueError:
        return None
    return N1MM_BANDS.get(f'{mhz:g}') or band_of(mhz * 1000)


# ------------------------------------------------------------------ imports
_ADIF_FIELD = re.compile(r'<([A-Za-z0-9_]+):(\d+)(?::[^>]*)?>', re.ASCII)


def parse_adif(text: str) -> list[dict[str, Any]]:
    """QSOs from an ADIF file (CALL, BAND or FREQ, MODE)."""
    eoh = re.search(r'<eoh>', text, re.IGNORECASE)
    body = text[eoh.end():] if eoh else text
    qsos = []
    for record in re.split(r'<eor>', body, flags=re.IGNORECASE):
        fields: dict[str, str] = {}
        for m in _ADIF_FIELD.finditer(record):
            fields[m.group(1).upper()] = record[m.end():m.end() + int(m.group(2))].strip()
        call = fields.get('CALL', '').upper()
        if not cs.is_valid(call):
            continue
        band = band_from_text(fields.get('BAND', ''))
        if band is None and fields.get('FREQ'):
            try:
                band = band_from_khz(float(fields['FREQ']) * 1000)
            except ValueError:
                band = None
        qsos.append({'call': call, 'band': band, 'mode': normalize_mode(fields.get('MODE', '')),
                     'time': f"{fields.get('QSO_DATE', '')} {fields.get('TIME_ON', '')}".strip()})
    return qsos


def parse_cabrillo(text: str) -> list[dict[str, Any]]:
    """QSOs from a Cabrillo log: QSO: freq mode date time mycall sent… call rcvd…"""
    qsos = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) < 7 or tokens[0].upper() != 'QSO:':
            continue
        mycall = tokens[5].upper()
        call = next((t.upper() for t in tokens[6:] if t.upper() != mycall and cs.is_valid(t.upper())), None)
        if call is None:
            continue
        band = CABRILLO_BANDS.get(tokens[1].upper())
        if band is None:
            try:
                band = band_from_khz(float(tokens[1]))
            except ValueError:
                band = None
        qsos.append({'call': call, 'band': band, 'mode': normalize_mode(tokens[2]),
                     'time': f'{tokens[3]} {tokens[4]}'})
    return qsos


def parse_log(text: str) -> list[dict[str, Any]]:
    """ADIF or Cabrillo, detected from the content."""
    if re.search(r'^\s*QSO:', text, re.MULTILINE) and not re.search(r'<call:', text, re.IGNORECASE):
        return parse_cabrillo(text)
    return parse_adif(text)


# ------------------------------------------------------------------ log in Redis
def _bump() -> None:
    get_redis().set(VERSION_KEY, uuid.uuid4().hex)


def add(qso: dict[str, Any], qso_id: Optional[str] = None) -> str:
    qso_id = qso_id or f"q:{uuid.uuid4().hex}"
    entry = {'call': cs.normalize(qso['call']), 'band': qso.get('band'), 'mode': normalize_mode(qso.get('mode', '')),
             'time': qso.get('time') or time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
             'source': qso.get('source', 'import')}
    get_redis().hset(QSOS_KEY, qso_id, json.dumps(entry))
    _bump()
    return qso_id


def import_log(text: str, replace: bool = False) -> int:
    qsos = parse_log(text)[:MAX_QSOS]
    if not qsos:
        return 0                         # an empty or unknown file never wipes the log
    r = get_redis()
    if replace:
        r.delete(QSOS_KEY)
    if qsos:
        r.hset(QSOS_KEY, mapping={f"imp:{uuid.uuid4().hex}": json.dumps({**q, 'source': 'import'}) for q in qsos})
    _bump()
    return len(qsos)


def delete(qso_id: str) -> bool:
    removed = bool(get_redis().hdel(QSOS_KEY, qso_id))
    if removed:
        _bump()
    return removed


def clear() -> None:
    get_redis().delete(QSOS_KEY)
    _bump()


def all_qsos() -> list[dict[str, Any]]:
    return [json.loads(v) for v in get_redis().hgetall(QSOS_KEY).values()]


def summary() -> dict[str, Any]:
    qsos = all_qsos()
    by_band: dict[str, int] = {}
    for q in qsos:
        by_band[q.get('band') or '?'] = by_band.get(q.get('band') or '?', 0) + 1
    return {'qsos': len(qsos), 'by_band': dict(sorted(by_band.items())),
            'sources': sorted({q.get('source', 'import') for q in qsos})}


# ------------------------------------------------------------------ index for the classifier
def mult_value(kind: str, call: str, refdata: RefData) -> Optional[str]:
    """Value of a multiplier type for a callsign (None when unknown)."""
    if kind == 'wpx':
        return cs.wpx_prefix(call)
    entity = refdata.cty.lookup(call)
    if entity is None:
        return None
    if kind == 'dxcc':
        return str(entity.adif)
    if kind == 'cq_zone':
        return str(entity.cq_zone)
    if kind == 'itu_zone':
        return str(entity.itu_zone)
    if kind == 'continent':
        return entity.continent
    return None


@dataclass
class WorkedIndex:
    calls: set[tuple[str, Optional[str], str]] = field(default_factory=set)       # (base call, band, mode)
    mults: set[tuple[str, str, Optional[str]]] = field(default_factory=set)       # (type, value, band|None)

    def is_dupe(self, call: str, band: Optional[str], mode: str, scope: str) -> bool:
        base = cs.base_call(call) or cs.normalize(call)
        if scope == 'contest':
            return any(c == base for c, _, _ in self.calls)
        if scope == 'band':
            return any(c == base and b == band for c, b, _ in self.calls)
        return (base, band, mode) in self.calls

    def has_mult(self, kind: str, value: str, band: Optional[str]) -> bool:
        return (kind, value, band) in self.mults


def build_index(qsos: list[dict[str, Any]], refdata: RefData) -> WorkedIndex:
    index = WorkedIndex()
    for q in qsos:
        call = q['call']
        base = cs.base_call(call) or call
        index.calls.add((base, q.get('band'), q.get('mode', 'CW')))
        for kind in ('dxcc', 'wpx', 'cq_zone', 'itu_zone', 'continent'):
            value = mult_value(kind, call, refdata)
            if value is not None:
                index.mults.add((kind, value, q.get('band')))
                index.mults.add((kind, value, None))
    return index


_index: Optional[WorkedIndex] = None
_index_key: Optional[tuple[int, str]] = None


def index(refdata: RefData) -> WorkedIndex:
    """Cached index; rebuilt when the log or the reference data change."""
    global _index, _index_key
    r = get_redis()
    version = r.get(VERSION_KEY)
    if version is None:                  # new or flushed Redis: start a fresh version
        version = uuid.uuid4().hex
        r.set(VERSION_KEY, version, nx=True)
        version = r.get(VERSION_KEY) or version
    key = (refdata.generation, version)
    if _index is None or key != _index_key:
        _index = build_index(all_qsos(), refdata)
        _index_key = key
    return _index
