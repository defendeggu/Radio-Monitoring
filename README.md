# 📻 Radio Message Transcription System

A complete professional radio monitoring system for capturing radio signals from **HackRF One**, **RTL-SDR**, or **Airspy HF+** with automatic hardware detection, transcribing them using faster-whisper, with Elasticsearch-based data storage, full-text search, and Kibana analytics dashboards.

## ✨ Features

### 🎯 Core Capabilities
- 📡 **Triple SDR Support**: Automatic detection and support for HackRF One, RTL-SDR, and Airspy HF+ devices
- 📻 **Radio Capture**: Capture radio signals with configurable frequency and modulation
- 🔄 **Hardware Abstraction**: Transparent hardware switching with frequency range validation
- 📊 **Multiple Modulation Support**: FM, AM, USB, LSB
- 🎤 **Speech-to-Text**: Automatic transcription using faster-whisper
- 📍 **APRS Packet Decoding**: Decode APRS (Automatic Packet Reporting System) messages using direwolf
- 📟 **POCSAG Pager Decoding**: Decode POCSAG pager messages (512, 1200, 2400 baud) using multimon-ng
- 🔁 **Repeater Activity Monitoring**: Automated scanning and activity analysis of Swiss FM amateur radio repeaters (NEW)
- ⚡ **Quad Processing Modes**: Voice transcription, APRS packet decoding, POCSAG pager decoding, or Repeater Activity scanning
- 🌐 **Web Interface**: Easy-to-use tabbed control panel with separate sections for Voice, APRS, POCSAG, and Repeater Scan
- 🔌 **REST API**: Flask-based API for programmatic access
- 🐳 **Docker Support**: Complete Docker setup for easy deployment

### 💾 Data Storage & Analytics (ELK Stack)
- 🗄️ **Elasticsearch**: Time-series data storage with daily indices for all captures, APRS, POCSAG, and repeater activity
- 🔍 **Full-Text Search**: Advanced multi-language search (English, German, French, Spanish) with analyzers and stemming
- 📍 **APRS Message Storage**: Dedicated index for APRS packets with callsign, geo-point position, message data
- 📟 **POCSAG Message Storage**: Dedicated index for POCSAG pager messages with address, function code, message type, and baud rate
- 📡 **Repeater Activity Storage**: Time-series index for repeater scans with transmission counts, signal strength, activity percentages
- 🗺️ **Geospatial Queries**: Native geo_point mapping for APRS station positions with map visualization support
- 🎛️ **Advanced Filtering**: Filter by frequency, modulation, language, callsign, APRS type, POCSAG address, band, canton, date range
- ♻️ **Index Lifecycle Management**: Automatic data retention with hot/warm/cold/delete phases (configurable retention period)
- 🔌 **REST API**: Logstash HTTP input endpoints for data ingestion with multi-pipeline architecture
- 📊 **Statistics & Analytics**: Real-time aggregations for frequency usage, language distribution, APRS statistics, POCSAG statistics, repeater activity trends

### 📈 Monitoring & Visualization (ELK Stack)
- 📊 **Kibana Dashboards**: Professional data visualization and analytics platform
- 🎙️ **Captures Dashboard**: Interactive dashboard to browse, search, and filter all radio captures with full-text search
- 📍 **APRS Dashboard**: Dedicated dashboard with geospatial map, packet statistics, callsign analytics, and message timeline
- 📟 **POCSAG Dashboard**: Dedicated dashboard with pager address analytics, message type distribution, baud rate statistics, and timeline visualization
- 📡 **Repeater Activity Dashboard**: Dashboard showing most active repeaters, activity trends by band/canton, scan statistics, and signal quality metrics
- 💻 **System Metrics Dashboard**: Real-time system performance monitoring powered by Metricbeat
- 🛠️ **Kibana Dev Tools**: Console for direct Elasticsearch queries and index management
- 📈 **Metricbeat**: Automated system and container metrics collection (replaces Prometheus + cAdvisor)
- 🔄 **Logstash Pipelines**: Data ingestion and transformation with 5 dedicated pipelines (captures, APRS, POCSAG, repeater activity, metrics)

## Architecture

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Web Interface  │   │     Kibana      │   │   Portainer     │
│   (HTML/JS)     │   │   Dashboards    │   │  Docker Mgmt    │
│   Port 8080     │   │   Port 5601     │   │  Ports 9000/    │
│                 │   │                 │   │       9443      │
└────────┬────────┘   └────────┬────────┘   └─────────────────┘
         │                     │
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
            │     Flask API (Gunicorn)        │
            │         Port 5000               │
            │  Production WSGI Server         │
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
            │      Radio Capture              │◄─── HackRF One / RTL-SDR / Airspy HF+
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

## 📋 Requirements

### 🔧 Hardware

**📡 SDR Device (one of the following):**

The system supports HackRF One, RTL-SDR, and Airspy HF+ with **automatic hardware detection**. Choose based on your frequency coverage needs:

| Feature | HackRF One | RTL-SDR | Airspy HF+ |
|---------|------------|---------|------------|
| **Frequency Range** | 1 MHz - 6 GHz | 24 MHz - 1.766 GHz | 0.5 kHz - 31 MHz (HF)<br>60 - 260 MHz (VHF) |
| **TX Capability** | Yes (transmit) | No (receive-only) | No (receive-only) |
| **Max Sample Rate** | 20 MHz | 3.2 MHz | 912 kHz |
| **Price** | ~$300 USD | ~$25 USD | ~$200 USD |
| **Best For** | Full-spectrum monitoring | Budget VHF/UHF | Professional HF/VHF reception |
| **Strengths** | Widest frequency coverage; automatic IQ/DC correction | Affordable, stable | Best HF sensitivity (-141 dBm) |
| **Limitations** | USB bandwidth issues >120s | No HF (<24 MHz) | Frequency gap 31-60 MHz, lower max sample rate |
| **USB Stability** | Stable up to 3600s with correct pipe handling | Excellent up to 660s | Excellent stability |

**Recommended for HF monitoring (shortwave, amateur HF):** Airspy HF+ (0.5 kHz - 31 MHz, excellent sensitivity)
**Recommended for beginners:** RTL-SDR (affordable, covers most common frequencies, excellent USB stability)
**Recommended for advanced users:** HackRF One (full spectrum coverage, supports long streaming sessions up to 3600s)
**Recommended for long captures (>120s):** All supported devices work well; RTL-SDR and Airspy HF+ have inherently lower USB overhead

**🔌 Additional Hardware:**
- 🔌 USB cable
- 💻 Computer with USB port
- 📡 Appropriate antenna for target frequencies

### 🔍 Hardware Detection

The system automatically detects which SDR is connected:
- **Detection priority**: HackRF > Airspy HF+ > RTL-SDR (when multiple devices connected)
- Validates frequency range at runtime
- Shows detected device in web interface
- Automatic sample rate clamping for device capabilities
- Prevents invalid captures for device limitations
- **HackRF**: Automatic software IQ correction (DC offset removal + IQ imbalance correction) applied to every capture

