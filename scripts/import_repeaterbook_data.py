#!/usr/bin/env python3
"""
Swiss Repeater Data Import Script

Fetches Swiss amateur radio repeater data from RepeaterBook.com
and imports it into the PostgreSQL database.

Usage:
    python import_repeaterbook_data.py --band 2m
    python import_repeaterbook_data.py --band 70cm
    python import_repeaterbook_data.py --band all
"""

import requests
from bs4 import BeautifulSoup
import psycopg2
import argparse
import sys
import re
from typing import List, Dict, Optional
from datetime import datetime


# Swiss canton mapping for common location names
CANTON_MAPPING = {
    'zurich': 'ZH', 'zürich': 'ZH', 'zuerich': 'ZH',
    'bern': 'BE', 'berne': 'BE',
    'luzern': 'LU', 'lucerne': 'LU',
    'uri': 'UR',
    'schwyz': 'SZ',
    'obwalden': 'OW',
    'nidwalden': 'NW',
    'glarus': 'GL',
    'zug': 'ZG',
    'fribourg': 'FR', 'freiburg': 'FR',
    'solothurn': 'SO',
    'basel': 'BS', 'baselstadt': 'BS', 'baselland': 'BL',
    'schaffhausen': 'SH',
    'appenzell': 'AR', 'ausserrhoden': 'AR', 'innerrhoden': 'AI',
    'st. gallen': 'SG', 'st.gallen': 'SG', 'stgallen': 'SG', 'gallen': 'SG',
    'graubünden': 'GR', 'graubuenden': 'GR', 'grisons': 'GR',
    'aargau': 'AG',
    'thurgau': 'TG',
    'ticino': 'TI', 'tessin': 'TI',
    'vaud': 'VD', 'waadt': 'VD',
    'valais': 'VS', 'wallis': 'VS',
    'neuchâtel': 'NE', 'neuchatel': 'NE', 'neuenburg': 'NE',
    'genève': 'GE', 'geneve': 'GE', 'geneva': 'GE', 'genf': 'GE',
    'jura': 'JU',
    'uetliberg': 'ZH',  # Famous locations
    'säntis': 'AI',
    'rigi': 'SZ',
    'pilatus': 'LU',
    'titlis': 'OW',
    'chasseral': 'BE',
    'weissenstein': 'SO',
    'schilthorn': 'BE',
    'generoso': 'TI',
    'chasseron': 'VD',
    'mont tendre': 'VD',
}


def extract_canton_from_location(location: str) -> Optional[str]:
    """
    Extract Swiss canton code from location string.

    Args:
        location: Location name string

    Returns:
        Two-letter canton code or None
    """
    if not location:
        return None

    location_lower = location.lower()

    # Direct canton code match (e.g., "Zurich, ZH")
    canton_match = re.search(r'\b([A-Z]{2})\b', location)
    if canton_match:
        canton = canton_match.group(1)
        # Validate it's a real canton code
        if canton in ['ZH', 'BE', 'LU', 'UR', 'SZ', 'OW', 'NW', 'GL', 'ZG',
                      'FR', 'SO', 'BS', 'BL', 'SH', 'AR', 'AI', 'SG', 'GR',
                      'AG', 'TG', 'TI', 'VD', 'VS', 'NE', 'GE', 'JU']:
            return canton

    # Check mapping
    for key, canton in CANTON_MAPPING.items():
        if key in location_lower:
            return canton

    return None


def parse_frequency(freq_str: str) -> Optional[int]:
    """
    Parse frequency string to Hz.

    Args:
        freq_str: Frequency string (e.g., "145.625", "438.100")

    Returns:
        Frequency in Hz or None
    """
    if not freq_str:
        return None

    try:
        # Remove any non-numeric characters except decimal point
        freq_clean = re.sub(r'[^\d.]', '', freq_str)
        freq_mhz = float(freq_clean)
        return int(freq_mhz * 1_000_000)  # Convert MHz to Hz
    except (ValueError, TypeError):
        return None


def parse_offset(offset_str: str) -> Optional[float]:
    """
    Parse offset string to MHz.

    Args:
        offset_str: Offset string (e.g., "+", "-", "+0.6", "-0.6")

    Returns:
        Offset in MHz (positive or negative) or None
    """
    if not offset_str or offset_str == '—' or offset_str == '':
        return None

    # Standard offsets by band
    if offset_str == '+':
        return 0.6  # 2m standard: +600kHz
    elif offset_str == '-':
        return -0.6  # Assume 600kHz

    try:
        # Parse explicit offset
        offset_clean = re.sub(r'[^\d.-]', '', offset_str)
        return float(offset_clean)
    except (ValueError, TypeError):
        return None


