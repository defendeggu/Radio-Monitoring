#!/usr/bin/env bash
#
# Import all Kibana saved objects (index patterns, dashboards) from
# monitoring/kibana/dashboards/*.ndjson. Overwrites existing objects.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -f .env ]] && { set -a; source .env; set +a; }
KIBANA_URL="${KIBANA_URL:-http://127.0.0.1:${KIBANA_PORT:-5601}}"

kibana_ready() {
  curl -fs "$KIBANA_URL/api/status" 2>/dev/null | grep -q '"level":"available"'
}

# Kibana answers HTTP requests while it is still starting (or crash-looping
# after a failed saved-object migration), so wait for overall level "available".
echo "Waiting for Kibana at $KIBANA_URL ..."
for _ in $(seq 1 100); do
  kibana_ready && break
  sleep 3
done
if ! kibana_ready; then
  echo "Kibana is not available — check: docker logs --tail 50 radio-kibana" >&2
  exit 1
fi

failed=0
# index patterns first, dashboards afterwards
for f in $(ls monitoring/kibana/dashboards/*index-patterns*.ndjson; ls monitoring/kibana/dashboards/*.ndjson | grep -v index-patterns); do
  result="$(curl -s -u "elastic:${ELASTIC_PASSWORD}" -H 'kbn-xsrf: true' \
    -F "file=@$f" "$KIBANA_URL/api/saved_objects/_import?overwrite=true")"
  if grep -q '"success":true' <<<"$result"; then
    echo "  ok   $(basename "$f")"
  else
    echo "  FAIL $(basename "$f"): ${result:0:200}"
    failed=1
  fi
done
exit $failed
