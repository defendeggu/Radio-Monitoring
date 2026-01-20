# Archived Test Logs

This directory contains logs from manual hardware tests conducted during development.

## 📅 Log Timeline

### January 2026 Tests

**Duration Bug Investigation (Jan 20, 2026)**
- `live-streaming-test-20260120-*.log` - Multiple test runs
- Tests conducted to debug and fix streaming decoder duration issue
- Results documented in `TEST_REPORT_20260120.md`

**RTL-SDR Hardware Tests (Jan 9, 2026)**
- `hardware-test-rtlsdr-20260109-111337.log` - RTL-SDR specific tests
- `hardware-test-streaming-highgain-20260109-122951.log` - High gain tests
- Tests conducted during RTL-SDR Unicode detection fix

**Retry Logic Tests (Jan 9, 2026)**
- `hardware-test-retry-20260109-*.log` - Multiple retry test runs
- Testing USB timeout handling and recovery

**Initial Hardware Tests (Jan 9, 2026)**
- `hardware-test-20260109-030504.log` - First comprehensive hardware test
- Baseline testing for all SDR types

### January 2026 (Earlier)
- `live-streaming-test-20260111-221520.log` - Early streaming tests

## 📊 Key Findings

These logs document:
- RTL-SDR Unicode detection issue (fixed in commit 337043a)
- Duration bug in streaming decoders (fixed in commit d1f40c4)
- High gain signal quality analysis
- USB stability testing

## 🔍 Log Format

Most logs contain:
- Test start/end timestamps
- API endpoint calls and responses
- Session IDs for tracking
- Error messages and debugging output
- Test results and statistics

## 🧹 Retention Policy

Logs older than 90 days may be deleted unless they document:
- Critical bug fixes
- Important system behavior discoveries
- Performance benchmarks

**Last Updated**: January 20, 2026
**Total Logs**: 11 files
**Disk Usage**: ~100 KB
