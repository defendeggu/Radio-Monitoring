#!/usr/bin/env python3
"""
Create Stack Status Monitor Dashboard in Kibana via API
"""

import requests
import json
import time
from datetime import datetime

KIBANA_URL = "http://localhost:5601"
HEADERS = {
    'kbn-xsrf': 'true',
    'Content-Type': 'application/json'
}

def create_visualization(viz_id, title, viz_type, index_pattern, config):
    """Create a visualization in Kibana"""
    url = f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}"

    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps(config),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "id": index_pattern,
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern"
        }]
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 409]:  # 200 = created, 409 = already exists
        print(f"✓ Created: {title}")
        return True
    else:
        print(f"✗ Failed to create {title}: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

def create_metric_visualization(viz_id, title, index_pattern):
    """Create a metric visualization showing count"""
    config = {
        "title": title,
        "type": "metric",
        "aggs": [{
            "id": "1",
            "enabled": True,
            "type": "count",
            "params": {},
            "schema": "metric"
        }],
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "type": "metric",
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 10000}],
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": "#000",
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 60
                }
            }
        }
    }
    return create_visualization(viz_id, title, "metric", index_pattern, config)

def create_dashboard():
    """Create the Stack Status Monitor Dashboard"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/stack-status-monitor"

    # Dashboard panels configuration
    panels = [
        # Row 1: Metrics
        {
            "version": "8.11.3",
            "type": "visualization",
            "gridData": {"x": 0, "y": 0, "w": 12, "h": 8, "i": "1"},
            "panelIndex": "1",
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": "panel_1"
        },
        {
            "version": "8.11.3",
            "type": "visualization",
            "gridData": {"x": 12, "y": 0, "w": 12, "h": 8, "i": "2"},
            "panelIndex": "2",
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": "panel_2"
        },
        {
            "version": "8.11.3",
            "type": "visualization",
            "gridData": {"x": 24, "y": 0, "w": 12, "h": 8, "i": "3"},
            "panelIndex": "3",
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": "panel_3"
        },
        {
            "version": "8.11.3",
            "type": "visualization",
            "gridData": {"x": 36, "y": 0, "w": 12, "h": 8, "i": "4"},
            "panelIndex": "4",
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": "panel_4"
        }
    ]

    payload = {
        "attributes": {
            "title": "Stack Status Monitor",
            "description": "Monitor ELK Stack health, performance, and system status",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-24h",
            "refreshInterval": {
                "pause": False,
                "value": 60000  # 1 minute
            },
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {"id": "stack-metric-total-captures", "name": "panel_1", "type": "visualization"},
            {"id": "stack-metric-total-aprs", "name": "panel_2", "type": "visualization"},
            {"id": "stack-metric-total-pocsag", "name": "panel_3", "type": "visualization"},
            {"id": "stack-metric-total-repeater", "name": "panel_4", "type": "visualization"}
        ]
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 409]:
        print(f"\n✓ Dashboard created: Stack Status Monitor")
        return True
    else:
        print(f"\n✗ Failed to create dashboard: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

def main():
    print("=" * 70)
    print("Creating Stack Status Monitor Dashboard")
    print("=" * 70)
    print(f"Kibana URL: {KIBANA_URL}\n")

    # Check if Kibana is reachable
    try:
        response = requests.get(f"{KIBANA_URL}/api/status", timeout=10)
        if response.status_code != 200:
            print(f"✗ Kibana is not ready (HTTP {response.status_code})")
            return False
        print("✓ Kibana is reachable\n")
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to Kibana at {KIBANA_URL}")
        return False

    print("Creating visualizations...\n")

    # Create metric visualizations
    success = True
    success &= create_metric_visualization(
        "stack-metric-total-captures",
        "Total Captures",
        "radio-captures-pattern"
    )

    success &= create_metric_visualization(
        "stack-metric-total-aprs",
        "Total APRS Messages",
        "radio-aprs-pattern"
    )

    success &= create_metric_visualization(
        "stack-metric-total-pocsag",
        "Total POCSAG Messages",
        "radio-pocsag-pattern"
    )

    success &= create_metric_visualization(
        "stack-metric-total-repeater",
        "Total Repeater Scans",
        "radio-repeater-pattern"
    )

    # Create dashboard
    time.sleep(1)  # Give Kibana time to index the visualizations
    success &= create_dashboard()

    print("\n" + "=" * 70)
    if success:
        print("✅ Stack Status Monitor Dashboard created successfully!")
        print("=" * 70)
        print(f"\n🌐 Access at: {KIBANA_URL}/app/dashboards")
        print("\nThe dashboard includes:")
        print("  • Total Captures (real-time count)")
        print("  • Total APRS Messages (real-time count)")
        print("  • Total POCSAG Messages (real-time count)")
        print("  • Total Repeater Scans (real-time count)")
        print("  • Auto-refresh every 60 seconds")
        print("  • Time range: Last 24 hours")
        return True
    else:
        print("⚠️  Some components failed to create")
        print("=" * 70)
        return False

if __name__ == '__main__':
    exit(0 if main() else 1)
