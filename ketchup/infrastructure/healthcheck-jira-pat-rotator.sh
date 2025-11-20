#!/bin/bash
# Health check script for JIRA PAT Rotator service
# Checks if scheduler is running and has executed recently
# Returns 0 if healthy, 1 if unhealthy

HEALTH_FILE="/tmp/pat_rotator_health"
LAST_RUN_FILE="/tmp/pat_rotator_last_run"

# Maximum age for health file (5 minutes - health status updated every minute during idle)
MAX_HEALTH_AGE=300

# Maximum age for last rotation check (25 hours - rotator runs every 24 hours + buffer)
MAX_RUN_AGE=90000

# Check if health file exists
if [ ! -f "$HEALTH_FILE" ]; then
    echo "ERROR: PAT rotator health file not found - service may not have started"
    exit 1
fi

# Read health status (format: timestamp:status)
health_data=$(cat "$HEALTH_FILE" 2>/dev/null)
if [ -z "$health_data" ]; then
    echo "ERROR: Empty health file"
    exit 1
fi

# Parse timestamp and status
IFS=':' read -r health_time status <<< "$health_data"

# Validate timestamp format
if ! [[ "$health_time" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid health timestamp: $health_time"
    exit 1
fi

# Check if health status is recent (updated within last 5 minutes)
current_time=$(date +%s)
health_age=$((current_time - health_time))

if [ $health_age -gt $MAX_HEALTH_AGE ]; then
    echo "ERROR: Health status is stale (${health_age} seconds old) - service may be stuck"
    exit 1
fi

# Check scheduler status - must not be in error state
if [ "$status" = "error" ]; then
    echo "ERROR: PAT rotator is in error state"
    exit 1
fi

# Validate status is a known value
if [ "$status" != "running" ] && [ "$status" != "idle" ] && [ "$status" != "starting" ] && [ "$status" != "stopped" ]; then
    echo "WARNING: PAT rotator in unexpected state: $status"
    # Don't fail on unexpected state, just warn
fi

# Check last rotation check timestamp (optional during startup grace period)
if [ ! -f "$LAST_RUN_FILE" ]; then
    echo "WARNING: No rotation checks completed yet"
    # Don't fail during startup period (15 minutes grace period)
    if [ $health_age -lt 900 ]; then
        echo "OK: PAT rotator status: $status (startup grace period)"
        exit 0
    fi
    echo "ERROR: No rotation checks after startup grace period"
    exit 1
fi

last_run=$(cat "$LAST_RUN_FILE" 2>/dev/null)
if ! [[ "$last_run" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid last run timestamp: $last_run"
    exit 1
fi

# PAT rotator runs once every 24 hours, check if last run was recent enough (within 25 hours)
run_age=$((current_time - last_run))
if [ $run_age -gt $MAX_RUN_AGE ]; then
    echo "ERROR: Last rotation check was ${run_age} seconds ago (threshold: ${MAX_RUN_AGE} seconds / 25 hours)"
    exit 1
fi

echo "OK: PAT rotator status: $status, last rotation check: ${run_age} seconds ago, health age: ${health_age}s"
exit 0
