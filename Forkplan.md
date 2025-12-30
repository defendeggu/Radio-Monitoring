# Radio Monitoring System Fork - RTL-SDR + ELK Stack Migration

## Fork Overview

**Goal**: Create a modernized fork of the Radio Monitoring System with:
1. **Dual SDR Support**: HackRF One + RTL-SDR with automatic hardware detection
2. **ELK Stack Migration**: Replace PostgreSQL + Prometheus + Grafana with Elasticsearch + Logstash + Kibana

**Implementation Strategy**: Phased approach
- **Phase 1**: RTL-SDR Integration (maintain existing PostgreSQL/Prometheus/Grafana)
- **Phase 2**: ELK Stack Migration (complete data layer replacement)

**User Goals**:
- Better log aggregation and real-time analysis capabilities
- Learning/experimenting with ELK Stack ecosystem
- Scalability for higher data volumes
- Broader hardware compatibility (RTL-SDR is cheaper, more accessible)

---

## Phase 1: RTL-SDR Integration

### 1.1 Hardware Comparison

| Feature | HackRF One | RTL-SDR |
|---------|------------|---------|
| **Frequency Range** | 1 MHz - 6 GHz | 24 MHz - 1766 MHz |
| **TX Capability** | Yes | No (RX only) |
| **Max Sample Rate** | 20 MHz | 3.2 MHz |
| **IQ Format** | Signed int8 | Unsigned uint8 |
| **Normalization** | / 127.0 | - 127.5, then / 127.5 |
| **CLI Tool** | hackrf_transfer | rtl_sdr |
| **Price** | ~$300 | ~$25 |

**Key Implementation Differences**:
- **IQ Conversion**: RTL-SDR uses uint8 (0-255), must center around 127.5 before normalization
- **Command Syntax**: Different parameter names (`rtl_sdr -f freq -s rate -g gain` vs `hackrf_transfer -r out -f freq -s rate -l gain`)
- **Frequency Limits**: RTL-SDR cannot cover full range (no HF below 24 MHz, no microwave above 1.766 GHz)

### 1.2 Architecture Design: Hardware Abstraction Layer

**New File**: `/home/spia/my-project/sdr_hardware.py`

**Core Classes**:

```python
class SDRType(Enum):
    HACKRF = "hackrf"
    RTLSDR = "rtlsdr"
    UNKNOWN = "unknown"

class SDRCapture(ABC):
    """Abstract base class for SDR hardware."""

    @abstractmethod
    def is_available(self) -> bool

    @abstractmethod
    def capture_iq(self, duration: int, output_file: str) -> None

    @abstractmethod
    def capture_audio(self, duration: int, output_file: str, modulation: str) -> None

    @abstractmethod
    def get_frequency_range(self) -> Tuple[int, int]

    @abstractmethod
    def get_max_sample_rate(self) -> int

class HackRFCapture(SDRCapture):
    """Existing radio_capture.py logic, refactored."""

    def is_available(self) -> bool:
        # Check: hackrf_info returns success and "Serial number" in output

    def capture_iq(self, duration: int, output_file: str) -> None:
        # Existing logic from radio_capture.py lines 106-172
        # hackrf_transfer → int8 IQ → complex64 normalized by /127.0

    def capture_audio(self, duration: int, output_file: str, modulation: str) -> None:
        # Existing logic from radio_capture.py
        # FM/AM/SSB demodulation

class RTLSDRCapture(SDRCapture):
    """NEW implementation for RTL-SDR."""

    def is_available(self) -> bool:
        # Check: rtl_test -t returns success or "Found" in output

    def capture_iq(self, duration: int, output_file: str) -> None:
        # Run: rtl_sdr -f freq -s rate -g gain -n bytes output.raw
        # Convert: uint8 → (sample - 127.5) / 127.5 → complex64

    def capture_audio(self, duration: int, output_file: str, modulation: str) -> None:
        # For FM: Use rtl_fm tool (direct demodulation)
        # For AM/SSB: Capture IQ, then manual demodulation

def detect_sdr() -> SDRType:
    """Auto-detect available SDR hardware (prefer HackRF if both present)."""

def get_sdr_instance(frequency: int, sample_rate: int, gain: int,
                     sdr_type: Optional[SDRType] = None) -> SDRCapture:
    """Factory function with frequency range validation."""
```

