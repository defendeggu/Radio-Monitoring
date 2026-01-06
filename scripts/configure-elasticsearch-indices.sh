#!/bin/bash
#
# Configure Elasticsearch Index Settings
#
# This script applies performance-optimized index settings via the Elasticsearch API.
# Run this after Elasticsearch is started and healthy.
#
# Usage: ./scripts/configure-elasticsearch-indices.sh
#

set -e

# Load environment variables
if [ -f .env.elk ]; then
    source .env.elk
fi

# Elasticsearch connection
ES_HOST="${ES_HOST:-http://localhost:9200}"
ES_USER="${ELASTICSEARCH_USERNAME:-elastic}"
ES_PASS="${ELASTIC_PASSWORD}"

if [ -z "$ES_PASS" ]; then
    echo "Error: ELASTIC_PASSWORD not set"
    echo "Please source .env.elk or set ELASTIC_PASSWORD"
    exit 1
fi

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
until curl -s -u "$ES_USER:$ES_PASS" "$ES_HOST/_cluster/health" > /dev/null; do
    echo "Waiting for Elasticsearch..."
    sleep 5
done
echo "Elasticsearch is ready!"

# Apply index template with performance settings
echo "Applying index template with performance settings..."
curl -X PUT -u "$ES_USER:$ES_PASS" \
    -H "Content-Type: application/json" \
    "$ES_HOST/_index_template/radio-monitoring-performance" \
    -d '{
  "index_patterns": ["radio-*"],
  "priority": 100,
  "template": {
    "settings": {
      "index": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "5s",
        "translog": {
          "durability": "async",
          "sync_interval": "30s"
        },
        "search": {
          "slowlog": {
            "threshold": {
              "query": {
                "warn": "10s",
                "info": "5s"
              }
            }
          }
        },
        "indexing": {
          "slowlog": {
            "threshold": {
              "index": {
                "warn": "10s",
                "info": "5s"
              }
            }
          }
        }
      }
    }
  }
}'

echo -e "\n\nIndex template applied successfully!"

# Update settings for existing indices
echo -e "\nUpdating settings for existing indices..."
curl -X PUT -u "$ES_USER:$ES_PASS" \
    -H "Content-Type: application/json" \
    "$ES_HOST/radio-*/_settings" \
    -d '{
  "index": {
    "refresh_interval": "5s",
    "translog": {
      "durability": "async",
      "sync_interval": "30s"
    }
  }
}'

echo -e "\n\nElasticsearch index settings configured successfully!"
echo "Performance optimizations applied:"
echo "  - Refresh interval: 5s (reduced from 1s default)"
echo "  - Translog: async with 30s sync interval"
echo "  - Shards: 1 (single node setup)"
echo "  - Replicas: 0 (single node setup)"
echo "  - Slow query logging enabled"
