#!/usr/bin/env python3
"""
Delete old/outdated dashboards from Kibana
Keep only the enhanced dashboards and stack health monitor
"""

import requests

KIBANA_URL = "http://localhost:5601"
HEADERS = {'kbn-xsrf': 'true'}

# Dashboards to KEEP (newest versions)
KEEP_DASHBOARDS = {
    'pocsag-dashboard-enhanced',
    'aprs-dashboard-enhanced',
    'overview-dashboard-enhanced',
    'repeater-dashboard-enhanced',
    'stack-health-monitor',  # Latest stack monitoring dashboard
}

# Dashboards to DELETE (old versions)
DELETE_DASHBOARDS = [
    'aprs-dashboard',                    # Old version
    'radio-overview-dashboard',          # Old version
    'pocsag-dashboard',                  # Old version
    'radio-monitoring-overview',         # Old from create_monitoring_dashboards.py
    'repeater-activity-dashboard',       # Old from create_monitoring_dashboards.py
    'pocsag-monitoring-dashboard',       # Old from create_monitoring_dashboards.py
    'aprs-activity-dashboard',           # Old from create_monitoring_dashboards.py
    'simple-radio-overview',             # From create_simple_dashboards.py
    'test-working-dashboard',            # Test dashboard
    'radio-overview-working',            # Working version (superseded by enhanced)
    'aprs-dashboard-working',            # Working version (superseded by enhanced)
    'pocsag-dashboard-working',          # Working version (superseded by enhanced)
    'repeater-dashboard-working',        # Working version (superseded by enhanced)
    'stack-status-monitor',              # Old version (keep stack-health-monitor)
]


def list_all_dashboards():
    """Get all dashboards from Kibana"""
    url = f"{KIBANA_URL}/api/saved_objects/_find?type=dashboard&per_page=100"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        data = response.json()
        return {obj['id']: obj['attributes']['title'] for obj in data['saved_objects']}
    return {}


def delete_dashboard(dashboard_id, title):
    """Delete a dashboard by ID"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}"
    response = requests.delete(url, headers=HEADERS)

    if response.status_code in [200, 404]:
        print(f"  ✓ Deleted: {dashboard_id:40} ({title})")
        return True
    else:
        print(f"  ✗ Failed:  {dashboard_id:40} ({response.status_code})")
        return False


def main():
    print("=" * 80)
    print("Cleaning up old Kibana dashboards")
    print("=" * 80)
    print()

    # Get all dashboards
    all_dashboards = list_all_dashboards()
    print(f"Found {len(all_dashboards)} total dashboards")
    print()

    # Show what will be kept
    print("✅ KEEPING (newest versions):")
    for dash_id in sorted(KEEP_DASHBOARDS):
        if dash_id in all_dashboards:
            print(f"  • {dash_id:40} → {all_dashboards[dash_id]}")
    print()

    # Show what will be deleted
    print("🗑️  DELETING (old versions):")
    deleted_count = 0
    for dash_id in DELETE_DASHBOARDS:
        if dash_id in all_dashboards:
            if delete_dashboard(dash_id, all_dashboards[dash_id]):
                deleted_count += 1

    print()
    print("=" * 80)
    print(f"✅ Cleanup complete! Deleted {deleted_count} old dashboards")
    print("=" * 80)
    print()
    print("Remaining dashboards:")

    # List remaining dashboards
    remaining = list_all_dashboards()
    for dash_id, title in sorted(remaining.items()):
        status = "✓" if dash_id in KEEP_DASHBOARDS else "?"
        print(f"  {status} {dash_id:40} → {title}")

    print()


if __name__ == '__main__':
    main()