### 📊 Frequency Coverage Examples

**📻 HackRF One can receive:**
- ✅ HF bands (1-30 MHz): Shortwave, amateur HF
- ✅ VHF (30-300 MHz): FM radio, aviation, APRS, amateur 2m
- ✅ UHF (300-3000 MHz): Amateur 70cm, PMR, POCSAG pagers
- ✅ Microwave (>3 GHz): Satellite, radar, WiFi, 23cm amateur

**📡 RTL-SDR can receive:**
- ❌ HF bands (<24 MHz): Not supported
- ✅ VHF (24-300 MHz): FM radio (88-108 MHz), aviation (118-137 MHz), APRS (144.8 MHz), amateur 2m
- ✅ UHF (300-1766 MHz): Amateur 70cm (430-440 MHz), PMR (446 MHz), POCSAG pagers (147 MHz)
- ❌ Microwave (>1.766 GHz): Not supported

**📻 Airspy HF+ can receive:**
- ✅ HF bands (0.5 kHz - 31 MHz): **Best sensitivity** - Shortwave, amateur HF (160m, 80m, 40m, 20m, 10m), broadcast
- ❌ Gap (31-60 MHz): Not supported by hardware
- ✅ VHF (60-260 MHz): FM radio (88-108 MHz), aviation (118-137 MHz), APRS (144.8 MHz), amateur 2m
- ❌ UHF (>260 MHz): Not supported

### 💻 Software
- 🐳 Docker and Docker Compose (recommended)
- 🐍 OR Python 3.11+ with system dependencies

### 💾 System Requirements

**Memory Requirements:**

The system uses the ELK stack (Elasticsearch, Logstash, Kibana) which requires significant memory for optimal performance:

| Component | Heap Size | Container Overhead | Total Memory |
|-----------|-----------|-------------------|--------------|
| Elasticsearch | 4 GB | ~1 GB | ~5 GB |
| Logstash | 2 GB | ~0.5 GB | ~2.5 GB |
| Kibana | - | ~0.5 GB | ~0.5 GB |
| Radio API | - | ~1 GB | ~1 GB |
| Redis | - | ~0.1 GB | ~0.1 GB |
| Metricbeat | - | ~0.1 GB | ~0.1 GB |
| **Total** | **6 GB** | **~3.2 GB** | **~9.2 GB** |

**Recommended System Specifications:**
- 💻 **Minimum RAM**: 12 GB (allows OS + other processes)
- 🚀 **Recommended RAM**: 16 GB or higher
- 💾 **Disk Space**: 50 GB minimum (for logs and audio recordings)
- 🔄 **SSD**: Strongly recommended for Elasticsearch performance

**Performance Notes:**
- Elasticsearch heap is set to 4 GB for fast indexing and search
- Logstash heap is set to 2 GB for high-throughput data ingestion
- System uses multi-stage Docker builds for 34% smaller image sizes
- Elasticsearch configured with optimized settings:
  - Index refresh interval: 5 seconds (vs default 1s)
  - Async translog for better write performance
  - Disabled unused features (ML, Graph, Watcher) to save memory

