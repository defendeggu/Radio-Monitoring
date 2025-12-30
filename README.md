# Radio Message Transcription System

A complete professional radio monitoring system for capturing radio signals from **HackRF One** or **RTL-SDR** with automatic hardware detection, transcribing them using faster-whisper, with Elasticsearch-based data storage, full-text search, and Kibana analytics dashboards.

## Features

### Core Capabilities
- **Dual SDR Support**: Automatic detection and support for HackRF One and RTL-SDR devices
- **Radio Capture**: Capture radio signals with configurable frequency and modulation
- **Hardware Abstraction**: Transparent hardware switching with frequency range validation
- **Multiple Modulation Support**: FM, AM, USB, LSB
- **Speech-to-Text**: Automatic transcription using faster-whisper
- **APRS Packet Decoding**: Decode APRS (Automatic Packet Reporting System) messages using direwolf
- **POCSAG Pager Decoding**: Decode POCSAG pager messages (512, 1200, 2400 baud) using multimon-ng
- **Repeater Activity Monitoring**: Automated scanning and activity analysis of Swiss FM amateur radio repeaters (NEW)
- **Quad Processing Modes**: Voice transcription, APRS packet decoding, POCSAG pager decoding, or Repeater Activity scanning
- **Web Interface**: Easy-to-use tabbed control panel with separate sections for Voice, APRS, POCSAG, and Repeater Scan
- **N8N Integration**: Workflow automation for orchestrating capture and transcription
- **REST API**: Flask-based API for programmatic access
- **Docker Support**: Complete Docker setup for easy deployment

### Data Storage & Analytics (ELK Stack)
- **Elasticsearch**: Time-series data storage with daily indices for all captures, APRS, POCSAG, and repeater activity
- **Full-Text Search**: Advanced multi-language search (English, German, French, Spanish) with analyzers and stemming
- **APRS Message Storage**: Dedicated index for APRS packets with callsign, geo-point position, message data
- **POCSAG Message Storage**: Dedicated index for POCSAG pager messages with address, function code, message type, and baud rate
- **Repeater Activity Storage**: Time-series index for repeater scans with transmission counts, signal strength, activity percentages
- **Geospatial Queries**: Native geo_point mapping for APRS station positions with map visualization support
- **Advanced Filtering**: Filter by frequency, modulation, language, callsign, APRS type, POCSAG address, band, canton, date range
- **Index Lifecycle Management**: Automatic data retention with hot/warm/cold/delete phases (configurable retention period)
- **REST API**: Logstash HTTP input endpoints for data ingestion with multi-pipeline architecture
- **Statistics & Analytics**: Real-time aggregations for frequency usage, language distribution, APRS statistics, POCSAG statistics, repeater activity trends
- **Data Migration**: Bulk import from PostgreSQL to Elasticsearch with schema transformation

### Monitoring & Visualization (ELK Stack)
- **Kibana Dashboards**: Professional data visualization and analytics platform
- **Captures Dashboard**: Interactive dashboard to browse, search, and filter all radio captures with full-text search
- **APRS Dashboard**: Dedicated dashboard with geospatial map, packet statistics, callsign analytics, and message timeline
- **POCSAG Dashboard**: Dedicated dashboard with pager address analytics, message type distribution, baud rate statistics, and timeline visualization
- **Repeater Activity Dashboard**: Dashboard showing most active repeaters, activity trends by band/canton, scan statistics, and signal quality metrics
- **System Metrics Dashboard**: Real-time system performance monitoring powered by Metricbeat
- **Kibana Dev Tools**: Console for direct Elasticsearch queries and index management
- **Metricbeat**: Automated system and container metrics collection (replaces Prometheus + cAdvisor)
- **Logstash Pipelines**: Data ingestion and transformation with 5 dedicated pipelines (captures, APRS, POCSAG, repeater activity, metrics)

