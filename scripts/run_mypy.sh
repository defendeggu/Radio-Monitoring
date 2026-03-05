#!/bin/bash
set -e

echo "========================================="
echo "Running mypy type checking..."
echo "========================================="

mypy --config-file mypy.ini \
    api_service.py \
    sdr_hardware.py \
    transcription_service.py \
    aprs_decoder_service.py \
    repeater_activity_analyzer.py \
    elasticsearch_service.py \
    streaming_decoder_service.py

echo ""
echo "========================================="
echo "✓ Type checking passed!"
echo "========================================="
