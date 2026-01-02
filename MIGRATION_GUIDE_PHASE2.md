# Phase 2 Migration Guide: PostgreSQL → Elasticsearch

## Overview

This document provides detailed guidance for migrating from PostgreSQL to Elasticsearch for the Radio Monitoring System.

## Database Service → Elasticsearch Service API Mapping

### Core Initialization
```python
# OLD (PostgreSQL)
from database_service import get_database_service
db = get_database_service()

# NEW (Elasticsearch)
from elasticsearch_service import get_elasticsearch_service
es = get_elasticsearch_service()
```

### Voice Captures

#### Save Capture
```python
# OLD
capture_id = db.save_capture(
    frequency=int(frequency),
    modulation=modulation,
    duration=duration,
    gain=gain,
    sample_rate=sample_rate,
    audio_file_path=audio_file,
    transcription_text=transcription_text,
    language=language,
    language_confidence=confidence,
    segments=segments,
    metadata=metadata
)

# NEW
capture_data = {
    'uuid': str(uuid.uuid4()),
    'created_at': datetime.utcnow().isoformat(),
    'frequency': int(frequency),
    'modulation': modulation,
    'duration_seconds': duration,
    'rf_gain': gain,
    'sample_rate': sample_rate,
    'sdr_type': 'hackrf',  # or 'rtlsdr' based on detection
    'audio_file': audio_file,
    'transcription': transcription_text,
    'detected_language': language,
    'confidence_score': confidence,
    'segments': segments,
    'metadata': metadata,
    'status': 'completed'
}
capture_uuid = es.index_capture(capture_data)
```

#### Search Captures
```python
# OLD
results = db.search_captures(
    text=query,
    frequency=frequency,
    modulation=modulation,
    language=language,
    start_date=start_date,
    end_date=end_date,
    limit=limit,
    offset=offset
)

# NEW
results = es.search_captures(
    query=query,
    frequency_min=frequency_min,
    frequency_max=frequency_max,
    modulation=modulation,
    language=language,
    hours=24,  # or calculate from start_date/end_date
    limit=limit,
    offset=offset
)
# Returns: {'hits': [...], 'total': N, 'limit': M, 'offset': O}
```

#### Get Capture by ID
```python
# OLD
capture = db.get_capture_by_id(capture_id)

# NEW
# Use search with UUID filter
results = es.search_captures(hours=24*365, limit=1)  # Wide time range
# Then filter results by UUID in application code
# OR modify elasticsearch_service.py to add get_by_uuid() method
```

#### Get Statistics
```python
# OLD
stats = db.get_statistics()

# NEW
stats = es.get_overall_stats()
# Returns: {
#   'total_captures': N,
#   'total_aprs_messages': M,
#   'total_pocsag_messages': P,
#   'total_repeater_scans': R,
#   'cluster_health': {...}
# }
```

### APRS Messages

#### Save APRS Messages
```python
# OLD
packet_ids = db.save_aprs_capture(capture_id, packets)

# NEW
for packet in packets:
    aprs_data = {
        'uuid': str(uuid.uuid4()),
        'timestamp': packet.get('timestamp'),
        'capture_id': capture_uuid,
        'source_callsign': packet['source'],
        'destination_callsign': packet.get('destination'),
        'packet_type': packet['type'],
        'latitude': packet.get('latitude'),
        'longitude': packet.get('longitude'),
        'message_text': packet.get('message'),
        'raw_packet': packet.get('raw'),
        'frequency': frequency
    }
    es.index_aprs(aprs_data)
```

#### Search APRS
```python
# OLD
results = db.search_aprs_messages(
    callsign=callsign,
    packet_type=packet_type,
    start_date=start_date,
    end_date=end_date,
    limit=limit
)

# NEW
results = es.search_aprs(
    callsign=callsign,
    packet_type=packet_type,
    hours=24,  # or calculate from dates
    limit=limit
)
# Returns: {'hits': [...], 'total': N}
```

#### APRS Statistics
```python
# OLD
stats = db.get_aprs_statistics()

# NEW
stats = es.get_aprs_stats(hours=24)
# Returns: {
#   'total_packets': N,
#   'unique_callsigns': M,
#   'top_callsigns': [{callsign, count}, ...],
#   'packet_types': [{type, count}, ...]
# }
```

### POCSAG Messages

#### Save POCSAG Messages
```python
# OLD
message_ids = db.save_pocsag_capture(capture_id, messages)

# NEW
for message in messages:
    pocsag_data = {
        'uuid': str(uuid.uuid4()),
        'timestamp': message.get('timestamp'),
        'capture_id': capture_uuid,
        'address': message['address'],
        'message_type': message['type'],
        'function_code': message.get('function'),
        'baud_rate': message['baud'],
        'message_text': message.get('message'),
        'frequency': frequency
    }
    es.index_pocsag(pocsag_data)
```

#### Search POCSAG
```python
# OLD
results = db.search_pocsag_messages(
    address=address,
    message_type=message_type,
    start_date=start_date,
    end_date=end_date,
    limit=limit
)

# NEW
results = es.search_pocsag(
    address=address,
    message_type=message_type,
    hours=24,
    limit=limit
)
```

