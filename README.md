# Radio Message Transcription System

A complete professional radio monitoring system for capturing radio signals from **HackRF One** or **RTL-SDR** with automatic hardware detection, transcribing them using faster-whisper, with PostgreSQL database storage, full-text search, and Grafana analytics dashboards.

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

### Database & Analytics (NEW)
- **PostgreSQL Database**: Permanent storage of all captures with full metadata
- **Full-Text Search**: Search through all transcriptions, APRS, and POCSAG messages with PostgreSQL full-text search
- **APRS Message Storage**: Dedicated table for APRS packets with callsign, position, message data
- **POCSAG Message Storage**: Dedicated table for POCSAG pager messages with address, function code, message type, and baud rate
- **Repeater Database**: Swiss FM repeater directory with frequency, offset, tone, location, canton
- **Activity Tracking**: Historical repeater activity records with transmission counts, signal strength, activity percentages
- **Scan Session Management**: Track multi-repeater scan sessions with progress and results
- **Geospatial Indexing**: Efficient queries for APRS station positions using PostGIS-compatible GIST indices
- **Advanced Filtering**: Filter by frequency, modulation, language, callsign, APRS type, POCSAG address, band, canton, date range
- **Database API**: REST endpoints for searching and analyzing historical data
- **Statistics & Analytics**: Frequency usage, language distribution, APRS statistics, POCSAG statistics, repeater activity trends, success rates
- **Data Migration**: Import existing JSON transcriptions and repeater CSV data into database

### Monitoring & Visualization (NEW)
- **Grafana Dashboards**: Professional monitoring and data visualization
- **Database Browser**: Interactive dashboard to browse, search, and filter all captures
- **APRS Dashboard**: Dedicated dashboard with station map, packet statistics, and callsign analytics
- **POCSAG Dashboard**: Dedicated dashboard with pager address analytics, message type distribution, baud rate statistics, and timeline visualization
- **Repeater Activity Dashboard**: Dedicated dashboard showing most active repeaters, activity trends by band/canton, scan statistics, and signal quality metrics (NEW)
- **Statistics Dashboard**: Real-time metrics and performance monitoring
- **pgAdmin 4**: Full-featured PostgreSQL database management web interface
- **Prometheus Metrics**: System performance, API metrics, APRS decode statistics, POCSAG decode statistics, and repeater scan metrics
- **cAdvisor**: Container resource monitoring

## Architecture

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Web Interface  │   │     Grafana     │   │     pgAdmin     │   │      N8N        │
│   (HTML/JS)     │   │   Dashboards    │   │   DB Manager    │   │   Workflows     │
│   Port 8080     │   │   Port 3000     │   │   Port 5050     │   │   Port 5679     │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                      │                     │
         │            ┌────────┴────────┬─────────────┘                     │
         │            │                 │                                   │
         │            ▼                 ▼                                   │
         │    ┌──────────────┐  ┌──────────────┐                          │
         │    │  Prometheus  │  │  PostgreSQL  │                          │
         │    │  Port 9090   │  │  Port 5432   │                          │
         │    └──────┬───────┘  └──────┬───────┘                          │
         │           │                  │                                   │
         └───────────┼──────────────────┼───────────────────────────────────┘
                     │                  │
                     ▼                  ▼
            ┌─────────────────────────────────┐
            │         Flask API               │
            │         Port 5000               │
            ├─────────────────────────────────┤
            │  /capture-and-transcribe        │
            │  /search (Database Search)      │
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
            │  /captures/<id>                 │
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
            │   Database Service              │
            │   (PostgreSQL Client)           │
            │   captures + aprs_messages      │
            │   + pocsag_messages + repeaters │
            │   + repeater_activity + sessions│
            └─────────────────────────────────┘
                     │
                     ▼
            ┌─────────────────┐
            │    cAdvisor     │
            │   Port 8081     │
            │ (Container Mon) │
            └─────────────────┘
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
   docker-compose up -d
   ```

6. **Access the interfaces**
   - Web Interface: http://localhost:8080
   - Grafana Dashboards: http://localhost:3000 (credentials from setup-secrets.sh)
   - pgAdmin Database Manager: http://localhost:5050 (credentials from setup-secrets.sh)
   - N8N Workflow: http://localhost:5679 (credentials from setup-secrets.sh)
   - API: http://localhost:5000
   - Prometheus: http://localhost:9090
   - cAdvisor: http://localhost:8081

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
├── postgres_user.txt
├── postgres_password.txt
├── postgres_db.txt
├── grafana_admin_user.txt
├── grafana_admin_password.txt
├── n8n_basic_auth_user.txt
├── n8n_basic_auth_password.txt
├── pgadmin_email.txt
└── pgadmin_password.txt
```

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
# PostgreSQL
cat secrets/postgres_password.txt

# Grafana
cat secrets/grafana_admin_password.txt

# N8N
cat secrets/n8n_basic_auth_password.txt

