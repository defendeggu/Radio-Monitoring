#!/bin/bash
#
# Post-Docker Setup Script
# Runs after docker compose up to configure the ELK stack
#
# This script:
# - Waits for all services to be healthy
# - Imports Kibana dashboards automatically
# - Verifies the setup
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Radio Monitoring System"
echo "Post-Docker Setup"
echo "=========================================="
echo ""

# Load environment variables
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a  # Automatically export all variables
    source "${PROJECT_ROOT}/.env"
    set +a
elif [ -f "${PROJECT_ROOT}/.env.elk" ]; then
    set -a  # Automatically export all variables
    source "${PROJECT_ROOT}/.env.elk"
    set +a
fi

# Check if Docker Compose is running
echo "🔍 Checking Docker services..."
if ! docker compose ps | grep -q "radio-"; then
    echo "❌ ERROR: No Radio Monitoring Docker services found"
    echo "   Please start the stack first:"
    echo "     docker compose up -d"
    exit 1
fi

echo "✅ Docker services are running"
echo ""

# Wait for Elasticsearch to be healthy
echo "⏳ Waiting for Elasticsearch to be ready..."
MAX_WAIT=120
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if docker exec radio-elasticsearch curl -sf -u "elastic:${ELASTIC_PASSWORD}" http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        echo "✅ Elasticsearch is healthy"
        break
    fi

    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        echo "   Still waiting... (${WAIT_COUNT}s / ${MAX_WAIT}s)"
    fi

    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "❌ ERROR: Elasticsearch did not become healthy within ${MAX_WAIT} seconds"
    echo "   Check logs: docker logs radio-elasticsearch"
    exit 1
fi

echo ""

# Configure Elasticsearch users and roles
# This must run after ES is healthy but before Logstash/Kibana are expected to connect
echo "👤 Configuring Elasticsearch users and roles..."
"${SCRIPT_DIR}/setup-elk-users.sh"
echo ""

# Restart Logstash and Metricbeat so they pick up the newly created credentials
echo "🔄 Restarting Logstash and Metricbeat with new credentials..."
docker compose restart logstash metricbeat
echo "✅ Logstash and Metricbeat restarted"
echo ""

# Wait for Kibana to be healthy
echo "⏳ Waiting for Kibana to be ready..."
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -sf -u "elastic:${ELASTIC_PASSWORD}" http://localhost:5601/api/status > /dev/null 2>&1; then
        echo "✅ Kibana is healthy"
        break
    fi

    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        echo "   Still waiting... (${WAIT_COUNT}s / ${MAX_WAIT}s)"
    fi

    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "❌ ERROR: Kibana did not become healthy within ${MAX_WAIT} seconds"
    echo "   Check logs: docker logs radio-kibana"
    exit 1
fi

echo ""

# Import Kibana Dashboards
echo "📊 Importing Kibana dashboards..."
echo ""

if [ -f "${SCRIPT_DIR}/import-kibana-dashboards.sh" ]; then
    "${SCRIPT_DIR}/import-kibana-dashboards.sh"
else
    echo "⚠️  Warning: Dashboard import script not found"
    echo "   Run manually: ./scripts/import-kibana-dashboards.sh"
fi

echo ""

# Verify API is accessible
echo "🔍 Verifying API service..."
if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ Radio API is responding"
else
    echo "⚠️  Warning: Radio API is not responding at http://localhost:5000"
    echo "   Check logs: docker logs radio-transcription-api"
fi

echo ""

# Display service URLs
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "🌐 Access your services:"
echo ""
echo "  Web Interface:  http://localhost:8080"
echo "  Radio API:      http://localhost:5000"
echo "  Kibana:         http://localhost:5601"
echo "    Username:     elastic"
echo "    Password:     ${ELASTIC_PASSWORD}"
echo ""
echo "  Elasticsearch:  http://localhost:9200"
echo "  Logstash:       http://localhost:9600"
echo "  Portainer:      http://localhost:9000"
echo ""
echo "📊 Kibana Dashboards:"
echo "    http://localhost:5601/app/dashboards"
echo ""
echo "📚 Documentation:"
echo "    See README.md for usage instructions"
echo ""
echo "🔧 Useful Commands:"
echo "    docker compose logs -f              # View all logs"
echo "    docker compose ps                   # Check service status"
echo "    docker compose restart radio-api    # Restart API"
echo "    docker compose down                 # Stop all services"
echo ""
