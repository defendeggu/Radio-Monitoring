# Multi-Device RTL-SDR Setup Guide

This guide explains how to use multiple RTL-SDR devices simultaneously with the Radio Monitoring System.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Setting Device Serial Numbers](#setting-device-serial-numbers)
- [Identifying Devices](#identifying-devices)
- [Using Specific Devices in API Calls](#using-specific-devices-in-api-calls)
- [Docker Configuration](#docker-configuration)
- [Common Use Cases](#common-use-cases)
- [Troubleshooting](#troubleshooting)

## Overview

The Radio Monitoring System supports multiple RTL-SDR devices connected simultaneously. This allows you to:
- Monitor multiple frequencies at the same time
- Dedicate one device to APRS while another monitors voice
- Run parallel scanning operations
- Create redundant monitoring setups

## Prerequisites

- Multiple RTL-SDR devices
- USB hub with sufficient power (recommended: powered USB 3.0 hub)
- rtl-sdr tools installed (`rtl_test`, `rtl_eeprom`)

## Setting Device Serial Numbers

By default, all RTL-SDR devices have the same serial number (00000001). To use multiple devices, you must assign unique serial numbers.

### Step 1: Connect Only One Device

Connect the first RTL-SDR device to your computer.

### Step 2: Verify Detection

```bash
rtl_test -t
```

Expected output:
```
Found 1 device(s):
  0:  Realtek, RTL2838UHIDIR, SN: 00000001
```

### Step 3: Set Unique Serial Number

Set a descriptive serial number (max 256 characters):

```bash
# For the first device
rtl_eeprom -d 0 -s RTLSDR_APRS

# Or use shorter names
rtl_eeprom -d 0 -s DEV01
```

⚠️ **Warning**: This writes to the device EEPROM. Use carefully!

### Step 4: Verify the Change

```bash
rtl_test -t
```

Expected output:
```
Found 1 device(s):
  0:  Realtek, RTL2838UHIDIR, SN: RTLSDR_APRS
```

### Step 5: Repeat for Additional Devices

Disconnect the first device, connect the second, and repeat:

```bash
rtl_eeprom -d 0 -s RTLSDR_VOICE
```

Continue for all devices:
- `RTLSDR_APRS` - Dedicated to APRS monitoring
- `RTLSDR_VOICE` - Dedicated to voice transcription
- `RTLSDR_POCSAG` - Dedicated to pager decoding
- `RTLSDR_SCAN` - Dedicated to scanning operations

## Identifying Devices

Once all devices have unique serial numbers, connect them all and verify:

```bash
rtl_test -t
```

Expected output with 4 devices:
```
Found 4 device(s):
  0:  Realtek, RTL2838UHIDIR, SN: RTLSDR_APRS
  1:  Realtek, RTL2838UHIDIR, SN: RTLSDR_VOICE
  2:  Realtek, RTL2838UHIDIR, SN: RTLSDR_POCSAG
  3:  Realtek, RTL2838UHIDIR, SN: RTLSDR_SCAN
```

**Important**: Device indices (0, 1, 2, 3) can change between reboots or USB reconnections. Always use serial numbers for consistent device selection!

## Using Specific Devices in API Calls

### Method 1: Specify Device by Serial Number (Recommended)

Add the `device_serial` parameter to your API calls:

```bash
# Capture APRS with dedicated device
curl -X POST http://localhost:5000/aprs/decode \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 144800000,
    "device_serial": "RTLSDR_APRS",
    "duration": 300
  }'

# Capture voice with dedicated device
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 145500000,
    "modulation": "fm",
    "device_serial": "RTLSDR_VOICE",
    "duration": 30
  }'
```

### Method 2: Specify Device by Index (Not Recommended)

Device indices can change between reboots:

```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 145500000,
    "device_index": 0,
    "duration": 30
  }'
```

### Method 3: Use Default Device

If no device is specified, the system uses device index 0:

```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 145500000,
    "duration": 30
  }'
```

## Docker Configuration

The Docker container has USB device access configured by default in `docker-compose.yml`:

```yaml
radio-api:
  devices:
    - /dev/bus/usb:/dev/bus/usb
```

This grants access to **all** USB devices. No additional configuration is needed for multiple RTL-SDR devices.

### Verify Devices in Container

```bash
# Enter the running container
docker exec -it radio-transcription-api bash

# Check devices
rtl_test -t
```

## Common Use Cases

### Use Case 1: Simultaneous APRS and Voice Monitoring

Monitor APRS on 144.800 MHz while recording voice on 145.500 MHz:

**Terminal 1 - APRS Monitoring:**
```bash
curl -X POST http://localhost:5000/stream-decode/aprs \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 144800000,
    "device_serial": "RTLSDR_APRS",
    "sample_rate": 48000
  }'
```

**Terminal 2 - Voice Capture:**
```bash
curl -X POST http://localhost:5000/capture-and-transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 145500000,
    "modulation": "fm",
    "device_serial": "RTLSDR_VOICE",
    "duration": 60
  }'
```

### Use Case 2: Parallel Frequency Scanning

Scan different frequency ranges simultaneously:

```bash
# Device 1: Scan 2m band
curl -X POST http://localhost:5000/scan-repeaters \
  -H "Content-Type: application/json" \
  -d '{
    "band": "2m",
    "device_serial": "RTLSDR_SCAN",
    "canton": "all"
  }'

# Device 2: Scan 70cm band
curl -X POST http://localhost:5000/scan-repeaters \
  -H "Content-Type: application/json" \
  -d '{
    "band": "70cm",
    "device_serial": "RTLSDR_SCAN2",
    "canton": "all"
  }'
```

### Use Case 3: Dedicated POCSAG Pager Monitoring

Use one device exclusively for pager decoding:

```bash
curl -X POST http://localhost:5000/stream-decode/pocsag \
  -H "Content-Type: application/json" \
  -d '{
    "frequency": 169650000,
    "device_serial": "RTLSDR_POCSAG",
    "baud": 1200
  }'
```

## Web Interface Multi-Device Support

The web interface (http://localhost:8080) supports device selection:

1. Open the web interface
2. Click the "SDR Hardware" section
3. Select your device from the dropdown:
   - HackRF One (if connected)
   - RTL-SDR: RTLSDR_APRS
   - RTL-SDR: RTLSDR_VOICE
   - RTL-SDR: RTLSDR_POCSAG
   - RTL-SDR: RTLSDR_SCAN

The selected device will be used for all captures until you change it.

## Troubleshooting

### Problem: Device Not Found

**Symptom:**
```
Error: No RTL-SDR devices found
```

**Solution:**
1. Check USB connection: `lsusb | grep RTL`
2. Verify permissions: `ls -l /dev/bus/usb/*/*`
3. Add user to plugdev group: `sudo usermod -a -G plugdev $USER`
4. Reconnect USB devices

### Problem: Wrong Device Selected

**Symptom:**
The wrong RTL-SDR device is being used.

**Solution:**
1. Always use `device_serial` instead of `device_index`
2. Verify serial numbers: `rtl_test -t`
3. Check for typos in serial number strings

### Problem: Device Busy

**Symptom:**
```
Error: usb_claim_interface error -6
```

**Solution:**
1. Check if another process is using the device:
   ```bash
   lsof | grep rtl
   ```
2. Close other SDR applications (GQRX, SDR#, etc.)
3. Stop streaming sessions:
   ```bash
   curl -X DELETE http://localhost:5000/stream-decode/<session_id>
   ```

### Problem: USB Power Issues

**Symptom:**
- Devices disconnect randomly
- "Device not found" errors
- Poor reception quality

**Solution:**
1. Use a powered USB hub (recommended: USB 3.0 with 2A+ power supply)
2. Don't daisy-chain USB hubs
3. Reduce number of devices if power is insufficient
4. Check USB cable quality (use short, high-quality cables)

### Problem: Conflicting PPM Corrections

**Symptom:**
Each device has different frequency error (PPM).

**Solution:**
1. Measure PPM for each device:
   ```bash
   # Using kalibrate-rtl
   kal -s GSM900 -d 0
   kal -s GSM900 -d 1
   ```
2. Record PPM values in `rtlsdr.conf`
3. Apply corrections in API calls:
   ```json
   {
     "frequency": 144800000,
     "device_serial": "RTLSDR_APRS",
     "ppm_error": 52
   }
   ```

### Problem: Devices Not Detected in Docker

**Symptom:**
`rtl_test` works on host but not in Docker container.

**Solution:**
1. Verify device mapping in `docker-compose.yml`:
   ```yaml
   devices:
     - /dev/bus/usb:/dev/bus/usb
   ```
2. Restart container:
   ```bash
   docker compose down
   docker compose up -d
   ```
3. Check container privileges (may need privileged mode)

## Advanced Configuration

### Persistent Device Assignment with udev Rules

Create a udev rule to assign consistent device paths:

```bash
# Create udev rule file
sudo nano /etc/udev/rules.d/99-rtlsdr.rules
```

Add rules for each device:
```
# RTL-SDR APRS Device
SUBSYSTEM=="usb", ATTRS{serial}=="RTLSDR_APRS", SYMLINK+="rtlsdr_aprs"

# RTL-SDR Voice Device
SUBSYSTEM=="usb", ATTRS{serial}=="RTLSDR_VOICE", SYMLINK+="rtlsdr_voice"
```

Reload udev rules:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Now devices will have persistent paths:
- `/dev/rtlsdr_aprs`
- `/dev/rtlsdr_voice`

## Performance Considerations

### CPU Usage

Each active RTL-SDR device adds CPU overhead:
- Idle: ~1-2% CPU
- Active FM demodulation: ~10-15% CPU
- APRS decoding: ~5-10% CPU
- POCSAG decoding: ~5-10% CPU

**Recommendation**: Monitor with Metricbeat dashboard in Kibana

### Memory Usage

Each device adds ~100-200 MB RAM depending on sample rate and processing.

**Recommendation**: Ensure at least 1 GB RAM per active device

### USB Bandwidth

USB 2.0 bandwidth: ~480 Mbps
USB 3.0 bandwidth: ~5 Gbps

**Recommendation**:
- USB 2.0: Maximum 2-3 RTL-SDR devices at 2.4 MHz sample rate
- USB 3.0: Up to 8+ devices possible

### Sample Rate Limits

Higher sample rates consume more CPU and USB bandwidth:
- 250 kHz: Very low CPU, narrow bandwidth
- 1.024 MHz: Low CPU, good for voice
- 2.048 MHz: Medium CPU, good for APRS/POCSAG
- 2.4 MHz: High CPU, maximum bandwidth

## Support

For issues with multiple RTL-SDR devices:
1. Check the troubleshooting section above
2. Verify device detection: `rtl_test -t`
3. Check container logs: `docker logs radio-transcription-api`
4. File an issue on GitHub with `rtl_test` output

## References

- RTL-SDR Official Site: https://www.rtl-sdr.com/
- rtl-sdr tools: https://github.com/osmocom/rtl-sdr
- USB Device Identification: https://www.linux-usb.org/