# pgAdmin
cat secrets/pgadmin_password.txt
```

### Changing Passwords

1. Update the secret file:
   ```bash
   echo "new_strong_password" > secrets/postgres_password.txt
   ```

2. Restart the service:
   ```bash
   docker compose restart postgres
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
7. Analyze historical data in Grafana Repeater Activity Dashboard

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

# Database Configuration
POSTGRES_HOST=radio-postgres     # PostgreSQL host
POSTGRES_PORT=5432               # PostgreSQL port
POSTGRES_DB=radio_monitoring     # Database name
POSTGRES_USER=radio_user         # Database user
POSTGRES_PASSWORD=radio_password_change_in_production

# N8N Webhook
N8N_WEBHOOK_URL=http://localhost:5678/webhook/radio-transcription

# Grafana Configuration
GF_SECURITY_ADMIN_USER=admin     # Grafana admin username
GF_SECURITY_ADMIN_PASSWORD=admin # Change on first login
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
├── repeater_activity_analyzer.py    # Repeater activity signal processing (NEW)
├── api_service.py                   # Flask REST API with database integration
├── database_service.py              # PostgreSQL database client
├── web_interface.html               # Web control panel (tabbed: Voice/APRS/POCSAG/Repeater)
├── database/
│   ├── init.sql                    # PostgreSQL database schema
│   └── migrations/                 # Database migration scripts
├── scripts/
│   ├── import_repeaters_csv.py     # CSV import tool for repeater data (NEW)
│   ├── example_repeaters.csv       # Example Swiss repeater data (NEW)
│   └── README.md                   # Script documentation (NEW)
├── monitoring/
│   ├── grafana/
│   │   ├── dashboards/             # Grafana dashboard JSON files
│   │   │   ├── radio-database-browser.json
│   │   │   ├── database-statistics.json
│   │   │   ├── aprs-dashboard.json
│   │   │   ├── pocsag-dashboard.json
│   │   │   └── repeater-activity-dashboard.json  # Repeater monitoring (NEW)
│   │   └── provisioning/           # Auto-provisioning configs
│   │       └── datasources/
│   │           └── postgres.yml
│   └── prometheus/
│       └── prometheus.yml          # Prometheus configuration
├── n8n-workflow.json                # N8N workflow definition
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image definition
├── docker-compose.yml               # Docker Compose with all services
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

### PostgreSQL Storage

All radio captures are permanently stored in a PostgreSQL database with:
- Full metadata (frequency, modulation, duration, gain, sample rate)
- Complete transcription text and segments
- Language detection with confidence scores
- JSONB fields for flexible metadata storage
- Automatic timestamps (created_at, updated_at)
- UUID support for distributed systems

**Repeater Monitoring Tables:**
- **repeaters**: Master directory of Swiss FM repeaters with frequency, offset, tone, location, canton
- **repeater_activity**: Historical activity records with transmission counts, signal strength, activity percentages
- **repeater_scan_sessions**: Track multi-repeater scan sessions with progress and statistics
- Optimized indexes for band, canton, status, and frequency-based queries
- Pre-computed statistics views for quick dashboard updates

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

### Database Backup

**Backup database:**
```bash
docker exec radio-postgres pg_dump -U radio_user radio_monitoring > backup.sql
```

**Restore database:**
```bash
docker exec -i radio-postgres psql -U radio_user radio_monitoring < backup.sql
```

## Grafana Dashboards

### Accessing Grafana

Open http://localhost:3000 in your browser and log in with:
- Username: `admin`
- Password: `admin` (change on first login)

### Available Dashboards

#### Radio Captures Database Browser
**URL**: http://localhost:3000/d/radio-db-browser/radio-captures-database-browser

**Features:**
- View all captures in an interactive table
- Sort by any column (timestamp, frequency, language, etc.)
- Filter by modulation type (FM, AM, USB, LSB)
- Filter by detected language (en, de, es, etc.)
- Full-text search in transcriptions
- Real-time updates as new captures are added

**Usage:**
1. Use the **Modulation** dropdown to filter by signal type
2. Use the **Language** dropdown to filter by detected language
3. Use the **Search Text** field to search transcription content
4. Click column headers to sort
5. Results auto-refresh when filters change

#### Database Statistics Dashboard
**URL**: http://localhost:3000/d/radio-stats/radio-statistics

**Panels:**
- Total captures count
- Successful transcriptions count
- Capture success rate gauge
- Transcription success rate gauge
- Captures over time graph
- Distribution by modulation type (pie chart)
- Captures per hour (bar chart)
- Top 10 most active frequencies
- Language distribution
- Failed captures count

#### Repeater Activity Dashboard (NEW)
**URL**: http://localhost:3000/d/repeater-activity/repeater-activity-monitoring

**Features:**
- Monitor Swiss FM repeater activity in real-time
- Track transmission counts and signal quality
- View activity trends by band (2m, 70cm) and canton
- Analyze scan performance and coverage