## 🚀 Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone https://github.com/defendeggu/Radio-Monitoring
   cd Radio-Monitoring
   ```

2. **Generate ELK credentials** (Required for first-time setup)
   ```bash
   ./scripts/setup-elk-security.sh
   ```
   This generates secure passwords for all ELK services and writes them to `.env.elk` and `.env` in the project root. Save the credentials shown!

3. **Connect SDR device**
   ```bash
   # Verify HackRF One is detected
   hackrf_info

   # OR verify RTL-SDR is detected
   rtl_test -t
   ```

4. **Start the services**
   ```bash
   docker compose up -d
   ```

5. **Run post-setup** (Required after first start — creates Elasticsearch users and imports Kibana dashboards)
   ```bash
   ./scripts/post-docker-setup.sh
   ```
   This script:
   - Waits for Elasticsearch to be healthy
   - Creates the `logstash_writer` user and other required Elasticsearch users
   - Restarts Logstash and Metricbeat so they pick up the new credentials
   - Imports Kibana dashboards

   > **Why is this step required?** Logstash connects to Elasticsearch using a custom `logstash_writer` user that does not exist in a fresh Elasticsearch cluster. The post-setup script creates this user. Without it, Logstash will fail to start. Logstash is configured with `restart: on-failure` so it will recover automatically once the user is created.

   **Manual alternative** (if you prefer to import dashboards later):
   ```bash
   # Import dashboards manually at any time
   ./scripts/import-kibana-dashboards.sh
   ```

6. **Access the interfaces**
   - 🌐 **Web Interface**: http://localhost:8080
   - 📊 **Kibana Dashboards**: http://localhost:5601 (elastic / [password from .env.elk])
     - Pre-configured dashboards:
       - 📡 Radio Monitoring Overview
       - 📍 APRS Activity Dashboard (with geospatial map)
       - 📟 POCSAG Pager Monitoring
       - 🔁 Repeater Activity Dashboard
   - 🐳 **Portainer** (Docker Management): http://localhost:9000 or https://localhost:9443
   - 🔍 **Elasticsearch API**: http://localhost:9200
   - 🔌 **Logstash Pipelines**: http://localhost:9600-9604
   - 🔌 **API**: http://localhost:5000

## 📝 Recent Updates

### March 2026

**HackRF Streaming Fixes & Stop Buttons (2026-03-24)**
- Fixed USB stall that caused HackRF streaming sessions to abort after ~6 seconds: replaced `signal.resample` on large arrays with multi-stage decimation (`scipy.signal.decimate`) and removed `nice -n 10` priority penalty from `hackrf_transfer`
- Fixed FM demodulation gain: switched from broken `÷π` formula to conjugate-product discriminator with correct deviation-based gain (`sample_rate / (2π × deviation)`); POCSAG/APRS audio now at 96% of full scale instead of 0.45%
- Fixed HackRF not being released after a session ends: added in-process decoder registry so `DELETE /stream-decode/<id>` calls `decoder.stop_stream()` directly
- Replaced `pkill`-based process killing (not available in container) with `/proc` filesystem scanning via `os.kill()`
- Added `POST /sdr/force-stop` emergency endpoint that kills all active decoders and SDR processes
- Added Stop buttons to all Web Interface modules (Voice, APRS, POCSAG) — each button stops the running task and releases the HackRF immediately
- POCSAG sessions now run for the full configured duration (300s / 3600s) and decode packets correctly

**Installation Bug Fixes (2026-03-24)**
- `session_store.py` and `maidenhead_grid.py` were missing from the Dockerfile — API container crashed on startup
- `mqtt-bridge` build context was `./mqtt-bridge/` but the script lived in `./scripts/` — image build failed
- `setup-elk-security.sh` wrote `.env.elk` to `scripts/` instead of project root — credentials not found
- `setup-elk-security.sh` now also creates `.env` for Docker Compose variable interpolation (health checks, redis command)
- `setup-elk-users.sh` now creates the `logstash_writer` role and user in Elasticsearch (was missing entirely, causing Logstash to fail on every fresh install)
- `post-docker-setup.sh` now runs user setup automatically and restarts Logstash/Metricbeat
- Added `restart: on-failure` to Logstash so it recovers automatically once users are created

**Project Cleanup & Security Hardening**
- Removed all dead code: N8N integration, Grafana dashboards, PostgreSQL import scripts, pgAdmin
- Kibana encryption key and Redis password externalized — generated by `setup-elk-security.sh`, no more hardcoded placeholders
- All remaining `print()` calls in `api_service.py` replaced with structured `logger` calls
- Replaced Docker-based CI scripts with direct `mypy`/`pytest` invocations (no `Dockerfile.test` dependency)
- Fixed 10 mypy errors: declared `sdr_type` attribute in `BaseStreamingDecoder` base class
- Fixed 20 failing CI tests across streaming decoders, SDR hardware, and repeater scanning
- Renamed default branch from `fork-rtlsdr-elk` to `main`
- **Commits**: `6dd3c5f`, `90e821e`, `8a2bfd2`

### January 2026

**Duration Bug Fix (2026-01-20)**
- Streaming decoder sessions (APRS/POCSAG) now properly complete at configured duration
- Sessions no longer remain in "running" state indefinitely
- **Commit**: `d1f40c4`

**RTL-SDR Unicode Detection Fix (2026-01-20)**
- RTL-SDR detection no longer fails with Unicode decode errors on certain systems
- Removed `text=True` from subprocess call; bytes handled directly in `sdr_hardware.py`

**Docker Secrets Implementation (2026-01-20)**
- Passwords stored in `.secrets/` with restrictive permissions (600/700)
- Entrypoint wrappers inject secrets at runtime for all ELK services
- **Commit**: `337043a`

For detailed session summaries see `docs/current/`.

## 📡 RTL-SDR Quick Start Guide

New to RTL-SDR? This section will help you get started quickly!

### 📦 What You Need

- **RTL-SDR USB Dongle** (~$25-40 USD)
  - R820T/R820T2 tuner (most common)
  - Software: rtl-sdr tools (included in Docker image)
- **Antenna** (usually included with RTL-SDR)
  - Telescopic antenna for VHF/UHF
  - Longer antenna for better reception
- **USB Extension Cable** (recommended)
  - Reduces USB noise interference
  - Allows better antenna positioning

### 🔌 First-Time Setup

1. **Connect RTL-SDR Device**
   ```bash
   # Plug in RTL-SDR USB dongle
   # Extend antenna to appropriate length for your frequency
   ```

2. **Verify Device Detection**
   ```bash
   # Check if device is detected
   rtl_test -t

   # Expected output:
   # Found 1 device(s):
   #   0:  Realtek, RTL2838UHIDIR, SN: 00000001
   ```

3. **Test Reception** (Optional)
   ```bash
   # Listen to local FM radio station (e.g., 100.7 MHz)
   rtl_fm -f 100.7M -M fm -s 200k - | aplay -r 200k -f S16_LE
   # Press Ctrl+C to stop
   ```

### 🎯 Common Frequencies to Try

#### FM Radio (87.5-108 MHz)
Perfect for testing your RTL-SDR setup!

```bash
# Example: Monitor FM radio at 100.7 MHz
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 100700000,
    "modulation": "fm",
    "duration": 30
  }'
```

#### APRS (Amateur Radio Position Reporting)

**Europe:** 144.800 MHz | **North America:** 144.390 MHz | **Australia:** 145.175 MHz

```bash
# Start APRS monitoring (Europe)
curl -X POST http://localhost:5000/stream-decode/aprs \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 144800000
  }'

# Check decoded APRS packets
curl http://localhost:5000/aprs/search?hours=1
```

#### Amateur Radio Repeaters

**2m Band (144-146 MHz)** | **70cm Band (430-440 MHz)**

```bash
# Scan Swiss 2m repeaters for activity
curl -X POST http://localhost:5000/scan-repeaters \
  -H "Content-Type: application/json" \
  -d '{
    "band": "2m",
    "canton": "all"
  }'
```

#### Aviation Band (118-137 MHz)

```bash
# Monitor emergency frequency 121.5 MHz
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 121500000,
    "modulation": "am",
    "duration": 60
  }'
```

#### Weather Satellites (NOAA APT)

**NOAA-15:** 137.620 MHz | **NOAA-18:** 137.9125 MHz | **NOAA-19:** 137.100 MHz

### 📝 RTL-SDR Configuration File

Copy the example configuration file to get started with common frequencies:

```bash
cp rtlsdr-example.conf rtlsdr.conf
# Edit rtlsdr.conf to customize frequencies for your region
```

The configuration file includes:
- Common frequency presets (FM, Aviation, Marine, Amateur Radio)
- APRS frequencies by region
- POCSAG pager frequencies
- Swiss repeater channels
- PPM calibration settings
- Gain settings guide

### 🔧 Frequency Correction (PPM)

RTL-SDR devices have small frequency errors. Calibrate for better accuracy:

1. **Find your PPM error:**
   - Tune to a known frequency (e.g., local FM station at 100.7 MHz)
   - Note the actual frequency where signal is strongest
   - PPM error = (actual - expected) / expected * 1000000

2. **Apply correction:**
   ```bash
   # Set in rtlsdr.conf
   FREQUENCY_CORRECTION=52  # Example: 52 PPM
   ```

3. **Or use kalibrate-rtl:**
   ```bash
   kal -s GSM900
   # Use the displayed PPM value in your configuration
   ```

### 🔀 Multiple RTL-SDR Devices

Have multiple RTL-SDR dongles? You can use them simultaneously!

See the [Multi-Device Setup Guide](MULTI_DEVICE.md) for detailed instructions on:
- Setting unique serial numbers with `rtl_eeprom`
- Using multiple devices for parallel monitoring
- Dedicated APRS, Voice, and POCSAG devices
- USB hub requirements and power considerations

Quick example:
```bash
# Set unique serial numbers
rtl_eeprom -d 0 -s RTLSDR_APRS
rtl_eeprom -d 1 -s RTLSDR_VOICE

# Use specific device in API calls
curl -X POST http://localhost:5000/aprs/decode \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 144800000,
    "device_serial": "RTLSDR_APRS",
    "duration": 300
  }'
```

### 🛠️ Troubleshooting

**Problem:** No RTL-SDR devices found
```bash
# Check USB connection
lsusb | grep RTL

