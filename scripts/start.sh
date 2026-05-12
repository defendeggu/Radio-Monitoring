#!/bin/bash

echo "========================================="
echo "Radio Monitoring System - Starting"
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

# Check for connected SDR devices
echo "Checking SDR device connection..."
SDR_DETECTED=false

if hackrf_info &> /dev/null 2>&1; then
    echo "✓ HackRF One detected (USB)"
    SDR_DETECTED=true
fi

if timeout 1 rtl_test -t &> /dev/null 2>&1; then
    echo "✓ RTL-SDR detected (USB)"
    SDR_DETECTED=true
fi

if airspyhf_info &> /dev/null 2>&1; then
    echo "✓ Airspy HF+ detected (USB)"
    SDR_DETECTED=true
fi

if command -v uhd_find_devices &> /dev/null && uhd_find_devices &> /dev/null 2>&1; then
    echo "✓ USRP N200 detected (Gigabit Ethernet)"
    echo "  → Multi-Channel DDC mode available in web interface"
    SDR_DETECTED=true
fi

if [ "$SDR_DETECTED" = false ]; then
    echo "Warning: No SDR device detected!"
    echo "  - USB SDRs (HackRF/RTL-SDR/Airspy): check USB connection"
    echo "  - USRP N200: check Ethernet cable and host IP subnet"
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

# Start web interface (serves the pre-built Vite bundle from frontend/dist/)
echo "Starting web interface on port 8080..."
if [ -d "frontend/dist" ]; then
    python -m http.server 8080 --directory frontend/dist &
    WEB_PID=$!
else
    echo "Warning: frontend/dist/ not found. Run 'cd frontend && npm install && npm run build' first."
    echo "Alternatively, run 'cd frontend && npm run dev' for the Vite hot-reload dev server (port 5173)."
    WEB_PID=0
fi

echo ""
echo "========================================="
echo "Services Started!"
echo "========================================="
echo ""
echo "🌐 Web Interface: http://localhost:8080   (dark sidebar UI — served from frontend/dist/)"
echo "🔌 API Endpoint:  http://localhost:5000"
echo "📊 Health Check:  http://localhost:5000/health"
echo ""
echo "Development Tools:"
echo "  pytest                    # Run tests"
echo "  ./scripts/run_mypy.sh     # Type checking"
echo "  ./scripts/run_coverage.sh # Test coverage report"
echo ""
echo "Frontend (dark sidebar UI):"
echo "  cd frontend && npm run dev  # Vite hot-reload dev server (port 5173)"
echo "  cd frontend && npm run build # Rebuild dist/ (required after source changes)"
echo ""
echo "Production Deployment:"
echo "  Docker with Gunicorn + ELK Stack:"
echo "    ./scripts/setup-elk-security.sh  # First time only: generate passwords"
echo "    docker compose up -d"
echo "    ./scripts/post-docker-setup.sh   # First time only: create ES users + import dashboards"
echo "  "
echo "  Then access:"
echo "    - Web Interface: http://localhost:8080"
echo "    - API:           http://localhost:5000"
echo "    - Kibana:        http://localhost:5601"
echo "    - Elasticsearch: http://localhost:9200"
echo "  "
echo "  ⚠️  Note: API authentication is enabled in Docker mode"
echo "  Get your API keys from .env (API_KEYS variable)"
echo ""
echo "System Resources (Docker):"
echo "  - API Memory Limit: 4 GB"
echo "  - Whisper Model: small (configurable in .env)"
echo "  - APRS/POCSAG streaming: up to 3600s single-channel sessions"
echo "  - Multi-Channel DDC: USRP N200 only — 2–8 channels from one wide-band IQ stream"
echo "    Select 'USRP N200 (Ethernet)' in the SDR device selector to enable the tab"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Trap Ctrl+C and cleanup
trap "echo ''; echo 'Stopping services...'; kill $API_PID 2>/dev/null; [ $WEB_PID -ne 0 ] && kill $WEB_PID 2>/dev/null; exit 0" INT

# Wait for processes
wait
