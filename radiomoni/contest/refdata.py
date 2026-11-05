"""
Contest reference data, cached in CONTEST_DATA_DIR so the skimmer works without internet:

- cty.csv     country, DXCC (ADIF) number, continent, CQ/ITU zone by prefix
              (Big CTY by AD1C, https://www.country-files.com/)
- MASTER.SCP  callsigns active in contests (Super Check Partial, https://www.supercheckpartial.com/)
- mostwanted.json  Club Log DXCC Most Wanted ranking, rank → ADIF number (https://clublog.org/)

Update with POST /contest/refdata/update or `python -m radiomoni.contest.refdata --update`.
"""

import argparse
import itertools
import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from radiomoni import config
from radiomoni.contest.callsign import base_call, location_prefix, normalize

logger = logging.getLogger(__name__)

SOURCES = {
    'cty.csv': 'https://www.country-files.com/cty/cty.csv',
    'MASTER.SCP': 'https://www.supercheckpartial.com/MASTER.SCP',
    'mostwanted.json': 'https://clublog.org/mostwanted.php?api=1',
}
MAX_DOWNLOAD = 20 * 1024 * 1024


@dataclass(frozen=True)
class Entity:
    prefix: str        # primary prefix (HB, DL, K …)
    name: str
    adif: int
    continent: str
    cq_zone: int
    itu_zone: int


_MOD_CQ = re.compile(r'\((\d+)\)')
_MOD_ITU = re.compile(r'\[(\d+)\]')
_MOD_CONT = re.compile(r'\{([A-Z]{2})\}')
_CORE = re.compile(r'^(=?)([A-Z0-9/]+)')


class CtyData:
    """Prefix → entity lookup from cty.csv (longest prefix wins, '=' entries are exact calls)."""

    def __init__(self, text: str = ''):
        self.entities: list[Entity] = []
        self.prefixes: dict[str, Entity] = {}
        self.exact: dict[str, Entity] = {}
        self._max_len = 0
        if text:
            self.parse(text)

    def parse(self, text: str) -> None:
        for line in text.splitlines():
            fields = line.strip().split(',')
            if len(fields) < 10:
                continue
            try:
                entity = Entity(prefix=fields[0].lstrip('*'), name=fields[1], adif=int(fields[2]),
                                continent=fields[3], cq_zone=int(fields[4]), itu_zone=int(fields[5]))
            except ValueError:
                continue
            self.entities.append(entity)
            for token in fields[9].rstrip(';').split():
                m = _CORE.match(token)
                if not m:
                    continue
                cq, itu, cont = _MOD_CQ.search(token), _MOD_ITU.search(token), _MOD_CONT.search(token)
                variant = entity
                if cq or itu or cont:
                    variant = Entity(entity.prefix, entity.name, entity.adif,
                                     cont.group(1) if cont else entity.continent,
                                     int(cq.group(1)) if cq else entity.cq_zone,
                                     int(itu.group(1)) if itu else entity.itu_zone)
                if m.group(1) == '=':
                    self.exact[m.group(2)] = variant
                else:
                    self.prefixes[m.group(2)] = variant
                    self._max_len = max(self._max_len, len(m.group(2)))

    def _longest(self, text: str) -> Optional[Entity]:
        for n in range(min(len(text), self._max_len), 0, -1):
            hit = self.prefixes.get(text[:n])
            if hit:
                return hit
        return None

    def lookup(self, call: str) -> Optional[Entity]:
        call = normalize(call)
        for candidate in (call, call.split('/')[0]):       # exact entries, also without /P
            if candidate in self.exact:
                return self.exact[candidate]
        where = location_prefix(call)
        if where:
            return self._longest(where)
        home = base_call(call)
        return self._longest(home) if home else None

    def __len__(self) -> int:
        return len(self.entities)


class Scp:
    """Super Check Partial: callsigns known to be active in contests."""

    def __init__(self, text: str = ''):
        self.calls: set[str] = set()
        for line in text.splitlines():
            line = line.strip().upper()
            if line and not line.startswith(('#', '!')):
                self.calls.add(line)

    def __contains__(self, call: object) -> bool:
        if not isinstance(call, str):
            return False
        call = normalize(call)
        return call in self.calls or (base_call(call) or '') in self.calls

    def __len__(self) -> int:
        return len(self.calls)


