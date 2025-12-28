# Radio Message Transcription System

A complete professional radio monitoring system for capturing radio signals from HackRF, transcribing them using faster-whisper, with PostgreSQL database storage, full-text search, and Grafana analytics dashboards.

## Features

### Core Capabilities
- **Radio Capture**: Capture radio signals from HackRF with configurable frequency and modulation
- **Multiple Modulation Support**: FM, AM, USB, LSB
- **Speech-to-Text**: Automatic transcription using faster-whisper
- **Web Interface**: Easy-to-use control panel for selecting frequency and modulation
- **N8N Integration**: Workflow automation for orchestrating capture and transcription
- **REST API**: Flask-based API for programmatic access
- **Docker Support**: Complete Docker setup for easy deployment

### Database & Analytics (NEW)
- **PostgreSQL Database**: Permanent storage of all captures with full metadata
- **Full-Text Search**: Search through all transcriptions with PostgreSQL full-text search
- **Advanced Filtering**: Filter by frequency, modulation, language, date range
- **Database API**: REST endpoints for searching and analyzing historical data
- **Statistics & Analytics**: Frequency usage, language distribution, success rates
- **Data Migration**: Import existing JSON transcriptions into database

### Monitoring & Visualization (NEW)
- **Grafana Dashboards**: Professional monitoring and data visualization
- **Database Browser**: Interactive dashboard to browse, search, and filter all captures
- **Statistics Dashboard**: Real-time metrics and performance monitoring
- **Prometheus Metrics**: System performance and API metrics collection
- **cAdvisor**: Container resource monitoring

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Web Interface  │     │     Grafana     │     │      N8N        │
│   (HTML/JS)     │     │   Dashboards    │     │   Workflows     │
│   Port 8080     │     │   Port 3000     │     │   Port 5679     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │              ┌────────┴────────┐             │
         │              │                 │             │
         │              ▼                 ▼             │
         │      ┌──────────────┐  ┌──────────────┐    │
         │      │  Prometheus  │  │  PostgreSQL  │    │
         │      │  Port 9090   │  │  Port 5432   │    │
         │      └──────┬───────┘  └──────┬───────┘    │
         │             │                  │             │
         └─────────────┼──────────────────┼─────────────┘
                       │                  │
                       ▼                  ▼
              ┌─────────────────────────────────┐
              │         Flask API               │
              │         Port 5000               │
              ├─────────────────────────────────┤
              │  /capture-and-transcribe        │
              │  /search (Database Search)      │
              │  /stats (Analytics)             │
              │  /captures/<id>                 │
              ├─────────────────────────────────┤
              │      Radio Capture              │◄─── HackRF Device
              ├─────────────────────────────────┤
              │    faster-whisper               │
              │     Transcription               │
              ├─────────────────────────────────┤
              │   Database Service              │
              │   (PostgreSQL Client)           │
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
- HackRF One SDR device
- USB cable
- Computer with USB port

### Software
- Docker and Docker Compose (recommended)
- OR Python 3.11+ with system dependencies

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   cd /home/spia/my-project
   ```

2. **Configure environment** (optional)
   ```bash
   cp .env.example .env
   # Edit .env to customize settings
   ```

3. **Connect HackRF device**
   ```bash
   # Verify HackRF is detected
   hackrf_info
   ```

4. **Start the services**
   ```bash
   docker-compose up -d
   ```

5. **Access the interfaces**
   - Web Interface: http://localhost:8080
   - Grafana Dashboards: http://localhost:3000 (admin/admin)
   - N8N Workflow: http://localhost:5679 (admin/admin)
   - API: http://localhost:5000
   - Prometheus: http://localhost:9090
   - cAdvisor: http://localhost:8081

## Manual Installation

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    libusb-1.0-0-dev \
    libhackrf-dev \
    hackrf \
    build-essential \
    python3-pip
```

**macOS:**
```bash
brew install hackrf
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

1. Open http://localhost:8080 in your browser
2. Use preset buttons or enter custom frequency
3. Select modulation type (FM, AM, USB, LSB)
4. Set recording duration and gain
5. Click "Start Recording & Transcription"
6. Wait for the transcription to complete

### Command Line

**Capture radio signal:**
```bash
python radio_capture.py \
    --frequency 100000000 \
    --modulation FM \
    --duration 30 \
    --gain 20 \
    --output recordings/capture.wav
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

**Capture and transcribe:**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 30,
    "gain": 20,
    "language": "en"
  }'
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

- **FM Radio**: 88.5 MHz (FM)
- **Marine VHF**: 162.55 MHz (FM)
- **Amateur 2m**: 144.39 MHz (FM)
- **FRS/GMRS**: 462.5625 MHz (FM)

## Modulation Types

- **FM (Frequency Modulation)**: Used for broadcast radio, amateur radio, marine VHF
- **AM (Amplitude Modulation)**: Used for AM broadcast radio, aviation
- **USB (Upper Sideband)**: Used for HF amateur radio, marine SSB
- **LSB (Lower Sideband)**: Used for HF amateur radio below 10 MHz

## Troubleshooting

### HackRF Not Detected

```bash
# Check if device is connected
hackrf_info

# Check USB permissions (Linux)
sudo usermod -a -G plugdev $USER
# Log out and back in

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

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
├── radio_capture.py           # HackRF capture service
├── transcription_service.py   # faster-whisper transcription
├── api_service.py             # Flask REST API with database integration
├── web_interface.html         # Web control panel
├── database/
│   ├── init.sql              # PostgreSQL database schema
│   └── migrations/           # Database migration scripts
├── monitoring/
│   ├── grafana/
│   │   ├── dashboards/       # Grafana dashboard JSON files
│   │   │   ├── radio-database-browser.json
│   │   │   └── database-statistics.json
│   │   └── provisioning/     # Auto-provisioning configs
│   │       └── datasources/
│   │           └── postgres.yml
│   └── prometheus/
│       └── prometheus.yml    # Prometheus configuration
├── n8n-workflow.json          # N8N workflow definition
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose with all services
├── .env.example               # Environment variables template
├── .gitignore                # Git ignore rules
├── README.md                  # This file
└── USER_MANUAL.md            # Complete user documentation
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
- Review faster-whisper documentation: https://github.com/guillaumekln/faster-whisper
- Review N8N documentation: https://docs.n8n.io/
- Review Grafana documentation: https://grafana.com/docs/
- Review PostgreSQL documentation: https://www.postgresql.org/docs/

## Acknowledgments

- HackRF One by Great Scott Gadgets
- faster-whisper by Guillaume Klein
- Whisper by OpenAI
- N8N workflow automation platform
- PostgreSQL database system
- Grafana visualization platform
- Prometheus monitoring system
