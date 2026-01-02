#!/bin/bash

echo "========================================="
echo "Radio Transcription System - Starting"
echo "========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found."
    echo "Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Create recordings directory
mkdir -p recordings

# Check if SDR is connected (HackRF or RTL-SDR)
echo "Checking SDR device connection..."
SDR_DETECTED=false

if hackrf_info &> /dev/null 2>&1; then
    echo "✓ HackRF detected"
    SDR_DETECTED=true
fi

if timeout 1 rtl_test -t &> /dev/null 2>&1; then
    echo "✓ RTL-SDR detected"
    SDR_DETECTED=true
fi

if [ "$SDR_DETECTED" = false ]; then
    echo "Warning: No SDR device detected!"
    echo "Running in simulation mode..."
    echo ""
fi

# Start Flask API in background
echo "========================================="
echo "⚠️  DEVELOPMENT MODE"
echo "========================================="
echo "Starting Flask development server on port 5000..."
echo ""
echo "Note: This uses Flask's built-in server, which is"
echo "NOT suitable for production deployment!"
echo ""
echo "For production with Gunicorn (recommended):"
echo "  gunicorn --config gunicorn_config.py api_service:app"
echo ""
echo "Or use Docker (includes Gunicorn + full ELK stack):"
echo "  docker compose up -d"
echo "========================================="
echo ""

python api_service.py &
API_PID=$!

# Wait for API to start
sleep 2

# Start simple HTTP server for web interface
echo "Starting web interface on port 8080..."
python -m http.server 8080 &
WEB_PID=$!

echo ""
echo "========================================="
echo "Services Started!"
echo "========================================="
echo ""
echo "Web Interface: http://localhost:8080"
echo "API: http://localhost:5000"
echo ""
echo "To start N8N (in another terminal):"
echo "  npx n8n"
echo "  Then access: http://localhost:5678"
echo ""
echo "For Docker deployment with full ELK stack:"
echo "  docker compose up -d"
echo "  Note: API authentication is enabled in Docker mode"
echo "  Get your API keys from .env (API_KEYS variable)"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Trap Ctrl+C and cleanup
trap "echo ''; echo 'Stopping services...'; kill $API_PID $WEB_PID 2>/dev/null; exit 0" INT

# Wait for processes
wait