# Add user to plugdev group (Linux)
sudo usermod -a -G plugdev $USER
# Log out and log back in
```

**Problem:** Poor reception quality
- Extend antenna fully
- Try different antenna positions (near window, higher elevation)
- Use USB extension cable to reduce noise
- Check for interference from computers, power supplies

**Problem:** Device busy error
- Close GQRX, SDR#, or other SDR software
- Only one application can use RTL-SDR at a time
- Stop any active streaming sessions

**Problem:** Wrong frequency received
- Calibrate PPM error (see above)
- Check antenna is connected
- Verify frequency is within RTL-SDR range (24 MHz - 1.766 GHz)

### 📚 Learning Resources

- **RTL-SDR Official Guide:** https://www.rtl-sdr.com/rtl-sdr-quick-start-guide/
- **APRS Information:** http://aprs.org/
- **Frequency Databases:**
  - https://www.radioreference.com/ (North America)
  - https://www.repeatermap.de/ (Europe)
- **Swiss Repeaters:** https://www.uska.ch/

### 💡 Usage Tips

1. **Start Simple:** Begin with strong local FM stations to verify everything works
2. **Check Antenna:** Proper antenna length and positioning greatly affects reception
3. **Monitor Dashboards:** Use Kibana dashboards to visualize captured data
4. **Experiment:** Try different frequencies, modulations, and gain settings
5. **Be Patient:** Some frequencies (like APRS) may have sporadic activity

### ⚖️ Legal Notice

Always comply with local laws regarding radio monitoring:
- Listening to unencrypted signals is generally legal
- Do not decrypt encrypted communications
- Do not retransmit or rebroadcast received signals (RTL-SDR is receive-only)
- Respect privacy and applicable regulations in your jurisdiction

## 🚀 Production Deployment

The API service runs with **Gunicorn**, a production-ready WSGI HTTP server optimized for long-running streaming sessions.

### ⚡ Why Gunicorn?

- ✅ **Production-ready**: Stable, battle-tested WSGI server
- ✅ **Asynchronous I/O**: Gevent workers handle long-running streaming sessions (1-24 hours)
- ✅ **Multiple workers**: Better CPU utilization and concurrent request handling
- ✅ **Auto-recovery**: Workers automatically restart if they crash
- ✅ **Graceful restarts**: No dropped connections during updates

### ⚙️ Configuration

Worker count and other settings can be configured via environment variables in `docker-compose.yml`:

```yaml
environment:
  - GUNICORN_WORKERS=5          # Number of worker processes (default: CPU cores * 2 + 1)
  - GUNICORN_LOG_LEVEL=info     # Log level: debug, info, warning, error
```

Or modify `gunicorn_config.py` directly for advanced settings.

### 🏥 Health Checks

The API includes a health check endpoint for monitoring:

```bash
curl http://localhost:5000/health
```

Returns:
```json
{
  "status": "healthy",
  "service": "radio-transcription-api",
  "timestamp": "2026-01-02T20:00:00.000000",
  "version": "2.0.0"
}
```

### 🛠️ Local Development (Flask Dev Server)

For local development without Docker, the Flask development server can still be used:

```bash
source venv/bin/activate
python api_service.py
```

**Note**: The development server shows a warning that it's not suitable for production. Use Docker with Gunicorn for production deployments.

## 🐳 Docker Container Management

### 🎛️ Portainer

The stack includes **Portainer Community Edition**, a web-based Docker management UI that provides:

- 📊 **Container Management**: Start, stop, restart, and monitor all containers
- 📈 **Resource Monitoring**: CPU, memory, and network usage for each container
- 📝 **Log Viewing**: Real-time container logs with search and filtering
- 🔍 **Image Management**: View, pull, and manage Docker images
- 🌐 **Network Management**: Inspect and manage Docker networks
- 💾 **Volume Management**: View and manage persistent storage volumes
- 📋 **Stack Management**: Deploy and manage multi-container applications

**🌐 Access Portainer:**
- 🌐 HTTP: http://localhost:9000
- 🔒 HTTPS: https://localhost:9443

**⚡ First-Time Setup:**

On first access, Portainer will ask you to create an admin account:

1. Open http://localhost:9000
2. Create admin username and password
3. Select "Docker" as the environment to manage
4. Click "Connect" to start managing your containers

**📋 Common Tasks:**

```bash
# View all running containers
Navigate to: Containers → All containers

# View container logs
Click on container name → Logs

# Restart a container
Click on container name → Restart container

# Monitor resource usage
Dashboard → View real-time stats

# Access container shell
Click on container name → Console → Connect
```

**💡 Why Portainer?**

- ✅ **Visual Overview**: See all containers, images, volumes, and networks at a glance
- ✅ **Easy Troubleshooting**: Quick access to logs and container stats
- ✅ **No CLI Required**: Manage Docker without memorizing commands
- ✅ **Persistent Configuration**: Stores settings in a Docker volume
- ✅ **Lightweight**: Minimal resource overhead (~50 MB memory)

## 🔐 Secrets Management

This project uses **Docker Secrets** for secure credential management, similar to Kubernetes Secrets.

### 🔒 Why Docker Secrets?

- **Security**: Passwords are stored in separate files, not in docker-compose.yml
- **Git-safe**: Secret files are automatically excluded from version control
- **Kubernetes-like**: Familiar pattern if you're used to K8s
- **Auditable**: Easy to track which services use which secrets

### ⚡ Quick Setup

Run the setup script to generate all required secrets:

```bash
./scripts/setup-elk-security.sh
```

This creates:
- Strong random passwords for all ELK services
- Secret files in the `.secrets/` directory
- Proper file permissions (600 - owner read/write only)

**⚠️ Important**: Save the displayed credentials to your password manager!

### 📁 Secret Files

The ELK credentials are stored in:

**ELK Stack Secrets** (`.secrets/` - created automatically):
```
.secrets/
├── elasticsearch_password.txt
├── kibana_password.txt
├── logstash_password.txt
├── beats_password.txt
└── README.md
```

**Note**: ELK passwords are automatically configured in `.env.elk` and injected via Docker Secrets at runtime using entrypoint wrappers. See `.secrets/README.md` for details.

### ⚙️ How It Works

Docker mounts secret files into containers at `/run/secrets/`. The application reads secrets automatically:

```python
def read_secret(secret_name: str) -> Optional[str]:
    secret_path = Path(f'/run/secrets/{secret_name}')
    if secret_path.exists():
        return secret_path.read_text().strip()
    return None