_generations = itertools.count(1)


class RefData:
    def __init__(self, cty: Optional[CtyData] = None, scp: Optional[Scp] = None,
                 most_wanted: Optional[dict[int, int]] = None, files: Optional[dict[str, Any]] = None):
        self.cty = cty or CtyData()
        self.scp = scp or Scp()
        self.most_wanted = most_wanted or {}       # ADIF → rank (1 = most wanted)
        self.files = files or {}
        self.generation = next(_generations)        # identifies this load for caches

    def rank(self, adif: Optional[int]) -> Optional[int]:
        return self.most_wanted.get(adif) if adif is not None else None

    def info(self) -> dict[str, Any]:
        return {'entities': len(self.cty), 'scp_calls': len(self.scp), 'most_wanted': len(self.most_wanted),
                'files': self.files}


def parse_most_wanted(text: str) -> dict[int, int]:
    """Club Log API answer {"1": "344", …} (rank → ADIF) as ADIF → rank."""
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    result: dict[int, int] = {}
    if isinstance(data, dict):
        for rank, adif in data.items():
            try:
                result.setdefault(int(adif), int(rank))
            except (TypeError, ValueError):
                continue
    return result


def _read(path: str) -> str:
    with open(path, encoding='latin-1') as f:
        return f.read()


def load(directory: Optional[str] = None) -> RefData:
    directory = directory or config.CONTEST_DATA_DIR
    files: dict[str, Any] = {}
    texts: dict[str, str] = {}
    for name in SOURCES:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            texts[name] = _read(path)
            files[name] = {'updated': datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat(),
                           'bytes': os.path.getsize(path)}
    return RefData(CtyData(texts.get('cty.csv', '')), Scp(texts.get('MASTER.SCP', '')),
                   parse_most_wanted(texts.get('mostwanted.json', '{}')), files)


_cache: Optional[RefData] = None
_cache_key: Optional[tuple[Any, ...]] = None
_lock = threading.Lock()


def _key(directory: str) -> tuple[Any, ...]:
    return tuple(os.path.getmtime(os.path.join(directory, n)) if os.path.isfile(os.path.join(directory, n))
                 else None for n in SOURCES)


def get() -> RefData:
    """Cached reference data; reloaded when a file changes."""
    global _cache, _cache_key
    directory = config.CONTEST_DATA_DIR
    key = _key(directory)
    with _lock:
        if _cache is None or key != _cache_key:
            _cache = load(directory)
            _cache_key = key
        return _cache


def update(directory: Optional[str] = None, session: Optional[requests.Session] = None) -> dict[str, Any]:
    """Download all sources (atomic replace). Returns per-file result; keeps old files on errors."""
    directory = directory or config.CONTEST_DATA_DIR
    os.makedirs(directory, exist_ok=True)
    http = session or requests.Session()
    result: dict[str, Any] = {}
    for name, url in SOURCES.items():
        try:
            response = http.get(url, timeout=30, headers={'User-Agent': 'RadioMoni contest skimmer'})
            response.raise_for_status()
            data = response.content[:MAX_DOWNLOAD]
            if name == 'cty.csv' and len(CtyData(data.decode('latin-1'))) < 100:
                raise ValueError('cty.csv looks wrong (fewer than 100 entities)')
            if name == 'mostwanted.json' and not parse_most_wanted(data.decode('utf-8', 'replace')):
                raise ValueError('Most Wanted list is empty')
            tmp = os.path.join(directory, f'.{name}.tmp')
            with open(tmp, 'wb') as f:
                f.write(data)
            os.replace(tmp, os.path.join(directory, name))
            result[name] = {'ok': True, 'bytes': len(data)}
        except Exception as e:
            logger.warning(f"Contest data {name} not updated: {e}")
            result[name] = {'ok': False, 'error': str(e)[:200]}
    return result


def main() -> None:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description='Contest reference data (cty.csv, MASTER.SCP, Most Wanted)')
    parser.add_argument('--update', action='store_true', help='download the current files')
    parser.add_argument('--dir', default=config.CONTEST_DATA_DIR)
    args = parser.parse_args()
    if args.update:
        print(json.dumps(update(args.dir), indent=2))
    print(json.dumps(load(args.dir).info(), indent=2))


if __name__ == '__main__':  # pragma: no cover
    main()