## Architecture

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Web Interface  │   │     Kibana      │   │      N8N        │
│   (HTML/JS)     │   │   Dashboards    │   │   Workflows     │
│   Port 8080     │   │   Port 5601     │   │   Port 5679     │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                      │
         │            ┌────────┴────────┐             │
         │            │                 │             │
         │            ▼                 ▼             │
         │    ┌──────────────┐  ┌──────────────┐     │
         │    │Elasticsearch │  │   Logstash   │     │
         │    │  Port 9200   │  │ Ports 9600-  │     │
         │    │              │  │      9604    │     │
         │    │ Time-Series  │  │              │     │
         │    │   Indices:   │  │  5 Pipelines:│     │
         │    │  - captures  │  │  - captures  │     │
         │    │  - aprs      │  │  - aprs      │     │
         │    │  - pocsag    │  │  - pocsag    │     │
         │    │  - repeater  │  │  - repeater  │     │
         │    │  - metrics   │  │  - metrics   │     │
         │    └──────┬───────┘  └──────▲───────┘     │
         │           │                  │             │
         │           │                  │             │
         │           ▼                  │             │
         │    ┌──────────────┐          │             │
         │    │  Metricbeat  │──────────┘             │
         │    │ (Container + │                        │
         │    │System Metrics│                        │
         │    └──────────────┘                        │
         │                                             │
         └─────────────────────────────────────────────┘
                     │
                     ▼
            ┌─────────────────────────────────┐
            │         Flask API               │
            │         Port 5000               │
            ├─────────────────────────────────┤
            │  /capture-and-transcribe        │
            │  /search (ES Full-Text Search)  │
            │  /aprs/search (APRS Search)     │
            │  /aprs/stats (APRS Analytics)   │
            │  /aprs/map (GeoJSON Map Data)   │
            │  /pocsag/search (POCSAG Search) │
            │  /pocsag/stats (POCSAG Stats)   │
            │  /pocsag/messages (Recent Msgs) │
            │  /scan-repeaters (Start Scan)   │
            │  /scan-repeaters/<id>/progress  │
            │  /repeaters (List Repeaters)    │
            │  /repeater-activity/summary     │
            │  /stats (Analytics)             │
            │  /sdr/detect (Hardware Info)    │
            ├─────────────────────────────────┤
            │      Radio Capture              │◄─── HackRF One / RTL-SDR
            │   (Hardware Abstraction Layer)  │     (Auto-detection)
            ├─────────────────────────────────┤
            │ Voice  │ APRS  │POCSAG │Repeater│
            │┌──────┐│┌─────┐│┌─────┐│┌──────┐│
            ││faster││direwolf│multi-││Activity│
            ││whisper│  APRS  │mon-ng││Analyzer│
            │└──────┘│└─────┘│└─────┘│└──────┘│
            ├─────────────────────────────────┤
            │  Elasticsearch Service          │
            │  (ES Python Client)             │
            │  Index to Logstash → ES         │
            └─────────────────────────────────┘
```

## Requirements

### Hardware

**SDR Device (one of the following):**

The system supports both HackRF One and RTL-SDR with **automatic hardware detection**. Choose based on your frequency coverage needs:

| Feature | HackRF One | RTL-SDR |
|---------|------------|---------|
| **Frequency Range** | 1 MHz - 6 GHz | 24 MHz - 1.766 GHz |
| **TX Capability** | Yes (transmit) | No (receive-only) |
| **Max Sample Rate** | 20 MHz | 3.2 MHz |
| **Price** | ~$300 USD | ~$25 USD |
| **Best For** | Full-spectrum monitoring, HF/VHF/UHF/microwave | Budget VHF/UHF monitoring (FM radio, APRS, aviation) |
| **Limitations** | Higher cost | Cannot receive HF (<24 MHz) or microwave (>1.766 GHz) |

**Recommended for beginners:** RTL-SDR (affordable, covers most common frequencies)
**Recommended for advanced users:** HackRF One (full spectrum coverage, higher performance)

**Additional Hardware:**
- USB cable
- Computer with USB port
- Appropriate antenna for target frequencies

### Hardware Detection

The system automatically detects which SDR is connected:
- Prefers HackRF if both are connected (better specs)
- Validates frequency range at runtime
- Shows detected device in web interface
- Prevents invalid captures for device limitations

### Frequency Coverage Examples

**HackRF One can receive:**
- ✅ HF bands (1-30 MHz): Shortwave, amateur HF
- ✅ VHF (30-300 MHz): FM radio, aviation, APRS, amateur 2m
- ✅ UHF (300-3000 MHz): Amateur 70cm, PMR, POCSAG pagers
- ✅ Microwave (>3 GHz): Satellite, radar, WiFi, 23cm amateur

**RTL-SDR can receive:**
- ❌ HF bands (<24 MHz): Not supported
- ✅ VHF (24-300 MHz): FM radio (88-108 MHz), aviation (118-137 MHz), APRS (144.8 MHz), amateur 2m
- ✅ UHF (300-1766 MHz): Amateur 70cm (430-440 MHz), PMR (446 MHz), POCSAG pagers (147 MHz)
- ❌ Microwave (>1.766 GHz): Not supported

### Software
- Docker and Docker Compose (recommended)
- OR Python 3.11+ with system dependencies

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   cd /home/spia/my-project
   ```

2. **Setup Secrets** (Required for first-time setup)
   ```bash
   ./setup-secrets.sh
   ```
   This script generates secure passwords for all services. Save the displayed credentials!

3. **Configure environment** (optional)
   ```bash
   cp .env.example .env
   # Edit .env to customize settings
   ```

4. **Connect SDR device**
   ```bash
   # Verify HackRF One is detected
   hackrf_info

   # OR verify RTL-SDR is detected
   rtl_test -t
   ```

5. **Start the services**
   ```bash
   docker-compose -f docker-compose.elk.yml up -d
   ```

6. **Access the interfaces**
   - Web Interface: http://localhost:8080
   - Kibana Dashboards: http://localhost:5601
   - Elasticsearch API: http://localhost:9200
   - Logstash Pipelines: http://localhost:9600-9604
   - N8N Workflow: http://localhost:5679 (credentials from setup-secrets.sh)
   - API: http://localhost:5000

## Secrets Management

This project uses **Docker Secrets** for secure credential management, similar to Kubernetes Secrets.

### 🔐 Why Docker Secrets?

- **Security**: Passwords are stored in separate files, not in docker-compose.yml
- **Git-safe**: Secret files are automatically excluded from version control
- **Kubernetes-like**: Familiar pattern if you're used to K8s
- **Auditable**: Easy to track which services use which secrets

### Quick Setup

Run the setup script to generate all required secrets:

```bash
./setup-secrets.sh
```

This creates:
- Strong random passwords for all services
- Secret files in the `secrets/` directory
- Proper file permissions (600 - owner read/write only)

**⚠️ Important**: Save the displayed credentials to your password manager!

### Secret Files

All secrets are stored in `secrets/*.txt` files:

```
secrets/
├── n8n_basic_auth_user.txt
└── n8n_basic_auth_password.txt
```

**Note**: The ELK stack (Elasticsearch, Logstash, Kibana) in this fork runs without authentication for simplicity. For production deployments, enable X-Pack Security.

### How It Works

Docker mounts secret files into containers at `/run/secrets/`:

```yaml
services:
  postgres:
    secrets:
      - postgres_password
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

The application reads secrets automatically:

```python
def read_secret(secret_name: str) -> Optional[str]:
    secret_path = Path(f'/run/secrets/{secret_name}')
    if secret_path.exists():
        return secret_path.read_text().strip()
    return None
```

### Viewing Your Credentials

```bash
# N8N
cat secrets/n8n_basic_auth_password.txt
```

### Changing Passwords

1. Update the secret file:
   ```bash
   echo "new_strong_password" > secrets/n8n_basic_auth_password.txt
   ```

2. Restart the service:
   ```bash
   docker compose -f docker-compose.elk.yml restart n8n
   ```

For more details, see [`secrets/README.md`](secrets/README.md).

## Manual Installation

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    libusb-1.0-0-dev \
    libhackrf-dev \
    hackrf \
    rtl-sdr \
    librtlsdr-dev \
    build-essential \
    python3-pip \
    direwolf \
    multimon-ng \
    libasound2-dev \
    cmake
```

**macOS:**
```bash
brew install hackrf rtl-sdr direwolf multimon-ng
```

### Python Dependencies

```bash
pip install -r requirements.txt
```

### Start Services

1. **Start Flask API**
   ```bash
   python api_service.py
   ```

2. **Start N8N** (in another terminal)
   ```bash
   npx n8n
   ```

3. **Serve Web Interface** (in another terminal)
   ```bash
   python -m http.server 8080
   ```

## Usage

### Web Interface

**Voice/APRS/POCSAG Modes:**
1. Open http://localhost:8080 in your browser
2. Use preset buttons or enter custom frequency
3. Select modulation type (FM, AM, USB, LSB)
4. Set recording duration and gain
5. Click "Start Recording & Transcription"
6. Wait for the transcription to complete

**Repeater Activity Scanning (NEW):**
1. Open http://localhost:8080 and click the "📻 Repeater Scan" tab
2. Select band (2m, 70cm) and optionally filter by canton (ZH, BE, etc.)
3. Set scan duration per repeater (30-300s, recommended: 120s)
4. Click "Start Repeater Scan"
5. Watch real-time progress as each repeater is scanned
6. View results table showing:
   - Active/Quiet status (🟢/⚫)
   - Transmission count
   - Activity percentage
   - Signal strength (dB)
7. Analyze historical data in Kibana Repeater Activity Dashboard

**Importing Repeater Data:**
```bash
# Import from CSV (recommended)
docker exec radio-transcription-api python /app/scripts/import_repeaters_csv.py /app/scripts/example_repeaters.csv

# Or from host machine (if secrets are configured)
python scripts/import_repeaters_csv.py scripts/my_repeaters.csv
```

See `scripts/README.md` for CSV format and detailed instructions.

### Command Line

**Capture radio signal:**
```bash
# The sdr_hardware.py module automatically detects HackRF or RTL-SDR
# Use via API service (recommended) or import in Python scripts

# Example using Python API:
from sdr_hardware import get_sdr_instance

# Auto-detect hardware and capture
capture = get_sdr_instance(frequency=100_000_000, sample_rate=2_000_000, gain=20)
capture.capture_audio(duration=30, output_file='recordings/capture.wav', modulation='FM')
```

**Transcribe audio:**
```bash
python transcription_service.py \
    --input recordings/capture.wav \
    --model base \
    --output recordings/capture.json
```

### API Endpoints

**Capture only:**
```bash
curl -X POST http://localhost:5000/capture \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 30,
    "gain": 20
  }'
```

**Transcribe only:**
```bash
curl -X POST http://localhost:5000/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "audio_file": "recordings/capture_20250101_120000.wav"
  }'
```

**Capture and transcribe (Voice mode):**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 30,
    "gain": 20,
    "language": "en",
    "mode": "voice"
  }'