```

### 👀 Viewing Your Credentials

```bash
cat .secrets/elasticsearch_password.txt
cat .env.elk
```

### 🔄 Changing Passwords

1. Regenerate credentials:
   ```bash
   ./scripts/setup-elk-security.sh
   ```

2. Restart the services:
   ```bash
   docker compose restart
   ```

## 🔒 API Security

The Radio Transcription API uses **API key authentication** to protect all endpoints (except `/health`).

### 🔑 Why API Keys?

- **Access Control**: Prevent unauthorized access to your radio monitoring system
- **Audit Trail**: Track which API key was used for each request
- **Multiple Keys**: Issue separate keys for different integrations (scripts, services, etc.)
- **Revocable**: Disable compromised keys without changing all credentials

### ⚙️ Setup API Keys

**✨ Automatic (Recommended):**

Run the setup script which automatically generates API keys:
```bash
./setup.sh
```

The script will:
1. Generate two secure API keys (32-byte random tokens)
2. Add them to your `.env` file as `API_KEYS=key1,key2`
3. Display the keys for you to save

**🔧 Manual:**

Generate API keys manually:
```bash
python3 scripts/generate_api_keys.py
```

Add the output to your `.env` file:
```bash
# API Security
API_KEYS=hAqaR34FS4oSanOQCiijqXhEd8bCIy6Z7L1CYrvX5Ns,VPdlHcd6qHBDR4luLGGyK_PufpH__aEhDX4W6v0vIN8
```

**Important:** Save your API keys to a password manager! You'll need them for all API requests.

### 🔑 Using API Keys

All API requests (except `/health`) require the `X-API-Key` header:

```bash
curl -X POST http://localhost:5000/capture \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 30
  }'
```

**Without API key:**
```bash
# Returns 401 Unauthorized
curl -X POST http://localhost:5000/capture \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### 🌐 Public Endpoints

The following endpoints do **not** require authentication:
- `GET /health` - Health check for monitoring

All other endpoints require a valid API key.

### 🛡️ Container Security

The Docker container runs as a **non-root user** (`radiouser`, UID 1000) for enhanced security:

- **Principle of Least Privilege**: Service runs with minimal permissions
- **USB Access**: User is member of `plugdev` and `dialout` groups for SDR hardware access
- **No root required**: Application processes cannot escalate privileges

This is automatically configured in the Dockerfile and requires no user action.

### ✅ Security Best Practices

1. **Never commit `.env`** to version control (already in `.gitignore`)
2. **Rotate API keys periodically** by regenerating and updating `.env`
3. **Use HTTPS in production** with a reverse proxy (nginx, Caddy)
4. **Enable rate limiting** for production deployments
5. **Monitor access logs** in Elasticsearch for suspicious activity
6. **Enable X-Pack Security** for Elasticsearch/Kibana in production

## 🛠️ Manual Installation

### 📦 System Dependencies

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

### 🐍 Python Dependencies

```bash
pip install -r requirements.txt
```

### ▶️ Start Services

1. **Start Flask API**
   ```bash
   python api_service.py
   ```

2. **Serve Web Interface** (in another terminal)
   ```bash
   python -m http.server 8080
   ```

## 📖 Usage

### 🌐 Web Interface

**🎙️ Voice/APRS/POCSAG Modes:**
1. Open http://localhost:8080 in your browser
2. Use preset buttons or enter custom frequency
3. Select modulation type (FM, AM, USB, LSB)
4. Set recording duration and gain
5. Click "Start Recording & Transcription"
6. Wait for the transcription to complete

**📡 Repeater Activity Scanning (NEW):**
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

### 💻 Command Line

**📻 Capture radio signal:**
```bash
# The sdr_hardware.py module automatically detects HackRF or RTL-SDR
# Use via API service (recommended) or import in Python scripts

# Example using Python API:
from sdr_hardware import get_sdr_instance

# Auto-detect hardware and capture
capture = get_sdr_instance(frequency=100_000_000, sample_rate=2_000_000, gain=20)
capture.capture_audio(duration=30, output_file='recordings/capture.wav', modulation='FM')
```

**🎤 Transcribe audio:**
```bash
python transcription_service.py \
    --input recordings/capture.wav \
    --model base \
    --output recordings/capture.json
```

### 🔌 API Endpoints

**⚠️ Note:** All endpoints (except `/health`) require the `X-API-Key` header. See [API Security](#api-security) section.

**📻 Capture only:**
```bash
curl -X POST http://localhost:5000/capture \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 30,
    "gain": 20
  }'
```

**🎤 Transcribe only:**
```bash
curl -X POST http://localhost:5000/transcribe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "audio_file": "recordings/capture_20250101_120000.wav"
  }'
```

**🎙️ Capture and transcribe (Voice mode):**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 30,
    "gain": 20,
    "language": "en",
    "mode": "voice"
  }'
```

**📍 Capture and decode APRS:**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "frequency": 144800000,
    "modulation": "FM",
    "duration": 300,
    "gain": 20,
    "mode": "aprs"
  }'
```

**🔍 Search APRS messages:**
```bash
curl -X GET "http://localhost:5000/aprs/search?callsign=N0CALL&limit=50" \
  -H "X-API-Key: your-api-key-here"
```

**📊 Get APRS statistics:**
```bash
curl -X GET "http://localhost:5000/aprs/stats" \
  -H "X-API-Key: your-api-key-here"
```

**🗺️ Get APRS map data (GeoJSON):**
```bash
curl -X GET "http://localhost:5000/aprs/map" \
  -H "X-API-Key: your-api-key-here"
```

**📟 Capture and decode POCSAG:**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "frequency": 147325000,
    "modulation": "FM",
    "duration": 300,
    "gain": 20,
    "mode": "pocsag"
  }'
```

**🔍 Search POCSAG messages:**
```bash
curl -X GET "http://localhost:5000/pocsag/search?address=1234567&limit=50" \
  -H "X-API-Key: your-api-key-here"
```

**📊 Get POCSAG statistics:**
```bash
curl -X GET "http://localhost:5000/pocsag/stats" \
  -H "X-API-Key: your-api-key-here"
```

**📝 Get recent POCSAG messages:**
```bash
curl -X GET "http://localhost:5000/pocsag/messages?limit=20" \
  -H "X-API-Key: your-api-key-here"
```

**📡 Start repeater activity scan:**
```bash
curl -X POST http://localhost:5000/scan-repeaters \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "duration_per_repeater": 120,
    "band": "2m",
    "canton": "ZH",
    "gain": 20
  }'
```

**📊 Get scan progress:**
```bash
curl -X GET "http://localhost:5000/scan-repeaters/1/progress" \
  -H "X-API-Key: your-api-key-here"
```

**📋 List available repeaters:**
```bash
curl -X GET "http://localhost:5000/repeaters?band=2m&canton=ZH" \
  -H "X-API-Key: your-api-key-here"
```

**📈 Get repeater activity summary:**
```bash
curl -X GET "http://localhost:5000/repeater-activity/summary?hours=24&limit=10" \
  -H "X-API-Key: your-api-key-here"
```

## ⚙️ Configuration

### 🔧 Environment Variables

The project includes a **comprehensive `.env.example`** file with all configuration options, helpful comments, and security best practices.

**⚡ Quick Setup:**
```bash
# 1. Copy the template
cp .env.example .env

