#!/bin/bash
set -e

echo "========================================="
echo "Generating coverage report..."
echo "========================================="

# Build test image
docker build -f Dockerfile.test -t radio-test:latest .

# Run tests with coverage
docker run --rm \
    -v "$(pwd)/htmlcov:/app/htmlcov" \
    -v "$(pwd)/coverage.xml:/app/coverage.xml" \
    radio-test:latest \
    pytest --cov=. --cov-report=html --cov-report=xml --cov-report=term --cov-fail-under=80

echo ""
echo "========================================="
echo "Coverage reports generated:"
echo "  HTML: htmlcov/index.html"
echo "  XML:  coverage.xml"
echo "========================================="
