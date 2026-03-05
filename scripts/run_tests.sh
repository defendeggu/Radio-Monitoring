#!/bin/bash
set -e

echo "========================================="
echo "Running tests..."
echo "========================================="

pytest -v --cov=. --cov-report=term-missing --cov-report=html --cov-report=xml

echo ""
echo "========================================="
echo "Tests completed successfully!"
echo "Coverage report: htmlcov/index.html"
echo "========================================="