```

**Capture and decode APRS:**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 144800000,
    "modulation": "FM",
    "duration": 300,
    "gain": 20,
    "mode": "aprs"
  }'
```

**Search APRS messages:**
```bash
curl -X GET "http://localhost:5000/aprs/search?callsign=N0CALL&limit=50"
```

**Get APRS statistics:**
```bash
curl -X GET "http://localhost:5000/aprs/stats"
```

**Get APRS map data (GeoJSON):**
```bash
curl -X GET "http://localhost:5000/aprs/map"
```

**Capture and decode POCSAG:**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 147325000,
    "modulation": "FM",
    "duration": 300,
    "gain": 20,
    "mode": "pocsag"
  }'
```

**Search POCSAG messages:**
```bash
curl -X GET "http://localhost:5000/pocsag/search?address=1234567&limit=50"
```

**Get POCSAG statistics:**
```bash
curl -X GET "http://localhost:5000/pocsag/stats"
```

**Get recent POCSAG messages:**
```bash
curl -X GET "http://localhost:5000/pocsag/messages?limit=20"
```

**Start repeater activity scan:**
```bash
curl -X POST http://localhost:5000/scan-repeaters \
  -H "Content-Type: application/json" \
  -d '{
    "duration_per_repeater": 120,
    "band": "2m",
    "canton": "ZH",
    "gain": 20
  }'
