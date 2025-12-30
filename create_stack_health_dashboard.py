#!/usr/bin/env python3
"""
Create comprehensive Stack Health Monitor Dashboard
Shows status of all ELK components and subsystems
"""

import requests
import json
import time

KIBANA_URL = "http://localhost:5601"
HEADERS = {'kbn-xsrf': 'true', 'Content-Type': 'application/json'}

def create_visualization(viz_id, title, config, references):
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
                    "filter": []
                })
            }
        },
        "references": references
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 409]:
        print(f"✓ Created: {title}")
        return True
    else:
        print(f"✗ Failed: {title} ({response.status_code})")
        return False

def create_markdown_viz(viz_id, title, markdown_text):
    """Create a markdown visualization"""
    config = {
        "title": title,
        "type": "markdown",
        "params": {
            "fontSize": 12,
            "openLinksInNewTab": False,
            "markdown": markdown_text
        },
        "aggs": []
    }
    return create_visualization(viz_id, title, config, [])

def create_metric_viz(viz_id, title, index_pattern, field=None, agg_type="count"):
    """Create a metric visualization"""
    aggs = []
    if agg_type == "count":
        aggs.append({
            "id": "1",
            "enabled": True,
            "type": "count",
            "params": {},
            "schema": "metric"
        })
    elif field:
        aggs.append({
            "id": "1",
            "enabled": True,
            "type": agg_type,
            "params": {"field": field},
            "schema": "metric"
        })

    config = {
        "title": title,
        "type": "metric",
        "aggs": aggs,
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
                "style": {"fontSize": 48}
            }
        }
    }

    refs = [{
        "id": index_pattern,
        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "type": "index-pattern"
    }]

    return create_visualization(viz_id, title, config, refs)

def create_timeseries_viz(viz_id, title, index_pattern, field, interval="1m"):
    """Create a time series line chart"""
    config = {
        "title": title,
        "type": "line",
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "avg",
                "params": {"field": field},
                "schema": "metric"
            },
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "params": {
                    "field": "@timestamp",
                    "interval": interval,
                    "min_doc_count": 1
                },
                "schema": "segment"
            }
        ],
        "params": {
            "type": "line",
            "grid": {"categoryLines": False},
            "categoryAxes": [{
                "id": "CategoryAxis-1",
                "type": "category",
                "position": "bottom",
                "show": True,
                "title": {}
            }],
            "valueAxes": [{
                "id": "ValueAxis-1",
                "name": "LeftAxis-1",
                "type": "value",
                "position": "left",
                "show": True,
                "title": {"text": "Average"}
            }],
            "seriesParams": [{
                "show": True,
                "type": "line",
                "mode": "normal",
                "data": {"label": "Average", "id": "1"},
                "valueAxis": "ValueAxis-1"
            }],
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False
        }
    }

    refs = [{
        "id": index_pattern,
        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "type": "index-pattern"
    }]

    return create_visualization(viz_id, title, config, refs)

def create_index_pattern_if_needed():
    """Create metricbeat index pattern if it doesn't exist"""
    url = f"{KIBANA_URL}/api/saved_objects/index-pattern/metricbeat-pattern"

    payload = {
        "attributes": {
            "title": "metricbeat-*",
            "timeFieldName": "@timestamp"
        }
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 409]:
        print("✓ Metricbeat index pattern ready")
        return True
    return False

