"""
Amateur radio callsigns: structure check, base call and CQ WPX prefix.

The structure check is deliberately permissive (letters and digits, at least
one digit inside, ends in a letter); whether the prefix exists is the job of
cty.csv (radiomoni.contest.refdata), whether the station exists that of MASTER.SCP.
"""

import re
from typing import Optional

# one part of a callsign: prefix (1–3 chars) + digit(s) + suffix ending in a letter
BASE_RE = re.compile(r'^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]$')
# suffixes after a stroke that do not change the country
PORTABLE_SUFFIXES = frozenset({'P', 'M', 'MM', 'AM', 'QRP', 'A', 'B', 'LH', 'J', 'R'})


def normalize(call: str) -> str:
    return call.strip().upper()


def is_valid(call: str) -> bool:
    """Plausible structure: a base call, optionally with a prefix and/or suffix."""
    call = normalize(call)
    if not 3 <= len(call) <= 14 or call.count('/') > 2:
        return False
    return base_call(call) is not None


def base_call(call: str) -> Optional[str]:
    """The home call without portable prefix or suffix: DL/OK2PDT/P → OK2PDT."""
    parts = [p for p in normalize(call).split('/') if p]
    candidates = [p for p in parts if BASE_RE.match(p) and any(c.isalpha() for c in p[:3])]
    if not candidates:
        return None
    return max(candidates, key=len)


def location_prefix(call: str) -> Optional[str]:
    """Prefix that sets the country for portable operation (DL/OK2PDT → DL), None for home calls."""
    parts = [p for p in normalize(call).split('/') if p]
    home = base_call(call)
    others = [p for p in parts if p != home and p not in PORTABLE_SUFFIXES and not p.isdigit()]
    return min(others, key=len) if others else None


def is_portable(call: str) -> bool:
    parts = normalize(call).split('/')
    return any(p in ('P', 'M', 'MM', 'AM') for p in parts[1:])


def wpx_prefix(call: str) -> Optional[str]:
    """
    CQ WPX prefix: letters and digits up to the last digit of the prefix.
    HB9XYZ → HB9, N8BJQ → N8, PA/N8BJQ → PA0, N8BJQ/4 → N4, RAEM → RA0.
    """
    call = normalize(call)
    home = base_call(call)
    if home is None:
        return None
    parts = call.split('/')
    portable_prefix = location_prefix(call)
    digit_suffix = next((p for p in parts[1:] if p.isdigit() and len(p) == 1), None)
    if portable_prefix:
        if any(c.isdigit() for c in portable_prefix):
            return portable_prefix
        return portable_prefix + '0'
    m = re.match(r'^([A-Z0-9]*?[0-9]+)(?=[A-Z]+$)', home) or re.match(r'^(.*[0-9])', home)
    prefix = m.group(1) if m else home[:2] + '0'
    if digit_suffix:
        prefix = re.sub(r'[0-9]+$', digit_suffix, prefix)
    return prefix
