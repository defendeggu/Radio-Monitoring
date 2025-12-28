# Radio Transcription System - User Manual

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Using the Web Interface](#using-the-web-interface)
4. [Database Features](#database-features)
5. [Monitoring with Grafana](#monitoring-with-grafana)
6. [Database Management with pgAdmin](#database-management-with-pgadmin)
7. [Understanding Results](#understanding-results)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

## Introduction

The Radio Transcription System is a complete application that allows you to:
- Capture radio signals from a HackRF One software-defined radio (SDR) device
- Automatically transcribe speech from the captured audio using AI
- Decode APRS (Automatic Packet Reporting System) digital messages
- Store all captures and APRS packets in a PostgreSQL database with full-text search
- Search and analyze historical captures and APRS messages
- Visualize APRS stations on interactive maps
- Monitor system performance and track operations

### What You Can Do

**Voice Transcription:**
- Listen to FM radio stations and get text transcriptions
- Monitor aviation communications (AM mode)
- Capture amateur radio transmissions
- Record and transcribe PMR/walkie-talkie communications

**APRS Packet Decoding:**
- Decode APRS position reports and messages on 144.8 MHz (NA), 144.39 MHz (JP), 145.175 MHz (EU)
- Track amateur radio stations on an interactive map
- Monitor APRS weather stations and telemetry
- Search APRS messages by callsign, type, or content

**Data Analysis:**
- Search through all historical captures by text, frequency, or date
- Analyze frequency usage, language distribution, and APRS statistics
- Track system performance through visual dashboards
- Export and query capture data via REST API

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
- **PostgreSQL Database**: Port 5432
- **Grafana**: Port 3000
- **pgAdmin**: Port 5050
- **Prometheus**: Port 9090
- **N8N**: Port 5678
- **cAdvisor**: Port 8081

### Accessing the Interfaces

Once started, open your web browser and navigate to:
- **Main Control Panel**: http://localhost:8080
- **Grafana Monitoring**: http://localhost:3000 (login: admin/admin)
- **pgAdmin Database Manager**: http://localhost:5050 (login: admin@admin.com/admin)

---

## Using the Web Interface

### Overview

The web interface is your main control panel for capturing and transcribing radio signals. Access it at **http://localhost:8080**.

### Interface Layout

The control panel consists of several sections:

#### 1. Quick Preset Buttons (Top Section)

Eight preset buttons for common frequencies:

**Voice Transcription Presets:**

| Button | Frequency | Modulation | Use Case |
|--------|-----------|------------|----------|
| **FM Radio** | 88.5 MHz | FM | Commercial FM broadcast radio |
| **Flugfunk** | 118.00 MHz | AM | Aviation communications |
| **Amateur 2m** | 145.500 MHz | FM | VHF amateur radio calling frequency |
| **Amateur 70cm** | 433.50 MHz | FM | UHF amateur radio |
| **PMR** | 446.00625 MHz | FM | Personal Mobile Radio / Walkie-talkies |

**APRS Decoding Presets:**

| Button | Frequency | Modulation | Use Case |
|--------|-----------|------------|----------|
| **APRS NA** | 144.800 MHz | FM | APRS in North America |
| **APRS JP** | 144.390 MHz | FM | APRS in Japan |
| **APRS EU** | 145.175 MHz | FM | APRS in Europe |

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
- Note: This field is only shown in Voice Transcription mode

**Processing Mode**
- **Voice Transcription**: Converts speech to text using AI (faster-whisper)
  - Use for: FM radio, aviation, amateur voice, PMR
  - Language field is visible and optional
  - Recommended duration: 30 seconds
- **APRS Decode**: Decodes digital APRS packets (direwolf)
  - Use for: APRS frequencies (144.8 MHz, 144.39 MHz, 145.175 MHz)
  - Language field is hidden (not applicable)
  - Recommended duration: 300 seconds (5 minutes) to capture more packets
- Voice mode is selected by default
- APRS presets automatically switch to APRS mode

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

## APRS Packet Decoding

### What is APRS?

APRS (Automatic Packet Reporting System) is a digital communication protocol used by amateur radio operators to:
- Share real-time position information (GPS coordinates)
- Send text messages between stations
- Broadcast weather station data
- Report telemetry from vehicles, balloons, and remote sensors

### Using APRS Mode

#### Step-by-Step: Decoding APRS Packets

1. **Click an APRS Preset**
   - **APRS NA** (144.800 MHz) - North America
   - **APRS JP** (144.390 MHz) - Japan
   - **APRS EU** (145.175 MHz) - Europe
   - The mode automatically switches to "APRS Decode"
   - Duration automatically sets to 300 seconds (5 minutes)

2. **Adjust Duration (Optional)**
   - APRS packets are transmitted periodically (every few minutes)
   - Longer captures = more packets decoded
   - Recommended: 300-600 seconds for good coverage
   - Shorter captures may not catch any packets

3. **Start Decoding**
   - Click "Start Recording & Transcription"
   - System captures radio signal using HackRF
   - Audio is processed by direwolf APRS decoder
   - All packets are saved to database

4. **View APRS Results**
   - Packet count displayed in metadata
   - Table shows all decoded packets with:
     - **Time**: When packet was received
     - **Callsign**: Source amateur radio callsign
     - **Type**: position, message, weather, telemetry, status
     - **Position**: GPS coordinates (if available)
     - **Message**: Text content (if available)

### Understanding APRS Results

**No Packets Decoded**:
- APRS activity is intermittent - try longer captures
- Ensure correct frequency for your region
- Check antenna is suitable for VHF (2m band)
- Increase RF gain if signal is weak

**Position Reports**:
- Show latitude/longitude coordinates
- Indicate station location on map
- Can track mobile stations (vehicles, bicycles)

**Message Types**:
- **position**: GPS location with optional comment
- **message**: Text message to another station
- **weather**: Weather station data
- **telemetry**: Sensor data (temperature, voltage, etc.)
- **status**: Station status text

### APRS Database Storage

Every decoded APRS packet is stored with:
- Source and destination callsigns
- Message type and content
- GPS coordinates (when available)
- Path (digipeater route)
- Raw packet data
- Timestamp

This enables powerful searches and analysis through the database and Grafana dashboards.

---

## Database Features

### Overview

All radio captures are automatically stored in a PostgreSQL database with comprehensive metadata. This enables:
- **Full-text search** through all transcriptions
- **Historical analysis** of captures and frequencies
- **Statistics and trends** over time
- **Advanced filtering** by frequency, modulation, language, and date
- **Data persistence** - captures are never lost

### What Gets Stored

Every capture automatically saves:
- Audio file path and size
- Recording parameters (frequency, modulation, duration, gain, sample rate)
- Transcription text with language detection
- Transcription segments with timestamps
- Metadata (capture time, processing duration)
- Unique identifiers (ID and UUID)

### Database API Endpoints

The system provides REST API endpoints for accessing the database. You can use these with `curl`, scripts, or programming languages.

#### 1. Search Captures

**Endpoint**: `GET /search`

Search through all captures with various filters.

**Query Parameters:**
- `text` - Full-text search in transcriptions
- `frequency` - Filter by exact frequency (Hz)
- `modulation` - Filter by modulation type (FM, AM, USB, LSB)
- `language` - Filter by detected language (en, de, es, etc.)
- `start_date` - Start date (ISO format: 2025-12-28T00:00:00)
- `end_date` - End date (ISO format)
- `limit` - Maximum results (default: 100)
- `offset` - Offset for pagination (default: 0)

**Examples:**

Search for captures containing "weather":
```bash
curl "http://localhost:5000/search?text=weather"
```

Find all FM captures:
```bash
curl "http://localhost:5000/search?modulation=FM&limit=20"
```

Search by frequency (100 MHz):
```bash
curl "http://localhost:5000/search?frequency=100000000"
```

Find German language captures:
```bash
curl "http://localhost:5000/search?language=de"
```

Search captures from today:
```bash
curl "http://localhost:5000/search?start_date=2025-12-28T00:00:00&end_date=2025-12-28T23:59:59"
```

Combine multiple filters:
```bash
curl "http://localhost:5000/search?modulation=AM&frequency=118000000&start_date=2025-12-28T00:00:00"
```

**Response Format:**
```json
{
  "status": "success",
  "count": 3,
  "results": [
    {
      "id": 15,
      "uuid": "38a12c6b-36d9-4521-9f60-e36f3b6816b4",
      "created_at": "Sun, 28 Dec 2025 16:56:51 GMT",
      "frequency": 100000000,
      "modulation": "FM",
      "duration": 2,
      "gain": 20,
      "audio_file_path": "/app/recordings/capture_20251228_165637.wav",
      "transcription_text": "You",
      "language": "en",
      "language_confidence": 0.439,
      "segments": [
        {
          "start": 0.0,
          "end": 2.0,
          "text": " You"
        }
      ],
      "status": "completed"
    }
  ]
}
```

#### 2. Get Single Capture

**Endpoint**: `GET /captures/<id>`

Retrieve complete details of a specific capture by ID.

**Example:**
```bash
curl "http://localhost:5000/captures/15"
```

**Response Format:**
```json
{
  "status": "success",
  "capture": {
    "id": 15,
    "uuid": "38a12c6b-36d9-4521-9f60-e36f3b6816b4",
    "created_at": "Sun, 28 Dec 2025 16:56:51 GMT",
    "updated_at": "Sun, 28 Dec 2025 16:56:51 GMT",
    "frequency": 100000000,
    "modulation": "FM",
    "duration": 2,
    "gain": 20,
    "sample_rate": 2000000,
    "audio_file_path": "/app/recordings/capture_20251228_165637.wav",
    "json_file_path": "/app/recordings/capture_20251228_165637.json",
    "file_size": 64044,
    "transcription_text": "You",
    "language": "en",
    "language_confidence": 0.439,
    "transcription_duration": 13.895,
    "segments": [...],
    "metadata": {
      "capture_timestamp": "20251228_165637",
      "audio_duration": 2.0
    },
    "status": "completed"
  }
}
```

#### 3. Database Statistics

**Endpoint**: `GET /stats`

Get overall database statistics.

**Example:**
```bash
curl "http://localhost:5000/stats"
```

**Response Format:**
```json
{
  "status": "success",
  "statistics": {
    "total_captures": 14,
    "successful_transcriptions": 2,
    "failed_captures": 0,
    "unique_frequencies": 1,
    "unique_languages": 2,
    "first_capture": "Sun, 28 Dec 2025 16:56:04 GMT",
    "last_capture": "Sun, 28 Dec 2025 16:56:51 GMT"
  }
}
```

**Statistics Explained:**
- `total_captures` - Total number of recordings in database
- `successful_transcriptions` - Captures with transcribed text
- `failed_captures` - Captures that failed
- `unique_frequencies` - Number of different frequencies captured
- `unique_languages` - Number of different languages detected
- `first_capture` - Timestamp of oldest capture
- `last_capture` - Timestamp of newest capture

#### 4. Frequency Usage Statistics

**Endpoint**: `GET /stats/frequencies`

Get most frequently used frequencies with usage counts.

**Query Parameters:**
- `limit` - Number of results (default: 10)

**Example:**
```bash
curl "http://localhost:5000/stats/frequencies?limit=5"
```

**Response Format:**
```json
{
  "status": "success",
  "frequencies": [
    {
      "frequency": 100000000,
      "capture_count": 14,
      "last_used": "Sun, 28 Dec 2025 16:56:51 GMT",
      "modulations": ["FM"]
    },
    {
      "frequency": 118000000,
      "capture_count": 5,
      "last_used": "Sun, 28 Dec 2025 14:30:22 GMT",
      "modulations": ["AM"]
    }
  ]
}
```

This helps you identify:
- Which frequencies you monitor most often
- When each frequency was last used
- Which modulation types work with each frequency

#### 5. APRS Message Search

**Endpoint**: `GET /aprs/search`

Search through all decoded APRS messages.

**Query Parameters:**
- `callsign` - Filter by source callsign (partial match, case-insensitive)
- `text` - Full-text search in message text
- `type` - Filter by APRS type (position, message, weather, telemetry, status)
- `start_date` - Start date (ISO format)
- `end_date` - End date (ISO format)
- `limit` - Maximum results (default: 100)
- `offset` - Offset for pagination (default: 0)

**Examples:**

Search for callsign:
```bash
curl "http://localhost:5000/aprs/search?callsign=N0CALL"
```

Find position reports:
```bash
curl "http://localhost:5000/aprs/search?type=position&limit=50"
```

Search messages containing text:
```bash
curl "http://localhost:5000/aprs/search?text=test"
```

Combine filters:
```bash
curl "http://localhost:5000/aprs/search?callsign=N0CALL&type=position&start_date=2025-12-28T00:00:00"
```

**Response Format:**
```json
{
  "status": "success",
  "count": 2,
  "results": [
    {
      "id": 1,
      "created_at": "Sun, 28 Dec 2025 18:30:15 GMT",
      "source_callsign": "N0CALL",
      "destination_callsign": "APRS",
      "path": "WIDE1-1,WIDE2-2",
      "latitude": 47.6062,
      "longitude": -122.3321,
      "message_text": "Test APRS packet",
      "aprs_type": "position",
      "frequency": 144800000,
      "modulation": "FM"
    }
  ]
}
```

#### 6. APRS Statistics

**Endpoint**: `GET /aprs/stats`

Get overall APRS statistics.

**Example:**
```bash
curl "http://localhost:5000/aprs/stats"
```

**Response Format:**
```json
{
  "status": "success",
  "statistics": {
    "total_packets": 25,
    "unique_callsigns": 8,
    "total_captures": 3,
    "packets_with_position": 15,
    "first_packet": "Sun, 28 Dec 2025 18:00:00 GMT",
    "last_packet": "Sun, 28 Dec 2025 20:30:45 GMT"
  }
}
```

**Statistics Explained:**
- `total_packets` - Total APRS packets decoded
- `unique_callsigns` - Number of different stations heard
- `total_captures` - Number of APRS capture sessions
- `packets_with_position` - Packets containing GPS coordinates
- `first_packet` / `last_packet` - Time range of APRS data

#### 7. APRS Map Data (GeoJSON)

**Endpoint**: `GET /aprs/map`

Get APRS station positions in GeoJSON format for mapping applications.

**Example:**
```bash
curl "http://localhost:5000/aprs/map"
```

Returns GeoJSON with recent APRS station positions (last 24 hours) for visualization on interactive maps.

### Using Database Search Features

#### Full-Text Search

The database uses PostgreSQL's powerful full-text search engine to find text in transcriptions.

**How it works:**
- Searches across all transcribed text
- Automatically handles word variations (stemming)
- Case-insensitive
- Ignores common words (stop words like "the", "a", "is")

**Search Tips:**

1. **Single word search:**
   ```bash
   curl "http://localhost:5000/search?text=weather"
   ```
   Finds all captures mentioning "weather"

2. **Multiple words:**
   ```bash
   curl "http://localhost:5000/search?text=traffic+update"
   ```
   Finds captures with both "traffic" and "update"

3. **Exact phrases:**
   For exact phrase matching, use the text filter and review results

4. **Language-specific search:**
   ```bash
   curl "http://localhost:5000/search?text=wetter&language=de"
   ```
   Search for "wetter" only in German transcriptions

#### Date Range Queries

Find captures within specific time periods.

**Today's captures:**
```bash
TODAY=$(date -I)
curl "http://localhost:5000/search?start_date=${TODAY}T00:00:00&end_date=${TODAY}T23:59:59"
```

**Last 7 days:**
```bash
START=$(date -I -d '7 days ago')
END=$(date -I)
curl "http://localhost:5000/search?start_date=${START}T00:00:00&end_date=${END}T23:59:59"
```

**Specific date:**
```bash
curl "http://localhost:5000/search?start_date=2025-12-25T00:00:00&end_date=2025-12-25T23:59:59"
```

#### Frequency Analysis

Find all captures on a specific frequency to analyze activity:

```bash
# All 100 MHz FM captures
curl "http://localhost:5000/search?frequency=100000000&modulation=FM"

# Aviation band captures (118 MHz)
curl "http://localhost:5000/search?frequency=118000000&modulation=AM"
```

#### Pagination

For large result sets, use pagination:

**First page (20 results):**
```bash
curl "http://localhost:5000/search?limit=20&offset=0"
```

**Second page:**
```bash
curl "http://localhost:5000/search?limit=20&offset=20"
```

**Third page:**
```bash
curl "http://localhost:5000/search?limit=20&offset=40"
```

### Database Views

The database includes pre-built views for common queries:

1. **capture_statistics** - Real-time statistics
2. **recent_captures** - Last 100 captures
3. **frequency_usage** - Frequency usage breakdown

These power the `/stats` endpoints but can also be queried directly if you need database access.

### Data Migration

If you had captures before the database was added, you can migrate them.

**Run Migration Script:**

From the project directory:
```bash
docker exec radio-transcription-api python3 migrate_json_to_db.py
```

Or with custom recordings directory:
```bash
docker exec radio-transcription-api python3 migrate_json_to_db.py --recordings-dir /path/to/recordings
```

**What happens:**
- Scans recordings directory for JSON files
- Reads each transcription file
- Imports data into database
- Preserves original timestamps from filenames
- Shows progress and summary

**Migration Output:**
```
Starting migration...
Recordings directory: ./recordings

Found 13 JSON files to migrate
✓ Migrated: capture_20251228_154752.json -> ID 2
✓ Migrated: capture_20251226_002913.json -> ID 3
...
==================================================
Migration Complete!
==================================================
Migrated: 13
Skipped:  0
Errors:   0
Total:    13
```

**Note:** Migration is safe to run multiple times - it won't create duplicates.

### Database Backup and Maintenance

#### Backing Up the Database

**Create a backup:**
```bash
docker exec radio-postgres pg_dump -U radio_user radio_monitoring > backup_$(date +%Y%m%d).sql
```

This creates a SQL file with all your data.

**Restore from backup:**
```bash
cat backup_20251228.sql | docker exec -i radio-postgres psql -U radio_user -d radio_monitoring
```

#### Cleaning Old Captures

The database includes a cleanup function to remove old captures:

**Via Python:**
```python
from database_service import get_database_service
db = get_database_service()
deleted = db.delete_old_captures(days_old=30)  # Delete captures older than 30 days
print(f"Deleted {deleted} old captures")
```

**Via SQL (advanced users):**
```bash
docker exec radio-postgres psql -U radio_user -d radio_monitoring -c \
  "DELETE FROM captures WHERE created_at < NOW() - INTERVAL '30 days'"
```

#### Database Size

**Check database size:**
```bash
docker exec radio-postgres psql -U radio_user -d radio_monitoring -c \
  "SELECT pg_size_pretty(pg_database_size('radio_monitoring'))"
```

**Check table size:**
```bash
docker exec radio-postgres psql -U radio_user -d radio_monitoring -c \
  "SELECT pg_size_pretty(pg_total_relation_size('captures'))"
```

### Programming with the Database API

The database API can be accessed from any programming language. Here are examples:

#### Python

```python
import requests
import json

# Search for captures
response = requests.get('http://localhost:5000/search', params={
    'modulation': 'FM',
    'limit': 10
})
data = response.json()

for capture in data['results']:
    print(f"ID: {capture['id']}")
    print(f"Frequency: {capture['frequency']/1e6} MHz")
    print(f"Text: {capture['transcription_text']}")
    print("---")

# Get statistics
stats = requests.get('http://localhost:5000/stats').json()
print(f"Total captures: {stats['statistics']['total_captures']}")
```

#### Bash/Shell Script

```bash
#!/bin/bash

# Get today's captures and save to file
TODAY=$(date -I)
curl -s "http://localhost:5000/search?start_date=${TODAY}T00:00:00" | \
  jq -r '.results[] | "\(.created_at) - \(.frequency) Hz - \(.transcription_text)"' > today_captures.txt

# Get statistics
curl -s "http://localhost:5000/stats" | jq '.statistics'
```

#### JavaScript/Node.js

```javascript
const axios = require('axios');

async function searchCaptures() {
  const response = await axios.get('http://localhost:5000/search', {
    params: {
      modulation: 'AM',
      frequency: 118000000
    }
  });

  console.log(`Found ${response.data.count} captures`);
  response.data.results.forEach(capture => {
    console.log(`${capture.created_at}: ${capture.transcription_text}`);
  });
}

searchCaptures();
```

### Advanced Database Features

#### Full-Text Search with pg_trgm

The database uses the `pg_trgm` extension for fuzzy text matching. This allows:
- Finding similar words even with typos
- Partial word matching
- Fast text search on large datasets

#### JSONB Storage

Transcription segments and metadata are stored in JSONB format, allowing:
- Flexible schema for future enhancements
- Fast queries on nested data
- Efficient storage of complex structures

#### Automatic Timestamps

Every capture automatically records:
- `created_at` - When the capture was saved
- `updated_at` - When the record was last modified
- Both use UTC timezone for consistency

#### UUID Support

Every capture gets a unique UUID in addition to the sequential ID:
- IDs are sequential: 1, 2, 3, 4...
- UUIDs are globally unique: `38a12c6b-36d9-4521-9f60-e36f3b6816b4`
- Use UUIDs for distributed systems or external references

### Database Schema

For advanced users, here's the database structure:

**Captures Table:**
- `id` (integer) - Primary key, auto-increment
- `uuid` (UUID) - Unique identifier
- `created_at` (timestamp) - Creation timestamp
- `updated_at` (timestamp) - Last update timestamp
- `frequency` (bigint) - Frequency in Hz
- `modulation` (varchar) - FM, AM, USB, or LSB
- `duration` (integer) - Recording duration in seconds
- `gain` (integer) - RF gain (0-47 dB)
- `sample_rate` (integer) - Sample rate in Hz
- `audio_file_path` (varchar) - Path to audio file
- `json_file_path` (varchar) - Path to JSON file
- `file_size` (bigint) - File size in bytes
- `transcription_text` (text) - Transcribed text
- `language` (varchar) - Detected language code
- `language_confidence` (float) - Language detection confidence
- `transcription_duration` (float) - Processing time
- `segments` (JSONB) - Transcription segments with timestamps
- `metadata` (JSONB) - Additional metadata
- `status` (varchar) - completed, failed, etc.

**Indices:**
- Primary key on `id`
- Unique index on `uuid`
- Index on `created_at` (descending, for recent queries)
- Index on `frequency` (for frequency searches)
- Full-text index on `transcription_text` (for text search)
- Trigram index on `transcription_text` (for fuzzy search)

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

#### 3a. APRS Decoding Metrics
- **Total APRS Packets**: Number of APRS packets decoded
- **Successful Decodes**: APRS decode operations that succeeded
- **Unique Callsigns**: Number of different stations heard
- **Packets with Position**: Number of packets containing GPS coordinates

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

### APRS Monitoring Dashboard

A dedicated APRS dashboard is pre-configured at Grafana with comprehensive APRS packet analytics and visualization.

**How to Access:**
1. Go to http://localhost:3000 (Grafana)
2. Login (admin/admin)
3. Click "Dashboards" in left sidebar
4. Select "APRS Monitoring Dashboard"

**Dashboard Panels:**

1. **Statistics Cards (Top Row)**
   - Total APRS Packets decoded
   - Successful Decodes count
   - Unique Callsigns heard
   - Packets with Position data

2. **APRS Packets Timeline**
   - Time series graph showing packet activity
   - 5-minute buckets
   - Visualizes when APRS activity occurs

3. **APRS Message Types (Pie Chart)**
   - Breakdown by type: position, message, weather, telemetry, status
   - Shows distribution of packet types

4. **Recent APRS Packets (Table)**
   - Last 50 packets decoded
   - Columns: Time, Callsign, Type, Position, Message
   - Clickable and sortable

5. **Top 15 Callsigns (Bar Chart)**
   - Most active stations
   - Packet count per callsign
   - Horizontal bar chart for easy comparison

6. **APRS Stations Map (Geomap)**
   - Interactive map showing station positions
   - Each marker represents an APRS station
   - Most recent position for each callsign
   - Pan and zoom to explore

**Dashboard Features:**
- Auto-refresh every 30 seconds
- Default time range: Last 24 hours
- Adjustable time range (top-right corner)
- Direct PostgreSQL queries for APRS data

**Using the Map:**
- Zoom with mouse wheel or zoom controls
- Click markers to see station details
- Shows callsign, position, and message
- Green markers indicate APRS stations

---

## Database Management with pgAdmin

### Introduction to pgAdmin

pgAdmin 4 is a powerful, full-featured web-based database management tool for PostgreSQL. It provides a graphical interface to:
- Browse and edit database tables
- Execute SQL queries
- Import and export data
- Manage database backups
- Monitor database performance
- Visualize database schema

### Accessing pgAdmin

1. Open your web browser
2. Navigate to **http://localhost:5050**
3. Login with:
   - **Email**: `admin@admin.com`
   - **Password**: `admin`

### Automatic Server Connection

**Good news! The PostgreSQL server is already configured for you.**

When you login to pgAdmin, the **"Radio Monitoring Database"** server is automatically registered and ready to use.

#### What You'll See:

After logging in, look at the left sidebar:
- **Servers** (expand this)
  - **Radio Monitoring Database** ← This is automatically configured!

#### Accessing the Database:

Simply expand the server tree by clicking on each level:

1. Click on **"Radio Monitoring Database"** to expand it
2. Click on **"Databases (1)"** to expand
3. Click on **"radio_monitoring"** to expand
4. Click on **"Schemas (1)"** to expand
5. Click on **"public"** to expand
6. Click on **"Tables"** to see all database tables
7. Click on **"captures"** to see your radio captures table

**Pre-configured Connection Details:**
- Server Name: Radio Monitoring Database
- Host: radio-postgres
- Port: 5432
- Database: radio_monitoring
- Username: radio_user
- Password: Automatically loaded (no need to enter)

**No manual setup required!** Just login and start browsing your data.

### Browsing Database Tables

Once connected, you can browse all database tables:

#### Navigating to Tables

1. In the left sidebar, expand: **Servers** → **Radio Monitoring Database** → **Databases** → **radio_monitoring** → **Schemas** → **public** → **Tables**
2. Click on **captures** to see the table structure

#### Viewing Table Data

**Method 1: View All Rows**
1. Right-click on the **captures** table
2. Select **"View/Edit Data" → "All Rows"**
3. Browse all records in a spreadsheet-like interface

**Method 2: View First 100 Rows**
1. Right-click on the **captures** table
2. Select **"View/Edit Data" → "First 100 Rows"**
3. Useful for large tables to avoid loading too much data

**Method 3: Filtered Rows**
1. Right-click on the **captures** table
2. Select **"View/Edit Data" → "Filtered Rows..."**
3. Enter a WHERE clause (e.g., `modulation = 'FM'`)
4. Click OK to view filtered results

### Running SQL Queries

pgAdmin provides a powerful Query Tool for executing custom SQL queries.

#### Opening the Query Tool

**Method 1:**
- Right-click on **radio_monitoring** database
- Select **"Query Tool"**

**Method 2:**
- Click on **radio_monitoring** database
- Click the "Query Tool" icon in the toolbar (looks like a play button)

#### Example Queries

**Get all captures from today:**
```sql
SELECT
    id,
    created_at,
    ROUND(frequency::numeric / 1000000, 3) as freq_mhz,
    modulation,
    transcription_text,
    language
FROM captures
WHERE created_at::date = CURRENT_DATE
ORDER BY created_at DESC;
```

**Search transcriptions for keywords:**
```sql
SELECT
    id,
    created_at,
    frequency,
    transcription_text
FROM captures
WHERE transcription_text ILIKE '%weather%'
ORDER BY created_at DESC
LIMIT 20;
```

**Get frequency statistics:**
```sql
SELECT
    ROUND(frequency::numeric / 1000000, 3) as freq_mhz,
    modulation,
    COUNT(*) as capture_count,
    AVG(duration) as avg_duration,
    MAX(created_at) as last_capture
FROM captures
GROUP BY frequency, modulation
ORDER BY capture_count DESC;
```

**Get captures by language:**
```sql
SELECT
    language,
    COUNT(*) as count,
    AVG(language_confidence) as avg_confidence
FROM captures
WHERE language IS NOT NULL
GROUP BY language
ORDER BY count DESC;
```

**Find empty transcriptions:**
```sql
SELECT
    id,
    created_at,
    frequency,
    modulation,
    duration
FROM captures
WHERE transcription_text = '' OR transcription_text IS NULL
ORDER BY created_at DESC;
```

#### Query Tool Features

- **Syntax Highlighting**: SQL keywords are color-coded
- **Auto-completion**: Press Ctrl+Space for suggestions
- **Execute**: Press F5 or click the Execute button (▶)
- **Explain**: Analyze query performance
- **Download Results**: Export to CSV/Excel
- **Query History**: View previously executed queries

### Exporting Data

#### Method 1: Export from Query Results

1. Run a query in the Query Tool
2. Click the **"Download as CSV"** icon in the results toolbar
3. Save the file to your computer

#### Method 2: Export Entire Table

1. Right-click on the **captures** table
2. Select **"Import/Export..."**
3. Configure export options:
   - **Export**: Choose this option
   - **Format**: CSV, Text, or Binary
   - **Filename**: Choose destination file
   - **Header**: Include column names
   - **Delimiter**: Comma (,) or Tab
   - **Quote**: Double quote (")
   - **Escape**: Backslash (\)
4. Click **"OK"** to export

#### Method 3: Backup Database (Full Export)

1. Right-click on **radio_monitoring** database
2. Select **"Backup..."**
3. Choose backup options:
   - **Format**:
     - **Custom**: Compressed, best for restore
     - **Tar**: Archive format
     - **Plain**: SQL text file (human-readable)
   - **Filename**: Choose destination file
   - **Compression**: 0-9 (9 = maximum compression)
4. Click **"Backup"** button

### Importing Data

#### Restore from Backup

1. Right-click on **radio_monitoring** database
2. Select **"Restore..."**
3. Choose backup file
4. Configure restore options
5. Click **"Restore"** button

#### Import CSV into Table

1. Right-click on target table
2. Select **"Import/Export..."**
3. Configure import options:
   - **Import**: Choose this option
   - **Filename**: Select CSV file
   - **Format**: CSV
   - **Header**: Check if CSV has column names
   - **Delimiter**: Comma or appropriate delimiter
4. Click **"OK"** to import

### Database Administration

#### Viewing Table Statistics

1. Right-click on **captures** table
2. Select **"Properties"**
3. View tabs:
   - **General**: Table name, owner, tablespace
   - **Columns**: List of all columns with data types
   - **Constraints**: Primary keys, foreign keys
   - **Indexes**: Database indexes for performance
   - **Triggers**: Automated database actions
   - **Statistics**: Row count, table size, last vacuum

#### Analyzing Query Performance

1. Write your query in the Query Tool
2. Click **"Explain"** button (instead of Execute)
3. Click **"Explain Analyze"** for detailed execution plan
4. Review:
   - Execution time
   - Rows scanned
   - Index usage
   - Performance bottlenecks

#### Creating New Queries with Visual Builder

1. In Query Tool, click **"Query" → "Graphical Query Builder"**
2. Drag tables onto the canvas
3. Select columns to include
4. Define relationships between tables
5. Add WHERE conditions
6. pgAdmin generates SQL automatically

### Best Practices for pgAdmin

#### Security

- **Change Default Password**: After first login, go to **File → Preferences → Paths** to change admin password
- **Don't Share Sessions**: Always logout when done
- **Use Read-Only Connections**: For browsing, create read-only database users

#### Performance

- **Limit Result Sets**: Always use LIMIT clause for large tables
- **Use Filters**: Instead of loading all rows, filter in the query
- **Close Idle Connections**: Right-click server → Disconnect when done
- **Enable Query Timeout**: Set in **File → Preferences → Query Tool**

#### Maintenance

- **Regular Backups**: Schedule periodic database backups
- **Monitor Table Size**: Check statistics to track database growth
- **Vacuum Tables**: Periodically run `VACUUM ANALYZE` to optimize performance

### Troubleshooting pgAdmin

#### Cannot Connect to Database

**Problem**: "Could not connect to server" error or server not appearing in pgAdmin

**Solutions**:
1. Verify PostgreSQL container is running:
   ```bash
   docker ps | grep postgres
   ```

2. Restart pgAdmin to reload server configuration:
   ```bash
   docker restart pgadmin
   ```
   Wait 15 seconds, then refresh pgAdmin in your browser

3. Check if server configuration files are mounted correctly:
   ```bash
   docker exec pgadmin ls -la /pgadmin4/servers.json
   docker exec pgadmin ls -la /pgpass
   ```

4. Test PostgreSQL connection from command line:
   ```bash
   docker exec radio-postgres psql -U radio_user -d radio_monitoring -c "SELECT 1;"
   ```

5. If server still doesn't appear, check pgAdmin logs:
   ```bash
   docker logs pgadmin --tail 50
   ```

#### pgAdmin is Slow

**Problem**: Queries take too long to execute

**Solutions**:
1. Add LIMIT clause to queries: `LIMIT 100`
2. Filter data with WHERE clause before loading
3. Create indexes on frequently searched columns
4. Close unused query tool tabs

#### Login Issues

**Problem**: Forgot pgAdmin password

**Solution**: Reset by restarting pgAdmin container:
```bash
docker restart pgadmin
```
Default credentials will be restored: admin@admin.com / admin

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

### Problem: Database Not Saving Captures

**Solution:**
1. Check if PostgreSQL container is running:
   ```bash
   docker-compose ps postgres
   ```

2. Verify database is healthy:
   ```bash
   docker exec radio-postgres pg_isready -U radio_user
   ```

3. Check API logs for database connection errors:
   ```bash
   docker-compose logs radio-api | grep -i database
   ```

4. Verify statistics endpoint works:
   ```bash
   curl http://localhost:5000/stats
   ```

5. If database is down, restart it:
   ```bash
   docker-compose restart postgres
   docker-compose restart radio-api
   ```

### Problem: Search Returns No Results

**Possible Causes:**

1. **No captures in database yet**
   - Solution: Make at least one capture first
   - Verify: `curl http://localhost:5000/stats`

2. **Search text uses stop words**
   - Stop words like "a", "the", "is", "you" are ignored
   - Solution: Use more meaningful search terms

3. **Date range too narrow**
   - Solution: Expand date range or remove date filter

4. **Wrong filter combination**
   - Solution: Try searching without filters first

### Problem: Migration Script Fails

**Solution:**
1. Verify recordings directory exists:
   ```bash
   docker exec radio-transcription-api ls -la /app/recordings/
   ```

2. Check for JSON files:
   ```bash
   docker exec radio-transcription-api find /app/recordings -name "*.json"
   ```

3. Verify database is accessible:
   ```bash
   curl http://localhost:5000/stats
   ```

4. Check migration script output for specific errors

5. Run migration with verbose output:
   ```bash
   docker exec radio-transcription-api python3 -u migrate_json_to_db.py
   ```

### Problem: Database Running Out of Space

**Solution:**
1. Check database size:
   ```bash
   docker exec radio-postgres psql -U radio_user -d radio_monitoring -c \
     "SELECT pg_size_pretty(pg_database_size('radio_monitoring'))"
   ```

2. Delete old captures (older than 30 days):
   ```bash
   docker exec radio-postgres psql -U radio_user -d radio_monitoring -c \
     "DELETE FROM captures WHERE created_at < NOW() - INTERVAL '30 days'"
   ```

3. Delete old audio files:
   ```bash
   cd /home/spia/my-project/recordings
   find . -name "*.wav" -mtime +30 -delete
   find . -name "*.json" -mtime +30 -delete
   ```

4. Vacuum database to reclaim space:
   ```bash
   docker exec radio-postgres psql -U radio_user -d radio_monitoring -c "VACUUM FULL"
   ```

### Problem: No APRS Packets Decoded

**Possible Causes & Solutions:**

1. **APRS frequency has low activity**
   - APRS packets are transmitted sporadically (every few minutes)
   - Solution: Increase capture duration to 5-10 minutes (300-600 seconds)
   - Solution: Try different times of day (more activity during daytime)

2. **Wrong frequency for region**
   - North America: 144.800 MHz
   - Japan: 144.390 MHz
   - Europe: 145.175 MHz
   - Solution: Verify correct frequency for your location

3. **Antenna not suitable for VHF**
   - APRS uses 2m band (144-146 MHz)
   - Solution: Use VHF antenna designed for 2m band
   - Solution: Check antenna is connected properly

4. **RF gain too low**
   - Weak signals won't decode
   - Solution: Increase gain to 30-40 dB
   - Solution: Try different gain values

5. **Direwolf decoding issues**
   - Check API logs for direwolf errors:
     ```bash
     docker-compose logs radio-api | grep -i direwolf
     ```
   - Restart service if direwolf crashed:
     ```bash
     docker-compose restart radio-api
     ```

### Problem: APRS Map Shows No Stations

**Solution:**
1. **No packets with position data**
   - Only position reports appear on map
   - Other message types (messages, telemetry, weather) don't have coordinates
   - Solution: Wait for position reports (may take longer captures)

2. **Check if any packets were decoded**
   - Verify APRS statistics:
     ```bash
     curl http://localhost:5000/aprs/stats
     ```
   - If total_packets is 0, refer to "No APRS Packets Decoded" above

3. **Database query issue**
   - Test APRS map endpoint:
     ```bash
     curl http://localhost:5000/aprs/map
     ```
   - Should return GeoJSON with features

### Problem: APRS Dashboard Shows No Data

**Solution:**
1. **Make APRS captures first**
   - Dashboard needs APRS data to display
   - Click APRS preset button and capture for 5+ minutes

2. **Verify APRS data in database**
   - Check APRS statistics:
     ```bash
     curl http://localhost:5000/aprs/stats
     ```

3. **Refresh Grafana dashboard**
   - Click refresh icon (top-right)
   - Adjust time range to include when you made APRS captures

4. **Check PostgreSQL data source**
   - In Grafana: Configuration → Data Sources → PostgreSQL
   - Click "Test" - should show "Database Connection OK"

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

### For Database Management

1. **Regular backups**
   - Backup database weekly or daily:
     ```bash
     docker exec radio-postgres pg_dump -U radio_user radio_monitoring > backup_$(date +%Y%m%d).sql
     ```
   - Keep backups in a safe location
   - Test restore process periodically

2. **Monitor database size**
   - Check size monthly:
     ```bash
     curl http://localhost:5000/stats
     ```
   - Delete old captures if space is limited
   - Vacuum database after large deletions

3. **Use search efficiently**
   - Combine filters to narrow results
   - Use date ranges for large datasets
   - Leverage pagination for better performance

4. **Optimize queries**
   - Search by frequency or modulation for faster results
   - Full-text search is indexed and fast
   - Date range queries use indexed timestamps

5. **Data retention policy**
   - Decide how long to keep captures
   - Set up automated cleanup scripts
   - Balance disk space vs. historical data needs

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
| PostgreSQL | localhost:5432 | radio_user/radio_password_change_in_production |
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

# Database commands
# - Get statistics
curl http://localhost:5000/stats

# - Search captures
curl "http://localhost:5000/search?modulation=FM&limit=10"

# - Migrate JSON files
docker exec radio-transcription-api python3 migrate_json_to_db.py

# - Backup database
docker exec radio-postgres pg_dump -U radio_user radio_monitoring > backup.sql
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
*System Version: 2.0 - Now with PostgreSQL Database*

**New in Version 2.0:**
- PostgreSQL database for permanent storage
- Full-text search across all captures
- Advanced filtering by frequency, modulation, language, and date
- Database statistics and analytics
- REST API endpoints for programmatic access
- Historical data migration from JSON files
- Database backup and maintenance tools