# 2. Generate API keys
python3 scripts/generate_api_keys.py

# 3. Generate ELK credentials (if using full stack)
./setup-elk-security.sh

# 4. Edit .env with your generated values
nano .env
```

**🔑 Key Configuration Categories:**

The `.env.example` file (247 lines) includes complete documentation for:

- ✅ **HackRF/RTL-SDR Configuration** - Frequency, sample rate, modulation, gain
- ✅ **API Security** - API keys for authentication (REQUIRED for production)
- ✅ **Whisper Transcription** - Model size, device (CPU/GPU), compute type
- ✅ **Elasticsearch/ELK Stack** - Connection URLs, credentials, index configuration
- ✅ **Redis** - Session management for streaming decoders
- ✅ **Logstash Pipelines** - Separate endpoints for captures, APRS, POCSAG, repeater data
- ✅ **Streaming Decoders** - Session timeouts, concurrent limits
- ✅ **Repeater Scanner** - Scan limits, session cleanup
- ✅ **Flask/Gunicorn** - Production WSGI server configuration

**📝 Example: Essential Variables**
```bash
# API Security (REQUIRED for production)
# Generate with: python3 scripts/generate_api_keys.py
API_KEYS=your-generated-key-1,your-generated-key-2

# Radio Configuration
DEFAULT_FREQUENCY=100000000      # 100 MHz
DEFAULT_SAMPLE_RATE=2000000      # 2 MHz
DEFAULT_MODULATION=FM
DEFAULT_GAIN=20                  # 0-40 dB (HackRF), 0-50 dB (RTL-SDR)

# Whisper Configuration
WHISPER_MODEL=small              # tiny, base, small, medium, large
                                 # Recommended: small (good accuracy, lower RAM)
WHISPER_DEVICE=cpu               # cpu or cuda (GPU)
WHISPER_COMPUTE_TYPE=int8        # int8 (fastest), float16, float32

# Elasticsearch Configuration
ELASTICSEARCH_HOSTS=http://elasticsearch:9200
ELASTICSEARCH_URL=http://elastic:${ELASTIC_PASSWORD}@elasticsearch:9200

# Redis Configuration (for streaming sessions)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

RADIO_API_KEY=your-api-key-here  # Use one of your API_KEYS
```

**💡 See `.env.example` for:**
- Complete variable list (50+ variables documented)
- Detailed explanations for each option
- Security best practices and warnings
- Docker vs. manual setup differences
- Quick start guide and examples

### 📻 Frequency Presets

The web interface includes common frequency presets:

**🎙️ Voice Transcription:**
- **FM Radio**: 88.5 MHz (FM)
- **Flugfunk (Aviation)**: 118.00 MHz (AM)
- **Amateur 2m**: 145.500 MHz (FM)
- **Amateur 70cm**: 433.50 MHz (FM)
- **PMR**: 446.00625 MHz (FM)

**📍 APRS Decoding:**
- **APRS Europe**: 144.800 MHz (FM) - Default
- **APRS North America**: 144.390 MHz (FM)
- **APRS Japan**: 144.660 MHz (FM)
- **APRS Australia**: 145.175 MHz (FM)

**📟 POCSAG Pager Decoding:**
- **Switzerland**: 147.325 MHz (FM) - Primary Swiss pager frequency
- **Preset 2**: 466.075 MHz (FM)
- **Preset 3**: 439.9875 MHz (FM)
- **Preset 4**: 161.425 MHz (FM)
- **Custom**: Enter your own frequency

Note: POCSAG frequency presets can be customized in `web_interface.html`. Consult your local frequency allocation guides for active pager frequencies in your region.

## 📊 Modulation Types

- **FM (Frequency Modulation)**: Used for broadcast radio, amateur radio, marine VHF
- **AM (Amplitude Modulation)**: Used for AM broadcast radio, aviation
- **USB (Upper Sideband)**: Used for HF amateur radio, marine SSB
- **LSB (Lower Sideband)**: Used for HF amateur radio below 10 MHz

## 🔧 Troubleshooting

### 📡 SDR Hardware Not Detected

**🔍 Check HackRF One:**
```bash
# Verify HackRF is connected
hackrf_info

# Should output: "Serial number: 0x..."
# If not found, check USB connection and permissions
```

**🔍 Check RTL-SDR:**
```bash
# Verify RTL-SDR is connected
rtl_test -t

# Should output: "Found Rafael Micro R820T tuner" or similar
# Press Ctrl+C to stop the test
```

**🔧 Fix USB Permissions (Linux):**
```bash
# Add user to plugdev group
sudo usermod -a -G plugdev $USER

# Log out and back in

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**🌐 Check in Web Interface:**
- Open http://localhost:8080
- Look for SDR indicator at top of page
- Should show: "✅ SDR: HACKRF (1.0-6000 MHz)" or "✅ SDR: RTLSDR (24.0-1766 MHz)"
- If red error message, SDR not detected

### ⚠️ Frequency Out of Range Error

**❌ Error:** "Frequency X MHz is out of range for RTL-SDR"

**✅ Solution:**
- RTL-SDR only supports 24-1766 MHz
- For frequencies outside this range, use HackRF One
- Or choose a different frequency within RTL-SDR range

**💡 Common Workarounds:**
- HF shortwave (<24 MHz): Requires HackRF One or upconverter for RTL-SDR
- Microwave (>1.766 GHz): Requires HackRF One

### 🔇 No Audio Captured

- Check antenna is connected
- Verify frequency is correct
- Increase RF gain
- Try different modulation type
- Check for nearby interference

### ❌ Transcription Fails

- Ensure audio file exists and is valid WAV format
- Check faster-whisper is installed correctly
- Try different Whisper model (tiny for speed, large for accuracy)
- Verify audio contains speech

### 🐳 Docker USB Access Issues

```bash
# USB device access is configured in docker-compose.yml
# If you need to specify a specific USB device:
docker run --device=/dev/bus/usb/XXX/YYY ...
```

## 🚀 Advanced Usage

### 🔌 Integration with Other Services

The API can be integrated with:
- Home automation systems
- Monitoring dashboards
- Database logging
- Alert systems
- Machine learning pipelines

## 📁 File Structure