```

**Get scan progress:**
```bash
curl -X GET "http://localhost:5000/scan-repeaters/1/progress"
```

**List available repeaters:**
```bash
curl -X GET "http://localhost:5000/repeaters?band=2m&canton=ZH"
```

**Get repeater activity summary:**
```bash
curl -X GET "http://localhost:5000/repeater-activity/summary?hours=24&limit=10"
```

### N8N Workflow

1. Access N8N at http://localhost:5678
2. Import the workflow from `n8n-workflow.json`
3. The workflow provides a webhook endpoint at: `http://localhost:5678/webhook/radio-transcription`
4. Send POST requests with radio parameters to trigger capture and transcription

## Configuration

### Environment Variables

Edit `.env` file to customize:

```bash
# Radio Configuration
DEFAULT_FREQUENCY=100000000      # 100 MHz
DEFAULT_SAMPLE_RATE=2000000      # 2 MHz
DEFAULT_MODULATION=FM
DEFAULT_GAIN=20                  # 0-47 dB

# Whisper Configuration
WHISPER_MODEL=base               # tiny, base, small, medium, large
WHISPER_DEVICE=cpu               # cpu or cuda
WHISPER_COMPUTE_TYPE=int8        # int8, int16, float16, float32

# Recording Configuration
RECORDING_DURATION=30            # seconds
AUDIO_OUTPUT_DIR=./recordings

# Elasticsearch Configuration
ELASTICSEARCH_HOSTS=http://elasticsearch:9200  # Elasticsearch cluster hosts (comma-separated)
LOGSTASH_HOST=http://logstash:9600            # Logstash HTTP input endpoint

# N8N Webhook
N8N_WEBHOOK_URL=http://localhost:5678/webhook/radio-transcription
```

### Frequency Presets

The web interface includes common frequency presets:

**Voice Transcription:**
- **FM Radio**: 88.5 MHz (FM)
- **Flugfunk (Aviation)**: 118.00 MHz (AM)
- **Amateur 2m**: 145.500 MHz (FM)
- **Amateur 70cm**: 433.50 MHz (FM)
- **PMR**: 446.00625 MHz (FM)

**APRS Decoding:**
- **APRS Europe**: 144.800 MHz (FM) - Default
- **APRS North America**: 144.390 MHz (FM)
- **APRS Japan**: 144.660 MHz (FM)
- **APRS Australia**: 145.175 MHz (FM)

**POCSAG Pager Decoding:**
- **Switzerland**: 147.325 MHz (FM) - Primary Swiss pager frequency
- **Preset 2**: 466.075 MHz (FM)
- **Preset 3**: 439.9875 MHz (FM)
- **Preset 4**: 161.425 MHz (FM)
- **Custom**: Enter your own frequency

Note: POCSAG frequency presets can be customized in `web_interface.html`. Consult your local frequency allocation guides for active pager frequencies in your region.

## Modulation Types

- **FM (Frequency Modulation)**: Used for broadcast radio, amateur radio, marine VHF
- **AM (Amplitude Modulation)**: Used for AM broadcast radio, aviation
- **USB (Upper Sideband)**: Used for HF amateur radio, marine SSB
- **LSB (Lower Sideband)**: Used for HF amateur radio below 10 MHz

## Troubleshooting

### SDR Hardware Not Detected

**Check HackRF One:**
```bash
# Verify HackRF is connected
hackrf_info

# Should output: "Serial number: 0x..."
# If not found, check USB connection and permissions
```

**Check RTL-SDR:**
```bash
# Verify RTL-SDR is connected
rtl_test -t

# Should output: "Found Rafael Micro R820T tuner" or similar
# Press Ctrl+C to stop the test
```