**Why This Design**:
- Single interface for all SDR hardware (easy to add BladeRF, LimeSDR, etc. later)
- Frequency range validation at runtime (prevent invalid captures)
- Auto-detection with preference for HackRF (better specs if both connected)
- No breaking changes to API or Web UI (transparent hardware swapping)

### 1.3 Integration Changes

**File 1**: `/home/spia/my-project/api_service.py`
- Replace `from radio_capture import HackRFCapture` with `from sdr_hardware import get_sdr_instance, detect_sdr`
- Update all endpoints that create capture instances:
  ```python
  # OLD:
  capture = HackRFCapture(frequency=freq, sample_rate=rate, gain=gain)

  # NEW:
  capture = get_sdr_instance(frequency=freq, sample_rate=rate, gain=gain)
  ```
- Add new endpoint `GET /sdr/detect`:
  ```python
  @app.route('/sdr/detect', methods=['GET'])
  def detect_hardware():
      sdr_type = detect_sdr()
      if sdr_type == SDRType.UNKNOWN:
          return jsonify({'error': 'No SDR detected'}), 404

      instance = get_sdr_instance(frequency=100_000_000, sdr_type=sdr_type)
      min_freq, max_freq = instance.get_frequency_range()

      return jsonify({
          'type': sdr_type.value,
          'frequency_range': {
              'min_hz': min_freq,
              'max_hz': max_freq,
              'min_mhz': min_freq / 1e6,
              'max_mhz': max_freq / 1e6
          },
          'max_sample_rate': instance.get_max_sample_rate()
      })
  ```

**File 2**: `/home/spia/my-project/web_interface.html`
- Add SDR detection on page load:
  ```javascript
  async function detectSDR() {
      const response = await fetch('http://localhost:5000/sdr/detect');
      const data = await response.json();

      // Display in header
      document.getElementById('sdr-indicator').textContent =
          `SDR: ${data.type.toUpperCase()} (${data.frequency_range.min_mhz}-${data.frequency_range.max_mhz} MHz)`;

      // Store for frequency validation
      window.sdrFrequencyRange = data.frequency_range;
  }

  function validateFrequency(frequency) {
      if (!window.sdrFrequencyRange) return true;

      const min = window.sdrFrequencyRange.min_hz;
      const max = window.sdrFrequencyRange.max_hz;

      if (frequency < min || frequency > max) {
          alert(`Frequency ${frequency/1e6} MHz out of range for ${window.sdrType}.\nValid: ${min/1e6}-${max/1e6} MHz`);
          return false;
      }
      return true;
  }
  ```
- Add visual indicator in page header (e.g., "SDR: HACKRF (1-6000 MHz)" or "SDR: RTLSDR (24-1766 MHz)")

**File 3**: `/home/spia/my-project/Dockerfile`
- Add RTL-SDR packages:
  ```dockerfile
  RUN apt-get update && apt-get install -y \
      hackrf \
      libhackrf-dev \
      rtl-sdr \
      librtlsdr-dev \
      rtl-433 \
      && rm -rf /var/lib/apt/lists/*
  ```

**File 4**: `/home/spia/my-project/docker-compose.yml`
- No changes needed (USB passthrough `/dev/bus/usb` works for both)

**File 5**: `/home/spia/my-project/radio_capture.py`
- **Delete this file** (functionality moved to sdr_hardware.py)

**File 6**: `/home/spia/my-project/README.md`
- Update "Hardware Requirements" section to list both HackRF and RTL-SDR
- Add frequency coverage comparison table
- Add auto-detection documentation

### 1.4 Testing Strategy

**Unit Tests** (`tests/test_sdr_hardware.py`):
- Test `detect_sdr()` with mocked subprocess calls
- Test IQ conversion: uint8 → complex64 for RTL-SDR
- Test frequency range validation (reject 10 MHz for RTL-SDR)
- Test sample rate clamping (RTL-SDR max 3.2 MHz)

