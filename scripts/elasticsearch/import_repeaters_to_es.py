#!/usr/bin/env python3
"""
Import repeaters from CSV into the configured storage (Elasticsearch or SQLite).

Usage (inside the API container):
    docker compose exec radio-api python scripts/elasticsearch/import_repeaters_to_es.py scripts/repeaters_ch.csv
    ... --deactivate-missing   # also mark stored repeaters that are not in the file as inactive

IDs are derived from callsign and frequency (plus the location when the file lists
the same callsign on the same frequency at several sites), so re-importing updates
instead of duplicating.
"""

import csv
import sys
import uuid
import argparse
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

# Add project root to path to allow importing the 'radiomoni' package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from radiomoni.storage import get_storage


def parse_frequency(freq_str: str) -> Optional[int]:
    """Convert frequency in MHz to Hz."""
    try:
        freq_mhz = float(freq_str.strip())
        return int(freq_mhz * 1_000_000)
    except (ValueError, TypeError):
        return None


def parse_optional_float(value: str) -> Optional[float]:
    """Parse optional float value."""
    if not value or value.strip() == '':
        return None
    try:
        return float(value.strip())
    except (ValueError, TypeError):
        return None


def repeater_uuid(callsign: str, output_frequency: int, location: str, shared_frequency: bool) -> str:
    """Stable ID; the location only distinguishes several sites with the same callsign and frequency."""
    key = f'radiomoni:repeater:{callsign}:{output_frequency}'
    if shared_frequency:
        key += f':{location}'
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _shared_frequencies(csv_file: str) -> set[tuple[str, Optional[int]]]:
    """(callsign, frequency) pairs that appear more than once in the file."""
    with open(csv_file, 'r', encoding='utf-8') as f:
        keys = [(row.get('callsign', '').strip().upper(), parse_frequency(row.get('frequency_mhz', '')))
                for row in csv.DictReader(f)]
    return {k for k in keys if keys.count(k) > 1}


def deactivate_missing(storage, imported_ids: set[str]) -> int:
    """Mark stored repeaters that are not in the imported file as inactive."""
    deactivated = 0
    for repeater in storage.get_repeaters(limit=10_000):
        if repeater.get('uuid') in imported_ids or repeater.get('status') == 'inactive':
            continue
        repeater['status'] = 'inactive'
        repeater['updated_at'] = datetime.now(timezone.utc).isoformat()
        storage.index_repeater(repeater)
        print(f"– {repeater.get('callsign', '?'):8s} {repeater.get('output_frequency', 0) / 1e6:9.4f} MHz  "
              "not in the list any more → inactive")
        deactivated += 1
    return deactivated


def import_csv(csv_file: str, deactivate: bool = False) -> int:
    """
    Import repeaters from CSV file into Elasticsearch.

    Args:
        csv_file: Path to CSV file
        deactivate: mark stored repeaters that are not in the file as inactive

    Returns:
        Number of repeaters imported
    """
    if not Path(csv_file).exists():
        print(f"Error: File '{csv_file}' not found")
        return 0

    es = get_storage()
    shared = _shared_frequencies(csv_file)
    imported_ids: set[str] = set()

    imported = 0
    errors = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Validate headers
        required_fields = ['callsign', 'frequency_mhz', 'mode', 'band']
        if not all(field in reader.fieldnames for field in required_fields):
            print(f"Error: CSV must contain columns: {', '.join(required_fields)}")
            print(f"Found columns: {', '.join(reader.fieldnames)}")
            return 0

        print(f"Importing repeaters from {csv_file}...")
        print()

        for line_num, row in enumerate(reader, start=2):
            try:
                # Parse required fields
                callsign = row['callsign'].strip().upper()
                output_frequency = parse_frequency(row['frequency_mhz'])
                mode = row.get('mode', 'FM').strip()
                band = row.get('band', '').strip()

                if not callsign or not output_frequency:
                    print(f"Line {line_num}: Skipping - missing callsign or frequency")
                    errors += 1
                    continue

                # Parse optional fields
                offset_mhz = parse_optional_float(row.get('offset_mhz', ''))
                tone = parse_optional_float(row.get('tone', ''))
                location = row.get('location', '').strip()
                canton = row.get('canton', '').strip().upper()
                status = row.get('status', 'active').strip().lower()

                # Calculate input frequency
                input_frequency = output_frequency
                if offset_mhz:
                    input_frequency = int(output_frequency + (offset_mhz * 1_000_000))

                # Validate status
                if status not in ['active', 'inactive', 'testing']:
                    status = 'active'

                # Create repeater document
                repeater_id = repeater_uuid(callsign, output_frequency, location,
                                            (callsign, output_frequency) in shared)
                imported_ids.add(repeater_id)
                repeater_doc = {
                    'uuid': repeater_id,
                    'callsign': callsign,
                    'output_frequency': output_frequency,
                    'input_frequency': input_frequency,
                    'offset_mhz': offset_mhz,
                    'ctcss_tone': tone,
                    'modulation': 'FM',
                    'mode': mode,
                    'band': band,
                    'location_name': location if location else None,
                    'canton': canton if canton else None,
                    'status': status,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }

                # Index to Elasticsearch
                es.index_repeater(repeater_doc)

                freq_mhz = output_frequency / 1e6
                print(f"✓ Line {line_num}: Imported {callsign:8s} {freq_mhz:9.4f} MHz  {mode:6s} {band:4s} {location}")
                imported += 1

            except Exception as e:
                print(f"✗ Line {line_num}: Error - {e}")
                errors += 1
                continue

    deactivated = deactivate_missing(es, imported_ids) if deactivate and imported else 0

    print()
    print("=" * 60)
    print(f"Import complete!")
    print(f"  Imported: {imported}")
    print(f"  Errors:   {errors}")
    if deactivate:
        print(f"  Deactivated (not in list): {deactivated}")
    print("=" * 60)

    return imported


def main():
    parser = argparse.ArgumentParser(description='Import Swiss repeaters from CSV file to Elasticsearch')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--es-hosts', help='Elasticsearch hosts (default: ELASTICSEARCH_HOSTS)')
    parser.add_argument('--deactivate-missing', action='store_true',
                        help='mark stored repeaters that are not in the CSV as inactive')
    args = parser.parse_args()
    if args.es_hosts:
        import os
        os.environ['ELASTICSEARCH_HOSTS'] = args.es_hosts

    print("=" * 60)
    print("Repeater CSV import")
    print("=" * 60)
    print()

    imported = import_csv(args.csv_file, deactivate=args.deactivate_missing)

    sys.exit(0 if imported > 0 else 1)


if __name__ == '__main__':
    main()