```
.
├── sdr_hardware.py                  # SDR hardware abstraction (HackRF + RTL-SDR)
├── transcription_service.py         # faster-whisper transcription
├── aprs_decoder_service.py          # APRS decoder using direwolf
├── pocsag_decoder_service.py        # POCSAG decoder using multimon-ng
├── repeater_activity_analyzer.py    # Repeater activity signal processing
├── api_service.py                   # Flask REST API with blueprint registration
├── elasticsearch_service.py         # Elasticsearch client and indexing service
├── session_store.py                 # Shared session_manager instance (avoids circular imports)
├── streaming_decoder_service.py     # Real-time APRS/POCSAG streaming decoders
├── web_interface.html               # Web control panel (tabbed: Voice/APRS/POCSAG/Repeater)
├── blueprints/                      # Modular API endpoint blueprints
│   ├── __init__.py                  # Blueprint package initialization
│   ├── health.py                    # Health check endpoint
│   ├── sdr.py                       # SDR hardware detection
│   ├── capture.py                   # Audio capture endpoints
│   ├── aprs.py                      # APRS decoder endpoints
│   ├── pocsag.py                    # POCSAG decoder endpoints
│   ├── repeater.py                  # Repeater scanning endpoints
│   └── streaming.py                 # Streaming decoder endpoints
├── scripts/
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
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image definition
├── mqtt-bridge/
│   └── Dockerfile               # Dedicated image for MQTT-to-Logstash bridge
├── docker-compose.yml           # Docker Compose with ELK stack
├── .env.example                     # Environment variables template
├── .gitignore                      # Git ignore rules
├── README.md                        # This file
└── USER_MANUAL.md                  # Complete user documentation
```

## 📚 API Reference

**🔒 Authentication:** All endpoints (except `/health`) require the `X-API-Key` header.

### POST /capture
Capture radio signal to WAV file.

**Headers:**
```
Content-Type: application/json
X-API-Key: your-api-key-here
```

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

**Headers:**
```
Content-Type: application/json
X-API-Key: your-api-key-here
```

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

**Headers:**
```
Content-Type: application/json
X-API-Key: your-api-key-here
```

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

## 💾 Database Features

### 🗄️ Elasticsearch Storage

All radio data is stored in Elasticsearch time-series indices with:
- Full metadata (frequency, modulation, duration, gain, sample rate, SDR type)
- Complete transcription text with multi-language analyzers
- Language detection with confidence scores
- Flexible JSON document structure
- Automatic @timestamp field for time-series queries
- UUID-based document IDs (_id field)

**📅 Daily Index Patterns:**
- **radio-captures-YYYY.MM.DD**: Voice transcription captures
- **radio-aprs-YYYY.MM.DD**: APRS packet messages with geo_point positions
- **radio-pocsag-YYYY.MM.DD**: POCSAG pager messages
- **radio-repeater-activity-YYYY.MM.DD**: Repeater activity records with nested transmissions
- **radio-metrics-YYYY.MM.DD**: System and application metrics

**✨ Index Features:**
- Optimized mappings for each data type
- Index Lifecycle Management (ILM) for automatic retention
- Keyword + text multi-fields for flexible querying
- Geo-spatial indexing for APRS positions

### 🔍 Full-Text Search

The database supports powerful text search capabilities:

```bash
# Simple text search
curl "http://localhost:5000/search?text=amateur"

# Case-insensitive partial matching
curl "http://localhost:5000/search?text=weat"  # matches "weather"
```

### 🎛️ Advanced Filtering

Combine multiple filters for precise queries:

```bash
# FM captures in German language containing "antenna"
curl "http://localhost:5000/search?modulation=FM&language=de&text=antenna"

# All amateur 2m band captures (144-146 MHz)
curl "http://localhost:5000/search?frequency=145500000"
```

### 🔄 Database Migration

Import existing JSON transcription files into the database:

**🚀 Using the migration script:**
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

### 💾 Data Backup and Export

**📤 Export data from Elasticsearch:**
```bash
# Export all captures from last 30 days
curl -X GET "localhost:9200/radio-captures-*/_search?pretty&size=10000" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"range": {"@timestamp": {"gte": "now-30d"}}}}' \
  > captures_backup.json

# Export APRS data
curl -X GET "localhost:9200/radio-aprs-*/_search?pretty&size=10000" > aprs_backup.json
```

**📸 Snapshot and Restore (recommended for large datasets):**
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

## 📊 Kibana Dashboards

### 🚀 Automatic Dashboard Import

The system includes pre-configured Kibana dashboards that are **automatically imported** during setup.

**Automated Import (Recommended):**
```bash
# Run after docker compose up -d
./scripts/post-docker-setup.sh
```

This script automatically:
- ✅ Waits for Kibana to be ready
- 📊 Imports all dashboard NDJSON files
- ✅ Creates index patterns (radio-captures-\*, radio-aprs-\*, radio-pocsag-\*, radio-repeater-activity-\*)
- 📈 Imports all visualizations and dashboards

**Manual Import (Alternative):**
```bash
# Import dashboards at any time
./scripts/import-kibana-dashboards.sh

# Or use Python script directly
python3 scripts/import_kibana_dashboards.py
```

**Dashboard Files Location:**
- `monitoring/kibana/dashboards/index-patterns.ndjson` - Index patterns for all data types
- `monitoring/kibana/dashboards/radio-overview-dashboard.ndjson` - Main radio monitoring dashboard
- `monitoring/kibana/dashboards/aprs-dashboard.ndjson` - APRS activity with geospatial map
- `monitoring/kibana/dashboards/pocsag-dashboard.ndjson` - POCSAG pager monitoring
- `monitoring/kibana/dashboards/repeater-activity-dashboard.ndjson` - Repeater activity analytics

### 🌐 Accessing Kibana

Open http://localhost:5601 in your browser.

**Login Credentials:**
- Username: `elastic`
- Password: See `ELASTIC_PASSWORD` in `.env` or `.env.elk`

**First-Time Access:**
1. Log in with elastic credentials
2. Navigate to **Analytics → Dashboard**
3. All dashboards are pre-imported and ready to use!

### 📈 Available Dashboards

#### 🎙️ Radio Captures Explorer
**🌐 Access**: Kibana → Discover → Index Pattern: `radio-captures-*`

**✨ Features:**
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

#### 📍 APRS Monitoring Dashboard
**🌐 Access**: Kibana → Dashboard → APRS Activity

**📊 Visualizations:**
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

#### 📡 Repeater Activity Dashboard
**🌐 Access**: Kibana → Dashboard → Repeater Activity Monitoring

**📊 Visualizations:**
- **Most Active Repeaters (24h)**: Data table aggregated by callsign with avg activity percentage
- **Activity by Band**: Pie chart showing 2m vs 70cm activity distribution
- **Scan Rate**: Line chart showing scan operations over time
- **Recent Scans**: Data table of last 100 repeater activity records

**💻 Aggregation Examples (Kibana Dev Tools):**
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

### 🎨 Creating Custom Dashboards

Create custom visualizations and dashboards in Kibana:

1. Go to **Kibana → Visualize → Create visualization**
2. Select visualization type (Line, Bar, Pie, Data Table, Metric, Map, etc.)
3. Choose index pattern (`radio-captures-*`, `radio-aprs-*`, etc.)
4. Configure metrics and buckets/aggregations
5. Save visualization and add to dashboard

**📝 Example Aggregation - Recent FM Captures:**
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

## 🛠️ Kibana Dev Tools