**Integration Tests**:
1. **HackRF only**: Full workflow (capture → transcribe)
2. **RTL-SDR only**: Full workflow (capture → transcribe)
3. **Both connected**: Verify HackRF is selected
4. **Neither connected**: Verify graceful error
5. **Edge cases**:
   - Frequency 20 MHz with RTL-SDR (below min) → error
   - Frequency 2 GHz with RTL-SDR (above max) → error
   - Frequency 5 GHz with HackRF → success

**Validation**:
- Capture same frequency with both SDRs, compare audio quality
- Verify APRS/POCSAG decoding works with RTL-SDR
- Verify repeater scanning works with RTL-SDR

### 1.5 Phase 1 Deliverables

✅ **New Files**:
- `sdr_hardware.py` (~450 lines)
- `tests/test_sdr_hardware.py` (~200 lines)

✅ **Modified Files**:
- `api_service.py` - Use abstraction layer, add /sdr/detect endpoint
- `web_interface.html` - SDR detection UI
- `Dockerfile` - Add RTL-SDR packages
- `README.md` - Document dual SDR support

✅ **Deleted Files**:
- `radio_capture.py` - Replaced by sdr_hardware.py

✅ **Success Criteria**:
- Auto-detection works
- Frequency validation prevents invalid captures
- All 4 processing modes work with RTL-SDR
- No performance regression
- Test coverage >85%

---

## Phase 2: ELK Stack Migration

### 2.1 Current vs Target Architecture

**Current Stack**:
- **PostgreSQL**: 9 tables (captures, aprs_messages, pocsag_messages, repeaters, repeater_activity, repeater_scan_sessions, etc.)
- **Prometheus**: 15+ metrics (counters, histograms, gauges) scraped every 15s
- **Grafana**: 8 dashboards querying both PostgreSQL and Prometheus
- **cAdvisor**: Container metrics → Prometheus

**Target Stack**:
- **Elasticsearch**: All data as documents in time-series indices (`radio-captures-2025.01.15`, `radio-aprs-2025.01.15`, etc.)
- **Logstash**: Data ingestion pipelines (HTTP input, parsing, enrichment, indexing)
- **Kibana**: Visualization and dashboards
- **Metricbeat**: System/container metrics → Elasticsearch (replaces cAdvisor + Prometheus)

**Migration Strategy**:
- PostgreSQL tables → Elasticsearch indices (one index pattern per data type)
- Prometheus metrics → Elasticsearch documents with @timestamp
- Grafana dashboards → Kibana dashboards (recreate with Kibana visualizations)
- Direct DB writes → HTTP POST to Logstash pipelines

### 2.2 Elasticsearch Index Design

**Index Naming**: `radio-{type}-{YYYY.MM.DD}` (daily rollover)

**Index 1: radio-captures-***
```json
{
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "uuid": {"type": "keyword"},
      "frequency": {"type": "long"},
      "frequency_mhz": {"type": "float"},
      "duration_seconds": {"type": "integer"},
      "modulation": {"type": "keyword"},
      "sample_rate": {"type": "integer"},
      "rf_gain": {"type": "integer"},
      "sdr_type": {"type": "keyword"},

      "transcription": {
        "type": "text",
        "fields": {
          "keyword": {"type": "keyword"},
          "english": {"type": "text", "analyzer": "english"},
          "german": {"type": "text", "analyzer": "german"}
        }
      },

      "detected_language": {"type": "keyword"},
      "confidence_score": {"type": "float"},
      "audio_file": {"type": "keyword"},
      "metadata": {"type": "object", "enabled": false}
    }
  },
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.lifecycle.name": "radio-ilm-policy"
  }
}
```

**ILM Policy** (Index Lifecycle Management):
- Hot (0-7 days): Searchable, writable, fast storage
- Warm (7-30 days): Searchable, read-only
- Cold (30-90 days): Less frequently accessed
- Delete (>90 days): Automatic cleanup

