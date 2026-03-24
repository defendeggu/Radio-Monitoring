#!/bin/bash
#
# Set passwords for Elasticsearch built-in users
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source the passwords from .env.elk (project root)
if [ -f "${PROJECT_ROOT}/.env.elk" ]; then
    source "${PROJECT_ROOT}/.env.elk"
elif [ -f "${PROJECT_ROOT}/.env" ]; then
    source "${PROJECT_ROOT}/.env"
else
    echo "Error: Neither .env.elk nor .env found in project root!"
    echo "Please run ./scripts/setup-elk-security.sh first"
    exit 1
fi

echo "=========================================="
echo "Setting up Elasticsearch built-in users"
echo "=========================================="
echo ""

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
until curl -s -u "elastic:${ELASTIC_PASSWORD}" http://localhost:9200/_cluster/health > /dev/null 2>&1; do
    echo "  Elasticsearch not ready yet, waiting..."
    sleep 5
done
echo "✅ Elasticsearch is ready"
echo ""

# Set kibana_system password
echo "Setting kibana_system password..."
curl -s -X POST -u "elastic:${ELASTIC_PASSWORD}" \
  "http://localhost:9200/_security/user/kibana_system/_password" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"${KIBANA_SYSTEM_PASSWORD}\"}" > /dev/null
echo "✅ kibana_system password set"

# Set logstash_system password
echo "Setting logstash_system password..."
curl -s -X POST -u "elastic:${ELASTIC_PASSWORD}" \
  "http://localhost:9200/_security/user/logstash_system/_password" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"${LOGSTASH_SYSTEM_PASSWORD}\"}" > /dev/null
echo "✅ logstash_system password set"

# Set beats_system password
echo "Setting beats_system password..."
curl -s -X POST -u "elastic:${ELASTIC_PASSWORD}" \
  "http://localhost:9200/_security/user/beats_system/_password" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"${BEATS_SYSTEM_PASSWORD}\"}" > /dev/null
echo "✅ beats_system password set"

# Create logstash_writer role (custom role - not a built-in user)
echo "Creating logstash_writer role..."
curl -s -X PUT -u "elastic:${ELASTIC_PASSWORD}" \
  "http://localhost:9200/_security/role/logstash_writer" \
  -H "Content-Type: application/json" \
  -d '{
    "cluster": ["manage_index_templates", "monitor", "manage_ilm"],
    "indices": [{
      "names": ["radio-*", "logstash-*"],
      "privileges": ["write", "create", "create_index", "manage", "manage_ilm"]
    }]
  }' > /dev/null
echo "✅ logstash_writer role created"

# Create logstash_writer user
echo "Creating logstash_writer user..."
curl -s -X PUT -u "elastic:${ELASTIC_PASSWORD}" \
  "http://localhost:9200/_security/user/logstash_writer" \
  -H "Content-Type: application/json" \
  -d "{
    \"password\": \"${LOGSTASH_WRITER_PASSWORD}\",
    \"roles\": [\"logstash_writer\"],
    \"full_name\": \"Logstash Writer\"
  }" > /dev/null
echo "✅ logstash_writer user created"

echo ""
echo "=========================================="
echo "User passwords configured successfully!"
echo "=========================================="
echo ""
echo "You can now restart the services:"
echo "  docker compose restart logstash"
echo "  docker compose restart metricbeat"
echo ""
