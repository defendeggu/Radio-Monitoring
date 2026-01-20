#!/bin/bash

# Schedule Hardware Test Suite for 03:05

TARGET_TIME="03:05"
CURRENT_TIME=$(date +%s)

# Calculate target timestamp (tomorrow 03:05)
TARGET_HOUR=3
TARGET_MINUTE=5

# Get current hour and minute
CURRENT_HOUR=$(date +%H)
CURRENT_MINUTE=$(date +%M)

# Calculate total minutes
CURRENT_TOTAL_MINUTES=$((10#$CURRENT_HOUR * 60 + 10#$CURRENT_MINUTE))
TARGET_TOTAL_MINUTES=$((TARGET_HOUR * 60 + TARGET_MINUTE))

# If target is in the past today, schedule for tomorrow
if [ $TARGET_TOTAL_MINUTES -le $CURRENT_TOTAL_MINUTES ]; then
    # Target is tomorrow
    MINUTES_UNTIL=$((1440 - CURRENT_TOTAL_MINUTES + TARGET_TOTAL_MINUTES))
else
    # Target is today (shouldn't happen at 23:00)
    MINUTES_UNTIL=$((TARGET_TOTAL_MINUTES - CURRENT_TOTAL_MINUTES))
fi

SECONDS_UNTIL=$((MINUTES_UNTIL * 60))

echo "========================================="
echo "Hardware Test Suite Scheduler"
echo "========================================="
echo "Current time: $(date)"
echo "Target time: $TARGET_TIME"
echo "Time until execution: $MINUTES_UNTIL minutes ($((MINUTES_UNTIL / 60))h $((MINUTES_UNTIL % 60))m)"
echo ""
echo "Tests to run:"
echo "  1. APRS One-Shot (120s) @ 144.800 MHz"
echo "  2. POCSAG One-Shot (120s) @ 147.375 MHz"
echo "  3. APRS Streaming (600s) @ 144.800 MHz"
echo "  4. POCSAG Streaming (600s) @ 147.375 MHz"
echo ""
echo "Total test duration: ~25-30 minutes"
echo "Expected completion: ~03:30"
echo ""
echo "Log file will be created: /home/spia/my-project/hardware-test-TIMESTAMP.log"
echo "========================================="
echo ""

# Sleep until target time, then execute tests
(
    sleep $SECONDS_UNTIL
    /home/spia/my-project/hardware_test_suite_0305.sh
) &

SCHEDULER_PID=$!
echo "Scheduler started with PID: $SCHEDULER_PID"
echo "Background sleep PID: $((SCHEDULER_PID + 1)) (approx)"
echo ""
echo "To check status:"
echo "  ps aux | grep hardware_test_suite"
echo "  ps -p $SCHEDULER_PID"
echo ""
echo "To cancel:"
echo "  kill $SCHEDULER_PID"
echo "  # or"
echo "  kill \$(cat /home/spia/my-project/test_scheduler.pid)"
echo ""
echo "PID saved to: /home/spia/my-project/test_scheduler.pid"
echo $SCHEDULER_PID > /home/spia/my-project/test_scheduler.pid

echo ""
echo "========================================="
echo "Scheduler is now running in background"
echo "========================================="