**Index 2: radio-aprs-***
```json
{
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "uuid": {"type": "keyword"},
      "capture_id": {"type": "keyword"},
      "source_callsign": {"type": "keyword"},
      "destination_callsign": {"type": "keyword"},
      "packet_type": {"type": "keyword"},

      "position": {"type": "geo_point"},
      "latitude": {"type": "float"},
      "longitude": {"type": "float"},

      "message_text": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
      },

      "raw_packet": {"type": "text"}
    }
  }
}
```

**Index 3: radio-pocsag-***
```json
{
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "address": {"type": "long"},
      "message_type": {"type": "keyword"},
      "baud_rate": {"type": "integer"},
      "message_text": {"type": "text"}
    }
  }
}
```

**Index 4: radio-repeater-activity-***
```json
{
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "repeater_id": {"type": "keyword"},
      "repeater_callsign": {"type": "keyword"},
      "frequency_mhz": {"type": "float"},
      "band": {"type": "keyword"},
      "carrier_detected": {"type": "boolean"},
      "transmission_count": {"type": "integer"},
      "activity_percentage": {"type": "float"},
      "average_signal_strength": {"type": "float"},
      "noise_floor": {"type": "float"},

      "transmissions": {
        "type": "nested",
        "properties": {
          "start_offset": {"type": "float"},
          "duration": {"type": "float"},
          "avg_strength": {"type": "float"}
        }
      }
    }
  }
}
```

**Index 5: radio-metrics-*** (replaces Prometheus)
```json
{
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "metric_name": {"type": "keyword"},
      "metric_type": {"type": "keyword"},
      "value": {"type": "double"},

      "labels": {
        "properties": {
          "status": {"type": "keyword"},
          "modulation": {"type": "keyword"},
          "band": {"type": "keyword"},
          "sdr_type": {"type": "keyword"}
        }
      }
    }
  }
}
```

### 2.3 Logstash Pipeline Configuration

**Pipeline 1**: `radio-capture-pipeline.conf`
```ruby
input {
  http {
    port => 9600
    type => "radio_capture"
    codec => json
  }
}

filter {
  # Add @timestamp
  mutate {
    add_field => { "[@timestamp]" => "%{created_at}" }
  }

  # Calculate frequency_mhz
  ruby {
    code => "event.set('frequency_mhz', event.get('frequency') / 1_000_000.0)"
  }

  # Add index name
  mutate {
    add_field => { "[@metadata][index]" => "radio-captures-%{+YYYY.MM.dd}" }
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "%{[@metadata][index]}"
    document_id => "%{uuid}"
  }
}
```

**Pipeline 2**: `radio-aprs-pipeline.conf`
```ruby
input {
  http {
    port => 9601
    type => "aprs_message"
    codec => json
  }
}

filter {
  # Geolocation
  if [latitude] and [longitude] {
    mutate {
      add_field => {
        "[position][lat]" => "%{latitude}"
        "[position][lon]" => "%{longitude}"
      }
    }
  }

  mutate {
    add_field => { "[@metadata][index]" => "radio-aprs-%{+YYYY.MM.dd}" }
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "%{[@metadata][index]}"
    document_id => "%{uuid}"
  }
}
```

**Pipeline 3**: `radio-metrics-pipeline.conf`
```ruby
input {
  http_poller {
    urls => {
      metrics => "http://radio-api:5000/metrics"
    }
    request_timeout => 60
    schedule => { every => "15s" }
    codec => "plain"
  }
}

filter {
  # Parse Prometheus format
  grok {
    match => {
      "message" => "%{NOTSPACE:metric_name}(\{%{DATA:labels}\})?\s+%{NUMBER:value:float}"
    }
  }

  # Parse labels (key1="val1",key2="val2")
  if [labels] {
    kv {
      source => "labels"
      field_split => ","
      value_split => "="
      target => "labels"
    }
  }

  # Metric type detection
  if [metric_name] =~ /_total$/ {
    mutate { add_field => { "metric_type" => "counter" } }
  } else if [metric_name] =~ /_bucket$/ {
    mutate { add_field => { "metric_type" => "histogram" } }
  } else {
    mutate { add_field => { "metric_type" => "gauge" } }
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "radio-metrics-%{+YYYY.MM.dd}"
  }
}
```

