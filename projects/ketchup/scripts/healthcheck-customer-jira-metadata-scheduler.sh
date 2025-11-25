#!/bin/bash
# Health check script for metadata updater scheduler
# Returns 0 if healthy, 1 if unhealthy

# Check if scheduler is running by looking at health file
HEALTH_FILE="/tmp/metadata_scheduler_health"
LAST_RUN_FILE="/tmp/metadata_last_run"

# Maximum age for health file (5 minutes)
MAX_AGE=300

# Check if health file exists
if [ ! -f "$HEALTH_FILE" ]; then
    echo "Health file not found"
    exit 1
fi

# Read health file
HEALTH_DATA=$(cat "$HEALTH_FILE")
TIMESTAMP=$(echo "$HEALTH_DATA" | cut -d':' -f1)
STATUS=$(echo "$HEALTH_DATA" | cut -d':' -f2)

# Check if timestamp is valid
if ! [[ "$TIMESTAMP" =~ ^[0-9]+$ ]]; then
    echo "Invalid timestamp in health file"
    exit 1
fi

# Calculate age
CURRENT_TIME=$(date +%s)
AGE=$((CURRENT_TIME - TIMESTAMP))

# Check if health data is too old
if [ "$AGE" -gt "$MAX_AGE" ]; then
    echo "Health data is too old: ${AGE}s"
    exit 1
fi

# Check status
if [ "$STATUS" = "error" ]; then
    echo "Scheduler in error state"
    exit 1
fi

# For running state, allow more time (20 minutes for metadata processing)
if [ "$STATUS" = "running" ] && [ "$AGE" -gt 1200 ]; then
    echo "Scheduler stuck in running state for ${AGE}s"
    exit 1
fi

# Check last run file for additional validation
if [ -f "$LAST_RUN_FILE" ]; then
    LAST_RUN=$(cat "$LAST_RUN_FILE")
    if [[ "$LAST_RUN" =~ ^[0-9]+$ ]]; then
        LAST_RUN_AGE=$((CURRENT_TIME - LAST_RUN))
        # Alert if no successful run in 25 minutes (15 min schedule + 10 min buffer)
        if [ "$LAST_RUN_AGE" -gt 1500 ]; then
            echo "No successful run in ${LAST_RUN_AGE}s"
            exit 1
        fi
    fi
fi

echo "Scheduler healthy - Status: $STATUS, Age: ${AGE}s"
exit 0