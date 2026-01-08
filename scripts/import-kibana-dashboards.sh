#!/bin/bash
#
# Kibana Dashboard Import Script
# Automatically imports all NDJSON dashboard files into Kibana
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DASHBOARDS_DIR="${PROJECT_ROOT}/monitoring/kibana/dashboards"

echo "=========================================="
echo "Kibana Dashboard Import"
echo "=========================================="
echo ""

# Check if Kibana is running
echo "🔍 Checking Kibana availability..."
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

# Wait for Kibana to be ready (max 60 seconds)
MAX_WAIT=60
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -sf "${KIBANA_URL}/api/status" > /dev/null 2>&1; then
        echo "✅ Kibana is ready at ${KIBANA_URL}"
        break
    fi

    if [ $WAIT_COUNT -eq 0 ]; then
        echo "⏳ Waiting for Kibana to start..."
    fi

    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "❌ ERROR: Kibana is not responding after ${MAX_WAIT} seconds"
    echo "   Please ensure Kibana is running at ${KIBANA_URL}"
    exit 1
fi

echo ""

# Load environment variables
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a  # Automatically export all variables
    source "${PROJECT_ROOT}/.env"
    set +a
    echo "✅ Loaded credentials from .env"
elif [ -f "${PROJECT_ROOT}/.env.elk" ]; then
    set -a  # Automatically export all variables
    source "${PROJECT_ROOT}/.env.elk"
    set +a
    echo "✅ Loaded credentials from .env.elk"
else
    echo "⚠️  Warning: No .env or .env.elk file found"
    echo "   Dashboard import may fail if authentication is required"
fi

echo ""

# Check if Python import script exists
IMPORT_SCRIPT="${SCRIPT_DIR}/import_kibana_dashboards.py"
if [ ! -f "$IMPORT_SCRIPT" ]; then
    echo "❌ ERROR: Import script not found: $IMPORT_SCRIPT"
    exit 1
fi

# Check if dashboard directory exists
if [ ! -d "$DASHBOARDS_DIR" ]; then
    echo "❌ ERROR: Dashboard directory not found: $DASHBOARDS_DIR"
    exit 1
fi

# Count dashboard files
DASHBOARD_COUNT=$(find "$DASHBOARDS_DIR" -name "*.ndjson" | wc -l)
if [ "$DASHBOARD_COUNT" -eq 0 ]; then
    echo "⚠️  Warning: No .ndjson dashboard files found in $DASHBOARDS_DIR"
    exit 0
fi

echo "📊 Found ${DASHBOARD_COUNT} dashboard file(s) to import"
echo ""

# Run Python import script
echo "🚀 Starting dashboard import..."
echo ""

if command -v python3 &> /dev/null; then
    # Try with virtual environment first
    if [ -f "${PROJECT_ROOT}/venv/bin/python3" ]; then
        echo "Using virtual environment Python..."
        "${PROJECT_ROOT}/venv/bin/python3" "$IMPORT_SCRIPT"
    else
        # Fall back to system Python
        python3 "$IMPORT_SCRIPT"
    fi
else
    echo "❌ ERROR: Python 3 is not installed"
    exit 1
fi

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "=========================================="
    echo "✅ Dashboard Import Complete!"
    echo "=========================================="
    echo ""
    echo "📊 Access dashboards at:"
    echo "   ${KIBANA_URL}/app/dashboards"
    echo ""
else
    echo "=========================================="
    echo "❌ Dashboard Import Failed"
    echo "=========================================="
    echo ""
    echo "Troubleshooting:"
    echo "  - Check Kibana is running: ${KIBANA_URL}"
    echo "  - Verify credentials in .env or .env.elk"
    echo "  - Check logs: docker logs radio-kibana"
    echo ""
    exit $EXIT_CODE
fi
