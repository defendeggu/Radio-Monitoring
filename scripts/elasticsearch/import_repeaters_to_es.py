#!/usr/bin/env python3
"""
Import repeaters from CSV into Elasticsearch

Usage:
    python3 import_repeaters_to_es.py scripts/example_repeaters.csv --es-hosts <host>
"""

import csv
import sys
import uuid
import argparse
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

# Add project root to path to allow importing 'elasticsearch_service'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from elasticsearch_service import ElasticsearchService


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


def import_csv(csv_file: str, es_hosts: List[str]) -> int:
    """
    Import repeaters from CSV file into Elasticsearch.

    Args:
        csv_file: Path to CSV file
        es_hosts: List of Elasticsearch hosts

    Returns:
        Number of repeaters imported
    """
    if not Path(csv_file).exists():
        print(f"Error: File '{csv_file}' not found")
        return 0

    es = ElasticsearchService(hosts=es_hosts)

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
                repeater_doc = {
                    'uuid': str(uuid.uuid4()),
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

    print()
    print("=" * 60)
    print(f"Import complete!")
    print(f"  Imported: {imported}")
    print(f"  Errors:   {errors}")
    print("=" * 60)

    return imported


def main():
    parser = argparse.ArgumentParser(description='Import Swiss repeaters from CSV file to Elasticsearch')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--es-hosts', help='Elasticsearch hosts', required=True)
    args = parser.parse_args()

    print("=" * 60)
    print("Repeater CSV Import to Elasticsearch")
    print("=" * 60)
    print()

    imported = import_csv(args.csv_file, [args.es_hosts])

    sys.exit(0 if imported > 0 else 1)


if __name__ == '__main__':
    main()