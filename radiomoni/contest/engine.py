"""
Classify a spot against the active contest: country and zones, dupe, new
multipliers, rarity (Club Log Most Wanted) and a priority for the operator.

    priority  high    new multiplier or rare DXCC entity (also alerts)
              normal  station not worked yet on this band (and mode)
              dupe    already in the log
              invalid callsign does not resolve to a DXCC entity
"""

from typing import Any, Optional

from radiomoni import config
from radiomoni.contest import callsign as cs
from radiomoni.contest import refdata as refdata_module
from radiomoni.contest import rules as rules_module
from radiomoni.contest import worked
from radiomoni.contest.refdata import RefData
from radiomoni.contest.rules import ContestRules
from radiomoni.redis_client import get_redis

ACTIVE_KEY = 'contest:active'
SWITZERLAND_ADIF = 287

MULT_LABELS = {'dxcc': 'DXCC', 'wpx': 'WPX', 'cq_zone': 'CQ zone', 'itu_zone': 'ITU zone', 'continent': 'continent'}


def active_contest() -> ContestRules:
    try:
        return rules_module.get(get_redis().get(ACTIVE_KEY))
    except Exception:
        return rules_module.get(None)


def set_active_contest(contest_id: str) -> ContestRules:
    if contest_id not in rules_module.all_rules():
        raise ValueError(f'Unknown contest: {contest_id}')
    get_redis().set(ACTIVE_KEY, contest_id)
    return rules_module.get(contest_id)


def classify(call: str, frequency: int, mode: str = 'CW', rules: Optional[ContestRules] = None,
             refdata: Optional[RefData] = None, index: Optional[worked.WorkedIndex] = None) -> dict[str, Any]:
    rules = rules or active_contest()
    refdata = refdata or refdata_module.get()
    index = index if index is not None else worked.index(refdata)
    call = cs.normalize(call)
    mode = worked.normalize_mode(mode)
    band = worked.band_from_khz(frequency / 1000.0)
    entity = refdata.cty.lookup(call)
    result: dict[str, Any] = {
        'callsign': call, 'band': band, 'mode': mode, 'contest': rules.id,
        'country': entity.name if entity else None, 'adif': entity.adif if entity else None,
        'continent': entity.continent if entity else None,
        'cq_zone': entity.cq_zone if entity else None, 'itu_zone': entity.itu_zone if entity else None,
        'wpx': cs.wpx_prefix(call), 'in_scp': call in refdata.scp if len(refdata.scp) else None,
        'portable': cs.is_portable(call), 'swiss': bool(entity and entity.adif == SWITZERLAND_ADIF),
        'highlight': rules.highlight, 'dupe': False, 'new_mults': [], 'rank': None, 'rare': False,
        'in_contest': band in rules.bands and mode in rules.modes,
    }
    if len(refdata.cty) and entity is None:
        result['priority'] = 'invalid'
        return result
    result['dupe'] = index.is_dupe(call, band, mode, rules.dupe)
    for m in rules.multipliers:
        value = worked.mult_value(m.type, call, refdata)
        if value is not None and not index.has_mult(m.type, value, band if m.per == 'band' else None):
            label = entity.name if m.type == 'dxcc' and entity else value
            result['new_mults'].append({'type': m.type, 'value': value, 'label': f'{MULT_LABELS[m.type]} {label}'})
    rank = refdata.rank(entity.adif if entity else None)
    result['rank'] = rank
    result['rare'] = rank is not None and rank <= config.SKIMMER_RARE_RANK
    if result['dupe']:
        result['priority'] = 'dupe'
    elif result['new_mults'] or result['rare']:
        result['priority'] = 'high'
    else:
        result['priority'] = 'normal'
    return result


def describe(result: dict[str, Any]) -> str:
    """Short comment for the cluster line and alerts: 'MULT DXCC Switzerland', 'RARE #12', 'DUPE'."""
    parts = []
    if result.get('dupe'):
        parts.append('DUPE')
    for m in result.get('new_mults') or []:
        parts.append(f"MULT {m['label']}")
    if result.get('rare'):
        parts.append(f"RARE #{result['rank']}")
    return ' '.join(parts)
