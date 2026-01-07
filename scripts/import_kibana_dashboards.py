#!/usr/bin/env python3
"""
Kibana Dashboard Import Script
Automatically imports all dashboard NDJSON files into Kibana
"""

import os
import sys
import glob
import requests
from pathlib import Path

# Configuration
KIBANA_URL = os.getenv('KIBANA_URL', 'http://localhost:5601')
KIBANA_USERNAME = os.getenv('KIBANA_USERNAME', 'elastic')
KIBANA_PASSWORD = os.getenv('ELASTIC_PASSWORD', '')
DASHBOARDS_DIR = Path(__file__).parent.parent / 'monitoring' / 'kibana' / 'dashboards'

def import_ndjson_file(file_path: Path) -> bool:
    """Import a single NDJSON file into Kibana"""
    print(f"Importing {file_path.name}...", end=" ")

    url = f"{KIBANA_URL}/api/saved_objects/_import"
    headers = {'kbn-xsrf': 'true'}
    auth = (KIBANA_USERNAME, KIBANA_PASSWORD) if KIBANA_PASSWORD else None

    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/ndjson')}
            response = requests.post(url, headers=headers, files=files, auth=auth, timeout=30)

        if response.status_code == 200:
            result = response.json()
            success_count = result.get('successCount', 0)
            print(f"✓ Success ({success_count} objects)")
            return True
        else:
            print(f"✗ Failed (HTTP {response.status_code})")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"✗ Failed (Cannot connect to Kibana at {KIBANA_URL})")
        return False
    except Exception as e:
        print(f"✗ Failed ({str(e)})")
        return False


def main():
    """Main import function"""
    print("=" * 70)
    print("Kibana Dashboard Import")
    print("=" * 70)
    print(f"Kibana URL: {KIBANA_URL}")
    print(f"Dashboards Directory: {DASHBOARDS_DIR}")
    print()

    # Check if Kibana is reachable
    auth = (KIBANA_USERNAME, KIBANA_PASSWORD) if KIBANA_PASSWORD else None
    try:
        response = requests.get(f"{KIBANA_URL}/api/status", auth=auth, timeout=10)
        if response.status_code != 200:
            print(f"✗ Kibana is not ready (HTTP {response.status_code})")
            sys.exit(1)
        print("✓ Kibana is reachable\n")
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to Kibana at {KIBANA_URL}")
        print("  Make sure Kibana is running and accessible")
        sys.exit(1)

    # Find all NDJSON files
    ndjson_files = sorted(DASHBOARDS_DIR.glob('*.ndjson'))

    if not ndjson_files:
        print(f"✗ No .ndjson files found in {DASHBOARDS_DIR}")
        sys.exit(1)

    print(f"Found {len(ndjson_files)} dashboard files:\n")

    # Import index patterns first (if exists)
    index_patterns_file = DASHBOARDS_DIR / 'index-patterns.ndjson'
    if index_patterns_file.exists():
        import_ndjson_file(index_patterns_file)
        ndjson_files.remove(index_patterns_file)
        print()

    # Import remaining dashboards
    success_count = 0
    for ndjson_file in ndjson_files:
        if import_ndjson_file(ndjson_file):
            success_count += 1

    # Summary
    print()
    print("=" * 70)
    print(f"Import Complete: {success_count}/{len(ndjson_files)} dashboards imported")
    print("=" * 70)

    if success_count == len(ndjson_files):
        print("\n✓ All dashboards imported successfully!")
        print(f"\nAccess dashboards at: {KIBANA_URL}/app/dashboards")
        sys.exit(0)
    else:
        print(f"\n⚠ {len(ndjson_files) - success_count} dashboard(s) failed to import")
        sys.exit(1)


if __name__ == '__main__':
    main()
