#!/bin/bash
set -e

echo "========================================="
echo "Generating coverage report..."
echo "========================================="

pytest --cov=. --cov-report=html --cov-report=xml --cov-report=term --cov-fail-under=80

echo ""
echo "========================================="
echo "Coverage reports generated:"
echo "  HTML: htmlcov/index.html"
echo "  XML:  coverage.xml"
echo "========================================="
