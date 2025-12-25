#!/bin/bash
set -e

echo "========================================="
echo "Running tests in Docker..."
echo "========================================="

# Build test image
docker build -f Dockerfile.test -t radio-test:latest .

# Run tests with coverage
docker run --rm \
    -v "$(pwd)/htmlcov:/app/htmlcov" \
    -v "$(pwd)/coverage.xml:/app/coverage.xml" \
    radio-test:latest \
    pytest -v --cov=. --cov-report=term-missing --cov-report=html --cov-report=xml

echo ""
echo "========================================="
echo "Tests completed successfully!"
echo "Coverage report: htmlcov/index.html"
echo "========================================="
