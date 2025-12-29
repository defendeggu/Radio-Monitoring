#!/usr/bin/env python3
"""
Simple CSV Repeater Import Script

Imports repeater data from a CSV file into the database.

CSV Format:
callsign,frequency_mhz,offset_mhz,tone,mode,band,location,canton,status

Example:
HB9AB,145.625,-0.6,123.0,FM,2m,Zurich,ZH,active
HB9XY,438.100,-7.6,71.9,FM,70cm,Bern,BE,active

Usage:
    python import_repeaters_csv.py repeaters.csv
    python import_repeaters_csv.py --help
"""

import csv
import psycopg2
import argparse
import sys
from pathlib import Path
from typing import Dict, Optional


def read_secret(secret_name: str) -> Optional[str]:
    """Read database secret from Docker secrets."""
    secret_path = Path(f'/run/secrets/{secret_name}')
    if secret_path.exists():
        return secret_path.read_text().strip()
    return None


def get_db_config() -> Dict:
    """Get database configuration from secrets or environment."""
    import os

    user = read_secret('postgres_user')
    password = read_secret('postgres_password')
    database = read_secret('postgres_db')

    if user and password and database:
        return {
            'host': os.getenv('POSTGRES_HOST', 'postgres'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'user': user,
            'password': password,
            'database': database
        }

    # Fallback for running outside Docker
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'user': os.getenv('POSTGRES_USER', 'radio_user'),
        'password': os.getenv('POSTGRES_PASSWORD', 'radio_password'),
        'database': os.getenv('POSTGRES_DB', 'radio_monitoring')
    }


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


def import_csv(csv_file: str, db_config: Dict, skip_duplicates: bool = True) -> int:
    """
    Import repeaters from CSV file.

    Args:
        csv_file: Path to CSV file
        db_config: Database configuration
        skip_duplicates: Skip repeaters that already exist (by callsign + frequency)

    Returns:
        Number of repeaters imported
    """
    if not Path(csv_file).exists():
        print(f"Error: File '{csv_file}' not found")
        return 0

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return 0

    imported = 0
    skipped = 0
    errors = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Validate headers
        required_fields = ['callsign', 'frequency_mhz', 'mode', 'band']
        if not all(field in reader.fieldnames for field in required_fields):
            print(f"Error: CSV must contain columns: {', '.join(required_fields)}")
            print(f"Found columns: {', '.join(reader.fieldnames)}")
            cur.close()
            conn.close()
            return 0

        print(f"Importing repeaters from {csv_file}...")
        print()

        for line_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
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

                # Check for duplicate
                if skip_duplicates:
                    cur.execute(
                        "SELECT id FROM repeaters WHERE callsign = %s AND output_frequency = %s",
                        (callsign, output_frequency)
                    )
                    if cur.fetchone():
                        print(f"Line {line_num}: Skipping {callsign} ({output_frequency/1e6:.4f} MHz) - already exists")
                        skipped += 1
                        continue

                # Insert repeater
                cur.execute("""
                    INSERT INTO repeaters (
                        callsign, output_frequency, input_frequency, offset_mhz,
                        ctcss_tone, modulation, mode, band, location_name, canton, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    callsign,
                    output_frequency,
                    input_frequency,
                    offset_mhz,
                    tone,
                    'FM',  # Default modulation
                    mode,
                    band,
                    location if location else None,
                    canton if canton else None,
                    status
                ))

                freq_mhz = output_frequency / 1e6
                print(f"✓ Line {line_num}: Imported {callsign:8s} {freq_mhz:9.4f} MHz  {mode:6s} {band:4s} {location}")
                imported += 1

            except psycopg2.Error as e:
                print(f"✗ Line {line_num}: Database error - {e}")
                conn.rollback()
                errors += 1
                continue
            except Exception as e:
                print(f"✗ Line {line_num}: Error - {e}")
                errors += 1
                continue

        conn.commit()
        cur.close()
        conn.close()

    print()
    print("=" * 60)
    print(f"Import complete!")
    print(f"  Imported: {imported}")
    print(f"  Skipped:  {skipped} (duplicates)")
    print(f"  Errors:   {errors}")
    print("=" * 60)

    return imported


def main():
    parser = argparse.ArgumentParser(
        description='Import Swiss repeaters from CSV file',
        epilog='''
CSV Format:
  callsign,frequency_mhz,offset_mhz,tone,mode,band,location,canton,status

Example:
  HB9AB,145.625,-0.6,123.0,FM,2m,Zurich,ZH,active
  HB9XY,438.100,-7.6,71.9,FM,70cm,Bern,BE,active

Required fields: callsign, frequency_mhz, mode, band
Optional fields: offset_mhz, tone, location, canton, status
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--allow-duplicates', action='store_true',
                       help='Allow importing duplicate repeaters (same callsign + frequency)')

    args = parser.parse_args()

    print("=" * 60)
    print("Swiss Repeater CSV Import")
    print("=" * 60)
    print()

    db_config = get_db_config()
    imported = import_csv(args.csv_file, db_config, skip_duplicates=not args.allow_duplicates)

    sys.exit(0 if imported > 0 or args.allow_duplicates else 1)


if __name__ == '__main__':
    main()