#### POCSAG Statistics
```python
# OLD
stats = db.get_pocsag_statistics()

# NEW
stats = es.get_pocsag_stats(hours=24)
# Returns: {
#   'total_messages': N,
#   'unique_addresses': M,
#   'top_addresses': [{address, count}, ...],
#   'message_types': [{type, count}, ...],
#   'baud_rates': [{baud, count}, ...]
# }
```

### Repeater Activity

#### Save Repeater Activity
```python
# OLD
activity_id = db.save_repeater_activity(
    session_id=session_id,
    repeater_id=repeater_id,
    carrier_detected=carrier_detected,
    transmission_count=transmission_count,
    activity_percentage=activity_percentage,
    average_signal_strength=avg_signal,
    transmissions=transmissions
)

# NEW
activity_data = {
    'uuid': str(uuid.uuid4()),
    'created_at': datetime.utcnow().isoformat(),
    'session_id': session_id,
    'repeater_id': repeater['id'],
    'repeater_callsign': repeater['callsign'],
    'frequency': repeater['output_frequency'],
    'band': repeater['band'],
    'canton': repeater.get('canton'),
    'location_name': repeater.get('location_name'),
    'carrier_detected': carrier_detected,
    'transmission_count': transmission_count,
    'activity_percentage': activity_percentage,
    'average_signal_strength': avg_signal,
    'noise_floor': noise_floor,
    'scan_duration_seconds': duration,
    'transmissions': transmissions
}
es.index_repeater_activity(activity_data)
```

#### Get Repeater Activity Summary
```python
# OLD
summary = db.get_repeater_activity_summary(
    hours=24,
    band=band,
    canton=canton,
    limit=20
)

# NEW
summary = es.get_repeater_activity_summary(
    hours=24,
    band=band,
    canton=canton,
    limit=20
)
# Returns: List[{callsign, avg_activity_pct, total_transmissions, ...}]
```

## Prometheus Metrics → Metricbeat

### OLD: Prometheus Counters/Histograms
```python
from prometheus_client import Counter, Histogram, Gauge

radio_captures_total = Counter('radio_captures_total', ...)
radio_captures_total.labels(modulation='FM', status='success').inc()
```

### NEW: Removed - Metricbeat Tracks System Metrics
Metricbeat automatically tracks:
- Container CPU, memory, disk, network
- Process-level metrics
- System-level metrics

Application metrics can be tracked by:
1. Indexing events to Elasticsearch with metric fields
2. Using Kibana visualizations on indexed data
3. Creating custom dashboards in Kibana

## Key Differences

### 1. No Integer IDs
- **PostgreSQL**: Auto-increment integer IDs
- **Elasticsearch**: UUID strings for document IDs

### 2. No Transactions
- **PostgreSQL**: ACID transactions
- **Elasticsearch**: Eventually consistent, no multi-document transactions
- **Mitigation**: Use idempotent operations, handle failures gracefully

### 3. Time-Based Indexing
- **PostgreSQL**: Single table for all time ranges
- **Elasticsearch**: Daily indices (e.g., `radio-captures-2025.01.15`)
- **Benefit**: Automatic lifecycle management, faster queries on recent data

### 4. Full-Text Search
- **PostgreSQL**: Basic LIKE/ILIKE or ts_vector
- **Elasticsearch**: Advanced full-text search with analyzers, stemming, multi-language support
- **Benefit**: Much better search quality and performance

### 5. Aggregations
- **PostgreSQL**: GROUP BY with aggregate functions
- **Elasticsearch**: Powerful aggregation framework with buckets, metrics, pipelines
- **Benefit**: Complex analytics without complex SQL

## Testing Strategy

1. **Unit Tests**: Update test mocks to use Elasticsearch service
2. **Integration Tests**:
   - Start ELK stack with `docker compose -f docker-compose.elk.yml up -d`
   - Run full capture → index → search workflow
3. **Performance Tests**:
   - Index 10,000 documents
   - Run concurrent searches
   - Verify <100ms p95 latency
4. **Data Migration**:
   - Export PostgreSQL data
   - Transform to Elasticsearch format
   - Bulk index with helpers.bulk()
   - Verify document counts match

## Rollback Plan

If ELK migration fails:
1. Stop ELK containers: `docker compose -f docker-compose.elk.yml down`
2. Restore original docker-compose.yml
3. Start PostgreSQL/Prometheus/Grafana: `docker compose up -d`
4. Restore PostgreSQL from backup
5. Revert code changes (git revert)

## Implementation Checklist

- [ ] Update all `db.save_capture()` calls to `es.index_capture()`
- [ ] Update all `db.search_*()` calls to `es.search_*()`
- [ ] Update all `db.get_*_statistics()` calls to `es.get_*_stats()`
- [ ] Remove Prometheus metric increment calls
- [ ] Add UUID generation for all indexed documents
- [ ] Handle Elasticsearch connection errors gracefully
- [ ] Update response formats to match new data structures
- [ ] Test each endpoint individually
- [ ] Run full integration test suite
- [ ] Update API documentation

## Next Steps

1. Create data migration script (`scripts/migrate_pg_to_es.py`)
2. Complete api_service.py updates systematically
3. Update web_interface.html if response formats changed
4. Test thoroughly before production deployment
