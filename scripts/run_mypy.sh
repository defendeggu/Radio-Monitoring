#!/bin/bash
set -e

echo "========================================="
echo "Running mypy type checking..."
echo "========================================="

# Build test image if not exists
docker build -f Dockerfile.test -t radio-test:latest . > /dev/null 2>&1

# Run mypy
docker run --rm radio-test:latest \
    mypy --config-file mypy.ini \
    api_service.py radio_capture.py transcription_service.py

echo ""
echo "========================================="
echo "✓ Type checking passed!"
echo "========================================="