**Panels:**
- **Most Active Repeaters (24h)**: Table showing repeaters with highest activity percentages
- **Scan Rate**: Time-series graph of scan operations per minute
- **Activity by Band**: Pie chart showing activity distribution across 2m and 70cm bands
- **Recent Scans (7 days)**: Detailed table of the last 100 scan results with signal strength data

**Usage:**
1. Run repeater scans from the Web Interface Repeater Scan tab
2. View real-time updates as scans complete (30s refresh interval)
3. Click on repeater callsigns to drill down into specific activity
4. Use time range selector to analyze historical trends
5. Monitor signal strength patterns to identify propagation conditions

**Example Queries:**
```sql
-- Top 10 active repeaters in last 24 hours
SELECT
  r.callsign,
  r.output_frequency / 1000000.0 AS frequency_mhz,
  r.band,
  r.location_name,
  r.canton,
  AVG(ra.activity_percentage) AS avg_activity_pct,
  SUM(ra.transmission_count) AS total_transmissions,
  COUNT(ra.id) AS scan_count,
  MAX(ra.created_at) AS last_scan
FROM repeaters r
LEFT JOIN repeater_activity ra ON r.id = ra.repeater_id
WHERE ra.created_at > NOW() - INTERVAL '24 hours'
GROUP BY r.id
ORDER BY avg_activity_pct DESC NULLS LAST
LIMIT 20;
```

### Creating Custom Dashboards

You can create your own dashboards using the PostgreSQL datasource:

1. Click **+ → Dashboard** in Grafana
2. Add a new panel
3. Select **Radio PostgreSQL** as datasource
4. Write custom SQL queries:

```sql
-- Example: Recent FM captures
SELECT
  created_at,
  ROUND(frequency::numeric / 1000000, 3) as frequency_mhz,
  transcription_text,
  language
FROM captures
WHERE modulation = 'FM'
ORDER BY created_at DESC
LIMIT 20;
```

## pgAdmin Database Management

### Accessing pgAdmin

Open http://localhost:5050 in your browser and log in with:
- Email: `admin@admin.com`
- Password: `admin`

### Automatic PostgreSQL Connection

**The PostgreSQL server is automatically registered!**

After logging into pgAdmin, you'll see the **"Radio Monitoring Database"** server already configured in the left sidebar under **Servers**.

Simply expand the server tree:
- **Servers** → **Radio Monitoring Database** → **Databases** → **radio_monitoring** → **Schemas** → **public** → **Tables**

No manual configuration needed! The connection is pre-configured with:
- Host: `radio-postgres`
- Port: `5432`
- Database: `radio_monitoring`
- Username: `radio_user`
- Password: Automatically loaded from secure configuration

### Using pgAdmin

**Browse Data:**
- Navigate to: Servers → Radio Monitoring Database → Databases → radio_monitoring → Schemas → public → Tables
- Right-click on `captures` table → **"View/Edit Data" → "All Rows"**

**Run SQL Queries:**
- Right-click on `radio_monitoring` database → **"Query Tool"**
- Execute custom SQL queries:

```sql
-- Get all captures from last 24 hours
SELECT * FROM captures
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;

-- Get frequency statistics
SELECT
  ROUND(frequency::numeric / 1000000, 3) as freq_mhz,
  modulation,
  COUNT(*) as count
FROM captures
GROUP BY frequency, modulation
ORDER BY count DESC;

-- Search transcriptions
SELECT
  id,
  created_at,
  frequency,
  transcription_text
FROM captures
WHERE transcription_text ILIKE '%weather%'
LIMIT 10;
```

**Export Data:**
- Select data in Query Tool results
- Click **"Download as CSV"** icon
- Or right-click table → **"Import/Export"** → Configure export options

**Backup Database:**
- Right-click on `radio_monitoring` database
- Select **"Backup..."**
- Choose format (Custom, Tar, Plain SQL)
- Configure options and save

**Restore Database:**
- Right-click on database
- Select **"Restore..."**
- Choose backup file
- Configure restore options

### pgAdmin Features

- ✅ Visual query builder
- ✅ Schema visualization (ERD diagrams)
- ✅ SQL syntax highlighting and auto-completion
- ✅ Query history and favorites
- ✅ Data import/export (CSV, JSON, etc.)
- ✅ Database backup and restore
- ✅ User and permission management
- ✅ Performance monitoring and explain plans
- ✅ Table statistics and analysis

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
- Review Grafana documentation: https://grafana.com/docs/
- Review PostgreSQL documentation: https://www.postgresql.org/docs/

## Acknowledgments

- HackRF One by Great Scott Gadgets
- RTL-SDR project and community
- faster-whisper by Guillaume Klein
- Whisper by OpenAI
- N8N workflow automation platform
- PostgreSQL database system
- pgAdmin 4 by The pgAdmin Development Team
- Grafana visualization platform
- Prometheus monitoring system
