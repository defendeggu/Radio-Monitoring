#!/bin/sh
# Start onair-server with the settings RadioMoni relies on. They are written again on every start
# (onair-server writes mode, frequency and gain back into the file; those are kept):
# - radio-api alone starts and stops the receiver under its SDR lock: autostart=0
# - no HackRF amplifier, no rtl_tcp share, no OnAir Web, no web relay
# - other computers (radio-api, the nginx proxy) need the token
set -eu

CONF=/data/server.conf
: "${ONAIR_TOKEN:?set ONAIR_TOKEN (16 characters or more) in .env}"
if [ "${#ONAIR_TOKEN}" -lt 16 ]; then
  echo "ONAIR_TOKEN must have 16 characters or more" >&2
  exit 1
fi

touch "$CONF"
chmod 600 "$CONF"
tmp=$(mktemp)
grep -vE '^[[:space:]]*(port|lan|token|autostart|amp|share_rtltcp|share_port|web|web_relay|web_lan|device)[[:space:]]*=' "$CONF" > "$tmp" || true
cat >> "$tmp" <<EOF
port=8765
lan=1
token=${ONAIR_TOKEN}
autostart=0
amp=0
share_rtltcp=0
web=0
web_relay=0
device=${ONAIR_DEVICE:-HackRF}
EOF
cat "$tmp" > "$CONF"
rm -f "$tmp"

# Decoded messages: the headless server has no /api/v1/events stream, so they go as JSON lines into
# the shared volume, where radio-api reads them. families: every event family except "time" (the
# default leaves out voice, session and satellite, i.e. DMR/P25 calls and passes). No MQTT, no webhook.
mkdir -p /data/events
cat > /data/integrations.json <<EOF
{"version":1,"families":${ONAIR_EVENT_FAMILIES:-33488895},"max_per_second":200,
 "mqtt":{"enabled":false},"webhook":{"enabled":false},
 "jsonl":{"enabled":true,"path":"/data/events/onair-events.jsonl","max_mb":${ONAIR_EVENTS_MAX_MB:-50}},
 "archive":{"enabled":false}}
EOF

exec onair-server --config "$CONF" "$@"