def parse_tone(tone_str: str) -> Optional[float]:
    """
    Parse CTCSS tone string.

    Args:
        tone_str: Tone string (e.g., "123.0", "71.9")

    Returns:
        Tone frequency in Hz or None
    """
    if not tone_str or tone_str == '—' or tone_str == '':
        return None

    try:
        tone_clean = re.sub(r'[^\d.]', '', tone_str)
        return float(tone_clean)
    except (ValueError, TypeError):
        return None


def determine_mode(mode_str: str) -> str:
    """
    Determine repeater mode from mode string.

    Args:
        mode_str: Mode description string

    Returns:
        Mode identifier ('FM', 'DMR', 'D-STAR', 'Fusion', 'P25', 'C4FM')
    """
    if not mode_str:
        return 'FM'

    mode_upper = mode_str.upper()

    if 'DMR' in mode_upper:
        return 'DMR'
    elif 'D-STAR' in mode_upper or 'DSTAR' in mode_upper:
        return 'D-STAR'
    elif 'FUSION' in mode_upper or 'C4FM' in mode_upper or 'YSF' in mode_upper:
        return 'Fusion'
    elif 'P25' in mode_upper or 'P-25' in mode_upper:
        return 'P25'
    else:
        return 'FM'


def fetch_repeater_data(band: str) -> List[Dict]:
    """
    Fetch repeater data from RepeaterBook.com for Swiss repeaters.

    Args:
        band: Band identifier ('2m' or '70cm')

    Returns:
        List of repeater dictionaries
    """
    # RepeaterBook URLs for Swiss repeaters
    urls = {
        '2m': 'https://www.repeaterbook.com/row_repeaters/Display_SS.php?state_id=CH&band=4',
        '70cm': 'https://www.repeaterbook.com/row_repeaters/Display_SS.php?state_id=CH&band=16'
    }

    if band not in urls:
        raise ValueError(f"Invalid band: {band}. Use '2m' or '70cm'")

    url = urls[band]
    print(f"Fetching {band} repeater data from {url}...")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return []

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find repeater table (this is RepeaterBook-specific parsing)
    # The structure may vary, so we'll try common patterns
    repeaters = []

    # Look for table rows
    table = soup.find('table')
    if not table:
        print("Warning: Could not find repeater table in HTML")
        return []

    rows = table.find_all('tr')[1:]  # Skip header row

    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 5:
            continue

        try:
            # Common RepeaterBook table structure:
            # Frequency | Offset | Tone | Location | Callsign | Use | Mode | Status
            # (Exact structure may vary, adjust as needed)

            frequency_str = cells[0].get_text(strip=True)
            offset_str = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            tone_str = cells[2].get_text(strip=True) if len(cells) > 2 else ''
            location = cells[3].get_text(strip=True) if len(cells) > 3 else ''
            callsign = cells[4].get_text(strip=True) if len(cells) > 4 else ''
            mode_str = cells[6].get_text(strip=True) if len(cells) > 6 else 'FM'
            status_str = cells[7].get_text(strip=True) if len(cells) > 7 else ''

            frequency = parse_frequency(frequency_str)
            if not frequency:
                continue

            offset = parse_offset(offset_str)
            input_frequency = frequency
            if offset:
                input_frequency = int(frequency + (offset * 1_000_000))

            mode = determine_mode(mode_str)
            canton = extract_canton_from_location(location)

            # Determine status
            status = 'active'
            if 'off' in status_str.lower() or 'inactive' in status_str.lower():
                status = 'inactive'
            elif 'test' in status_str.lower():
                status = 'testing'

            repeater = {
                'callsign': callsign,
                'output_frequency': frequency,
                'input_frequency': input_frequency,
                'offset_mhz': offset,
                'ctcss_tone': parse_tone(tone_str),
                'mode': mode,
                'band': band,
                'location_name': location,
                'canton': canton,
                'status': status,
                'modulation': 'FM'  # Default modulation
            }

            repeaters.append(repeater)

        except (IndexError, AttributeError) as e:
            print(f"Warning: Could not parse row: {e}")
            continue

    print(f"Found {len(repeaters)} repeaters in {band} band")
    return repeaters


