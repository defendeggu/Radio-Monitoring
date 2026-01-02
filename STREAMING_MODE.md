# Streaming Mode Documentation

## Overview

Streaming Mode enables continuous real-time decoding of APRS and POCSAG signals without storing intermediate audio files. This feature is designed for long-duration monitoring sessions (1-24 hours) where disk space and memory constraints make traditional capture-then-decode approaches impractical.

## Architecture

```
SDR Hardware → IQ Stream → FM Demodulation → 48kHz Audio → Decoder (direwolf/multimon-ng) → Elasticsearch
```

Key differences from capture mode:
- **No file storage**: Audio is streamed directly from SDR to decoder via pipes
- **Constant memory usage**: ~500MB regardless of session duration
- **Real-time indexing**: Decoded packets are sent to Elasticsearch immediately
- **Session management**: Redis tracks active streaming sessions with automatic cleanup

## Supported Modes

- **APRS**: Uses direwolf decoder for APRS packet decoding
- **POCSAG**: Uses multimon-ng decoder for pager message decoding

## When to Use Streaming Mode

### Use Streaming Mode for:
- Long monitoring sessions (1-24 hours)
- Continuous channel monitoring
- Low disk space environments
- Real-time packet analysis without archiving audio

### Use Capture Mode for:
- Short captures (< 5 minutes)
- Audio archival requirements
- Post-capture reprocessing needs
- Multiple decode attempts with different parameters

## Configuration

### Environment Variables

The following environment variables are configured in `docker-compose.elk.yml`:

```yaml
environment:
  - REDIS_HOST=redis          # Redis hostname (Docker network)
  - REDIS_PORT=6379          # Redis port
  - REDIS_DB=0               # Redis database number
```

### Session Limits

- **Max concurrent sessions per user**: 1
- **Max session duration**: 24 hours
- **Default duration**: 1 hour (3600 seconds)
- **Session TTL in Redis**: 7 days

### Hardware Requirements

**HackRF**:
- Sample rate: 2 MHz (hardware minimum)
- APRS duration limit: 180s (3 min)
- POCSAG duration limit: 60s (1 min)
- Memory usage: ~800MB per session

**RTL-SDR**:
- Sample rate: Can be reduced to 250 kHz for digital modes
- APRS duration limit: 300s (5 min)
- POCSAG duration limit: 120s (2 min)
- Memory usage: ~500MB per session

## Usage

### Web Interface

1. **Select Mode**: Navigate to APRS or POCSAG tab
2. **Enable Streaming**: Check "Continuous Streaming Mode" checkbox
3. **Configure Parameters**:
   - Frequency (Hz)
   - Duration (1-86400 seconds)
   - Gain (0-50 dB)
4. **Start Session**: Click "Start Streaming" button
5. **Monitor Progress**: Watch real-time statistics update every 2 seconds
6. **Stop Session**: Click "Stop Streaming" button (or wait for auto-completion)

### API Endpoints

#### Start Streaming Session

```bash
curl -X POST http://localhost:5000/stream-decode \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "mode": "aprs",
    "frequency": 144800000,
    "duration": 3600,
    "gain": 20,
    "sample_rate": 2000000
  }'
```

Response:
```json
{
  "status": "started",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "aprs",
  "frequency": 144800000,
  "duration": 3600
}
```

#### Get Session Status

```bash
curl http://localhost:5000/stream-decode/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your-api-key"
```

Response:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "mode": "aprs",
  "frequency": 144800000,
  "stats": {
    "packet_count": 142,
    "elapsed_seconds": 1845,
    "last_packet_time": "2026-01-02T15:30:45Z"
  }
}
```

#### Stop Session

```bash
curl -X DELETE http://localhost:5000/stream-decode/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your-api-key"
```

Response:
```json
{
  "status": "stopped",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "final_stats": {
    "packet_count": 142,
    "elapsed_seconds": 1845
  }
}
```

#### List All Sessions

```bash
curl http://localhost:5000/stream-decode \
  -H "X-API-Key: your-api-key"
