#!/bin/bash

# Hardware Test Suite - APRS & POCSAG
# Scheduled execution: 03:05
# Tests: 4 sequential tests with full monitoring

set -e  # Exit on error

# Configuration
API_URL="http://localhost:5000"
KIBANA_URL="http://localhost:5601"
ES_URL="http://elastic:***REMOVED***@localhost:9200"
LOG_FILE="/home/spia/my-project/hardware-test-$(date +%Y%m%d-%H%M%S).log"
API_KEY=""  # Empty for localhost (exempt from auth)

# ANSI colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check Kibana dashboard data
check_kibana_data() {
    local index_pattern=$1
    local test_name=$2

    log "Checking Kibana data for $test_name..."

    # Query Elasticsearch for recent data
    local count=$(curl -s -u "elastic:***REMOVED***" \
        -X GET "$ES_URL/${index_pattern}/_count?q=@timestamp:[now-5m TO now]" \
        2>/dev/null | jq -r '.count' 2>/dev/null || echo "0")

    if [ "$count" -gt 0 ]; then
        log_success "Found $count documents in Elasticsearch ($index_pattern)"
        echo "  Kibana Dashboard: $KIBANA_URL/app/dashboards" | tee -a "$LOG_FILE"
    else
        log_warning "No data found in Elasticsearch ($index_pattern) - check captures"
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
    log "Hardware Test Suite Starting"
    log "========================================="
    log "Start time: $(date)"
    log "Log file: $LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Initial system check
    check_system_status

    # ==========================================================================
    # TEST 1: APRS One-Shot (120s)
    # ==========================================================================
    log "========================================="
    log "TEST 1/4: APRS One-Shot Capture (120s)"
    log "========================================="
    log "Frequency: 144.800 MHz (European APRS)"
    log "Duration: 120s"
    log "Gain: 24 dB"
    echo "" | tee -a "$LOG_FILE"

    TEST1_START=$(date +%s)

    # Start capture
    log "Starting APRS capture..."
    RESPONSE=$(curl -s -X POST "$API_URL/capture-and-transcribe" \
        -H "Content-Type: application/json" \
        -d '{
            "frequency": 144800000,
            "modulation": "FM",
            "duration": 120,
            "gain": 24,
            "sample_rate": 2000000,
            "mode": "aprs"
        }' 2>&1 | tee -a "$LOG_FILE")

    if echo "$RESPONSE" | jq -e '.status == "success"' >/dev/null 2>&1; then
        log_success "APRS capture completed"
        echo "$RESPONSE" | jq '.' >> "$LOG_FILE"

        # Check data in Elasticsearch
        sleep 5
        check_kibana_data "radio-aprs-*" "APRS"
    else
        log_error "APRS capture failed"
        echo "$RESPONSE" >> "$LOG_FILE"
    fi

    TEST1_END=$(date +%s)
    TEST1_DURATION=$((TEST1_END - TEST1_START))
    log "Test 1 duration: ${TEST1_DURATION}s"
    echo "" | tee -a "$LOG_FILE"

    # Memory check after test 1
    check_system_status

    # Wait between tests
    log "Waiting 30s before next test..."
    sleep 30

    # ==========================================================================
    # TEST 2: POCSAG One-Shot (120s)
    # ==========================================================================
    log "========================================="
    log "TEST 2/4: POCSAG One-Shot Capture (120s)"
    log "========================================="
    log "Frequency: 147.375 MHz"
    log "Duration: 120s"
    log "Gain: 24 dB"
    echo "" | tee -a "$LOG_FILE"

    TEST2_START=$(date +%s)

    # Start capture
    log "Starting POCSAG capture..."
    RESPONSE=$(curl -s -X POST "$API_URL/capture-and-transcribe" \
        -H "Content-Type: application/json" \
        -d '{
            "frequency": 147375000,
            "modulation": "FM",
            "duration": 120,
            "gain": 24,
            "sample_rate": 2000000,
            "mode": "pocsag"
        }' 2>&1 | tee -a "$LOG_FILE")

    if echo "$RESPONSE" | jq -e '.status == "success"' >/dev/null 2>&1; then
        log_success "POCSAG capture completed"
        echo "$RESPONSE" | jq '.' >> "$LOG_FILE"

        # Check data in Elasticsearch
        sleep 5
        check_kibana_data "radio-pocsag-*" "POCSAG"
    else
        log_error "POCSAG capture failed"
        echo "$RESPONSE" >> "$LOG_FILE"
    fi

    TEST2_END=$(date +%s)
    TEST2_DURATION=$((TEST2_END - TEST2_START))
    log "Test 2 duration: ${TEST2_DURATION}s"
    echo "" | tee -a "$LOG_FILE"

    # Memory check after test 2
    check_system_status

    # Wait between tests
    log "Waiting 30s before next test..."
    sleep 30

    # ==========================================================================
    # TEST 3: APRS Continuous Streaming (600s = 10 minutes)
    # ==========================================================================
    log "========================================="
    log "TEST 3/4: APRS Continuous Streaming (600s)"
    log "========================================="
    log "Frequency: 144.800 MHz (European APRS)"
    log "Duration: 600s (10 minutes)"
    log "Gain: 24 dB"
    echo "" | tee -a "$LOG_FILE"

    TEST3_START=$(date +%s)

    # Start streaming
    log "Starting APRS streaming session..."
    RESPONSE=$(curl -s -X POST "$API_URL/stream/aprs/start" \
        -H "Content-Type: application/json" \
        -d '{
            "frequency": 144800000,
            "duration": 600,
            "sample_rate": 2000000,
            "gain": 24
        }' 2>&1 | tee -a "$LOG_FILE")

    if echo "$RESPONSE" | jq -e '.status == "success"' >/dev/null 2>&1; then
        SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
        log_success "APRS streaming started (Session: $SESSION_ID)"
        echo "$RESPONSE" | jq '.' >> "$LOG_FILE"

        # Monitor streaming session
        wait_with_monitoring 600 "APRS streaming"

        # Check session status
        log "Checking session status..."
        STATUS=$(curl -s "$API_URL/stream-decode/$SESSION_ID" | tee -a "$LOG_FILE")
        echo "$STATUS" | jq '.' >> "$LOG_FILE"

        # Check data in Elasticsearch
        sleep 5
        check_kibana_data "radio-aprs-*" "APRS Streaming"
    else
        log_error "APRS streaming failed to start"
        echo "$RESPONSE" >> "$LOG_FILE"
    fi

    TEST3_END=$(date +%s)
    TEST3_DURATION=$((TEST3_END - TEST3_START))
    log "Test 3 duration: ${TEST3_DURATION}s"
    echo "" | tee -a "$LOG_FILE"

    # Memory check after test 3
    check_system_status

    # Wait between tests
    log "Waiting 30s before next test..."
    sleep 30

    # ==========================================================================
    # TEST 4: POCSAG Continuous Streaming (600s = 10 minutes)
    # ==========================================================================
    log "========================================="
    log "TEST 4/4: POCSAG Continuous Streaming (600s)"
    log "========================================="
    log "Frequency: 147.375 MHz"
    log "Duration: 600s (10 minutes)"
    log "Gain: 24 dB"
    echo "" | tee -a "$LOG_FILE"

    TEST4_START=$(date +%s)

    # Start streaming
    log "Starting POCSAG streaming session..."
    RESPONSE=$(curl -s -X POST "$API_URL/stream/pocsag/start" \
        -H "Content-Type: application/json" \
        -d '{
            "frequency": 147375000,
            "duration": 600,
            "sample_rate": 2000000,
            "gain": 24
        }' 2>&1 | tee -a "$LOG_FILE")

    if echo "$RESPONSE" | jq -e '.status == "success"' >/dev/null 2>&1; then
        SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
        log_success "POCSAG streaming started (Session: $SESSION_ID)"
        echo "$RESPONSE" | jq '.' >> "$LOG_FILE"

        # Monitor streaming session
        wait_with_monitoring 600 "POCSAG streaming"

        # Check session status
        log "Checking session status..."
        STATUS=$(curl -s "$API_URL/stream-decode/$SESSION_ID" | tee -a "$LOG_FILE")
        echo "$STATUS" | jq '.' >> "$LOG_FILE"

        # Check data in Elasticsearch
        sleep 5
        check_kibana_data "radio-pocsag-*" "POCSAG Streaming"
    else
        log_error "POCSAG streaming failed to start"
        echo "$RESPONSE" >> "$LOG_FILE"
    fi

    TEST4_END=$(date +%s)
    TEST4_DURATION=$((TEST4_END - TEST4_START))
    log "Test 4 duration: ${TEST4_DURATION}s"
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
    log "Test 1 (APRS 120s):         ${TEST1_DURATION}s"
    log "Test 2 (POCSAG 120s):       ${TEST2_DURATION}s"
    log "Test 3 (APRS Stream 600s):  ${TEST3_DURATION}s"
    log "Test 4 (POCSAG Stream 600s):${TEST4_DURATION}s"
    log "Total duration:             ${TOTAL_DURATION}s ($((TOTAL_DURATION / 60)) minutes)"
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
    log "========================================="
}

# Execute main function
main
