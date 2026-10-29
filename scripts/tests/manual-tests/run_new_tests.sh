#!/bin/bash
#
# Test Runner for Phase 2 Tests
# Runs all newly created tests and generates coverage report
#

set -e

echo "═══════════════════════════════════════════════════════"
echo "    Radio Monitoring System - Test Execution"
echo "═══════════════════════════════════════════════════════"
echo ""

# Check if pytest is installed
if ! python3 -m pytest --version &> /dev/null; then
    echo "❌ pytest not found!"
    echo ""
    echo "Installing pytest and dependencies..."
    pip3 install pytest pytest-cov pytest-mock pytest-flask
    echo ""
fi

echo "🧪 Running Phase 2.1: Repeater Scanning Tests"
echo "─────────────────────────────────────────────────────"
python3 -m pytest tests/test_repeater_scanning.py -v --tb=short
echo ""

echo "🧪 Running Phase 2.2: Streaming Decoder Tests"
echo "─────────────────────────────────────────────────────"
python3 -m pytest tests/test_streaming_decoders.py -v --tb=short
echo ""

echo "🧪 Running Phase 2.3A: APRS Decoder Tests"
echo "─────────────────────────────────────────────────────"
python3 -m pytest tests/test_aprs_decoder.py -v --tb=short
echo ""

echo "🧪 Running Phase 2.3B: POCSAG Decoder Tests"
echo "─────────────────────────────────────────────────────"
python3 -m pytest tests/test_pocsag_decoder.py -v --tb=short
echo ""

echo "═══════════════════════════════════════════════════════"
echo "    Coverage Report Generation"
echo "═══════════════════════════════════════════════════════"
echo ""

echo "📊 Generating coverage report for new tests..."
python3 -m pytest \
    tests/test_repeater_scanning.py \
    tests/test_streaming_decoders.py \
    tests/test_aprs_decoder.py \
    tests/test_pocsag_decoder.py \
    --cov=radiomoni.repeater_activity_analyzer \
    --cov=radiomoni.decoders.streaming \
    --cov=radiomoni.decoders.aprs \
    --cov=radiomoni.decoders.pocsag \
    --cov-report=term-missing \
    --cov-report=html:htmlcov/phase2

echo ""
echo "═══════════════════════════════════════════════════════"
echo "    Test Execution Complete!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "📊 Coverage report saved to: htmlcov/phase2/index.html"
echo "🌐 Open in browser: file://$(pwd)/htmlcov/phase2/index.html"
echo ""
