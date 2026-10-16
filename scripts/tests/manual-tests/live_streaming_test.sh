#!/bin/bash

# Live Streaming Test - APRS and POCSAG Sequential
# Standard frequencies, 32dB gain, 720 seconds each
# Date: 2026-01-11

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8080/api}"
API_KEY="${API_KEY:-$(grep -E "^API_KEYS=" "$(dirname "$0")/../../../.env" 2>/dev/null | cut -d= -f2 | cut -d, -f1)}"
APRS_FREQUENCY=144800000  # 144.800 MHz
POCSAG_FREQUENCY=147325000  # 147.325 MHz
GAIN=32  # 32 dB
DURATION=720  # 12 minutes each
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_FILE="live-streaming-test-${TIMESTAMP}.log"

# Function to print colored messages
log_info() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] !${NC} $1" | tee -a "$LOG_FILE"
}

# Function to check API health
check_api() {
    log_info "Checking API health..."
    RESPONSE=$(curl -s -H "X-API-Key: ${API_KEY}" "$API_URL/health")
    if echo "$RESPONSE" | grep -q "healthy"; then
        log_success "API is healthy"
        return 0
    else
        log_error "API health check failed"
        return 1
    fi
}

# Function to detect SDR
detect_sdr() {
    log_info "Detecting SDR hardware..."
    RESPONSE=$(curl -s -H "X-API-Key: ${API_KEY}" "$API_URL/sdr/detect")
    SDR_TYPE=$(echo "$RESPONSE" | grep -o '"type":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$SDR_TYPE" ]; then
        log_error "No SDR detected"
        return 1
    fi

    log_success "Detected: $SDR_TYPE"
    echo "$RESPONSE" >> "$LOG_FILE"
    return 0
}

# Function to start streaming session
start_streaming() {
    local SESSION_TYPE=$1
    local FREQUENCY=$2
    local GAIN=$3
    local DURATION=$4

    log_info "Starting $SESSION_TYPE streaming session..."
    log_info "Frequency: $(echo "scale=3; $FREQUENCY / 1000000" | bc) MHz, Gain: ${GAIN}dB, Duration: ${DURATION}s"

    RESPONSE=$(curl -s -H "X-API-Key: ${API_KEY}" -X POST "$API_URL/stream/$SESSION_TYPE/start" \
        -H "Content-Type: application/json" \
        -d "{
            \"frequency\": $FREQUENCY,
            \"sample_rate\": 2048000,
            \"gain\": $GAIN,
            \"duration\": $DURATION
        }")

    SESSION_ID=$(echo "$RESPONSE" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$SESSION_ID" ]; then
        log_error "Failed to start $SESSION_TYPE session"
        echo "$RESPONSE" >> "$LOG_FILE"
        return 1
    fi

    log_success "$SESSION_TYPE session started: $SESSION_ID"
    echo "$RESPONSE" >> "$LOG_FILE"
    echo "$SESSION_ID"
}

# Function to monitor streaming session
monitor_session() {
    local SESSION_TYPE=$1
    local SESSION_ID=$2
    local DURATION=$3

    log_info "Monitoring $SESSION_TYPE session $SESSION_ID..."

    local ELAPSED=0
    local CHECK_INTERVAL=30

    while [ $ELAPSED -lt $DURATION ]; do
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))

        STATUS_RESPONSE=$(curl -s -H "X-API-Key: ${API_KEY}" "$API_URL/stream-decode/$SESSION_ID")
        SESSION_STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
        PACKETS=$(echo "$STATUS_RESPONSE" | grep -o '"packets_decoded":[0-9]*' | cut -d':' -f2)

        if [ -z "$PACKETS" ]; then
            PACKETS=0
        fi

        log_info "[$SESSION_TYPE] Elapsed: ${ELAPSED}s/${DURATION}s | Status: $SESSION_STATUS | Packets: $PACKETS"

        # Check if session ended prematurely
        if [ "$SESSION_STATUS" = "completed" ] || [ "$SESSION_STATUS" = "failed" ]; then
            log_warning "$SESSION_TYPE session ended with status: $SESSION_STATUS"
            echo "$STATUS_RESPONSE" >> "$LOG_FILE"
            break
        fi
    done

    # Wait a bit for final data to be processed
    log_info "Waiting 10s for final data processing..."
    sleep 10

    # Get final status
    FINAL_RESPONSE=$(curl -s -H "X-API-Key: ${API_KEY}" "$API_URL/stream-decode/$SESSION_ID")
    log_info "Final status:"
    echo "$FINAL_RESPONSE" | tee -a "$LOG_FILE"

    return 0
}

