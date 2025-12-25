# Quick Start Guide

Get up and running in 5 minutes!

## Option 1: Docker (Recommended)

The fastest way to get started:

```bash
# 1. Connect your HackRF device

# 2. Start all services
docker-compose up -d

# 3. Open your browser
open http://localhost:8080
```

**Access Points:**
- Web Interface: http://localhost:8080
- N8N: http://localhost:5678 (admin/admin)
- API: http://localhost:5000

## Option 2: Manual Setup

For development or customization:

```bash
# 1. Run setup script
./setup.sh

# 2. Log out and back in (for USB permissions)

# 3. Connect HackRF device

# 4. Start services
./start.sh

# 5. In another terminal, start N8N
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

The system includes simulation mode if HackRF is not connected. It will:
- Generate test audio signals
- Create mock transcriptions
- Allow you to test the workflow

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

**HackRF not detected?**
```bash
hackrf_info
# If it fails, reconnect device and check USB permissions
```

**Docker USB issues?**
```bash
# Already configured with privileged mode
# Just restart: docker-compose restart radio-api
```

**Can't access web interface?**
```bash
# Check if port 8080 is available
# Or use different port in docker-compose.yml
```

## Next Steps

- Customize settings in `.env` file
- Import N8N workflow and customize it
- Add your own frequency presets
- Integrate with other services

For detailed documentation, see README.md