```

Response:
```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "running",
      "mode": "aprs",
      "frequency": 144800000,
      "started_at": "2026-01-02T15:00:00Z"
    }
  ]
}
```

## Session States

- **starting**: Decoder subprocess is being initialized
- **running**: Active decoding in progress
- **stopping**: Graceful shutdown in progress
- **completed**: Session finished successfully
- **failed**: Session encountered an error

## Technical Details

### APRS Decoder (direwolf)

Command: `direwolf -c /dev/null -r 48000 -D 1 -t 0 -q d -`

- `-r 48000`: 48 kHz sample rate
- `-D 1`: Decode using D700 mode
- `-t 0`: No colors in output
- `-q d`: Quiet mode, decoded packets only
- `-`: Read audio from stdin

Output format:
```
[0] N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-Test
```

### POCSAG Decoder (multimon-ng)

Command: `multimon-ng -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -t raw -`

- `-a POCSAG512`: Decode POCSAG at 512 bps
- `-a POCSAG1200`: Decode POCSAG at 1200 bps
- `-a POCSAG2400`: Decode POCSAG at 2400 bps
- `-t raw`: Raw 16-bit signed PCM input
- `-`: Read audio from stdin

Output format:
```
POCSAG1200: Address: 1234567  Function: 0  Alpha:   Test message
```

### FM Demodulation

The IQ stream from the SDR is demodulated using phase differentiation:

```python
phase = np.angle(iq_complex)
audio = np.diff(np.unwrap(phase))
```

Audio is then resampled from the SDR sample rate to 48 kHz using `scipy.signal.resample`.

### Background Processing

Each streaming session runs two background threads:

1. **IQ→Audio Converter Thread**:
   - Reads IQ data from SDR (hackrf_transfer / rtl_sdr)
   - Demodulates FM signal
   - Resamples to 48 kHz
   - Writes to decoder stdin pipe

2. **Decoder Output Indexer Thread**:
   - Reads decoded packets from decoder stdout pipe
   - Parses packet data (callsign, position, message)
   - Indexes to Elasticsearch via Logstash
   - Updates session statistics in Redis

### Redis Session Storage

Session data is stored in Redis with the following schema:

```json
{
  "session_id": "uuid",
  "mode": "aprs|pocsag",
  "frequency": 144800000,
  "duration": 3600,
  "gain": 20,
  "sample_rate": 2000000,
  "status": "running",
  "started_at": "2026-01-02T15:00:00Z",
  "packet_count": 142,
  "last_packet_time": "2026-01-02T15:30:45Z"
}
```

TTL: 7 days (automatically expires old sessions)

## Monitoring

### Real-time Statistics

The web interface polls session status every 2 seconds:

- **Packet Count**: Total packets decoded
- **Elapsed Time**: Duration since session start (MM:SS or HH:MM:SS)
- **Last Packet**: Timestamp of most recent decoded packet
- **Status**: Current session state

### Logs

Check streaming logs:
```bash
docker logs -f radio-transcription-api
```

Example output:
```
INFO:streaming_decoder_service:Starting APRS streaming session 550e8400-e29b-41d4-a716-446655440000
INFO:streaming_decoder_service:Frequency: 144.800 MHz, Duration: 3600s, Gain: 20 dB
INFO:streaming_decoder_service:Decoded APRS packet from N0CALL
INFO:streaming_decoder_service:Session completed: 142 packets in 1845s
```

### Elasticsearch Queries

View streaming session data:

```bash
# APRS packets
curl "http://localhost:9200/radio-aprs/_search?q=session_id:550e8400-e29b-41d4-a716-446655440000"

