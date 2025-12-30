#!/usr/bin/env python3
"""
Create Radio Monitoring Dashboards for Kibana

Creates functional dashboards for:
- Radio Monitoring Overview
- APRS Activity Dashboard
- POCSAG Monitoring Dashboard
- Repeater Activity Dashboard
"""

import requests
import json
import time

KIBANA_URL = "http://localhost:5601"
HEADERS = {'kbn-xsrf': 'true', 'Content-Type': 'application/json'}


def delete_old_dashboards():
    """Delete old dashboards to start fresh"""
    dashboards = [
        'radio-monitoring-overview',
        'aprs-activity-dashboard',
        'pocsag-monitoring-dashboard',
        'repeater-activity-dashboard'
    ]

    for dash_id in dashboards:
        url = f"{KIBANA_URL}/api/saved_objects/dashboard/{dash_id}"
        requests.delete(url, headers=HEADERS)
        print(f"✓ Deleted old dashboard: {dash_id}")


def create_visualization(viz_id, title, viz_type, index_pattern, config):
    """Create a visualization in Kibana"""
    url = f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}"

    # Delete old version if exists
    requests.delete(url, headers=HEADERS)

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
                    "filter": []
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
    if response.status_code in [200, 409]:
        print(f"✓ Created: {title}")
        return True
    else:
        print(f"✗ Failed: {title} ({response.status_code})")
        return False


def create_metric_viz(viz_id, title, index_pattern):
    """Create a simple count metric visualization"""
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
                "style": {"fontSize": 60}
            }
        }
    }
    return create_visualization(viz_id, title, "metric", index_pattern, config)


def create_table_viz(viz_id, title, index_pattern, columns):
    """Create a data table visualization"""
    aggs = [
        {
            "id": "1",
            "enabled": True,
            "type": "count",
            "params": {},
            "schema": "metric"
        }
    ]

    # Add bucket aggregations for each column
    for idx, col in enumerate(columns, start=2):
        aggs.append({
            "id": str(idx),
            "enabled": True,
            "type": "terms",
            "params": {
                "field": f"{col}.keyword" if not col.endswith('_mhz') else col,
                "size": 10,
                "order": "desc",
                "orderBy": "1"
            },
            "schema": "bucket"
        })

    config = {
        "title": title,
        "type": "table",
        "aggs": aggs,
        "params": {
            "perPage": 10,
            "showPartialRows": False,
            "showMetricsAtAllLevels": False,
            "showTotal": False,
            "totalFunc": "sum",
            "percentageCol": ""
        }
    }
    return create_visualization(viz_id, title, "table", index_pattern, config)


def create_timeline_viz(viz_id, title, index_pattern):
    """Create a timeline area chart"""
    config = {
        "title": title,
        "type": "area",
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "count",
                "params": {},
                "schema": "metric"
            },
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "params": {
                    "field": "@timestamp",
                    "interval": "auto",
                    "min_doc_count": 1
                },
                "schema": "segment"
            }
        ],
        "params": {
            "type": "area",
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False,
            "grid": {"categoryLines": False}
        }
    }
    return create_visualization(viz_id, title, "area", index_pattern, config)


