"""
The OnAir modes RadioMoni offers, grouped (OnAir has about 400; /api/v1/modes).

The groups cover what RadioMoni does not decode itself, digital voice and
weather satellites. Modes for public-safety networks (TETRA, TETRAPOL), mobile
phone, Wi-Fi, DECT, Bluetooth and military HF are left out on purpose;
ONAIR_ALL_MODES=true offers every mode OnAir has (your responsibility).
"""

from typing import Any, Optional

from radiomoni import config

GROUPS: dict[str, tuple[str, ...]] = {
    'aviation': ('acars', 'vdl2', 'hfdl', 'uat'),
    'sondes': ('sonde', 'horus'),
    'digital_voice': ('dmr', 'p25', 'p25p2', 'nxdn', 'dpmr', 'dstar', 'fusion', 'm17'),
    'satellites': ('meteor', 'noaaapt', 'cubesat', 'issdown', 'orbcomm'),
    'maritime': ('ais', 'marinevhf', 'sitor', 'marine'),
    'lora': ('mesh', 'loraraw', 'lorawanwide', 'fanet', 'ogn', 'flarm'),
    'broadcast': ('dab', 'fm'),
    'sensors': ('ism', 'wmbus', 'pager'),
}

MODE_GROUP: dict[str, str] = {mode: group for group, ids in GROUPS.items() for mode in ids}


def offered(onair_modes: list[dict[str, Any]], all_modes: Optional[bool] = None) -> list[dict[str, Any]]:
    """OnAir's mode list reduced to the offered modes, each with its group, in group order."""
    every = config.ONAIR_ALL_MODES if all_modes is None else all_modes
    out = []
    for m in onair_modes:
        mode_id = str(m.get('id') or '')
        group = MODE_GROUP.get(mode_id)
        if group is None and not every:
            continue
        out.append({'id': mode_id, 'family': m.get('family'), 'sub': m.get('sub'), 'name': m.get('name'),
                    'default_frequency': int(round(float(m.get('defaultMhz') or 0) * 1e6)),
                    'group': group or 'other'})
    order = list(GROUPS) + ['other']
    out.sort(key=lambda m: (order.index(str(m['group'])), str(m['name'] or '')))
    return out


def find(onair_modes: list[dict[str, Any]], mode_id: str, sub: Optional[str] = None) -> dict[str, Any]:
    """The OnAir mode entry for an offered mode id (ValueError when not offered)."""
    for m in offered(onair_modes):
        if m['id'] == mode_id and (sub is None or m['sub'] == sub):
            return m
    raise ValueError(f"OnAir mode {mode_id!r} is not offered (see /onair/modes)")