def insert_repeaters(repeaters: List[Dict], db_config: Dict, fm_only: bool = True):
    """
    Insert repeaters into PostgreSQL database.

    Args:
        repeaters: List of repeater dictionaries
        db_config: Database configuration dictionary
        fm_only: If True, only insert FM repeaters (filter out digital modes)
    """
    # Filter for FM only if requested
    if fm_only:
        original_count = len(repeaters)
        repeaters = [r for r in repeaters if r['mode'] == 'FM']
        print(f"Filtered to FM-only: {len(repeaters)} of {original_count} repeaters")

    if not repeaters:
        print("No repeaters to insert")
        return

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        inserted_count = 0
        skipped_count = 0

        for repeater in repeaters:
            try:
                # Check if repeater already exists (by callsign + frequency)
                cur.execute(
                    "SELECT id FROM repeaters WHERE callsign = %s AND output_frequency = %s",
                    (repeater['callsign'], repeater['output_frequency'])
                )

                if cur.fetchone():
                    print(f"  Skipping {repeater['callsign']} ({repeater['output_frequency']/1e6:.4f} MHz) - already exists")
                    skipped_count += 1
                    continue

                # Insert repeater
                cur.execute("""
                    INSERT INTO repeaters (
                        callsign, output_frequency, input_frequency, offset_mhz,
                        ctcss_tone, modulation, mode, band, latitude, longitude,
                        elevation_meters, canton, location_name, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    repeater['callsign'],
                    repeater['output_frequency'],
                    repeater['input_frequency'],
                    repeater['offset_mhz'],
                    repeater['ctcss_tone'],
                    repeater['modulation'],
                    repeater['mode'],
                    repeater['band'],
                    None,  # latitude (not available from RepeaterBook listing)
                    None,  # longitude
                    None,  # elevation
                    repeater['canton'],
                    repeater['location_name'],
                    repeater['status']
                ))

                inserted_count += 1
                print(f"  ✓ Inserted {repeater['callsign']} ({repeater['output_frequency']/1e6:.4f} MHz) - {repeater['location_name']}")

            except psycopg2.Error as e:
                print(f"  ✗ Error inserting {repeater.get('callsign', 'Unknown')}: {e}")
                conn.rollback()
                continue

        conn.commit()
        print(f"\n✓ Successfully inserted {inserted_count} repeaters")
        print(f"  Skipped {skipped_count} existing repeaters")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)


def get_db_config_from_secrets() -> Dict:
    """Read database configuration from Docker secrets."""
    try:
        with open('/run/secrets/postgres_user', 'r') as f:
            user = f.read().strip()
        with open('/run/secrets/postgres_password', 'r') as f:
            password = f.read().strip()
        with open('/run/secrets/postgres_db', 'r') as f:
            database = f.read().strip()

        return {
            'host': 'postgres',
            'port': 5432,
            'user': user,
            'password': password,
            'database': database
        }
    except FileNotFoundError:
        # Fallback for running outside Docker
        import os
        return {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'user': os.getenv('POSTGRES_USER', 'radio_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'radio_password'),
            'database': os.getenv('POSTGRES_DB', 'radio_monitoring')
        }


def main():
    parser = argparse.ArgumentParser(description='Import Swiss repeater data from RepeaterBook.com')
    parser.add_argument('--band', choices=['2m', '70cm', 'all'], default='all',
                       help='Band to import (2m, 70cm, or all)')
    parser.add_argument('--include-digital', action='store_true',
                       help='Include digital modes (DMR, D-STAR, etc.), not just FM')

    args = parser.parse_args()

    print("=" * 60)
    print("Swiss Repeater Data Import")
    print("=" * 60)
    print(f"Band: {args.band}")
    print(f"FM Only: {not args.include_digital}")
    print()

    # Get database configuration
    db_config = get_db_config_from_secrets()

    # Fetch and import data
    bands = ['2m', '70cm'] if args.band == 'all' else [args.band]

    total_imported = 0
    for band in bands:
        print(f"\n--- Processing {band.upper()} Band ---")
        repeaters = fetch_repeater_data(band)

        if repeaters:
            insert_repeaters(repeaters, db_config, fm_only=not args.include_digital)
            total_imported += len(repeaters)

    print("\n" + "=" * 60)
    print(f"Import complete! Processed {total_imported} repeaters total")
    print("=" * 60)


if __name__ == '__main__':
    main()
