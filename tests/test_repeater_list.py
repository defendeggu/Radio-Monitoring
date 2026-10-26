"""
Tests for the Swiss repeater list: USKA conversion, CSV import and the shipped CSV.
"""

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts' / 'elasticsearch'))

import update_repeaters_from_uska as uska  # noqa: E402
import import_repeaters_to_es as importer  # noqa: E402
from storage import get_storage  # noqa: E402

FIELDS = uska.FIELDS


def _uska_row(**kw):
    row = {'tx': 145.6, 'rx': 145.0, 'call': 'HB9XX', 'qth': 'Somewhere', 'kanton': 'zh',
           'remarks': '', 'type': 'Analog', 'tx_tone': '', 'dmr': False, 'dstar': False,
           'c4fm': False, 'status': 'qrv'}
    row.update(kw)
    return row


class TestUskaConversion:

    def test_analog_repeater(self):
        [r] = uska.convert([_uska_row(remarks='EL#908271 NFM T71.9')])
        assert r == {'callsign': 'HB9XX', 'frequency_mhz': '145.6000', 'offset_mhz': '-0.6', 'tone': '71.9',
                     'mode': 'FM', 'band': '2m', 'location': 'Somewhere', 'canton': 'ZH', 'status': 'active'}

    def test_split_tones_use_the_tx_tone(self):
        [r] = uska.convert([_uska_row(tx=51.85, rx=51.25, remarks='FM RX-T94.8 TX-T103.5')])
        assert (r['tone'], r['band'], r['offset_mhz']) == ('103.5', '6m', '-0.6')

    def test_mixed_is_fm_and_digital_only_keeps_its_modes(self):
        mixed, digital = uska.convert([
            _uska_row(type='Mixed', c4fm=True),
            _uska_row(tx=438.2, rx=430.6, type='Digital', dmr=True, dstar=True),
        ])
        assert mixed['mode'] == 'FM'
        assert digital['mode'] == 'DMR/D-STAR'

    def test_status_mapping(self):
        rows = uska.convert([_uska_row(status=s, tx=145.6 + i * 0.0125)
                             for i, s in enumerate(['qrv', 'qrx', 'qrt', 'planned'])])
        assert [r['status'] for r in rows] == ['active', 'inactive', 'inactive', 'inactive']

    def test_simplex_offset_and_unknown_band(self):
        rows = uska.convert([_uska_row(tx=144.825, rx=144.825), _uska_row(tx=147.0, rx=147.0)])
        assert len(rows) == 1  # 147 MHz is outside the amateur bands
        assert rows[0]['offset_mhz'] == '0'


def _write_csv(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _csv_row(callsign, freq, location, status='active'):
    return {'callsign': callsign, 'frequency_mhz': freq, 'offset_mhz': '-0.6', 'tone': '', 'mode': 'FM',
            'band': '2m', 'location': location, 'canton': 'GR', 'status': status}


class TestImport:

    def test_same_callsign_and_frequency_at_two_sites_are_kept(self, tmp_path):
        path = tmp_path / 'r.csv'
        _write_csv(path, [_csv_row('HB9OK', '145.6250', 'Poschiavo'),
                          _csv_row('HB9OK', '145.6250', 'San Salvatore'),
                          _csv_row('HB9LU', '145.6000', 'Luzern')])

        assert importer.import_csv(str(path)) == 3
        repeaters = get_storage().get_repeaters(limit=100)
        assert sorted(r['location_name'] for r in repeaters) == ['Luzern', 'Poschiavo', 'San Salvatore']

    def test_unique_repeater_keeps_its_previous_id(self, tmp_path):
        path = tmp_path / 'r.csv'
        _write_csv(path, [_csv_row('HB9LU', '145.6000', 'Luzern')])
        importer.import_csv(str(path))

        [r] = get_storage().get_repeaters(limit=10)
        assert r['uuid'] == importer.repeater_uuid('HB9LU', 145_600_000, '', False)

    def test_deactivate_missing(self, tmp_path):
        old, new = tmp_path / 'old.csv', tmp_path / 'new.csv'
        _write_csv(old, [_csv_row('HB9AA', '145.6000', 'A'), _csv_row('HB9BB', '145.6125', 'B')])
        _write_csv(new, [_csv_row('HB9AA', '145.6000', 'A')])
        importer.import_csv(str(old))

        importer.import_csv(str(new), deactivate=True)

        status = {r['callsign']: r['status'] for r in get_storage().get_repeaters(limit=10)}
        assert status == {'HB9AA': 'active', 'HB9BB': 'inactive'}


class TestShippedList:

    def test_repeaters_ch_csv_imports_completely(self):
        path = ROOT / 'scripts' / 'repeaters_ch.csv'
        with open(path, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 100

        assert importer.import_csv(str(path)) == len(rows)
        stored = get_storage().get_repeaters(limit=10_000)
        assert len(stored) == len(rows)  # no two rows collapse onto one ID
        assert {r['band'] for r in stored} <= {'10m', '6m', '2m', '70cm', '23cm'}
        assert len(get_storage().get_repeaters(mode='FM', status='active', limit=10_000)) > 50