### 2.4 API Service Changes

**New File**: `/home/spia/my-project/elasticsearch_service.py`

```python
from elasticsearch import Elasticsearch
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests

class ElasticsearchService:
    def __init__(self, hosts: List[str] = None, logstash_host: str = None):
        self.es_client = Elasticsearch(hosts or ['http://elasticsearch:9200'])
        self.logstash_host = logstash_host or 'http://logstash:9600'

    def index_capture(self, capture: Dict[str, Any]) -> str:
        """Index capture via Logstash pipeline."""
        response = requests.post(self.logstash_host, json=capture)
        return capture['uuid']

    def search_captures(self, query: str = None, frequency_min: int = None,
                       frequency_max: int = None, hours: int = 24,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """Search captures with full-text and filters."""

        must_clauses = [
            {'range': {'@timestamp': {'gte': f'now-{hours}h', 'lte': 'now'}}}
        ]

        if query:
            must_clauses.append({
                'multi_match': {
                    'query': query,
                    'fields': ['transcription', 'transcription.english', 'transcription.german']
                }
            })

        if frequency_min or frequency_max:
            range_clause = {}
            if frequency_min: range_clause['gte'] = frequency_min
            if frequency_max: range_clause['lte'] = frequency_max
            must_clauses.append({'range': {'frequency': range_clause}})

        body = {
            'query': {'bool': {'must': must_clauses}},
            'sort': [{'@timestamp': 'desc'}],
            'size': limit
        }

        result = self.es_client.search(index='radio-captures-*', body=body)
        return [hit['_source'] for hit in result['hits']['hits']]

    def get_repeater_activity_summary(self, hours: int = 24, limit: int = 10):
        """Get most active repeaters via aggregation."""

        body = {
            'query': {
                'bool': {
                    'must': [
                        {'range': {'@timestamp': {'gte': f'now-{hours}h'}}},
                        {'term': {'carrier_detected': True}}
                    ]
                }
            },
            'aggs': {
                'by_repeater': {
                    'terms': {
                        'field': 'repeater_callsign',
                        'size': limit,
                        'order': {'avg_activity': 'desc'}
                    },
                    'aggs': {
                        'avg_activity': {'avg': {'field': 'activity_percentage'}},
                        'total_transmissions': {'sum': {'field': 'transmission_count'}}
                    }
                }
            },
            'size': 0
        }

        result = self.es_client.search(index='radio-repeater-activity-*', body=body)

        repeaters = []
        for bucket in result['aggregations']['by_repeater']['buckets']:
            repeaters.append({
                'callsign': bucket['key'],
                'avg_activity_pct': bucket['avg_activity']['value'],
                'total_transmissions': int(bucket['total_transmissions']['value'])
            })

        return repeaters
```

**Modified File**: `/home/spia/my-project/api_service.py`

```python
# Replace imports
# from database_service import DatabaseService
from elasticsearch_service import ElasticsearchService

# Initialize
# db = DatabaseService()
es = ElasticsearchService(
    hosts=['http://elasticsearch:9200'],
    logstash_host='http://logstash:9600'
)

# Update endpoints
@app.route('/capture', methods=['POST'])
def capture_and_transcribe():
    # ... existing capture logic ...

    # OLD: db.save_capture(capture_data)
    # NEW:
    es.index_capture(capture_data)

    return jsonify(result)

@app.route('/search', methods=['GET'])
def search_captures():
    query = request.args.get('q')
    freq_min = request.args.get('freq_min', type=int)
    freq_max = request.args.get('freq_max', type=int)

    results = es.search_captures(
        query=query,
        frequency_min=freq_min,
        frequency_max=freq_max,
        hours=24
    )

    return jsonify({'results': results})
```

### 2.5 Kibana Dashboard Migration

**Strategy**: Recreate each Grafana dashboard in Kibana

**Dashboard 1**: APRS Activity Dashboard
- Panel 1: Total APRS Messages (Metric visualization)
- Panel 2: Top 15 Callsigns (Horizontal Bar)
- Panel 3: APRS Stations Map (Maps with geo_point)
- Panel 4: Messages Over Time (Line chart with date histogram)

