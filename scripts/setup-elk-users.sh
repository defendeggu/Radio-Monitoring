#!/usr/bin/env bash
#
# Configure Elasticsearch: built-in user passwords, least-privilege roles/users,
# ILM policies and index templates. Idempotent — safe to run after every upgrade.
#
# Elasticsearch is not published on the host, so all calls run inside the
# container via "docker exec".

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$(pwd)"
ES_CONTAINER="${ES_CONTAINER:-radio-elasticsearch}"

[[ -f .env ]] || { echo "No .env — run ./scripts/setup-env.sh first" >&2; exit 1; }
set -a; source .env; set +a

es() {  # es METHOD PATH [JSON-FILE|-]
  local method="$1" path="$2" body="${3:-}"
  if [[ -n "$body" ]]; then
    docker exec -i "$ES_CONTAINER" curl -s -o /dev/stderr -w '%{http_code}' -X "$method" \
      -u "elastic:${ELASTIC_PASSWORD}" -H 'Content-Type: application/json' \
      "http://localhost:9200${path}" --data-binary @- < "$body" 2>/dev/null
  else
    docker exec "$ES_CONTAINER" curl -s -o /dev/null -w '%{http_code}' -X "$method" \
      -u "elastic:${ELASTIC_PASSWORD}" "http://localhost:9200${path}"
  fi
}

put_json() {  # put_json METHOD PATH 'json' LABEL
  local tmp; tmp="$(mktemp)"
  printf '%s' "$3" > "$tmp"
  local code; code="$(es "$1" "$2" "$tmp")"; rm -f "$tmp"
  if [[ "$code" =~ ^2 ]]; then echo "  ok   $4"; else echo "  FAIL $4 (HTTP $code)"; FAILED=1; fi
}

put_file() {  # put_file PATH FILE LABEL
  local code; code="$(es PUT "$1" "$2")"
  if [[ "$code" =~ ^2 ]]; then echo "  ok   $3"; else echo "  FAIL $3 (HTTP $code)"; FAILED=1; fi
}

FAILED=0
echo "Waiting for Elasticsearch..."
for _ in $(seq 1 60); do
  [[ "$(es GET /_cluster/health)" == "200" ]] && break
  sleep 3
done
[[ "$(es GET /_cluster/health)" == "200" ]] || { echo "Elasticsearch not reachable" >&2; exit 1; }

echo "Built-in users"
put_json POST /_security/user/kibana_system/_password "{\"password\":\"${KIBANA_SYSTEM_PASSWORD}\"}" kibana_system
put_json POST /_security/user/logstash_system/_password "{\"password\":\"${LOGSTASH_SYSTEM_PASSWORD}\"}" logstash_system
put_json POST /_security/user/beats_system/_password "{\"password\":\"${BEATS_SYSTEM_PASSWORD}\"}" beats_system

echo "Roles"
put_json PUT /_security/role/logstash_writer '{
  "cluster": ["monitor", "manage_index_templates", "manage_ilm"],
  "indices": [{"names": ["radio-*"], "privileges": ["create_doc", "create", "index", "create_index", "auto_configure", "view_index_metadata"]}]
}' "role logstash_writer"
put_json PUT /_security/role/radio_api '{
  "cluster": ["monitor"],
  "indices": [{"names": ["radio-*"], "privileges": ["read", "view_index_metadata", "create_doc", "index", "create_index", "auto_configure"]}]
}' "role radio_api"
put_json PUT /_security/role/beats_writer '{
  "cluster": ["monitor", "read_ilm", "read_pipeline", "manage_index_templates", "manage_ilm"],
  "indices": [{"names": ["radio-logs-*", "metricbeat-*", ".ds-metricbeat-*"],
               "privileges": ["create_doc", "create_index", "auto_configure", "view_index_metadata", "manage"]}]
}' "role beats_writer"

echo "Service users"
put_json PUT /_security/user/logstash_writer "{\"password\":\"${LOGSTASH_WRITER_PASSWORD}\",\"roles\":[\"logstash_writer\"],\"full_name\":\"Logstash writer\"}" logstash_writer
put_json PUT /_security/user/radio_api "{\"password\":\"${RADIO_API_PASSWORD}\",\"roles\":[\"radio_api\"],\"full_name\":\"RadioMoni API\"}" radio_api
put_json PUT /_security/user/beats_writer "{\"password\":\"${BEATS_WRITER_PASSWORD}\",\"roles\":[\"beats_writer\",\"remote_monitoring_collector\"],\"full_name\":\"Metricbeat/Filebeat\"}" beats_writer

echo "ILM policies"
for f in monitoring/elasticsearch/ilm-policies/*.json; do
  put_file "/_ilm/policy/$(basename "$f" .json)" "$ROOT/$f" "ilm $(basename "$f" .json)"
done

echo "Index templates"
for f in monitoring/elasticsearch/index-templates/*.json; do
  put_file "/_index_template/$(basename "$f" .json)" "$ROOT/$f" "template $(basename "$f" .json)"
done
# templates of older versions with conflicting patterns
for old in radio-aprs-template radio-monitoring-performance; do
  [[ "$(es DELETE "/_index_template/$old")" =~ ^(200|404)$ ]] || true
done

if [[ $FAILED == 1 ]]; then
  echo "Some steps failed — see above." >&2
  exit 1
fi
echo "Elasticsearch configured."
