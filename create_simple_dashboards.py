#!/usr/bin/env python3
"""
Create simple, working dashboards for Kibana 8.x
Uses basic saved searches and simple metrics
"""

import requests
import json
import time

KIBANA_URL = "http://localhost:5601"
HEADERS = {'kbn-xsrf': 'true', 'Content-Type': 'application/json'}


def create_lens_metric(viz_id, title, index_pattern_id, index_pattern_title):
    """Create a Lens metric visualization (Kibana 8.x native)"""
    url = f"{KIBANA_URL}/api/saved_objects/lens/{viz_id}"

    # Delete if exists
    requests.delete(url, headers=HEADERS)

    payload = {
        "attributes": {
            "title": title,
            "description": "",
            "visualizationType": "lnsMetric",
            "state": {
                "datasourceStates": {
                    "formBased": {
                        "layers": {
                            "layer1": {
                                "columns": {
                                    "col1": {
                                        "label": "Count",
                                        "dataType": "number",
                                        "operationType": "count",
                                        "isBucketed": False,
                                        "scale": "ratio",
                                        "sourceField": "___records___",
                                        "params": {
                                            "emptyAsNull": False
                                        }
                                    }
                                },
                                "columnOrder": ["col1"],
                                "incompleteColumns": {},
                                "sampling": 1
                            }
                        }
                    }
                },
                "visualization": {
                    "layerId": "layer1",
                    "layerType": "data",
                    "metricAccessor": "col1"
                },
                "query": {
                    "query": "",
                    "language": "kuery"
                },
                "filters": []
            },
            "references": [
                {
                    "type": "index-pattern",
                    "id": index_pattern_id,
                    "name": f"indexpattern-datasource-layer-layer1"
                }
            ]
        }
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 409]:
        print(f"✓ Created Lens metric: {title}")
        return True
    else:
        print(f"✗ Failed: {title} - {response.status_code}")
        print(f"  Response: {response.text[:200]}")
        return False


def create_simple_dashboard(dash_id, title, description, lens_panels):
    """Create a dashboard with Lens visualizations"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/{dash_id}"

    # Delete if exists
    requests.delete(url, headers=HEADERS)

    panel_configs = []
    references = []

    for idx, (lens_id, x, y, w, h) in enumerate(lens_panels, start=1):
        panel_configs.append({
            "version": "8.11.3",
            "type": "lens",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(idx)},
            "panelIndex": str(idx),
            "embeddableConfig": {
                "enhancements": {}
            },
            "panelRefName": f"panel_{idx}"
        })
        references.append({
            "id": lens_id,
            "name": f"panel_{idx}",
            "type": "lens"
        })

    payload = {
        "attributes": {
            "title": title,
            "description": description,
            "panelsJSON": json.dumps(panel_configs),
            "optionsJSON": json.dumps({
                "hidePanelTitles": False,
                "useMargins": True
            }),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-7d",  # Use 7 days to be safe
            "refreshInterval": {
                "pause": False,
                "value": 60000
            },
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
        print(f"✗ Failed: {title} - {response.status_code}")
        print(f"  Response: {response.text[:200]}")
        return False


def main():
    print("="*70)
    print("Creating Simple Kibana 8.x Dashboards")
    print("="*70)
    print()

    # Check Kibana
    try:
        response = requests.get(f"{KIBANA_URL}/api/status", timeout=10)
        if response.status_code != 200:
            print("✗ Kibana not ready")
            return False
    except:
        print("✗ Cannot connect to Kibana")
        return False

    print("✓ Kibana is reachable\n")

    # Create Lens metrics
    print("Creating Lens visualizations...")
    create_lens_metric("lens-total-captures", "Total Captures", "radio-captures-pattern", "radio-captures-*")
    create_lens_metric("lens-total-aprs", "Total APRS", "radio-aprs-pattern", "radio-aprs-*")
    create_lens_metric("lens-total-pocsag", "Total POCSAG", "radio-pocsag-pattern", "radio-pocsag-*")
    create_lens_metric("lens-total-repeater", "Total Repeater Activity", "radio-repeater-pattern", "radio-repeater-activity-*")

    print()
    time.sleep(2)

    # Create dashboard
    print("Creating dashboard...")
    create_simple_dashboard(
        "simple-radio-overview",
        "Radio Monitoring - Simple Overview",
        "Simple overview with working Lens visualizations",
        [
            ("lens-total-captures", 0, 0, 12, 8),
            ("lens-total-aprs", 12, 0, 12, 8),
            ("lens-total-pocsag", 24, 0, 12, 8),
            ("lens-total-repeater", 36, 0, 12, 8)
        ]
    )

    print()
    print("="*70)
    print("✅ Simple dashboards created!")
    print("="*70)
    print(f"\n🌐 Access at: {KIBANA_URL}/app/dashboards")
    print("\nLook for: 'Radio Monitoring - Simple Overview'\n")


if __name__ == '__main__':
    main()