**Dashboard 2**: Repeater Activity Dashboard
- Panel 1: Most Active Repeaters (Data Table)
- Panel 2: Activity by Band (Pie Chart)
- Panel 3: Scan Rate (Line chart)
- Panel 4: Recent Scans (Data Table)

**Example Kibana Query** (equivalent to Grafana PostgreSQL query):
```json
{
  "query": {
    "bool": {
      "must": [
        {"range": {"@timestamp": {"gte": "now-24h"}}}
      ]
    }
  },
  "aggs": {
    "by_callsign": {
      "terms": {
        "field": "repeater_callsign",
        "size": 20,
        "order": {"avg_activity": "desc"}
      },
      "aggs": {
        "avg_activity": {"avg": {"field": "activity_percentage"}},
        "total_transmissions": {"sum": {"field": "transmission_count"}}
      }
    }
  }
}
```

### 2.6 Docker Compose Changes

**New File**: `docker-compose.elk.yml` (replaces docker-compose.yml)

```yaml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: radio-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks:
      - radio-network
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    container_name: radio-logstash
    volumes:
      - ./monitoring/logstash/pipelines:/usr/share/logstash/pipeline
      - ./monitoring/logstash/config/logstash.yml:/usr/share/logstash/config/logstash.yml
    ports:
      - "9600:9600"
      - "9601:9601"
      - "9602:9602"
    networks:
      - radio-network
    depends_on:
      elasticsearch:
        condition: service_healthy

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: radio-kibana
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    volumes:
      - ./monitoring/kibana/config/kibana.yml:/usr/share/kibana/config/kibana.yml
    ports:
      - "5601:5601"
    networks:
      - radio-network
    depends_on:
      elasticsearch:
        condition: service_healthy

  metricbeat:
    image: docker.elastic.co/beats/metricbeat:8.11.0
    container_name: radio-metricbeat
    user: root
    volumes:
      - ./monitoring/metricbeat/metricbeat.yml:/usr/share/metricbeat/metricbeat.yml:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /sys/fs/cgroup:/hostfs/sys/fs/cgroup:ro
      - /proc:/hostfs/proc:ro
    command: ["--strict.perms=false", "-system.hostfs=/hostfs"]
    networks:
      - radio-network
    depends_on:
      elasticsearch:
        condition: service_healthy

  radio-api:
    build: .
    container_name: radio-transcription-api
    privileged: true
    volumes:
      - /dev/bus/usb:/dev/bus/usb
      - ./captures:/app/captures
    ports:
      - "5000:5000"
    networks:
      - radio-network
    depends_on:
      elasticsearch:
        condition: service_healthy
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - LOGSTASH_HOST=http://logstash:9600

  web-interface:
    image: nginx:alpine
    container_name: radio-web-interface
    volumes:
      - ./web_interface.html:/usr/share/nginx/html/index.html:ro
    ports:
      - "8080:80"
    networks:
      - radio-network

volumes:
  elasticsearch-data:

networks:
  radio-network:
    driver: bridge
```

**Services Removed**:
- ❌ postgres
- ❌ pgadmin
- ❌ prometheus
- ❌ grafana
- ❌ cadvisor
- ❌ n8n (no longer used)

**Services Added**:
- ✅ elasticsearch
- ✅ logstash
- ✅ kibana
- ✅ metricbeat

### 2.7 Data Migration Script

**New File**: `scripts/migrate_to_elasticsearch.py`

```python
import psycopg2
from elasticsearch import Elasticsearch, helpers
from datetime import datetime

def migrate_captures(pg_conn, es_client):
    cursor = pg_conn.cursor()
    cursor.execute("""
        SELECT id, uuid, created_at, frequency, duration_seconds,
               modulation, sample_rate, rf_gain, transcription_text,
               detected_language, confidence_score
        FROM captures
        ORDER BY created_at
    """)

    docs = []
    for row in cursor.fetchall():
        created_at = row[2]
        index = f"radio-captures-{created_at:%Y.%m.%d}"

        doc = {
            '_index': index,
            '_id': row[1],  # uuid
            '@timestamp': created_at.isoformat(),
            'frequency': row[3],
            'frequency_mhz': row[3] / 1_000_000.0,
            'duration_seconds': row[4],
            'modulation': row[5],
            'transcription': row[8],
            'detected_language': row[9]
        }
        docs.append(doc)

        if len(docs) >= 500:
            helpers.bulk(es_client, docs)
            docs = []

    if docs:
        helpers.bulk(es_client, docs)

# Similar for APRS, POCSAG, repeaters, etc.
```

