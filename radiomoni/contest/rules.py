"""
Contest rules from radiomoni/contest/rules/*.yaml.

A rule file names the bands and modes, the dupe scope and the multiplier types:

    id: cq-ww-cw
    modes: [CW]
    bands: [160m, 80m, 40m, 20m, 15m, 10m]
    dupe: band                      # band | band_mode | contest
    multipliers:
      - {type: cq_zone, per: band}  # dxcc | wpx | cq_zone | itu_zone | continent; per band | contest
    highlight: [portable, swiss]    # optional: mark /P stations, Swiss stations

Only what can be told from the callsign is modelled (no exchange-based multipliers).
"""

import os
from functools import lru_cache
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

RULES_DIR = os.path.join(os.path.dirname(__file__), 'rules')
DEFAULT_CONTEST = 'general'

MultiplierType = Literal['dxcc', 'wpx', 'cq_zone', 'itu_zone', 'continent']
Band = Literal['160m', '80m', '60m', '40m', '30m', '20m', '17m', '15m', '12m', '10m']


class Multiplier(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: MultiplierType
    per: Literal['band', 'contest'] = 'band'


class ContestRules(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(..., pattern=r'^[a-z0-9-]+$')
    name: str
    modes: list[Literal['CW', 'SSB']]
    bands: list[Band]
    dupe: Literal['band', 'band_mode', 'contest'] = 'band'
    multipliers: list[Multiplier] = []
    highlight: list[Literal['portable', 'swiss']] = []
    url: str = ''
    notes: str = ''
    assistance: str = ''


@lru_cache(maxsize=1)
def all_rules() -> dict[str, ContestRules]:
    rules: dict[str, ContestRules] = {}
    for name in sorted(os.listdir(RULES_DIR)):
        if not name.endswith('.yaml'):
            continue
        with open(os.path.join(RULES_DIR, name), encoding='utf-8') as f:
            rule = ContestRules.model_validate(yaml.safe_load(f))
        rules[rule.id] = rule
    return rules


def get(contest_id: str | None) -> ContestRules:
    rules = all_rules()
    return rules.get(contest_id or DEFAULT_CONTEST) or rules[DEFAULT_CONTEST]
