# Testing Guide - Phase 2 Tests

**Created:** 04. Januar 2026
**Tests:** 133 new tests across 4 files
**Coverage Goal:** 27% → 45%+

---

## 🎯 Quick Start

### Option 1: Run All Tests (Recommended)

```bash
# Make script executable (if not already)
chmod +x run_new_tests.sh

# Run all Phase 2 tests with coverage
./run_new_tests.sh
```

### Option 2: Run Individual Test Files

```bash
# Install pytest if needed
pip3 install pytest pytest-cov pytest-mock pytest-flask

# Run specific test file
pytest tests/test_repeater_scanning.py -v
pytest tests/test_streaming_decoders.py -v
pytest tests/test_aprs_decoder.py -v
pytest tests/test_pocsag_decoder.py -v
```

### Option 3: Run All Tests Including Original

```bash
# Run ALL tests (original 67 + new 133 = 200)
pytest tests/ -v

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
```

---

## 📊 Test Files Overview

### Phase 2.1: Repeater Scanning Tests

**File:** `tests/test_repeater_scanning.py`
**Tests:** 28
**Lines:** 617
**Coverage Target:** `repeater_activity_analyzer.py` (0% → 70%+)

**Test Categories:**
- ✅ Unit Tests (14): RepeaterActivityAnalyzer class
- ✅ API Tests (8): /scan-repeaters/* endpoints
- ✅ Progress Tests (4): Live updates, ETA calculation
- ✅ ES Tests (3): Elasticsearch integration

**Run Individually:**
```bash
pytest tests/test_repeater_scanning.py -v
```

**Coverage for this module:**
```bash
pytest tests/test_repeater_scanning.py \
  --cov=repeater_activity_analyzer \
  --cov-report=term-missing
```

---

### Phase 2.2: Streaming Decoder Tests

**File:** `tests/test_streaming_decoders.py`
**Tests:** 34
**Lines:** 557
**Coverage Target:** `streaming_decoder_service.py` (0% → 70%+)

**Test Categories:**
- ✅ StreamSession Tests (4): Serialization, lifecycle
- ✅ SessionManager Tests (9): Redis integration
- ✅ StreamingAPRS Tests (6): APRS streaming decoder
- ✅ StreamingPOCSAG Tests (6): POCSAG streaming decoder
- ✅ API Tests (6): /stream/* endpoints
- ✅ Integration Tests (3): Full workflow

**Run Individually:**
```bash
pytest tests/test_streaming_decoders.py -v
```

**Coverage for this module:**
```bash
pytest tests/test_streaming_decoders.py \
  --cov=streaming_decoder_service \
  --cov-report=term-missing
```

**Note:** Requires Redis mock (automatically handled by test fixtures)

---

### Phase 2.3A: APRS Decoder Tests

**File:** `tests/test_aprs_decoder.py`
**Tests:** 37
**Lines:** 484
**Coverage Target:** `aprs_decoder_service.py` (0% → 70%+)

**Test Categories:**
- ✅ Initialization Tests (2)
- ✅ Decode Workflow Tests (4)
- ✅ Packet Parsing Tests (8)
- ✅ Payload Parsing Tests (6)
- ✅ Position Parsing Tests (4)
- ✅ Type Determination Tests (3)
- ✅ Symbol Parsing Tests (2)
- ✅ Error Handling Tests (3)
- ✅ API Integration Tests (3)
- ✅ Integration Tests (2)

**Run Individually:**
```bash
pytest tests/test_aprs_decoder.py -v
```

**Coverage for this module:**
```bash
pytest tests/test_aprs_decoder.py \
  --cov=aprs_decoder_service \
  --cov-report=term-missing
```

---

### Phase 2.3B: POCSAG Decoder Tests

**File:** `tests/test_pocsag_decoder.py`
**Tests:** 34
**Lines:** 462
**Coverage Target:** `pocsag_decoder_service.py` (0% → 70%+)

**Test Categories:**
- ✅ Initialization Tests (2)
- ✅ Decode Workflow Tests (4)
- ✅ Message Parsing Tests (8)
- ✅ Baud Rate Detection Tests (3)
- ✅ Message Type Detection Tests (4)
- ✅ Address Parsing Tests (3)
- ✅ Error Handling Tests (3)
- ✅ API Integration Tests (3)
- ✅ Integration Tests (4)

**Run Individually:**
```bash
pytest tests/test_pocsag_decoder.py -v
```

**Coverage for this module:**
```bash
pytest tests/test_pocsag_decoder.py \
  --cov=pocsag_decoder_service \
  --cov-report=term-missing
```

---

## 📈 Expected Coverage Results

### Before Phase 2 Tests

```
Overall Coverage: 27%

Critical Modules:
- repeater_activity_analyzer.py:  0%
- streaming_decoder_service.py:   0%
- aprs_decoder_service.py:        0%
- pocsag_decoder_service.py:      0%
```

### After Phase 2 Tests (Expected)

```
Overall Coverage: 45%+ (estimated)

Critical Modules:
- repeater_activity_analyzer.py:  70%+
- streaming_decoder_service.py:   70%+
- aprs_decoder_service.py:        70%+
- pocsag_decoder_service.py:      70%+
```

---

## 🔍 Coverage Report Generation

### Generate HTML Coverage Report

```bash
# All tests with HTML report
pytest tests/ \
  --cov=. \
  --cov-report=html:htmlcov \
  --cov-report=term-missing

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Generate Terminal Coverage Report

```bash
# Simple terminal output
pytest tests/ --cov=. --cov-report=term

# Detailed with missing lines
pytest tests/ --cov=. --cov-report=term-missing
```

### Coverage for Specific Modules Only

```bash
# Only Phase 2 modules
pytest tests/test_repeater_scanning.py \
       tests/test_streaming_decoders.py \
       tests/test_aprs_decoder.py \
       tests/test_pocsag_decoder.py \
  --cov=repeater_activity_analyzer \
  --cov=streaming_decoder_service \
  --cov=aprs_decoder_service \
  --cov=pocsag_decoder_service \
  --cov-report=term-missing
```

---

## 🧪 Running Tests in CI/CD

### GitHub Actions

The tests will automatically run in GitHub Actions:

```yaml
# .github/workflows/tests.yml already configured
- MyPy type checking
- Pytest (all 200 tests)
- Coverage report
```

**Check latest CI run:**
```bash
gh run list --limit 5
gh run view --log
```

---

## 🐛 Debugging Failed Tests

### Run with Verbose Output

```bash
# Maximum verbosity
pytest tests/test_repeater_scanning.py -vv

# Show print statements
pytest tests/test_repeater_scanning.py -v -s

# Stop on first failure
pytest tests/test_repeater_scanning.py -x
```

### Run Specific Test

```bash
# Run single test method
pytest tests/test_repeater_scanning.py::TestRepeaterActivityAnalyzer::test_initialization -v

# Run specific test class
pytest tests/test_repeater_scanning.py::TestRepeaterActivityAnalyzer -v
```

### Debug Mode

```bash
# Drop into debugger on failure
pytest tests/test_repeater_scanning.py --pdb

# Full traceback
pytest tests/test_repeater_scanning.py --tb=long
```

---

## 📝 Test Statistics

### Current State

```
Total Tests: 200 (67 original + 133 new)
Total Test Files: 7
Total Test Code: ~3,937 lines

Breakdown:
- test_api_service.py:          25 tests (existing)
- test_sdr_hardware.py:          26 tests (existing)
- test_transcription_service.py: 16 tests (existing)
- test_repeater_scanning.py:     28 tests (NEW)
- test_streaming_decoders.py:    34 tests (NEW)
- test_aprs_decoder.py:          37 tests (NEW)
- test_pocsag_decoder.py:        34 tests (NEW)
```

---

## 🎯 What's Tested?

### ✅ Fully Tested Components

1. **Repeater Activity Analyzer**
   - RMS power calculation from IQ samples
   - Noise floor calibration
   - Carrier detection algorithms
   - Transmission segmentation
   - File I/O operations
   - Error handling (file not found, too short)
   - Serialization (to_dict methods)

2. **Streaming Decoders**
   - Redis session management (save, get, delete, list)
   - Session serialization/deserialization
   - APRS streaming decoder (direwolf integration)
   - POCSAG streaming decoder (multimon-ng integration)
   - Concurrent session limits
   - Session expiry (TTL)

3. **APRS Decoder**
   - Direwolf output parsing
   - Position packet parsing (various formats)
   - Message packet parsing
   - Status packet parsing
   - Coordinate conversion (Lat/Lon)
   - Symbol table/code extraction
   - Compressed format handling

4. **POCSAG Decoder**
   - Multimon-ng output parsing
   - Baud rate detection (512, 1200, 2400)
   - Message type detection (alpha, numeric, tone)
   - Address parsing
   - Multiple message handling
   - Error correction

---

## 🚨 Known Issues & Limitations

### Test Dependencies

Some tests require external tools that may not be installed:
- **direwolf** - APRS decoder (falls back to simulation mode)
- **multimon-ng** - POCSAG decoder (falls back to simulation mode)
- **Redis** - Session management (uses mock in tests)

**Solution:** Tests use simulation mode when tools unavailable.

### Hardware Requirements

Tests for SDR hardware use mocks:
- HackRF One / RTL-SDR not required
- IQ sample generation is synthetic
- No actual radio signals needed

---

## 📚 Additional Resources

### Test Documentation

- **README.md** - Project overview with testing section
- **IMPROVEMENT_PLAN.md** - Detailed test implementation plan
- **USER_MANUAL.md** - User guide (German) with testing info

### Coverage Tools

```bash
# Install coverage tools
pip install pytest-cov coverage

# Generate badge
coverage-badge -o coverage.svg
```

### Continuous Improvement

**Next Steps:**
- Run tests regularly during development
- Add tests for new features
- Maintain >70% coverage for critical modules
- Update tests when APIs change

---

## ✅ Test Execution Checklist

Before committing code:

- [ ] Run all tests: `pytest tests/ -v`
- [ ] Check coverage: `pytest tests/ --cov=.`
- [ ] Run MyPy: `./scripts/run_mypy.sh`
- [ ] Ensure coverage >40% overall
- [ ] Ensure no test failures

---

**Created:** 04. Januar 2026
**Version:** 1.0
**Last Updated:** 04. Januar 2026

For questions or issues, see: [IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md)
