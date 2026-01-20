# Manual Test Scripts

This directory contains manual test scripts that were used during development and testing of the radio monitoring system. These scripts are preserved for historical reference and potential future use.

## 📝 Scripts Overview

### Streaming Decoder Tests (Most Recent - Jan 2026)

**`monitor_session.sh`** (Jan 20, 2026)
- Monitors streaming decoder sessions in real-time
- Shows status updates every 30-60 seconds
- Useful for observing APRS/POCSAG streaming sessions
- **Status**: ✅ Active - Still useful for debugging

**`live_streaming_test.sh`** (Jan 20, 2026)
- Sequential APRS and POCSAG streaming tests
- Tests with configurable gain and duration
- Used for testing duration bug fix
- **Status**: ⚠️ Historical - Replaced by automated tests

**`start_pocsag_test.sh`** (Jan 20, 2026)
- Quick POCSAG streaming test starter
- Simple wrapper for starting POCSAG captures
- **Status**: ✅ Active - Still useful for quick tests

### Hardware Tests (Jan 2026)

**`hardware_test_rtlsdr.sh`** (Jan 9, 2026)
- RTL-SDR specific hardware tests
- Tests capture, modulation, and decoding
- Used during RTL-SDR Unicode fix development
- **Status**: ⚠️ Historical - Preserved for reference

**`hardware_test_streaming_high_gain.sh`** (Jan 9, 2026)
- Tests streaming decoders with high gain settings
- Validates signal quality at different gain levels
- **Status**: ⚠️ Historical - Replaced by automated tests

**`hardware_test_retry.sh`** (Jan 9, 2026)
- Retry logic for flaky hardware connections
- Handles USB timeout issues
- **Status**: ⚠️ Historical - Replaced by automated tests

**`hardware_test_suite_0305.sh`** (Jan 8, 2026)
- Comprehensive hardware test suite
- Tests all SDR types (HackRF, RTL-SDR, Airspy HF+)
- **Status**: ⚠️ Historical - Replaced by pytest suite

### Schedulers & Runners (Jan 2026)

**`schedule_hardware_tests.sh`** (Jan 8, 2026)
- Schedules periodic hardware tests
- Used cron-like scheduling
- **Status**: ⚠️ Deprecated - No longer needed

**`run_new_tests.sh`** (Jan 4, 2026)
- Runs new test implementations
- **Status**: ⚠️ Historical - Replaced by pytest

## 🗂️ Log Files

All log files from these tests have been moved to:
```
/home/spia/my-project/logs/archive/
```

Logs are preserved for debugging and analysis of test results.

## ⚡ Recommended Test Approach

For current testing, use the official test suite:

```bash
# Run all tests
pytest

# Run with coverage
./scripts/run_coverage.sh

# Run type checking
./scripts/run_mypy.sh

# Run specific test category
pytest -m unit
pytest -m integration
```

## 🔄 Maintenance

These scripts are kept for:
- Historical reference
- Understanding past debugging approaches
- Potential reuse in specific scenarios
- Documentation of manual testing procedures

**Last Updated**: January 20, 2026
**Status**: Archived - Use pytest suite for regular testing
