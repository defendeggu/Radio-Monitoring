# Radio Transcription System - User Manual

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Using the Web Interface](#using-the-web-interface)
4. [Monitoring with Grafana](#monitoring-with-grafana)
5. [Understanding Results](#understanding-results)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## Introduction

The Radio Transcription System is a complete application that allows you to:
- Capture radio signals from a HackRF One software-defined radio (SDR) device
- Automatically transcribe speech from the captured audio
- Monitor system performance and track operations

### What You Can Do

- Listen to FM radio stations and get text transcriptions
- Monitor aviation communications (AM mode)
- Capture amateur radio transmissions
- Record and transcribe PMR/walkie-talkie communications
- Track system performance through visual dashboards

---

## Getting Started

### Prerequisites

Before using the system, ensure:
1. Your HackRF One device is connected via USB
2. An appropriate antenna is connected to the HackRF
3. All services are running (see Quick Start below)

### Starting the System

**Option 1: Using Docker (Recommended)**

Open a terminal and run:

```bash
cd /home/spia/my-project
docker-compose up -d
```

This starts all services in the background.

**Option 2: Check if System is Running**

```bash
docker-compose ps
```

You should see services running on these ports:
- **Web Interface**: Port 8080
- **API Service**: Port 5000
- **Grafana**: Port 3000
- **Prometheus**: Port 9090
- **N8N**: Port 5678

### Accessing the Interfaces

Once started, open your web browser and navigate to:
- **Main Control Panel**: http://localhost:8080
- **Grafana Monitoring**: http://localhost:3000 (login: admin/admin)

---

## Using the Web Interface

### Overview

The web interface is your main control panel for capturing and transcribing radio signals. Access it at **http://localhost:8080**.

### Interface Layout

The control panel consists of several sections:

#### 1. Quick Preset Buttons (Top Section)

Five preset buttons for common frequencies:

| Button | Frequency | Modulation | Use Case |
|--------|-----------|------------|----------|
| **FM Radio** | 88.5 MHz | FM | Commercial FM broadcast radio |
| **Flugfunk** | 118.00 MHz | AM | Aviation communications |
| **Amateur 2m** | 145.500 MHz | FM | VHF amateur radio calling frequency |
| **Amateur 70cm** | 433.50 MHz | FM | UHF amateur radio |
| **PMR** | 446.00625 MHz | FM | Personal Mobile Radio / Walkie-talkies |

**How to use presets:**
- Simply click any preset button
- The frequency and modulation fields will automatically fill
- Adjust duration and gain if needed
- Click "Start Recording & Transcription"

#### 2. Manual Configuration Fields

**Frequency (Hz)**
- Enter the exact frequency you want to monitor in Hertz
- Examples:
  - 100 MHz = `100000000` Hz
  - 162.55 MHz = `162550000` Hz
  - 433.5 MHz = `433500000` Hz
- Tip: Most frequencies are in millions, so add six zeros to MHz values

**Modulation**
- **FM (Frequency Modulation)**: Use for broadcast radio, most amateur radio, marine VHF
- **AM (Amplitude Modulation)**: Use for aviation, AM broadcast radio
- **USB (Upper Sideband)**: Use for HF amateur radio, marine SSB
- **LSB (Lower Sideband)**: Use for HF amateur radio below 10 MHz

**Duration (seconds)**
- How long to record the signal (5-300 seconds)
- Recommended: 30 seconds for general use
- Longer durations = more chance to capture speech but slower processing
- Shorter durations = faster results but might miss content

**RF Gain (dB)**
- Signal amplification level (0-47 dB)
- Default: 20 dB
- Increase if signals are weak (no audio captured)
- Decrease if you hear distortion or clipping
- Start at 20 and adjust based on results

**Language (optional)**
- Leave blank for automatic language detection
- Enter language code for better accuracy:
  - `en` - English
  - `de` - German
  - `es` - Spanish
  - `fr` - French
  - `it` - Italian

### Step-by-Step: Making Your First Recording

1. **Choose Your Target**
   - Click a preset button (e.g., "FM Radio") OR
   - Enter a custom frequency manually

2. **Verify Settings**
   - Check that modulation matches your target
   - Set recording duration (30 seconds is a good start)
   - Keep gain at 20 dB initially

3. **Start Recording**
   - Click the blue "Start Recording & Transcription" button
   - The button will show a loading animation
   - Status message appears: "Starting capture on X.XXX MHz..."

4. **Wait for Processing**
   - The system will:
     1. Record audio for the specified duration
     2. Process the audio file
     3. Transcribe any speech detected
   - Total time = recording duration + ~10-30 seconds processing

5. **View Results**
   - Success message appears when complete
   - Transcription text displays in a box below
   - Metadata shows: language detected, duration, frequency, modulation

### Understanding the Status Messages

**Blue (Info)**:
- "Starting capture on X.XXX MHz..." - Recording is in progress

**Green (Success)**:
- "Transcription completed successfully!" - Everything worked

**Red (Error)**:
- Connection errors - Check if services are running
- HackRF errors - Check if device is connected
- Transcription errors - Audio might not contain speech

### Using the Results Section

After successful transcription, you'll see:

**Transcription Text**
- The detected speech converted to text
- If no speech detected: "No text detected"

**Metadata Cards**
- **Language**: Auto-detected language and confidence
- **Duration**: Length of audio processed
- **Frequency**: Frequency you recorded
- **Modulation**: Modulation type used

### Buttons

**Start Recording & Transcription**
- Begins the capture and transcription process
- Disabled while processing (prevents multiple simultaneous recordings)

**Reset**
- Clears all fields back to defaults
- Hides status and result sections
- Use this to start fresh

---

## Monitoring with Grafana

### Accessing Grafana

1. Open your web browser
2. Navigate to **http://localhost:3000**
3. Login with:
   - **Username**: `admin`
   - **Password**: `admin`
4. (Optional) Change password when prompted

### What is Grafana?

Grafana is a monitoring dashboard that shows you:
- How many recordings you've made
- Success vs. failure rates
- System performance (CPU, memory, network)
- Response times and latency
- Historical trends over time

### Grafana Interface Overview

**Top Navigation Bar**
- **Search**: Find dashboards and metrics
- **Dashboards**: Browse available dashboards
- **Explore**: Run custom queries
- **Alerting**: View configured alerts

**Left Sidebar**
- **Home**: Return to home page
- **Dashboards**: Browse and create dashboards
- **Data Sources**: View configured data sources (Prometheus)

### Available Metrics

The system automatically tracks:

#### 1. API Performance Metrics
- **Total Requests**: How many API calls were made
- **Request Duration**: How long requests take to complete
- **Error Rates**: Percentage of failed requests
- **Request/Response Sizes**: Data payload sizes

#### 2. Radio Operation Metrics
- **Total Captures**: Number of radio recordings made
- **Captures by Modulation**: Breakdown by FM/AM/USB/LSB
- **Capture Duration**: Time spent recording
- **Success/Failure Rates**: How many captures succeeded

#### 3. Transcription Metrics
- **Total Transcriptions**: Number of transcription requests
- **Transcription Duration**: How long transcriptions take
- **Success/Failure Rates**: Transcription success percentage

#### 4. Container Metrics
- **CPU Usage**: Processing power consumption
- **Memory Usage**: RAM utilization
- **Network I/O**: Data transfer rates
- **Disk I/O**: Storage read/write operations

### Creating Your First Dashboard

1. **Access Dashboards**
   - Click the "+" icon in left sidebar
   - Select "Dashboard"
   - Click "Add new panel"

2. **Select a Metric**
   - In the query editor at bottom, you'll see "Prometheus" as data source
   - Enter a metric name, for example:
     - `http_requests_total` - Total HTTP requests
     - `radio_captures_total` - Total radio captures
     - `transcription_requests_total` - Total transcriptions

3. **Customize Visualization**
   - Right panel shows visualization options
   - Choose graph type: Time series, Gauge, Stat, Table, etc.
   - Set title and description
   - Configure colors and thresholds

4. **Save Dashboard**
   - Click "Save" icon at top
   - Enter dashboard name
   - Click "Save"

### Useful Pre-Built Queries

Copy these into the Grafana query editor:

**Request Rate (requests per second)**
```promql
rate(http_requests_total[5m])
```

**95th Percentile Response Time**
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**Capture Success Rate (percentage)**
```promql
rate(radio_captures_total{status="success"}[5m]) / rate(radio_captures_total[5m]) * 100
```

**Memory Usage by Container**
```promql
container_memory_usage_bytes{name="radio-api"}
```

**CPU Usage Percentage**
```promql
rate(container_cpu_usage_seconds_total[5m]) * 100
```

### Understanding Time Ranges

- **Top-right corner**: Time range selector
- **Common ranges**: Last 5 minutes, 15 minutes, 1 hour, 24 hours
- **Custom range**: Click and select specific start/end times
- **Auto-refresh**: Enable to update dashboard automatically

### Setting Up Alerts

1. **Edit a Panel**
   - Click panel title → Edit

2. **Create Alert**
   - Click "Alert" tab
   - Set conditions (e.g., "when value is above X")
   - Configure notification channels

3. **Example Alert: High Error Rate**
   - Metric: `rate(http_requests_total{status="error"}[5m])`
   - Condition: IS ABOVE 10
   - For: 5 minutes
   - Action: Send notification

### Viewing System Health

**Pre-configured Alerts** (viewable in Prometheus at http://localhost:9090):
- API Down
- High Error Rate (>10% for 5 minutes)
- High Capture Failure Rate (>20%)
- Slow Captures (p95 > 2 minutes)
- High Transcription Failure Rate (>20%)
- Slow Transcriptions (p95 > 1 minute)
- High Memory Usage (>90%)
- High CPU Usage (>80%)

Access Prometheus to view alert status:
1. Go to http://localhost:9090
2. Click "Alerts" in top menu
3. View firing and pending alerts

---

## Understanding Results

### Good Results

**Signs of Successful Capture:**
- Clear transcribed text that makes sense
- Language detected with high confidence
- Duration matches your recording time
- Status shows "success"

**Example Good Result:**
```
Transcription: "Welcome to station FM 88.5, bringing you the best music all day long"
Language: en (English)
Duration: 30.5s
Frequency: 88.5 MHz
Modulation: FM
```

### Poor Results

**"No text detected"**
- No speech was present in the recording
- Only music, noise, or silence was captured
- Solution: Try a different frequency or time when speech is expected

**Garbled or Nonsensical Text**
- Signal was too weak
- Wrong modulation type
- Interference or noise
- Solution: Adjust RF gain, verify modulation, check antenna

**Short Transcription from Long Recording**
- Only part of recording contained speech
- Rest was music or silence
- This is normal - system only transcribes speech

### Interpreting Metadata

**Language Probability**
- >0.9: Very confident
- 0.7-0.9: Fairly confident
- <0.7: Uncertain, might be wrong language

**Duration Mismatch**
- Recording duration: How long you recorded
- Transcription duration: How long the audio file was
- These should match closely

---

## Troubleshooting

### Problem: "Connection refused" or "Cannot connect to API"

**Solution:**
1. Check if services are running:
   ```bash
   docker-compose ps
   ```

2. Start services if stopped:
   ```bash
   docker-compose up -d
   ```

3. Check service logs:
   ```bash
   docker-compose logs api
   ```

### Problem: No Audio Captured / Empty Recording

**Possible Causes & Solutions:**

1. **No antenna connected**
   - Connect appropriate antenna to HackRF

2. **Wrong frequency**
   - Verify frequency is correct for your location
   - FM stations vary by region

3. **RF gain too low**
   - Increase gain to 30-40 dB
   - Try different values

4. **Wrong modulation**
   - FM stations need FM mode
   - Aviation needs AM mode
   - Verify modulation type

### Problem: HackRF Not Detected

**Solution:**
1. Check USB connection:
   ```bash
   hackrf_info
   ```

2. Verify device permissions:
   ```bash
   sudo usermod -a -G plugdev $USER
   ```
   Then log out and back in

3. Restart Docker containers:
   ```bash
   docker-compose restart
   ```

### Problem: Transcription Takes Very Long

**Causes:**
- Long recording duration
- Slow CPU
- Large audio file

**Solutions:**
- Reduce recording duration to 15-30 seconds
- Use smaller Whisper model (edit `.env`: `WHISPER_MODEL=tiny`)
- Be patient - transcription is CPU-intensive

### Problem: Wrong Language Detected

**Solution:**
- Explicitly set language in the web interface
- Enter language code (e.g., "de" for German)
- This improves accuracy significantly

### Problem: Grafana Shows No Data

**Solution:**
1. Make at least one recording first (Grafana needs data to display)

2. Check Prometheus is collecting metrics:
   - Go to http://localhost:9090
   - Click "Status" → "Targets"
   - Verify targets are "UP"

3. Verify data source in Grafana:
   - Go to Configuration → Data Sources
   - Click Prometheus
   - Click "Test" button

### Problem: Web Interface Button Stuck on "Recording & Transcribing..."

**Solution:**
1. Check browser console for errors (F12 → Console tab)

2. Verify API is responding:
   ```bash
   curl http://localhost:5000/health
   ```

3. Refresh the webpage

4. Check API logs:
   ```bash
   docker-compose logs -f api
   ```

---

## Best Practices

### For Best Audio Quality

1. **Use appropriate antenna**
   - FM radio: FM dipole or whip antenna
   - Aviation: VHF air band antenna
   - Different frequencies need different antennas

2. **Start with presets**
   - Presets have tested, working configurations
   - Customize after you understand how it works

3. **Adjust gain carefully**
   - Too low: No signal captured
   - Too high: Distortion and clipping
   - Sweet spot: Usually 15-30 dB

4. **Match modulation to source**
   - FM radio stations = FM mode
   - Aviation = AM mode
   - Amateur radio = mostly FM (check band)

### For Best Transcription Results

1. **Record during active periods**
   - Radio shows with talking (not just music)
   - Aviation: During busy flight times
   - Amateur radio: During nets or contests

2. **Use appropriate duration**
   - 30 seconds is usually sufficient
   - Longer doesn't always mean better
   - Short bursts (15s) work for quick tests

3. **Specify language if known**
   - Improves accuracy significantly
   - Faster processing
   - Better punctuation

### For System Monitoring

1. **Check Grafana regularly**
   - Monitor success rates
   - Identify patterns (busy times, failure spikes)
   - Track resource usage

2. **Review errors**
   - Look at failed captures
   - Adjust settings based on patterns
   - Check alerts in Prometheus

3. **Clean up old recordings**
   - Recordings stored in `recordings/` folder
   - Delete old files to save disk space:
     ```bash
     cd /home/spia/my-project/recordings
     ls -lh  # View files
     rm old_file.wav  # Delete specific files
     ```

### Legal and Ethical Considerations

1. **Only monitor authorized frequencies**
   - Check local regulations
   - Some frequencies require licenses
   - Some communications are protected

2. **Respect privacy**
   - Do not record private communications
   - Do not share transcriptions of personal conversations
   - Use for learning and authorized purposes only

3. **Receive only**
   - This system does NOT transmit
   - Listening is generally legal, transmitting requires licenses
   - Never attempt to transmit without proper authorization

### Frequency Guide by Region

**Note**: Frequencies vary by country and region. Examples below are common but verify locally.

**Public Safety** (Often restricted/encrypted):
- Police: 150-174 MHz, 450-470 MHz
- Fire/EMS: Similar ranges
- May be encrypted or illegal to monitor

**Amateur Radio** (License required to transmit, listening OK):
- 2m band: 144-148 MHz (FM)
- 70cm band: 420-450 MHz (FM)
- HF bands: Various (USB/LSB)

**Aviation** (Listening OK):
- 118-137 MHz (AM)
- Example: 121.5 MHz (Emergency)

**Marine** (Listening OK):
- VHF Marine: 156-162 MHz (FM)
- Example: 156.8 MHz (Channel 16 - Distress/Calling)

**General Public**:
- FM Broadcast: 87.5-108 MHz (FM)
- PMR446: 446 MHz (FM, Europe)
- FRS/GMRS: 462-467 MHz (FM, USA, license-free)

---

## Quick Reference Card

### Common Frequencies (Examples - verify for your location)

| Service | Frequency | Modulation | Gain | Duration |
|---------|-----------|------------|------|----------|
| FM Radio | 88.5-108 MHz | FM | 20 dB | 30s |
| Aviation | 118-137 MHz | AM | 25 dB | 30s |
| Marine VHF | 156-162 MHz | FM | 20 dB | 30s |
| Amateur 2m | 144-148 MHz | FM | 20 dB | 30s |
| Amateur 70cm | 420-450 MHz | FM | 25 dB | 30s |
| PMR446 | 446 MHz | FM | 20 dB | 15s |

### Service Ports

| Service | URL | Credentials |
|---------|-----|-------------|
| Web Interface | http://localhost:8080 | None |
| API | http://localhost:5000 | None |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | None |
| N8N | http://localhost:5678 | admin/admin |
| cAdvisor | http://localhost:8081 | None |

### Essential Commands

```bash
# Start system
docker-compose up -d

# Stop system
docker-compose down

# View logs
docker-compose logs -f

# Restart single service
docker-compose restart api

# Check service status
docker-compose ps

# Check HackRF
hackrf_info
```

---

## Getting Help

If you encounter issues not covered in this manual:

1. **Check logs**
   ```bash
   docker-compose logs -f api
   ```

2. **Verify HackRF connection**
   ```bash
   hackrf_info
   ```

3. **Check system health**
   - Visit http://localhost:5000/health
   - View Prometheus alerts at http://localhost:9090/alerts

4. **Review configuration**
   - Check `.env` file for settings
   - Verify Docker containers are running

5. **Consult documentation**
   - HackRF: https://hackrf.readthedocs.io/
   - faster-whisper: https://github.com/guillaumekln/faster-whisper
   - Grafana: https://grafana.com/docs/

---

## Appendix: Modulation Types Explained

### FM (Frequency Modulation)
- **How it works**: Signal varies the frequency
- **Sound quality**: Excellent, resistant to noise
- **Common uses**:
  - FM broadcast radio
  - Most amateur radio VHF/UHF
  - Marine VHF
  - PMR/FRS/GMRS
- **Bandwidth**: Wider than AM

### AM (Amplitude Modulation)
- **How it works**: Signal varies the amplitude/volume
- **Sound quality**: Good, more susceptible to noise
- **Common uses**:
  - Aviation communications
  - AM broadcast radio
  - Some amateur radio bands
- **Bandwidth**: Narrower than FM

### USB (Upper Sideband)
- **How it works**: Uses upper half of AM signal
- **Sound quality**: More efficient than AM
- **Common uses**:
  - HF amateur radio (above 10 MHz)
  - Marine SSB
  - Long-distance communications
- **Bandwidth**: Half of AM

### LSB (Lower Sideband)
- **How it works**: Uses lower half of AM signal
- **Sound quality**: More efficient than AM
- **Common uses**:
  - HF amateur radio (below 10 MHz)
  - Long-distance communications
- **Bandwidth**: Half of AM

---

**End of User Manual**

*Last Updated: December 2025*
*System Version: 1.0*