def create_dashboard():
    """Create the comprehensive Stack Health Monitor Dashboard"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/stack-health-monitor"

    panels = [
        # Row 1: System Overview
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 24, "h": 6, "i": "1"}, "panelIndex": "1", "embeddableConfig": {}, "panelRefName": "panel_1"},

        # Row 2: Elasticsearch Status
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 24, "y": 0, "w": 12, "h": 6, "i": "2"}, "panelIndex": "2", "embeddableConfig": {}, "panelRefName": "panel_2"},
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 0, "w": 12, "h": 6, "i": "3"}, "panelIndex": "3", "embeddableConfig": {}, "panelRefName": "panel_3"},

        # Row 3: System Metrics
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 6, "w": 16, "h": 8, "i": "4"}, "panelIndex": "4", "embeddableConfig": {}, "panelRefName": "panel_4"},
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 16, "y": 6, "w": 16, "h": 8, "i": "5"}, "panelIndex": "5", "embeddableConfig": {}, "panelRefName": "panel_5"},
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 32, "y": 6, "w": 16, "h": 8, "i": "6"}, "panelIndex": "6", "embeddableConfig": {}, "panelRefName": "panel_6"},

        # Row 4: Data Metrics
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 14, "w": 12, "h": 6, "i": "7"}, "panelIndex": "7", "embeddableConfig": {}, "panelRefName": "panel_7"},
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 12, "y": 14, "w": 12, "h": 6, "i": "8"}, "panelIndex": "8", "embeddableConfig": {}, "panelRefName": "panel_8"},
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 24, "y": 14, "w": 12, "h": 6, "i": "9"}, "panelIndex": "9", "embeddableConfig": {}, "panelRefName": "panel_9"},
        {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 14, "w": 12, "h": 6, "i": "10"}, "panelIndex": "10", "embeddableConfig": {}, "panelRefName": "panel_10"},
    ]

    payload = {
        "attributes": {
            "title": "ELK Stack Health Monitor",
            "description": "Comprehensive monitoring of all ELK Stack components and subsystems",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-15m",
            "refreshInterval": {"pause": False, "value": 30000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {"id": "health-system-overview", "name": "panel_1", "type": "visualization"},
            {"id": "health-es-indices", "name": "panel_2", "type": "visualization"},
            {"id": "health-es-shards", "name": "panel_3", "type": "visualization"},
            {"id": "health-cpu-usage", "name": "panel_4", "type": "visualization"},
            {"id": "health-memory-usage", "name": "panel_5", "type": "visualization"},
            {"id": "health-disk-usage", "name": "panel_6", "type": "visualization"},
            {"id": "health-total-captures", "name": "panel_7", "type": "visualization"},
            {"id": "health-total-aprs", "name": "panel_8", "type": "visualization"},
            {"id": "health-total-pocsag", "name": "panel_9", "type": "visualization"},
            {"id": "health-total-repeater", "name": "panel_10", "type": "visualization"},
        ]
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 409]:
        print(f"\n✓ Dashboard created: ELK Stack Health Monitor")
        return True
    else:
        print(f"\n✗ Failed to create dashboard: {response.status_code}")
        return False

def main():
    print("=" * 70)
    print("Creating ELK Stack Health Monitor Dashboard")
    print("=" * 70)
    print(f"Kibana URL: {KIBANA_URL}\n")

    # Check Kibana
    try:
        response = requests.get(f"{KIBANA_URL}/api/status", timeout=10)
        if response.status_code != 200:
            print(f"✗ Kibana not ready")
            return False
        print("✓ Kibana is reachable\n")
    except:
        print(f"✗ Cannot connect to Kibana")
        return False

    print("Creating visualizations...\n")

    # Create index pattern
    create_index_pattern_if_needed()

    # System Overview (Markdown)
    markdown_overview = """
# 🚀 ELK Stack Health Monitor

## Components Status
- **Elasticsearch**: Cluster running
- **Logstash**: 5 pipelines active (captures, APRS, POCSAG, repeater, metrics)
- **Kibana**: Dashboard system
- **Metricbeat**: System metrics collection
- **API Service**: Radio transcription API

## Health Indicators
✅ Green = Healthy | ⚠️ Yellow = Warning | ❌ Red = Critical

**Last Updated**: Auto-refresh every 30 seconds
"""
    create_markdown_viz("health-system-overview", "System Overview", markdown_overview)

    # Elasticsearch Metrics
    create_metric_viz("health-es-indices", "Active Indices", "metricbeat-pattern",
                     "elasticsearch.cluster.stats.indices.count", "max")
    create_metric_viz("health-es-shards", "Active Shards", "metricbeat-pattern",
                     "elasticsearch.cluster.stats.indices.shards.total", "max")

    # System Metrics (from Metricbeat)
    create_timeseries_viz("health-cpu-usage", "CPU Usage %", "metricbeat-pattern",
                         "system.cpu.total.pct")
    create_timeseries_viz("health-memory-usage", "Memory Usage %", "metricbeat-pattern",
                         "system.memory.actual.used.pct")
    create_timeseries_viz("health-disk-usage", "Disk Usage %", "metricbeat-pattern",
                         "system.filesystem.used.pct")

    # Data Metrics
    create_metric_viz("health-total-captures", "Total Captures", "radio-captures-pattern")
    create_metric_viz("health-total-aprs", "APRS Messages", "radio-aprs-pattern")
    create_metric_viz("health-total-pocsag", "POCSAG Messages", "radio-pocsag-pattern")
    create_metric_viz("health-total-repeater", "Repeater Scans", "radio-repeater-pattern")

    # Create dashboard
    time.sleep(1)
    success = create_dashboard()

    print("\n" + "=" * 70)
    if success:
        print("✅ ELK Stack Health Monitor Dashboard created!")
        print("=" * 70)
        print(f"\n🌐 Access at: {KIBANA_URL}/app/dashboards")
        print("\nThe dashboard monitors:")
        print("  📊 System Overview (Components status)")
        print("  🔍 Elasticsearch (Indices, Shards)")
        print("  💻 System Metrics (CPU, Memory, Disk)")
        print("  📡 Data Metrics (Captures, APRS, POCSAG, Repeater)")
        print("  ⏱️  Auto-refresh: Every 30 seconds")
        print("  🕐 Time range: Last 15 minutes")
        return True
    else:
        print("⚠️  Dashboard creation had issues")
        return False

if __name__ == '__main__':
    exit(0 if main() else 1)
