# Elasticsearch Setup & Migration Scripts

Scripts for setting up and managing Elasticsearch data and indices.

## Scripts

### Data Import
- **`import_repeaters_to_es.py`** - Import repeater data from CSV to Elasticsearch
  - Indexes repeater information into `radio-repeaters` index
  - Supports bulk indexing for performance
  - Usage: `python import_repeaters_to_es.py <csv_file>`

### APRS Geo-Mapping
- **`setup_aprs_geo_mapping.py`** - Configure Elasticsearch geo-point mapping for APRS data
  - Sets up proper geo_point field types for APRS coordinates
  - Enables geo-queries and map visualizations in Kibana
  - Run once during initial setup

## Prerequisites

- Elasticsearch running (port 9200)
- Valid credentials in `.env.elk`
- CSV data files (for import scripts)

## Related

- See `../` for other utility scripts (Kibana dashboard import, etc.)
- See `../../monitoring/elasticsearch/` for index templates and ILM policies
- See `../../STREAMING_MODE.md` for streaming decode setup

---

Last updated: 2026-01-02
