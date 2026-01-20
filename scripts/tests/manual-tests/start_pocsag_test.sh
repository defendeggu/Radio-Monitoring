#!/bin/bash
# Start POCSAG live test
# Frequency: 147.325 MHz, Gain: 32dB, Duration: 720s (12 minutes)

set -e

API_URL="http://localhost:5000"
FREQUENCY=147325000  # 147.325 MHz
GAIN=32
DURATION=720

echo "========================================="
echo "Starting POCSAG Live Test"
echo "========================================="
echo "Frequency: 147.325 MHz"
echo "Gain: 32dB"
echo "Duration: 720 seconds (12 minutes)"
echo ""

# Start POCSAG streaming
echo "Starting POCSAG session..."
RESPONSE=$(curl -s -X POST "$API_URL/stream/pocsag/start" \
    -H "Content-Type: application/json" \
    -d "{
        \"frequency\": $FREQUENCY,
        \"sample_rate\": 2048000,
        \"gain\": $GAIN,
        \"duration\": $DURATION
    }")

echo "$RESPONSE"

SESSION_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', ''))" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
    echo "ERROR: Failed to start POCSAG session"
    exit 1
fi

echo ""
echo "✓ POCSAG session started: $SESSION_ID"
echo ""
echo "Monitor with: ./monitor_session.sh $SESSION_ID 60"
echo "Or check status: curl -s http://localhost:5000/stream-decode/$SESSION_ID | python3 -m json.tool"
echo ""
echo "Session will run for 12 minutes..."
echo "Expected end time: $(date -d '+720 seconds' '+%H:%M:%S')"
