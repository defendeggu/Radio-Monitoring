# Quick Start Guide

Get up and running in 5 minutes!

## Option 1: Docker (Recommended)

The fastest way to get started:

```bash
# 1. Connect your SDR device (HackRF One or RTL-SDR)

# 2. Start all services with ELK stack
docker compose up -d

# 3. Open your browser
open http://localhost:8080
```

**Access Points:**
- Web Interface: http://localhost:8080
- Kibana Dashboards: http://localhost:5601
- API: http://localhost:5000

## Option 2: Manual Setup

For development or customization:

```bash
# 1. Run setup script (installs HackRF and RTL-SDR packages)
./setup.sh

# 2. Log out and back in (for USB permissions)

# 3. Connect your SDR device (HackRF One or RTL-SDR)

# 4. Start services
./start.sh

# 5. In another terminal, start N8N (optional)
npx n8n
```

## First Recording

1. Open http://localhost:8080
2. Choose a preset frequency or enter custom frequency
3. Select modulation type (FM for most radio)
4. Click "Start Recording & Transcription"
5. Wait 30 seconds for capture and transcription
6. View the transcribed text!

## Testing Without Hardware

The system includes simulation mode if no SDR device is connected. It will:
- Generate test audio signals
- Create mock transcriptions
- Allow you to test the workflow
- Auto-detect available hardware (HackRF or RTL-SDR)

## Common Frequencies to Try

### FM Radio
- Frequency: 88.5 MHz (88500000 Hz)
- Modulation: FM

### Marine VHF
- Frequency: 156.8 MHz (156800000 Hz)
- Modulation: FM

### Amateur Radio 2m
- Frequency: 146.52 MHz (146520000 Hz)
- Modulation: FM

### Weather Radio (US)
- Frequency: 162.55 MHz (162550000 Hz)
- Modulation: FM

## Troubleshooting

**SDR device not detected?**
```bash
# For HackRF:
hackrf_info

# For RTL-SDR:
rtl_test -t

# If it fails, reconnect device and check USB permissions
```

**Docker USB issues?**
```bash
# USB device access is configured in docker-compose.yml
# Just restart the API container:
docker compose restart radio-api
```

**Can't access web interface?**
```bash
# Check if port 8080 is available
# Or modify port mapping in docker-compose.yml
```

## Development & Testing

**Run the test suite:**
```bash
# Activate virtual environment
source venv/bin/activate

# Run all 67 tests
pytest

# Run with coverage report
./scripts/run_coverage.sh

# Run type checking
./scripts/run_mypy.sh
```

**Test Results:**
- ✅ 67 tests covering API, SDR hardware, and transcription
- ✅ 27% code coverage (target: 15% minimum)
- ✅ Full MyPy type checking compliance
- ✅ Automated CI/CD pipeline on GitHub Actions

**Development Mode:**
```bash
# Start Flask dev server (port 5000)
python api_service.py

# In another terminal: Web interface (port 8080)
python -m http.server 8080
```

**Production Mode:**
```bash
# Docker with Gunicorn + full ELK stack
docker compose -f docker-compose.yml -f docker-compose.elk.yml up -d

# Access services:
# - Web Interface: http://localhost:8080
# - Kibana: http://localhost:5601
# - N8N: http://localhost:5679
# - Elasticsearch: http://localhost:9200
```

## Next Steps

- ✨ **Explore Kibana Dashboards** at http://localhost:5601
- 🔧 **Customize settings** in `.env` file
- 🔄 **Import N8N workflow** and automate captures
- 📡 **Add frequency presets** for your region
- 🧪 **Run tests** to verify your changes
- 📊 **Monitor with ELK** stack for analytics

For detailed documentation, see:
- **README.md** - Complete system documentation
- **USER_MANUAL.md** - Detailed user guide
- **STREAMING_MODE.md** - Real-time decoding guide
