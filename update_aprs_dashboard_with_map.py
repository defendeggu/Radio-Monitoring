#!/usr/bin/env python3
"""
Update APRS dashboard in enhanced_dashboards.ndjson to include the map
"""

import json

def update_aprs_dashboard():
    """Add map panel to APRS dashboard"""

    # Read all lines
    with open('enhanced_dashboards.ndjson', 'r') as f:
        lines = f.readlines()

    # Find and update APRS dashboard (line 24 = index 23)
    for i, line in enumerate(lines):
        obj = json.loads(line)
        if obj.get('id') == 'aprs-dashboard-enhanced':
            # Parse current panels
            panels = json.loads(obj['attributes']['panelsJSON'])

            # Add map panel (panel 5) - large map at top
            panels.insert(0, {
                "version": "8.11.3",
                "type": "visualization",
                "gridData": {"x": 0, "y": 0, "w": 48, "h": 16, "i": "5"},
                "panelIndex": "5",
                "embeddableConfig": {},
                "panelRefName": "panel_5"
            })

            # Adjust positions of existing panels (move down)
            for panel in panels[1:]:  # Skip the newly added map panel
                panel['gridData']['y'] += 16

            # Update panelsJSON
            obj['attributes']['panelsJSON'] = json.dumps(panels)

            # Add map reference
            obj['references'].append({
                "id": "aprs-coordinate-map",
                "name": "panel_5",
                "type": "visualization"
            })

            # Update description
            obj['attributes']['description'] = "APRS monitoring with coordinate map and analytics"

            # Write back
            lines[i] = json.dumps(obj) + '\n'
            print(f"✅ Updated APRS dashboard at line {i+1}")
            break

    # Write updated file
    with open('enhanced_dashboards.ndjson', 'w') as f:
        f.writelines(lines)

    print("✅ APRS dashboard now includes coordinate map")


if __name__ == '__main__':
    update_aprs_dashboard()
