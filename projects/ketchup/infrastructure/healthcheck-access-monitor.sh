#!/bin/bash
# Health check script for access request monitor service
# Returns 0 if healthy, 1 if unhealthy
# Validates that the monitoring service is running and processing health checks

HEALTH_FILE="/tmp/access_monitor_health"

# Maximum age for health file (8 minutes - monitor runs every 5 minutes + buffer)
MAX_AGE=480

# Check if health file exists
if [ ! -f "$HEALTH_FILE" ]; then
    echo "Access monitor health file not found - service may not have started"
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
    echo "Access monitor health data is stale (${AGE}s old) - service may be stuck"
    exit 1
fi

# Check if service is in error state
if [ "$STATUS" = "error" ]; then
    echo "Access monitor service is in error state"
    exit 1
fi

# Additional validation - check that service is actively monitoring
if [ "$STATUS" != "running" ] && [ "$STATUS" != "idle" ] && [ "$STATUS" != "monitoring" ]; then
    echo "Access monitor in unexpected state: $STATUS"
    exit 1
fi

echo "Access monitor healthy - Status: $STATUS, Health age: ${AGE}s"
exit 0