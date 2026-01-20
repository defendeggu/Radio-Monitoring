#!/bin/bash
# Simple session monitor

SESSION_ID=$1
CHECK_INTERVAL=${2:-30}

if [ -z "$SESSION_ID" ]; then
    echo "Usage: $0 <session_id> [check_interval_seconds]"
    exit 1
fi

API_URL="http://localhost:5000"

echo "Monitoring session: $SESSION_ID"
echo "Check interval: ${CHECK_INTERVAL}s"
echo "Press Ctrl+C to stop monitoring"
echo ""

while true; do
    TIMESTAMP=$(date "+%H:%M:%S")
    RESPONSE=$(curl -s "$API_URL/stream-decode/$SESSION_ID")

    STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('session', {}).get('status', 'unknown'))" 2>/dev/null || echo "error")
    PACKETS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('session', {}).get('packet_count', 0))" 2>/dev/null || echo "0")
    MODE=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('session', {}).get('mode', 'unknown'))" 2>/dev/null || echo "unknown")

    echo "[$TIMESTAMP] Mode: $MODE | Status: $STATUS | Packets: $PACKETS"

    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        echo ""
        echo "Session ended with status: $STATUS"
        echo "Final response:"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        break
    fi

    sleep $CHECK_INTERVAL
done
