#!/usr/bin/env python3
"""
Update existing APRS index template to add missing fields
"""

import requests
import json

ELASTICSEARCH_URL = "http://localhost:9200"

def update_aprs_template():
    """Update APRS template with additional fields"""

    # Get existing template
    response = requests.get(f"{ELASTICSEARCH_URL}/_index_template/radio-aprs")
    existing = response.json()['index_templates'][0]['index_template']

    # Add new fields to existing mappings
    existing['template']['mappings']['properties'].update({
        "source": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword"}}
        },
        "destination": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword"}}
        },
        "path": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword"}}
        },
        "message": {
            "type": "text"
        },
        "symbol": {
            "type": "keyword"
        },
        "speed": {
            "type": "float"
        },
        "course": {
            "type": "float"
        },
        "maidenhead": {
            "type": "keyword"
        },
        "location": {
            "type": "geo_point"
        }
    })

    # Update template
    response = requests.put(
        f"{ELASTICSEARCH_URL}/_index_template/radio-aprs",
        headers={'Content-Type': 'application/json'},
        json=existing
    )

    if response.status_code in [200, 201]:
        print("✅ Updated APRS index template with geo fields")
        print("   Added fields: source, destination, path, message, symbol, speed, course, maidenhead, location")
        return True
    else:
        print(f"❌ Failed to update template: {response.status_code}")
        print(response.text)
        return False


if __name__ == '__main__':
    print("Updating APRS index template...")
    update_aprs_template()
    print()
    print("📝 Note: Existing template already has 'position' (geo_point) field")
    print("📝 Added 'location' as alternative geo_point field for compatibility")
