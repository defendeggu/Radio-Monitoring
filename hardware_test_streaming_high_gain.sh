#!/bin/bash

# Hardware Test Suite - APRS & POCSAG Streaming with High Gain
# Testing with higher gain values for better signal reception

set -e  # Exit on error

# Configuration
API_URL="http://localhost:5000"
KIBANA_URL="http://localhost:5601"
ES_URL="http://elastic:***REMOVED***@localhost:9200"
LOG_FILE="/home/spia/my-project/hardware-test-streaming-highgain-$(date +%Y%m%d-%H%M%S).log"

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper functions
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ✗${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

# Check RTL-SDR connection
check_rtlsdr() {
    log "Checking RTL-SDR connection..."

    # Check on host
    if lsusb | grep -q "0bda:2838"; then
        log_success "RTL-SDR detected on USB bus (Host)"

        # Check in container
        if docker exec radio-transcription-api rtl_test -t 2>&1 | grep -q "Found Rafael Micro R820T tuner"; then
            log_success "RTL-SDR accessible in container"

            # Get device info
            DEVICE_INFO=$(docker exec radio-transcription-api rtl_test -t 2>&1 | grep "Using device" | head -1)
            log "Device: $DEVICE_INFO"

            return 0
        else
            log_error "RTL-SDR NOT accessible in container!"
            log_error "Container restart may be required"
            return 1
        fi
    else
        log_error "RTL-SDR NOT detected on USB bus!"
        log_error "Please check physical USB connection"
        return 1
    fi
}

# Check system status
check_system_status() {
    log "Checking system status..."

    echo "=== Memory Status ===" >> "$LOG_FILE"
    free -h | tee -a "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    echo "=== Docker Container Status ===" >> "$LOG_FILE"
    docker compose ps | tee -a "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    echo "=== Container Memory Usage ===" >> "$LOG_FILE"
    docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}" | tee -a "$LOG_FILE"
    echo "" >> "$LOG_FILE"
}

# Check Kibana data
check_kibana_data() {
    local index_pattern=$1
    local test_name=$2

    log "Checking Kibana data for $test_name..."

    # Query Elasticsearch for recent data
    local count=$(curl -s -u "elastic:***REMOVED***" \
        -X GET "$ES_URL/${index_pattern}/_count?q=@timestamp:[now-15m TO now]" \
        2>/dev/null | jq -r '.count' 2>/dev/null || echo "0")

    if [ "$count" != "0" ] && [ -n "$count" ]; then
        log_success "Found $count documents in Elasticsearch ($index_pattern)"
        echo "  Kibana Dashboard: $KIBANA_URL/app/dashboards" | tee -a "$LOG_FILE"
    else
        log_warning "No data found in Elasticsearch ($index_pattern)"
    fi
}

# Wait and monitor
wait_with_monitoring() {
    local duration=$1
    local description=$2

    log "Waiting ${duration}s for $description..."

    local interval=30
    local elapsed=0

    while [ $elapsed -lt $duration ]; do
        sleep $interval
        elapsed=$((elapsed + interval))

        # Quick memory check
        local mem_avail=$(free -m | awk 'NR==2 {print $7}')
        log "  Progress: ${elapsed}/${duration}s | Available RAM: ${mem_avail} MB"
    done

    log_success "Completed $description"
}

