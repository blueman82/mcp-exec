#!/bin/bash
# Health check script for JIRA reporter service
# Returns 0 if healthy, 1 if unhealthy
# Validates that the service is running properly and processing requests

HEALTH_FILE="/tmp/jira_reporter_health"
LAST_RUN_FILE="/tmp/jira_reporter_last_run"

# Maximum age for health file (10 minutes)
MAX_AGE=600

# Maximum time since last successful run (25 minutes - allows for 15min check interval + buffer)
MAX_LAST_RUN_AGE=1500

# Check if health file exists
if [ ! -f "$HEALTH_FILE" ]; then
    echo "Health file not found - service may not have started properly"
    exit 1
fi

# Read health file (format: timestamp:status)
HEALTH_DATA=$(cat "$HEALTH_FILE")
TIMESTAMP=$(echo "$HEALTH_DATA" | cut -d':' -f1)
STATUS=$(echo "$HEALTH_DATA" | cut -d':' -f2)

# Validate timestamp format
if ! [[ "$TIMESTAMP" =~ ^[0-9]+$ ]]; then
    echo "Invalid timestamp in health file: $TIMESTAMP"
    exit 1
fi

# Check if health data is too old
CURRENT_TIME=$(date +%s)
AGE=$((CURRENT_TIME - TIMESTAMP))

if [ "$AGE" -gt "$MAX_AGE" ]; then
    echo "Health data is stale (${AGE}s old) - service may be stuck"
    exit 1
fi

# Check if service is in error state
if [ "$STATUS" = "error" ]; then
    echo "JIRA Reporter service is in error state"
    exit 1
fi

# Check last successful run if file exists
if [ -f "$LAST_RUN_FILE" ]; then
    LAST_RUN=$(cat "$LAST_RUN_FILE")
    
    if [[ "$LAST_RUN" =~ ^[0-9]+$ ]]; then
        LAST_RUN_AGE=$((CURRENT_TIME - LAST_RUN))
        
        if [ "$LAST_RUN_AGE" -gt "$MAX_LAST_RUN_AGE" ]; then
            echo "No successful run in ${LAST_RUN_AGE}s - service may be failing"
            exit 1
        fi
    else
        echo "Invalid last run timestamp: $LAST_RUN"
        exit 1
    fi
fi

echo "JIRA Reporter healthy - Status: $STATUS, Health age: ${AGE}s"
exit 0