# Monitoring Setup

## Overview

This monitoring stack provides comprehensive observability for the Radio Transcription System using the **ELK Stack** (Elasticsearch, Logstash, Kibana) with Metricbeat for system metrics.

## Components

- **Elasticsearch** (Port 9200): Time-series data storage and search engine
- **Logstash** (Ports 9600-9604): Data ingestion pipelines (5 dedicated pipelines)
- **Kibana** (Port 5601): Visualization, dashboards, and data exploration
- **Metricbeat** (Internal): Container and system metrics collection

## Access

- **Kibana**: http://localhost:5601
  - Username: `elastic`
  - Password: See `.env.elk` file (`ELASTIC_PASSWORD`)

- **Elasticsearch API**: http://localhost:9200
  - Username: `elastic`
  - Password: See `.env.elk` file

## Data Indices

### Radio Captures
- **Index Pattern**: `radio-captures-*` (daily rollover: `radio-captures-2025.01.02`)
- **Contents**: Voice transcriptions with frequency, modulation, SDR type, language detection
- **Features**: Full-text search with multi-language analyzers (English, German, French, Spanish)

### APRS Messages
- **Index Pattern**: `radio-aprs-*`
- **Contents**: APRS packet data with callsigns, positions, message types
- **Features**: Geospatial queries with geo_point mapping for station positions

### POCSAG Messages
- **Index Pattern**: `radio-pocsag-*`
- **Contents**: Pager messages with addresses, function codes, baud rates
- **Features**: Address and message type aggregations

### Repeater Activity
- **Index Pattern**: `radio-repeater-activity-*`
- **Contents**: Scan results with transmission counts, signal strength, activity percentages
- **Features**: Activity trends by band/canton, signal quality metrics

### System Metrics
- **Index Pattern**: `metricbeat-*`
- **Contents**: Container CPU, memory, disk, network metrics
- **Features**: Real-time performance monitoring (replaces Prometheus + cAdvisor)

## Logstash Pipelines

Five dedicated ingestion pipelines:

1. **Port 9600**: Radio captures (voice transcriptions)
2. **Port 9601**: APRS messages
3. **Port 9602**: POCSAG messages
4. **Port 9603**: Repeater activity
5. **Port 9604**: Custom metrics (future use)

## Kibana Dashboards

Pre-configured dashboards available in Kibana:

- **Captures Dashboard**: Browse and search all radio captures with full-text search
- **APRS Dashboard**: Geospatial map, packet statistics, callsign analytics
- **POCSAG Dashboard**: Pager address analytics, message type distribution
- **Repeater Activity Dashboard**: Most active repeaters, activity by band/canton
- **System Metrics Dashboard**: Container performance monitoring

## Data Retention

- **Index Lifecycle Management (ILM)** automatically manages data:
  - **Hot (0-7 days)**: Fast storage, searchable, writable
  - **Warm (7-30 days)**: Searchable, read-only
  - **Cold (30-90 days)**: Less frequently accessed
  - **Delete (>90 days)**: Automatic cleanup

- **Elasticsearch data** stored in Docker volume: `elasticsearch-data`

## Starting the Monitoring Stack

```bash
# Start all services including ELK stack
docker compose -f docker-compose.elk.yml up -d

# View logs
docker compose -f docker-compose.elk.yml logs -f elasticsearch logstash kibana

# Stop services
docker compose -f docker-compose.elk.yml down

# Check cluster health
curl -u elastic:YOUR_PASSWORD http://localhost:9200/_cluster/health?pretty
```

## Security

The ELK stack uses **X-Pack Security** for authentication:

- All services require authentication
- Passwords configured in `.env.elk` file
- Separate users for each service (logstash_system, kibana_system, beats_system)
- See `ELK_SECURITY.md` for setup instructions

## Custom Dashboards

Import custom dashboards:

1. Go to Kibana → Stack Management → Saved Objects
2. Click "Import"
3. Select NDJSON file from `monitoring/kibana/dashboards/`
4. Dashboards appear in Kibana → Dashboard

## Querying Data

### Elasticsearch Query Examples

```bash
# Search recent captures
curl -u elastic:PASSWORD http://localhost:9200/radio-captures-*/_search?pretty \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match_all": {}}, "size": 10}'

# Full-text search in transcriptions
curl -u elastic:PASSWORD http://localhost:9200/radio-captures-*/_search?pretty \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match": {"transcription": "emergency"}}}'

# Get APRS statistics
curl -u elastic:PASSWORD http://localhost:9200/radio-aprs-*/_search?pretty \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 0,
    "aggs": {
      "top_callsigns": {
        "terms": {"field": "source_callsign", "size": 10}
      }
    }
  }'
```

### Kibana Dev Tools

Use Kibana Dev Tools Console for interactive queries:

```json
GET radio-captures-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"range": {"@timestamp": {"gte": "now-24h"}}},
        {"term": {"modulation": "FM"}}
      ]
    }
  }
}
```

## Monitoring Best Practices

1. **Index Patterns**: Create index patterns for each data type in Kibana
2. **Time Range**: Set appropriate time ranges in dashboards (Last 24h, Last 7d)
3. **Refresh Interval**: Configure auto-refresh for real-time monitoring
4. **Disk Space**: Monitor Elasticsearch disk usage, adjust ILM policies if needed
5. **Performance**: Keep cluster health "green" or "yellow" (check `_cluster/health`)

## Troubleshooting

**Kibana shows no data?**
- Ensure captures have been made
- Check time range (set to "Last 24 hours")
- Verify index patterns exist (Kibana → Stack Management → Index Patterns)
- Create index patterns: `radio-captures-*`, `radio-aprs-*`, etc.

**Elasticsearch cluster unhealthy?**
```bash
# Check cluster status
docker compose -f docker-compose.elk.yml exec elasticsearch curl -u elastic:PASSWORD http://localhost:9200/_cluster/health?pretty

# View Elasticsearch logs
docker compose -f docker-compose.elk.yml logs elasticsearch
```

**Logstash not receiving data?**
```bash
# Test pipeline connectivity
curl -X POST http://localhost:9600 \
  -H 'Content-Type: application/json' \
  -d '{"test": "message"}'

# Check Logstash logs
docker compose -f docker-compose.elk.yml logs logstash
```

## Migration from Prometheus/Grafana

This system has migrated from Prometheus/Grafana to ELK Stack for:
- Better full-text search capabilities
- Geospatial query support (APRS positions)
- Time-series data lifecycle management
- Unified data platform for logs and metrics

For migration details, see `MIGRATION_GUIDE_PHASE2.md`.
