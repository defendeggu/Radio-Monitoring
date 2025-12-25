# Radio Message Transcription System

A complete application for capturing radio signals from HackRF and transcribing them using faster-whisper, orchestrated by N8N.

## Features

- **Radio Capture**: Capture radio signals from HackRF with configurable frequency and modulation
- **Multiple Modulation Support**: FM, AM, USB, LSB
- **Speech-to-Text**: Automatic transcription using faster-whisper
- **Web Interface**: Easy-to-use control panel for selecting frequency and modulation
- **N8N Integration**: Workflow automation for orchestrating capture and transcription
- **REST API**: Flask-based API for programmatic access
- **Docker Support**: Complete Docker setup for easy deployment

## Architecture

```
┌─────────────────┐
│  Web Interface  │ (Port 8080)
│   (HTML/JS)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      N8N        │ (Port 5678)
│   Workflow      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Flask API     │ (Port 5000)
│                 │
├─────────────────┤
│ Radio Capture   │◄─── HackRF Device
│                 │
├─────────────────┤
│ faster-whisper  │
│  Transcription  │
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
   - N8N Workflow: http://localhost:5678 (admin/admin)
   - API: http://localhost:5000

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

# N8N Webhook
N8N_WEBHOOK_URL=http://localhost:5678/webhook/radio-transcription
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
├── api_service.py             # Flask REST API
├── web_interface.html         # Web control panel
├── n8n-workflow.json          # N8N workflow definition
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose configuration
├── .env.example               # Environment variables template
├── .gitignore                # Git ignore rules
└── README.md                  # This file
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
- Review HackRF documentation: https://hackrf.readthedocs.io/
- Review faster-whisper documentation: https://github.com/guillaumekln/faster-whisper
- Review N8N documentation: https://docs.n8n.io/

## Acknowledgments

- HackRF One by Great Scott Gadgets
- faster-whisper by Guillaume Klein
- Whisper by OpenAI
- N8N workflow automation platform