def create_dashboards():
    """Create all monitoring dashboards"""

    print("\n" + "="*70)
    print("Creating Radio Monitoring Dashboards")
    print("="*70 + "\n")

    # Delete old dashboards
    delete_old_dashboards()
    print()

    # Create visualizations for Radio Monitoring Overview
    print("Creating Radio Monitoring Overview visualizations...")
    create_metric_viz("overview-total-captures", "Total Captures", "radio-captures-pattern")
    create_metric_viz("overview-total-aprs", "APRS Messages", "radio-aprs-pattern")
    create_metric_viz("overview-total-pocsag", "POCSAG Messages", "radio-pocsag-pattern")
    create_timeline_viz("overview-captures-timeline", "Captures Over Time", "radio-captures-pattern")
    create_table_viz("overview-recent-captures", "Recent Captures", "radio-captures-pattern", ["mode", "modulation"])
    print()

    # Create visualizations for APRS
    print("Creating APRS Dashboard visualizations...")
    create_metric_viz("aprs-total-messages", "Total APRS Messages", "radio-aprs-pattern")
    create_timeline_viz("aprs-timeline", "APRS Messages Over Time", "radio-aprs-pattern")
    create_table_viz("aprs-by-station", "Messages by Station", "radio-aprs-pattern", ["source", "destination"])
    print()

    # Create visualizations for POCSAG
    print("Creating POCSAG Dashboard visualizations...")
    create_metric_viz("pocsag-total-messages", "Total POCSAG Messages", "radio-pocsag-pattern")
    create_timeline_viz("pocsag-timeline", "POCSAG Messages Over Time", "radio-pocsag-pattern")
    create_table_viz("pocsag-by-address", "Messages by Address", "radio-pocsag-pattern", ["address", "message_type"])
    print()

    # Create visualizations for Repeater Activity
    print("Creating Repeater Activity Dashboard visualizations...")
    create_metric_viz("repeater-total-scans", "Total Scans", "radio-repeater-pattern")
    create_timeline_viz("repeater-activity-timeline", "Repeater Activity Over Time", "radio-repeater-pattern")
    create_table_viz("repeater-by-callsign", "Activity by Repeater", "radio-repeater-pattern", ["repeater_callsign", "band"])
    print()

    time.sleep(2)  # Give Kibana time to index visualizations

    # Create dashboards
    print("Creating dashboards...")

    # Radio Monitoring Overview Dashboard
    create_dashboard(
        "radio-monitoring-overview",
        "Radio Monitoring Overview",
        "Complete overview of all radio monitoring activities",
        [
            ("overview-total-captures", 0, 0, 12, 8),
            ("overview-total-aprs", 12, 0, 12, 8),
            ("overview-total-pocsag", 24, 0, 12, 8),
            ("overview-captures-timeline", 0, 8, 36, 10),
            ("overview-recent-captures", 0, 18, 48, 10)
        ]
    )

    # APRS Activity Dashboard
    create_dashboard(
        "aprs-activity-dashboard",
        "APRS Activity Dashboard",
        "Monitor APRS packet activity and statistics",
        [
            ("aprs-total-messages", 0, 0, 16, 8),
            ("aprs-timeline", 16, 0, 32, 10),
            ("aprs-by-station", 0, 10, 48, 12)
        ]
    )

    # POCSAG Monitoring Dashboard
    create_dashboard(
        "pocsag-monitoring-dashboard",
        "POCSAG Monitoring Dashboard",
        "Monitor POCSAG pager messages and activity",
        [
            ("pocsag-total-messages", 0, 0, 16, 8),
            ("pocsag-timeline", 16, 0, 32, 10),
            ("pocsag-by-address", 0, 10, 48, 12)
        ]
    )

    # Repeater Activity Dashboard
    create_dashboard(
        "repeater-activity-dashboard",
        "Repeater Activity Dashboard",
        "Monitor repeater scan results and activity",
        [
            ("repeater-total-scans", 0, 0, 16, 8),
            ("repeater-activity-timeline", 16, 0, 32, 10),
            ("repeater-by-callsign", 0, 10, 48, 12)
        ]
    )

    print("\n" + "="*70)
    print("✅ All dashboards created successfully!")
    print("="*70)
    print(f"\n🌐 Access at: {KIBANA_URL}/app/dashboards\n")


def create_dashboard(dash_id, title, description, panels):
    """Create a dashboard with specified panels"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/{dash_id}"

    # Build panel configurations
    panel_configs = []
    references = []

    for idx, (viz_id, x, y, w, h) in enumerate(panels, start=1):
        panel_configs.append({
            "version": "8.11.3",
            "type": "visualization",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(idx)},
            "panelIndex": str(idx),
            "embeddableConfig": {},
            "panelRefName": f"panel_{idx}"
        })
        references.append({
            "id": viz_id,
            "name": f"panel_{idx}",
            "type": "visualization"
        })

    payload = {
        "attributes": {
            "title": title,
            "description": description,
            "panelsJSON": json.dumps(panel_configs),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-24h",
            "refreshInterval": {"pause": False, "value": 60000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": references
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 409]:
        print(f"✓ Dashboard created: {title}")
        return True
    else:
        print(f"✗ Failed to create dashboard: {title} ({response.status_code})")
        return False


if __name__ == '__main__':
    # Check Kibana availability
    try:
        response = requests.get(f"{KIBANA_URL}/api/status", timeout=10)
        if response.status_code != 200:
            print(f"✗ Kibana not ready")
            exit(1)
    except:
        print(f"✗ Cannot connect to Kibana at {KIBANA_URL}")
        exit(1)

    create_dashboards()