**Fix USB Permissions (Linux):**
```bash
# Add user to plugdev group
sudo usermod -a -G plugdev $USER

# Log out and back in

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Check in Web Interface:**
- Open http://localhost:8080
- Look for SDR indicator at top of page
- Should show: "✅ SDR: HACKRF (1.0-6000 MHz)" or "✅ SDR: RTLSDR (24.0-1766 MHz)"
- If red error message, SDR not detected

### Frequency Out of Range Error

**Error:** "Frequency X MHz is out of range for RTL-SDR"

**Solution:**
- RTL-SDR only supports 24-1766 MHz
- For frequencies outside this range, use HackRF One
- Or choose a different frequency within RTL-SDR range

**Common Workarounds:**
- HF shortwave (<24 MHz): Requires HackRF One or upconverter for RTL-SDR
- Microwave (>1.766 GHz): Requires HackRF One

### No Audio Captured

- Check antenna is connected
- Verify frequency is correct
- Increase RF gain
- Try different modulation type
- Check for nearby interference

### Transcription Fails

- Ensure audio file exists and is valid WAV format
- Check faster-whisper is installed correctly
- Try different Whisper model (tiny for speed, large for accuracy)
- Verify audio contains speech

### Docker USB Access Issues

```bash
# Run with privileged mode (already in docker-compose.yml)
# Or add specific USB device:
docker run --device=/dev/bus/usb/XXX/YYY ...
```

## Advanced Usage

### Custom N8N Workflows

You can extend the N8N workflow to:
- Send transcriptions to Slack/Discord/Email
- Save to database
- Trigger alerts on specific keywords
- Schedule automatic recordings
- Post-process transcriptions with AI

### Integration with Other Services

The API can be integrated with:
- Home automation systems
- Monitoring dashboards
- Database logging
- Alert systems
- Machine learning pipelines

## File Structure

```
.
├── sdr_hardware.py                  # SDR hardware abstraction (HackRF + RTL-SDR)
├── transcription_service.py         # faster-whisper transcription
├── aprs_decoder_service.py          # APRS decoder using direwolf
├── pocsag_decoder_service.py        # POCSAG decoder using multimon-ng
├── repeater_activity_analyzer.py    # Repeater activity signal processing
├── api_service.py                   # Flask REST API with Elasticsearch integration
├── elasticsearch_service.py         # Elasticsearch client and indexing service
├── web_interface.html               # Web control panel (tabbed: Voice/APRS/POCSAG/Repeater)
├── scripts/
│   ├── import_repeaters_csv.py     # CSV import tool for repeater data
│   ├── migrate_pg_to_elasticsearch.py  # PostgreSQL to Elasticsearch migration script
│   ├── example_repeaters.csv       # Example Swiss repeater data
│   └── README.md                   # Script documentation
├── monitoring/
│   ├── elasticsearch/
│   │   ├── index-templates/        # Index templates for data types
│   │   │   ├── radio-captures.json
│   │   │   ├── radio-aprs.json
│   │   │   ├── radio-pocsag.json
│   │   │   ├── radio-repeater-activity.json
│   │   │   └── radio-metrics.json
│   │   └── ilm-policies/           # Index Lifecycle Management policies
│   │       └── radio-ilm-policy.json
│   ├── logstash/
│   │   ├── pipelines/              # Logstash pipeline configurations
│   │   │   ├── radio-capture-pipeline.conf
│   │   │   ├── radio-aprs-pipeline.conf
│   │   │   ├── radio-pocsag-pipeline.conf
│   │   │   ├── radio-repeater-pipeline.conf
│   │   │   └── radio-metrics-pipeline.conf
│   │   └── config/
│   │       └── logstash.yml
│   ├── kibana/
│   │   ├── config/
│   │   │   └── kibana.yml
│   │   └── dashboards/             # Kibana dashboard exports (ndjson format)
│   └── metricbeat/
│       └── metricbeat.yml          # Container metrics configuration
├── n8n-workflow.json                # N8N workflow definition
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image definition
├── docker-compose.elk.yml           # Docker Compose with ELK stack
├── .env.example                     # Environment variables template
├── .gitignore                      # Git ignore rules
├── README.md                        # This file
└── USER_MANUAL.md                  # Complete user documentation
```

## API Reference

### POST /capture
Capture radio signal to WAV file.

**Request:**
```json
{
  "frequency": 100000000,
  "modulation": "FM",
  "duration": 30,
  "gain": 20,
  "sample_rate": 2000000
}
```

**Response:**
```json
{
  "status": "success",
  "audio_file": "recordings/capture_20250101_120000.wav",
  "frequency": 100000000,
  "modulation": "FM",
  "duration": 30,
  "timestamp": "2025-01-01T12:00:00"
}
```

### POST /transcribe
Transcribe existing audio file.

**Request:**
```json
{
  "audio_file": "recordings/capture.wav",
  "language": "en"
}
```

**Response:**
```json
{
  "status": "success",
  "result": {
    "text": "Transcribed text here",
    "language": "en",
    "language_probability": 0.95,
    "duration": 30.5,
    "segments": [...],
    "audio_file": "recordings/capture.wav",
    "timestamp": "2025-01-01T12:00:30"
  }
}
```

### POST /capture-and-transcribe
Capture and transcribe in one operation.

**Request:**
```json
{
  "frequency": 100000000,
  "modulation": "FM",
  "duration": 30,
  "gain": 20,
  "language": "en"
}
```

**Response:**
```json
{
  "status": "success",
  "capture": {
    "audio_file": "recordings/capture_20250101_120000.wav",
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 30
  },
  "transcription": {
    "text": "Transcribed text here",
    "language": "en",
    "duration": 30.5,
    ...
  },
  "timestamp": "2025-01-01T12:00:30"
}
```

### GET /list-recordings
List all captured recordings.

**Response:**
```json
{
  "recordings": [
    {
      "filename": "capture_20250101_120000.wav",
      "path": "recordings/capture_20250101_120000.wav",
      "size": 1920044,
      "created": "2025-01-01T12:00:00"
    }
  ]
}
```

### GET /sdr/detect
Detect connected SDR hardware and return capabilities.

**Response (HackRF detected):**
```json
{
  "type": "hackrf",
  "frequency_range": {
    "min_hz": 1000000,
    "max_hz": 6000000000,
    "min_mhz": 1.0,
    "max_mhz": 6000.0
  },
  "max_sample_rate_hz": 20000000,
  "max_sample_rate_mhz": 20.0
}
```

**Response (RTL-SDR detected):**
```json
{
  "type": "rtlsdr",
  "frequency_range": {
    "min_hz": 24000000,
    "max_hz": 1766000000,
    "min_mhz": 24.0,
    "max_mhz": 1766.0
  },
  "max_sample_rate_hz": 3200000,
  "max_sample_rate_mhz": 3.2
}
```

**Response (No SDR detected):**
```json
{
  "error": "No SDR hardware detected",
  "message": "Please connect HackRF One or RTL-SDR device"
}
```
Status: 404

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "radio-transcription-api",
  "timestamp": "2025-01-01T12:00:00"
}
```

