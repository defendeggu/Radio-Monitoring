# Kibana Dashboards

This directory contains pre-configured Kibana dashboards for the Radio Monitoring System.

## Dashboard Files

- **index-patterns.ndjson** - Index patterns for all radio data types
- **aprs-dashboard.ndjson** - APRS Activity Monitoring Dashboard
- **repeater-activity-dashboard.ndjson** - Repeater Activity Dashboard
- **pocsag-dashboard.ndjson** - POCSAG Pager Monitoring Dashboard
- **radio-overview-dashboard.ndjson** - Radio System Overview Dashboard

## Import Methods

### Method 1: Automatic Import (Recommended)

Run the import script from the project root:

```bash
# From inside the radio-api container
docker exec radio-transcription-api python /app/scripts/import_kibana_dashboards.py

# Or from host (if you have Python + requests)
python scripts/import_kibana_dashboards.py
```

### Method 2: Manual Import via Kibana UI

1. Open Kibana: http://localhost:5601
2. Navigate to **Stack Management** → **Saved Objects**
3. Click **Import**
4. Select each `.ndjson` file and import:
   - First: `index-patterns.ndjson`
   - Then: All dashboard files
5. Click **Import** and confirm

### Method 3: Command Line Import

```bash
# Import index patterns first
curl -X POST "http://localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  --form file=@monitoring/kibana/dashboards/index-patterns.ndjson

# Import APRS dashboard
curl -X POST "http://localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  --form file=@monitoring/kibana/dashboards/aprs-dashboard.ndjson

# Import Repeater Activity dashboard
curl -X POST "http://localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  --form file=@monitoring/kibana/dashboards/repeater-activity-dashboard.ndjson

# Import POCSAG dashboard
curl -X POST "http://localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  --form file=@monitoring/kibana/dashboards/pocsag-dashboard.ndjson

# Import Radio Overview dashboard
curl -X POST "http://localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  --form file=@monitoring/kibana/dashboards/radio-overview-dashboard.ndjson
```

## Dashboard Descriptions

### APRS Activity Dashboard
- **Total APRS Packets**: Count of all received packets
- **Unique Callsigns**: Number of distinct stations
- **Packets with Position**: Geo-located packets count
- **APRS Timeline**: Packet activity over time
- **Message Types**: Distribution of packet types (Position, Weather, Message, etc.)
- **Top 15 Callsigns**: Most active stations
- **APRS Stations Map**: Geographic visualization of stations

### Repeater Activity Dashboard
- **Most Active Repeaters**: Table showing repeaters with highest activity percentage
- **Activity by Band**: Distribution between 2m and 70cm bands
- **Scan Rate**: Number of scans over time
- **Recent Scans**: Latest 100 repeater scan results

### POCSAG Monitoring Dashboard
- **Total Messages**: Count of all POCSAG messages
- **Unique Addresses**: Number of distinct pager addresses
- **Top 15 Addresses**: Most active pager addresses
- **Message Types**: Distribution (Alphanumeric, Numeric, Tone)
- **Baud Rates**: Distribution of 512, 1200, 2400 baud
- **Timeline**: Message activity over time

### Radio Monitoring Overview
- **Total Captures**: Count of all radio captures
- **Total Transcriptions**: Count of successful transcriptions
- **Captures Timeline**: Capture activity over time
- **Captures by Modulation**: Distribution (FM, AM, USB, LSB)
- **Language Distribution**: Detected languages
- **Top Frequencies**: Most monitored frequencies

## Access Dashboards

After import, access dashboards at:
- http://localhost:5601/app/dashboards

Or use the Dashboard menu in Kibana's left sidebar.

## Troubleshooting

**Index patterns not found:**
- Make sure you've run some captures first to create the indices
- Check that Elasticsearch has data: `curl http://localhost:9200/radio-*/_count`

**Visualizations show "No results":**
- Adjust the time range (top right corner in Kibana)
- Ensure the selected time range includes your data
- Check index pattern matches your indices

**Import fails:**
- Ensure Kibana is running: `docker ps | grep kibana`
- Check Kibana logs: `docker logs radio-kibana`
- Try manual import via UI instead

## Export Dashboards

To export modified dashboards:

1. Go to **Stack Management** → **Saved Objects**
2. Select dashboards to export
3. Click **Export** → **Export as NDJSON**
4. Save to this directory