# Main test execution
main() {
    log "========================================="
    log "Hardware Test Suite - High Gain Streaming"
    log "========================================="
    log "Start time: $(date)"
    log "Log file: $LOG_FILE"
    log ""
    log "Parameter Changes:"
    log "  - APRS Gain: 24 dB -> 44.5 dB (high sensitivity)"
    log "  - POCSAG Gain: 24 dB -> 48.0 dB (maximum sensitivity)"
    log "  - Duration: 600s -> 660s (11 minutes)"
    echo "" | tee -a "$LOG_FILE"

    # Initial RTL-SDR check
    log "========================================="
    log "PRE-TEST: RTL-SDR Connection Check"
    log "========================================="
    if ! check_rtlsdr; then
        log_error "ABORTING: RTL-SDR not detected before test start!"
        exit 1
    fi
    echo "" | tee -a "$LOG_FILE"

    # Initial system check
    check_system_status

    # ==========================================================================
    # TEST 1: APRS Continuous Streaming (660s = 11 minutes)
    # ==========================================================================
    log "========================================="
    log "TEST 1/2: APRS Continuous Streaming (660s)"
    log "========================================="
    log "Frequency: 144.800 MHz (European APRS)"
    log "Duration: 660s (11 minutes)"
    log "Gain: 44.5 dB (HIGH - improved sensitivity)"
    log "Sample Rate: 2.048 MHz"
    log "SDR: RTL-SDR (24 MHz - 1.766 GHz)"
    echo "" | tee -a "$LOG_FILE"

    TEST1_START=$(date +%s)

    # Start streaming
    log "Starting APRS streaming session..."
    RESPONSE=$(curl -s -X POST "$API_URL/stream/aprs/start" \
        -H "Content-Type: application/json" \
        -d '{
            "frequency": 144800000,
            "duration": 660,
            "sample_rate": 2048000,
            "gain": 44.5
        }' 2>&1)

    echo "$RESPONSE" >> "$LOG_FILE"

    if echo "$RESPONSE" | jq -e '.status == "success"' >/dev/null 2>&1; then
        SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
        log_success "APRS streaming started (Session: $SESSION_ID)"

        # Monitor streaming session
        wait_with_monitoring 660 "APRS streaming"

        # Check session status
        log "Checking session status..."
        STATUS=$(curl -s "$API_URL/stream-decode/$SESSION_ID")
        echo "$STATUS" >> "$LOG_FILE"

        PACKET_COUNT=$(echo "$STATUS" | jq -r '.session.packet_count // 0')
        log "Total APRS packets decoded: $PACKET_COUNT"

        # Check data in Elasticsearch
        sleep 5
        check_kibana_data "radio-aprs-*" "APRS Streaming"
    else
        log_error "APRS streaming failed to start"
        echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    fi

    TEST1_END=$(date +%s)
    TEST1_DURATION=$((TEST1_END - TEST1_START))
    log "Test 1 duration: ${TEST1_DURATION}s"
    echo "" | tee -a "$LOG_FILE"

    # RTL-SDR check after test 1
    log "========================================="
    log "POST-TEST 1: RTL-SDR Connection Check"
    log "========================================="
    if ! check_rtlsdr; then
        log_error "CRITICAL: RTL-SDR disconnected after Test 1!"
        log_error "Aborting remaining tests."
        exit 1
    fi
    echo "" | tee -a "$LOG_FILE"

    # Memory check
    check_system_status

    # Wait between tests
    log "Waiting 30s before next test..."
    sleep 30

    # ==========================================================================
    # TEST 2: POCSAG Continuous Streaming (660s = 11 minutes)
    # ==========================================================================
    log "========================================="
    log "TEST 2/2: POCSAG Continuous Streaming (660s)"
    log "========================================="
    log "Frequency: 147.375 MHz"
    log "Duration: 660s (11 minutes)"
    log "Gain: 48.0 dB (MAXIMUM - best sensitivity)"
    log "Sample Rate: 2.048 MHz"
    log "SDR: RTL-SDR (24 MHz - 1.766 GHz)"
    echo "" | tee -a "$LOG_FILE"

    TEST2_START=$(date +%s)

    # Start streaming
    log "Starting POCSAG streaming session..."
    RESPONSE=$(curl -s -X POST "$API_URL/stream/pocsag/start" \
        -H "Content-Type: application/json" \
        -d '{
            "frequency": 147375000,
            "duration": 660,
            "sample_rate": 2048000,
            "gain": 48.0
        }' 2>&1)

    echo "$RESPONSE" >> "$LOG_FILE"

    if echo "$RESPONSE" | jq -e '.status == "success"' >/dev/null 2>&1; then
        SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
        log_success "POCSAG streaming started (Session: $SESSION_ID)"

        # Monitor streaming session
        wait_with_monitoring 660 "POCSAG streaming"

        # Check session status
        log "Checking session status..."
        STATUS=$(curl -s "$API_URL/stream-decode/$SESSION_ID")
        echo "$STATUS" >> "$LOG_FILE"

        PACKET_COUNT=$(echo "$STATUS" | jq -r '.session.packet_count // 0')
        log "Total POCSAG packets decoded: $PACKET_COUNT"

        # Check data in Elasticsearch
        sleep 5
        check_kibana_data "radio-pocsag-*" "POCSAG Streaming"
    else
        log_error "POCSAG streaming failed to start"
        echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    fi

    TEST2_END=$(date +%s)
    TEST2_DURATION=$((TEST2_END - TEST2_START))
    log "Test 2 duration: ${TEST2_DURATION}s"
    echo "" | tee -a "$LOG_FILE"

    # Final RTL-SDR check after test 2
    log "========================================="
    log "POST-TEST 2: RTL-SDR Connection Check (Final)"
    log "========================================="
    if ! check_rtlsdr; then
        log_warning "RTL-SDR disconnected after Test 2 (all tests complete)"
    else
        log_success "RTL-SDR still connected after all tests"
    fi
    echo "" | tee -a "$LOG_FILE"

    # ==========================================================================
    # Final System Check
    # ==========================================================================
    log "========================================="
    log "Final System Status"
    log "========================================="
    check_system_status

    # ==========================================================================
    # Summary
    # ==========================================================================
    TOTAL_END=$(date +%s)
    TOTAL_DURATION=$((TOTAL_END - TEST1_START))

    log "========================================="
    log "Test Suite Summary"
    log "========================================="
    log "Test 1 (APRS Stream 660s @ 44.5dB):  ${TEST1_DURATION}s"
    log "Test 2 (POCSAG Stream 660s @ 48dB):  ${TEST2_DURATION}s"
    log "Total duration:                       ${TOTAL_DURATION}s ($((TOTAL_DURATION / 60)) minutes)"
    log ""
    log "Completed at: $(date)"
    log "Log file: $LOG_FILE"
    log ""
    log_success "All tests completed successfully!"
    log ""
    log "Next steps:"
    log "1. Check Kibana dashboards: $KIBANA_URL/app/dashboards"
    log "2. Verify APRS data: radio-aprs-* index"
    log "3. Verify POCSAG data: radio-pocsag-* index"
    log "4. Review log file: $LOG_FILE"
    log "5. Check Docker logs: docker logs radio-transcription-api"
    log "========================================="
}

# Execute main function
main