### 2.8 Phase 2 Deliverables

✅ **New Files**:
- `elasticsearch_service.py` - ES client wrapper
- `monitoring/logstash/pipelines/*.conf` - Pipeline configs (5 files)
- `monitoring/logstash/config/logstash.yml`
- `monitoring/kibana/config/kibana.yml`
- `monitoring/kibana/dashboards/*.json` - Dashboard definitions (8 files)
- `monitoring/metricbeat/metricbeat.yml`
- `scripts/migrate_to_elasticsearch.py`
- `scripts/create_index_templates.sh`
- `docker-compose.elk.yml`

✅ **Modified Files**:
- `api_service.py` - Use ElasticsearchService
- `requirements.txt` - Add elasticsearch==8.11.0
- `Dockerfile` - Remove PostgreSQL client
- `README.md` - Update architecture
- `USER_MANUAL.md` - Kibana instead of Grafana

✅ **Deleted Files**:
- `database_service.py`
- `database/init.sql`
- `monitoring/prometheus/prometheus.yml`
- `monitoring/grafana/provisioning/**/*` (all files)
- `monitoring/grafana/dashboards/*.json` (8 files)
- `docker-compose.yml` (replaced by docker-compose.elk.yml)

✅ **Success Criteria**:
- All data migrated (100% accuracy)
- Full-text search working
- Geospatial queries working (APRS map)
- Dashboards functional
- Indexing throughput >1000 docs/sec
- Search latency <100ms
- ILM policies active (auto-delete >90 days)

---

## Critical Files

### Phase 1: RTL-SDR Integration

**New (2)**:
1. `/home/spia/my-project/sdr_hardware.py` - Hardware abstraction
2. `/home/spia/my-project/tests/test_sdr_hardware.py` - Tests

**Modified (4)**:
1. `/home/spia/my-project/api_service.py` - Use abstraction
2. `/home/spia/my-project/web_interface.html` - SDR detection UI
3. `/home/spia/my-project/Dockerfile` - RTL-SDR packages
4. `/home/spia/my-project/README.md` - Docs

**Deleted (1)**:
1. `/home/spia/my-project/radio_capture.py` - Replaced

### Phase 2: ELK Stack Migration

**New (15)**:
1. `/home/spia/my-project/elasticsearch_service.py`
2. `/home/spia/my-project/monitoring/logstash/pipelines/radio-capture-pipeline.conf`
3. `/home/spia/my-project/monitoring/logstash/pipelines/radio-aprs-pipeline.conf`
4. `/home/spia/my-project/monitoring/logstash/pipelines/radio-pocsag-pipeline.conf`
5. `/home/spia/my-project/monitoring/logstash/pipelines/radio-repeater-pipeline.conf`
6. `/home/spia/my-project/monitoring/logstash/pipelines/radio-metrics-pipeline.conf`
7. `/home/spia/my-project/monitoring/logstash/config/logstash.yml`
8. `/home/spia/my-project/monitoring/kibana/config/kibana.yml`
9-14. `/home/spia/my-project/monitoring/kibana/dashboards/*.json` (6 dashboard files)
15. `/home/spia/my-project/monitoring/metricbeat/metricbeat.yml`
16. `/home/spia/my-project/scripts/migrate_to_elasticsearch.py`
17. `/home/spia/my-project/docker-compose.elk.yml`

**Modified (5)**:
1. `/home/spia/my-project/api_service.py` - Use ES
2. `/home/spia/my-project/requirements.txt` - Add elasticsearch
3. `/home/spia/my-project/Dockerfile` - Remove PostgreSQL
4. `/home/spia/my-project/README.md` - Update architecture
5. `/home/spia/my-project/USER_MANUAL.md` - Kibana instructions