### GET /search
Search through all database captures with filters.

**Query Parameters:**
- `text` - Full-text search in transcriptions (optional)
- `frequency` - Filter by exact frequency in Hz (optional)
- `modulation` - Filter by modulation type: FM, AM, USB, LSB (optional)
- `language` - Filter by detected language code: en, de, es, etc. (optional)
- `start_date` - Start date in ISO format: 2025-12-28T00:00:00 (optional)
- `end_date` - End date in ISO format (optional)
- `limit` - Maximum results, default 100 (optional)
- `offset` - Offset for pagination, default 0 (optional)

**Examples:**
```bash
# Search for text in transcriptions
curl "http://localhost:5000/search?text=weather"

# Filter by modulation
curl "http://localhost:5000/search?modulation=FM&limit=20"

# Search by frequency
curl "http://localhost:5000/search?frequency=145500000"

# Combined filters
curl "http://localhost:5000/search?modulation=FM&language=de&text=amateur"

# Date range search
curl "http://localhost:5000/search?start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59"
```

**Response:**
```json
{
  "status": "success",
  "results": [
    {
      "id": 1,
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2025-01-01T12:00:00",
      "frequency": 145500000,
      "modulation": "FM",
      "duration": 30,
      "transcription_text": "CQ CQ CQ this is HB9ABC...",
      "language": "de",
      "language_confidence": 0.98,
      "status": "completed"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### GET /stats
Get overall database statistics.

**Response:**
```json
{
  "status": "success",
  "stats": {
    "total_captures": 27,
    "successful_transcriptions": 15,
    "failed_captures": 2,
    "unique_frequencies": 5,
    "languages": {
      "en": 12,
      "de": 10,
      "es": 3
    },
    "modulations": {
      "FM": 20,
      "AM": 5,
      "USB": 2
    },
    "date_range": {
      "earliest": "2025-01-01T10:00:00",
      "latest": "2025-01-15T18:30:00"
    }
  }
}
```

### GET /stats/frequencies
Get frequency usage statistics with top frequencies.

**Response:**
```json
{
  "status": "success",
  "frequencies": [
    {
      "frequency": 145500000,
      "frequency_mhz": "145.500",
      "count": 12,
      "modulations": ["FM"],
      "last_capture": "2025-01-15T18:30:00"
    },
    {
      "frequency": 100000000,
      "frequency_mhz": "100.000",
      "count": 8,
      "modulations": ["FM"],
      "last_capture": "2025-01-15T16:00:00"
    }
  ],
  "total_unique_frequencies": 5
}
```

### GET /captures/<id>
Get detailed information about a specific capture.

**Response:**
```json
{
  "status": "success",
  "capture": {
    "id": 1,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-01-01T12:00:00",
    "frequency": 145500000,
    "modulation": "FM",
    "duration": 30,
    "gain": 25,
    "sample_rate": 2000000,
    "audio_file_path": "/app/recordings/capture.wav",
    "transcription_text": "Full transcription text here...",
    "language": "de",
    "language_confidence": 0.98,
    "segments": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "CQ CQ CQ this is HB9ABC"
      }
    ],
    "metadata": {
      "operator": "HB9ABC",
      "qso_type": "cq_call"
    },
    "status": "completed"
  }
}
```

## Database Features

### Elasticsearch Storage

All radio data is stored in Elasticsearch time-series indices with:
- Full metadata (frequency, modulation, duration, gain, sample rate, SDR type)
- Complete transcription text with multi-language analyzers
- Language detection with confidence scores
- Flexible JSON document structure
- Automatic @timestamp field for time-series queries
- UUID-based document IDs (_id field)

**Daily Index Patterns:**
- **radio-captures-YYYY.MM.DD**: Voice transcription captures
- **radio-aprs-YYYY.MM.DD**: APRS packet messages with geo_point positions
- **radio-pocsag-YYYY.MM.DD**: POCSAG pager messages
- **radio-repeater-activity-YYYY.MM.DD**: Repeater activity records with nested transmissions
- **radio-metrics-YYYY.MM.DD**: System and application metrics

**Index Features:**
- Optimized mappings for each data type
- Index Lifecycle Management (ILM) for automatic retention
- Keyword + text multi-fields for flexible querying
- Geo-spatial indexing for APRS positions

### Full-Text Search

The database supports powerful text search capabilities:

```bash
# Simple text search
curl "http://localhost:5000/search?text=amateur"