# Function to get session statistics
get_session_stats() {
    local SESSION_TYPE=$1
    local SESSION_ID=$2

    log_info "Retrieving $SESSION_TYPE session statistics..."

    STATS_RESPONSE=$(curl -s -H "X-API-Key: ${API_KEY}" "$API_URL/stream-decode/$SESSION_ID")
    echo "$STATS_RESPONSE" | tee -a "$LOG_FILE"

    PACKETS=$(echo "$STATS_RESPONSE" | grep -o '"packets_decoded":[0-9]*' | cut -d':' -f2)

    if [ -z "$PACKETS" ]; then
        PACKETS=0
    fi

    log_success "$SESSION_TYPE session decoded $PACKETS packets"
    return 0
}

# Main test execution
main() {
    log_info "========================================="
    log_info "Live Streaming Test - APRS and POCSAG"
    log_info "========================================="
    log_info "Start time: $(date)"
    log_info "Log file: $LOG_FILE"
    log_info ""

    # Pre-flight checks
    if ! check_api; then
        log_error "API health check failed. Exiting."
        exit 1
    fi

    if ! detect_sdr; then
        log_error "SDR detection failed. Exiting."
        exit 1
    fi

    log_info ""
    log_info "========================================="
    log_info "Test 1: APRS Streaming"
    log_info "========================================="

    # Start APRS streaming
    APRS_SESSION_ID=$(start_streaming "aprs" "$APRS_FREQUENCY" "$GAIN" "$DURATION")

    if [ -z "$APRS_SESSION_ID" ]; then
        log_error "Failed to start APRS session"
        exit 1
    fi

    # Monitor APRS session
    monitor_session "aprs" "$APRS_SESSION_ID" "$DURATION"

    # Get APRS statistics
    get_session_stats "aprs" "$APRS_SESSION_ID"

    log_info ""
    log_info "========================================="
    log_info "Test 2: POCSAG Streaming"
    log_info "========================================="

    # Start POCSAG streaming
    POCSAG_SESSION_ID=$(start_streaming "pocsag" "$POCSAG_FREQUENCY" "$GAIN" "$DURATION")

    if [ -z "$POCSAG_SESSION_ID" ]; then
        log_error "Failed to start POCSAG session"
        exit 1
    fi

    # Monitor POCSAG session
    monitor_session "pocsag" "$POCSAG_SESSION_ID" "$DURATION"

    # Get POCSAG statistics
    get_session_stats "pocsag" "$POCSAG_SESSION_ID"

    log_info ""
    log_info "========================================="
    log_info "Test Suite Summary"
    log_info "========================================="
    log_info "APRS Session ID:   $APRS_SESSION_ID"
    log_info "POCSAG Session ID: $POCSAG_SESSION_ID"
    log_info "Total duration:    $((DURATION * 2))s ($(((DURATION * 2) / 60)) minutes)"
    log_info ""
    log_info "Completed at: $(date)"
    log_info "Log file: $LOG_FILE"
    log_info ""
    log_success "All tests completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Check Kibana dashboards: http://localhost:5601/app/dashboards"
    log_info "2. Verify APRS data in index: radio-aprs-*"
    log_info "3. Verify POCSAG data in index: radio-pocsag-*"
    log_info "4. Search for APRS session: $APRS_SESSION_ID"
    log_info "5. Search for POCSAG session: $POCSAG_SESSION_ID"
    log_info "========================================="
}

# Run main function
main