### 🌐 Accessing Dev Tools

Open Kibana → Dev Tools (http://localhost:5601/app/dev_tools#/console) for direct Elasticsearch API access.

### 💻 Using the Console

**📚 Browse Indices:**
```json
# List all radio indices
GET /_cat/indices/radio-*?v

# View index mapping
GET /radio-captures-*/_mapping

# Count documents
GET /radio-captures-*/_count
```

**🔍 Run Queries:**
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

**📤 Export Data:**
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

**⚙️ Index Management:**
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

### ✨ Kibana Features

- ✅ Discover: Interactive log exploration with full-text search
- ✅ Visualize: Create charts, graphs, maps, and metrics
- ✅ Dashboard: Combine visualizations into comprehensive dashboards
- ✅ Dev Tools: Console for direct Elasticsearch API access
- ✅ Index Management: Lifecycle policies, rollover, and retention
- ✅ Canvas: Pixel-perfect data presentations
- ✅ Maps: Geospatial visualization for APRS positions
- ✅ Alerting: Set up alerts based on query conditions (requires X-Pack)

## 🧪 Development & Testing

### 🔄 CI/CD Pipeline

The project includes a comprehensive GitHub Actions CI/CD pipeline that runs on every push:

**⚙️ Pipeline Steps:**
1. ✅ **Code Checkout**: Clean checkout with full git history
2. ✅ **MyPy Type Checking**: Static type analysis with strict mode
3. ✅ **Pytest Test Suite**: 67 tests covering all major components
4. ✅ **Docker Build**: Verification that Docker image builds successfully

**📊 Test Coverage:**
- **67 Tests Total** across 3 test suites
- **API Tests (25)**: Flask endpoints, authentication, error handling
- **SDR Hardware Tests (26)**: HackRF/RTL-SDR detection, capture, validation
- **TranscriptionService Tests (16)**: Whisper integration, file handling
- **Current Coverage**: 27% (target: 15% minimum)

### 🧪 Running Tests Locally

**▶️ Run all tests:**
```bash
pytest
```

**📊 Run with coverage:**
```bash
./scripts/run_coverage.sh
```

**🔍 Run type checking:**
```bash
./scripts/run_mypy.sh
```

**🎯 Run specific test file:**
```bash
pytest tests/test_api_service.py -v
```

### 🧪 Test Environment

Tests use an isolated environment with:
- **Mocked SDR Hardware**: No physical HackRF/RTL-SDR required
- **Mocked Whisper**: Simulated transcription without CUDA
- **Temporary Directories**: Session-scoped temp dir for all test files
- **Disabled API Authentication**: No API keys needed for tests

### 🛠️ Development Setup

**1️⃣ Clone and install dependencies:**
```bash
git clone <repository-url>
cd my-project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2️⃣ Run tests to verify setup:**
```bash
pytest
```

**3️⃣ Run MyPy type checking:**
```bash
./scripts/run_mypy.sh
```

**4️⃣ Start development server:**
```bash
python api_service.py
```

### ✨ Code Quality

**🔒 Type Safety:**
- Full MyPy strict mode compliance
- Type hints for all functions and methods
- Generic types for collections and arrays
- Optional types for nullable values

**🧪 Testing:**
- Comprehensive unit and integration tests
- Mocked external dependencies (SDR hardware, Whisper)
- Isolated test environment
- Automatic cleanup

**🔄 CI/CD:**
- Automated testing on every push
- Type checking enforced
- Docker build verification
- Coverage reporting

### 📂 Project Structure

```
my-project/
├── api_service.py                    # Main Flask API with Gunicorn
├── transcription_service.py          # Whisper transcription service
├── sdr_hardware.py                   # SDR hardware abstraction (HackRF/RTL-SDR)
├── aprs_decoder_service.py           # APRS packet decoder
├── pocsag_decoder_service.py         # POCSAG pager decoder
├── repeater_activity_analyzer.py     # Swiss repeater scanner
├── elasticsearch_service.py          # Elasticsearch client
├── streaming_decoder_service.py      # Real-time streaming decoder
├── gunicorn_config.py               # Production WSGI config
├── blueprints/                      # Modular API endpoint blueprints
│   ├── __init__.py                  # Blueprint package initialization
│   ├── health.py                    # Health check endpoint
│   ├── sdr.py                       # SDR hardware detection
│   ├── capture.py                   # Audio capture endpoints
│   ├── aprs.py                      # APRS decoder endpoints
│   ├── pocsag.py                    # POCSAG decoder endpoints
│   ├── repeater.py                  # Repeater scanning endpoints
│   └── streaming.py                 # Streaming decoder endpoints
├── requirements.txt                  # Python dependencies
├── pytest.ini                        # Pytest configuration
├── mypy.ini                          # MyPy type checker config
├── Dockerfile                        # Container definition
├── docker-compose.yml               # Docker stack (API + ELK + all services)
├── tests/                           # Test suite
│   ├── conftest.py                  # Pytest fixtures and configuration
│   ├── test_api_service.py         # API endpoint tests
│   ├── test_sdr_hardware.py        # SDR hardware tests
│   └── test_transcription_service.py # Transcription tests
├── scripts/                         # Utility scripts
│   ├── setup.sh                    # Initial setup script
│   ├── start.sh                    # Start all services
│   ├── setup-elk-security.sh       # Generate ELK credentials
│   ├── run_mypy.sh                 # Type checking
│   ├── run_coverage.sh             # Test coverage
│   └── test_system.sh              # System integration test
├── .github/workflows/ci.yml        # GitHub Actions CI/CD
└── monitoring/kibana/dashboards/   # Kibana dashboard definitions
```

## ⚖️ Legal Notice

This software is intended for use with authorized radio frequencies only. Users are responsible for:
- Complying with local radio regulations
- Obtaining required licenses for transmission (if applicable)
- Only monitoring frequencies they are legally permitted to access
- Following spectrum allocation rules in their jurisdiction

**This is a receive-only application and does not transmit radio signals.**

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## 💬 Support

For issues and questions:
- Check the Troubleshooting section
- Review complete USER_MANUAL.md for detailed documentation
- Review HackRF documentation: https://hackrf.readthedocs.io/
- Review RTL-SDR documentation: https://www.rtl-sdr.com/about-rtl-sdr/
- Review faster-whisper documentation: https://github.com/guillaumekln/faster-whisper
- Review Elasticsearch documentation: https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
- Review Kibana documentation: https://www.elastic.co/guide/en/kibana/current/index.html
- Review Logstash documentation: https://www.elastic.co/guide/en/logstash/current/index.html

## 🙏 Acknowledgments

- HackRF One by Great Scott Gadgets
- RTL-SDR project and community
- faster-whisper by Guillaume Klein
- Whisper by OpenAI
- Elasticsearch by Elastic
- Logstash by Elastic
- Kibana by Elastic
- Metricbeat by Elastic