# Case-insensitive partial matching
curl "http://localhost:5000/search?text=weat"  # matches "weather"
```

### Advanced Filtering

Combine multiple filters for precise queries:

```bash
# FM captures in German language containing "antenna"
curl "http://localhost:5000/search?modulation=FM&language=de&text=antenna"

# All amateur 2m band captures (144-146 MHz)
curl "http://localhost:5000/search?frequency=145500000"
```

### Database Migration

Import existing JSON transcription files into the database:

**Using the migration script:**
```bash
# From inside the Docker container
docker exec -it radio-api python migrate_json_to_db.py

# Or manually with API
for json_file in recordings/*.json; do
  curl -X POST http://localhost:5000/migrate \
    -H "Content-Type: application/json" \
    -d "{\"json_file\": \"$json_file\"}"
done
```

### Data Backup and Export

**Export data from Elasticsearch:**
```bash
# Export all captures from last 30 days
curl -X GET "localhost:9200/radio-captures-*/_search?pretty&size=10000" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"range": {"@timestamp": {"gte": "now-30d"}}}}' \
  > captures_backup.json

# Export APRS data
curl -X GET "localhost:9200/radio-aprs-*/_search?pretty&size=10000" > aprs_backup.json
```

**Snapshot and Restore (recommended for large datasets):**
```bash
# Configure snapshot repository
curl -X PUT "localhost:9200/_snapshot/radio_backup" \
  -H 'Content-Type: application/json' \
  -d '{"type": "fs", "settings": {"location": "/usr/share/elasticsearch/backup"}}'

# Create snapshot
curl -X PUT "localhost:9200/_snapshot/radio_backup/snapshot_1?wait_for_completion=true"