**Deleted (20+)**:
1. `/home/spia/my-project/database_service.py`
2. `/home/spia/my-project/database/init.sql`
3. `/home/spia/my-project/monitoring/prometheus/prometheus.yml`
4-12. `/home/spia/my-project/monitoring/grafana/provisioning/**/*` (9+ config files)
13-20. `/home/spia/my-project/monitoring/grafana/dashboards/*.json` (8 dashboard files)
21. `/home/spia/my-project/docker-compose.yml` (replaced)

---

## Implementation Timeline

### Phase 1: RTL-SDR Integration
**Duration**: 1-2 weeks

**Week 1**:
- Days 1-2: Create sdr_hardware.py with abstract interface
- Day 3: Implement HackRFCapture (refactor existing code)
- Days 4-5: Implement RTLSDRCapture (new)
- Days 6-7: Integration testing with both hardware types

**Week 2** (if needed):
- Days 1-2: Web UI updates (detection, validation)
- Day 3: Documentation updates
- Days 4-5: End-to-end testing (all 4 modes)
- Days 6-7: Bug fixes, edge cases

### Phase 2: ELK Stack Migration
**Duration**: 3-4 weeks

**Week 1 - Elasticsearch Setup**:
- Days 1-2: Index template design (5 index patterns)
- Day 3: ILM policy configuration
- Days 4-5: ElasticsearchService implementation
- Days 6-7: Testing basic CRUD operations

**Week 2 - Logstash Pipelines**:
- Days 1-3: Pipeline configurations (5 pipelines)
- Days 4-5: API integration (replace DB calls with ES)
- Days 6-7: Testing data flow (capture → Logstash → ES)

**Week 3 - Kibana Dashboards**:
- Days 1-3: Dashboard creation (8 dashboards)
- Days 4-5: Metricbeat configuration
- Days 6-7: Docker Compose orchestration

**Week 4 - Migration & Validation**:
- Days 1-2: Migration script development
- Days 3-4: Execute migration, validate data
- Days 5-6: Performance testing, optimization
- Day 7: Documentation updates

**Total Estimated Duration**: 5-6 weeks

---

## Risk Mitigation

### Phase 1 Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| RTL-SDR driver issues in Docker | High | Use privileged mode, tested USB passthrough |
| IQ format bugs (uint8 vs int8) | Medium | Extensive unit tests, synthetic data validation |
| Frequency validation edge cases | Low | Clear error messages, runtime checks |

### Phase 2 Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data migration errors | Critical | Dry-run on copy, row count validation, spot checks |
| ES resource consumption | Medium | Memory limits, ILM policies, monitoring |
| Query performance regression | Medium | Benchmarking, index optimization |
| Kibana dashboard feature gaps | Low | Use Vega for complex visualizations |

---

## Rollback Plans

### Phase 1 Rollback
**If RTL-SDR integration fails:**
1. Git revert to pre-Phase 1 commit
2. Restore `radio_capture.py` from git history
3. Rebuild Docker image
**Estimated Time**: <1 hour

### Phase 2 Rollback
**If ELK migration fails:**
1. Stop ELK containers: `docker-compose -f docker-compose.elk.yml down`
2. Restore `docker-compose.yml` from backup
3. Start PostgreSQL/Prometheus/Grafana: `docker-compose up -d`
4. Restore PostgreSQL database from backup
**Estimated Time**: 2-4 hours
**Critical**: Keep PostgreSQL backup for 30 days post-migration

---

## Success Criteria Summary

### Phase 1
- ✅ Automatic SDR detection working
- ✅ Frequency range validation prevents errors
- ✅ All 4 modes work with RTL-SDR
- ✅ Test coverage >85%
- ✅ No performance regression

### Phase 2
- ✅ 100% data migration accuracy
- ✅ Full-text search functional
- ✅ All dashboards recreated in Kibana
- ✅ Indexing >1000 docs/sec
- ✅ Search latency <100ms (p95)
- ✅ ILM policies active
- ✅ Zero data loss