# POCSAG messages
curl "http://localhost:9200/radio-pocsag/_search?q=session_id:550e8400-e29b-41d4-a716-446655440000"
```

## Troubleshooting

### Session Fails to Start

**Error**: "Already have an active session"
- Only 1 concurrent session per user is allowed
- Stop existing session first or wait for completion

**Error**: "No SDR hardware detected"
- Verify SDR is connected: `lsusb | grep -i hackrf` or `lsusb | grep -i rtl`
- Check USB permissions: Container needs access to `/dev/bus/usb`

### No Packets Decoded

**Check frequency**:
- APRS: 144.800 MHz (North America), 144.390 MHz (Europe)
- POCSAG: Varies by region (e.g., 147.325 MHz in Switzerland)

**Check gain**:
- Too low: Weak signal, no decoding
- Too high: Overload, distortion
- Recommended: 20-30 dB for most scenarios

**Check antenna**:
- Proper antenna connected for frequency band
- Antenna positioned for good reception

### High Memory Usage

**Reduce duration**:
- Shorter sessions use less memory
- Split long monitoring into multiple sessions

**Use RTL-SDR instead of HackRF**:
- Lower sample rate = less memory
- RTL-SDR: ~500MB vs HackRF: ~800MB

### Session Stuck in "starting" State

**Check logs**:
```bash
docker logs radio-transcription-api --tail 50
```

**Common causes**:
- Decoder subprocess failed to start
- Invalid decoder configuration
- SDR initialization timeout

**Solution**: Delete stuck session and retry

### Redis Connection Errors

**Error**: "Connection refused to Redis"

**Check Redis status**:
```bash
docker compose -f docker-compose.elk.yml ps redis
```

**Verify environment variables**:
```bash
docker exec radio-transcription-api env | grep REDIS
```

Should show:
- REDIS_HOST=redis
- REDIS_PORT=6379
- REDIS_DB=0

## Performance Considerations

### Sample Rate vs Memory

| SDR Type | Sample Rate | Memory Usage | Buffer Size |
|----------|-------------|--------------|-------------|
| HackRF   | 2 MHz       | ~800 MB      | 2 MB chunks |
| RTL-SDR  | 250 kHz     | ~500 MB      | 256 KB chunks|

### Packet Throughput

**APRS**:
- Typical: 5-10 packets/minute (rural)
- High traffic: 30-60 packets/minute (urban)

**POCSAG**:
- Typical: 1-5 messages/minute
- High traffic: 20-50 messages/minute

### Elasticsearch Indexing

- Packets are indexed in real-time via Logstash
- No buffering: Each packet creates 1 Elasticsearch document
- Index sharding handles high-traffic scenarios

## Security

### API Key Authentication

All streaming endpoints require API key authentication via `X-API-Key` header.

Generate API keys:
```bash
python3 scripts/generate_api_keys.py
```

Add to `.env.elk`:
```
API_KEYS=key1,key2,key3
```

### Trusted IP Exemptions

Requests from trusted sources (localhost, Docker network, private IPs) bypass API key requirement.

### Container Security

- Non-root user (UID 1000)
- USB device access only (no privileged mode)
- Read-only volumes where possible
- Resource limits (8GB memory, 12GB swap)

## Migration from Capture Mode

Existing APRS/POCSAG workflows continue to work unchanged. Streaming mode is an optional parallel feature selected via checkbox in the UI.

### Data Compatibility

Both modes index to the same Elasticsearch indices:
- `radio-aprs` (APRS packets)
- `radio-pocsag` (POCSAG messages)

Kibana dashboards work with data from both modes.

### Workflow Comparison

| Feature | Capture Mode | Streaming Mode |
|---------|--------------|----------------|
| Duration | < 5 minutes | 1-24 hours |
| Audio Files | Stored | Not stored |
| Disk Usage | High | Low |
| Memory Usage | Variable | Constant |
| Reprocessing | Supported | Not supported |
| Real-time | No | Yes |

## Future Enhancements

Potential improvements for future releases:

- [ ] Multiple concurrent sessions per user
- [ ] Session pause/resume functionality
- [ ] Audio recording option for streaming sessions
- [ ] Frequency hopping/scanning support
- [ ] WebSocket API for real-time packet push
- [ ] Performance metrics (CPU, bandwidth, decode rate)
- [ ] Automatic frequency offset correction

## References

- [direwolf Documentation](https://github.com/wb2osz/direwolf)
- [multimon-ng Documentation](https://github.com/EliasOenal/multimon-ng)
- [APRS Protocol Specification](http://www.aprs.org/doc/APRS101.PDF)
- [POCSAG Specification](https://en.wikipedia.org/wiki/POCSAG)
- [Redis Documentation](https://redis.io/docs/)

---

Generated: 2026-01-02
Version: 1.0.0
