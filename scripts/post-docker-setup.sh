#!/usr/bin/env bash
#
# Run once after "docker compose up -d" (and after upgrades):
# configures Elasticsearch, restarts the ingest services and imports the
# Kibana dashboards. Does nothing ELK-related in the light profile.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -f .env ]] || { echo "No .env — run ./scripts/setup-env.sh first" >&2; exit 1; }
set -a; source .env; set +a

WEB="http://localhost:${WEB_PORT:-8080}"

if [[ ",${COMPOSE_PROFILES:-}," == *",elk,"* ]]; then
  ./scripts/setup-elk-users.sh
  echo "Restarting ingest services with the new credentials..."
  docker compose restart logstash metricbeat filebeat >/dev/null
  ./scripts/import-kibana-dashboards.sh || echo "Dashboard import failed — run ./scripts/import-kibana-dashboards.sh later"
else
  echo "Light profile (no ELK): nothing to configure in Elasticsearch."
fi

echo
echo "Checking the API through the web proxy..."
for _ in $(seq 1 30); do
  if curl -fs "$WEB/api/health" >/dev/null; then
    echo "  API is up: $WEB/api/health"
    break
  fi
  sleep 2
done

cat <<EOF

Setup complete.

  Web UI:   $WEB            (enter the API key under Settings)
  API docs: $WEB/#/api
EOF
if [[ ",${COMPOSE_PROFILES:-}," == *",elk,"* ]]; then
  echo "  Kibana:   http://${KIBANA_BIND:-127.0.0.1}:${KIBANA_PORT:-5601}   (user: elastic, password: ELASTIC_PASSWORD in .env)"
fi
echo
echo "API key: see API_KEYS in .env"
