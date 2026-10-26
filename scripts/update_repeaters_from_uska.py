#!/usr/bin/env python3
"""
Build scripts/repeaters_ch.csv from the USKA "HB Voice Repeater List".

Source: https://uska.ch/de/funkamateure/repeater-liste-und-bandplaene/hb-voice-repeater-list/
(the page loads its table from the JSON endpoint below).

Usage:
    python3 scripts/update_repeaters_from_uska.py                 # download and write the CSV
    python3 scripts/update_repeaters_from_uska.py --input list.json
    ./scripts/run_import.sh                                       # then import into the stack

Mapping:
- mode:   Analog and Mixed repeaters (FM plus a digital mode) → FM; digital-only → DMR / D-STAR / C4FM.
          The repeater scan measures FM repeaters (mode FM).
- status: qrv → active; qrx (temporarily off), qrt (closed) and planned → inactive.
- tone:   CTCSS output tone from tx_tone, else parsed from the remarks ("TX-T103.5", "T71.9").
"""

import argparse
import csv
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Optional

API_URL = 'https://uska.ch/wp-json/uska/v1/repeaters'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'repeaters_ch.csv'
FIELDS = ['callsign', 'frequency_mhz', 'offset_mhz', 'tone', 'mode', 'band', 'location', 'canton', 'status']

BANDS = [(28.0, 29.7, '10m'), (50.0, 54.0, '6m'), (144.0, 146.0, '2m'),
         (430.0, 440.0, '70cm'), (1240.0, 1300.0, '23cm')]
STATUS = {'qrv': 'active', 'qrx': 'inactive', 'qrt': 'inactive', 'planned': 'inactive'}
_TX_TONE = re.compile(r'\bTX-T(\d{2,3}\.\d)\b')
_TONE = re.compile(r'\bT(\d{2,3}\.\d)\b')


def band_of(mhz: float) -> Optional[str]:
    return next((name for lo, hi, name in BANDS if lo <= mhz <= hi), None)


def mode_of(row: dict[str, Any]) -> str:
    digital = [name for flag, name in (('dmr', 'DMR'), ('dstar', 'D-STAR'), ('c4fm', 'C4FM')) if row.get(flag)]
    if row.get('type') in ('Analog', 'Mixed') or not digital:
        return 'FM'
    return '/'.join(digital)


def tone_of(row: dict[str, Any]) -> str:
    if row.get('tx_tone'):
        return str(row['tx_tone'])
    remarks = str(row.get('remarks') or '')
    match = _TX_TONE.search(remarks) or _TONE.search(remarks)
    return match.group(1) if match else ''


def convert(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        tx, rx = float(row['tx']), float(row['rx'])
        band = band_of(tx)
        if band is None:
            print(f"Skipping {row.get('call')} {tx} MHz: outside the known amateur bands", file=sys.stderr)
            continue
        out.append({
            'callsign': str(row['call']).strip().upper(),
            'frequency_mhz': f'{tx:.4f}',
            'offset_mhz': f'{rx - tx:.4f}'.rstrip('0').rstrip('.') if rx != tx else '0',
            'tone': tone_of(row),
            'mode': mode_of(row),
            'band': band,
            'location': str(row.get('qth') or '').strip(),
            'canton': str(row.get('kanton') or '').strip().upper(),
            'status': STATUS.get(str(row.get('status')), 'inactive'),
        })
    out.sort(key=lambda r: (float(r['frequency_mhz']), r['callsign'], r['location']))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--input', help='read a saved JSON response instead of downloading')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    if args.input:
        data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    else:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'RadioMoni repeater list update'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)

    rows = convert(data['rows'])
    with open(args.output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    active_fm = sum(1 for r in rows if r['mode'] == 'FM' and r['status'] == 'active')
    print(f"USKA list of {data.get('updated', '?')}: wrote {len(rows)} repeaters "
          f"({active_fm} active FM) to {args.output}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