# Restore snapshot
curl -X POST "localhost:9200/_snapshot/radio_backup/snapshot_1/_restore"
```

## Kibana Dashboards

### Accessing Kibana

Open http://localhost:5601 in your browser. No authentication is required by default (enable X-Pack Security for production).

### Available Dashboards

**Note**: Kibana dashboards are created using the Discover, Visualize, and Dashboard features. The following dashboards mirror the functionality from the original Grafana implementation:

#### Radio Captures Explorer
**Access**: Kibana → Discover → Index Pattern: `radio-captures-*`

**Features:**
- View all captures with full-text search across transcriptions
- Filter by modulation type (FM, AM, USB, LSB)
- Filter by detected language (en, de, es, etc.)
- Filter by frequency range
- Time-based filtering (last 15m, 1h, 24h, 7d, 30d, custom)
- Sort by any field (@timestamp, frequency, language, etc.)
- Real-time updates with auto-refresh

**Usage:**
1. Use the search bar for full-text queries: `transcription: "amateur"` or `modulation: "FM"`
2. Use filters to narrow results (Add filter → field → value)
3. Click on time range selector to change time window
4. Enable auto-refresh for real-time monitoring

#### APRS Monitoring Dashboard
**Access**: Kibana → Dashboard → APRS Activity

**Visualizations:**
- **Total APRS Packets**: Metric showing total packet count
- **Unique Callsigns**: Metric showing distinct source callsigns
- **Packets with Position**: Count of packets with geo-location data
- **APRS Timeline**: Line chart of packets over time (5-minute buckets)
- **Message Types**: Pie chart showing distribution of APRS packet types
- **Top 15 Callsigns**: Horizontal bar chart of most active stations
- **APRS Stations Map**: Coordinate map showing station positions (geo_point visualization)
- **Recent Packets Table**: Data table of latest 50 APRS messages

**Usage:**
1. Use time picker to select time range (last 24h default)
2. Click on map markers to view station details
3. Filter by clicking on pie chart segments or bar chart elements
4. Dashboards auto-refresh every 30 seconds

#### Repeater Activity Dashboard
**Access**: Kibana → Dashboard → Repeater Activity Monitoring

**Visualizations:**
- **Most Active Repeaters (24h)**: Data table aggregated by callsign with avg activity percentage
- **Activity by Band**: Pie chart showing 2m vs 70cm activity distribution
- **Scan Rate**: Line chart showing scan operations over time
- **Recent Scans**: Data table of last 100 repeater activity records

**Aggregation Examples (Kibana Dev Tools):**
```json
POST /radio-repeater-activity-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "must": [
        {"range": {"@timestamp": {"gte": "now-24h"}}},
        {"term": {"carrier_detected": true}}
      ]
    }
  },
  "aggs": {
    "by_repeater": {
      "terms": {
        "field": "repeater_callsign",
        "size": 10,
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

### Creating Custom Dashboards

Create custom visualizations and dashboards in Kibana:

1. Go to **Kibana → Visualize → Create visualization**
2. Select visualization type (Line, Bar, Pie, Data Table, Metric, Map, etc.)
3. Choose index pattern (`radio-captures-*`, `radio-aprs-*`, etc.)
4. Configure metrics and buckets/aggregations
5. Save visualization and add to dashboard

**Example Aggregation - Recent FM Captures:**
```json
POST /radio-captures-*/_search
{
  "size": 20,
  "query": {
    "bool": {
      "must": [
        {"term": {"modulation": "FM"}},
        {"range": {"@timestamp": {"gte": "now-24h"}}}
      ]
    }
  },
  "sort": [{"@timestamp": "desc"}],
  "_source": ["@timestamp", "frequency_mhz", "transcription", "detected_language"]
}
```

## Kibana Dev Tools

### Accessing Dev Tools

Open Kibana → Dev Tools (http://localhost:5601/app/dev_tools#/console) for direct Elasticsearch API access.

### Using the Console

**Browse Indices:**
```json
# List all radio indices
GET /_cat/indices/radio-*?v

# View index mapping
GET /radio-captures-*/_mapping

# Count documents
GET /radio-captures-*/_count
```

**Run Queries:**
```json
# Get all captures from last 24 hours
POST /radio-captures-*/_search
{
  "query": {
    "range": {
      "@timestamp": {
        "gte": "now-24h"
      }
    }
  },
  "sort": [{"@timestamp": "desc"}],
  "size": 100
}

# Get frequency statistics
POST /radio-captures-*/_search
{
  "size": 0,
  "aggs": {
    "by_frequency": {
      "terms": {
        "field": "frequency_mhz",
        "size": 20,
        "order": {"_count": "desc"}
      },
      "aggs": {
        "by_modulation": {
          "terms": {"field": "modulation"}
        }
      }
    }
  }
}

# Full-text search in transcriptions
POST /radio-captures-*/_search
{
  "query": {
    "multi_match": {
      "query": "weather",
      "fields": ["transcription", "transcription.english", "transcription.german"]
    }
  },
  "highlight": {
    "fields": {
      "transcription": {}
    }
  },
  "size": 10
}
```

**Export Data:**
```json
# Export to JSON (use scroll API for large datasets)
POST /radio-captures-*/_search?scroll=5m
{
  "size": 1000,
  "query": {"match_all": {}}
}

# Then use the scroll_id to get next batch
POST /_search/scroll
{
  "scroll": "5m",
  "scroll_id": "<scroll_id_from_previous_response>"
}
```

**Index Management:**
```json
# View index stats
GET /radio-captures-*/_stats

# Delete old indices
DELETE /radio-captures-2024.01.*

# Reindex data
POST /_reindex
{
  "source": {"index": "radio-captures-2025.01.01"},
  "dest": {"index": "radio-captures-reindexed"}
}
```

### Kibana Features

- ✅ Discover: Interactive log exploration with full-text search
- ✅ Visualize: Create charts, graphs, maps, and metrics
- ✅ Dashboard: Combine visualizations into comprehensive dashboards
- ✅ Dev Tools: Console for direct Elasticsearch API access
- ✅ Index Management: Lifecycle policies, rollover, and retention
- ✅ Canvas: Pixel-perfect data presentations
- ✅ Maps: Geospatial visualization for APRS positions
- ✅ Alerting: Set up alerts based on query conditions (requires X-Pack)

## Legal Notice

This software is intended for use with authorized radio frequencies only. Users are responsible for:
- Complying with local radio regulations
- Obtaining required licenses for transmission (if applicable)
- Only monitoring frequencies they are legally permitted to access
- Following spectrum allocation rules in their jurisdiction

**This is a receive-only application and does not transmit radio signals.**

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Support

For issues and questions:
- Check the Troubleshooting section
- Review complete USER_MANUAL.md for detailed documentation
- Review HackRF documentation: https://hackrf.readthedocs.io/
- Review RTL-SDR documentation: https://www.rtl-sdr.com/about-rtl-sdr/
- Review faster-whisper documentation: https://github.com/guillaumekln/faster-whisper
- Review N8N documentation: https://docs.n8n.io/
- Review Elasticsearch documentation: https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
- Review Kibana documentation: https://www.elastic.co/guide/en/kibana/current/index.html
- Review Logstash documentation: https://www.elastic.co/guide/en/logstash/current/index.html

## Acknowledgments

- HackRF One by Great Scott Gadgets
- RTL-SDR project and community
- faster-whisper by Guillaume Klein
- Whisper by OpenAI
- N8N workflow automation platform
- Elasticsearch by Elastic
- Logstash by Elastic
- Kibana by Elastic
- Metricbeat by Elastic
