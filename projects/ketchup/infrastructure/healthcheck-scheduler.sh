#!/bin/bash
# Consolidated health check script for all scheduler services
# Parameterized via environment variables for flexibility
#
# Usage: HEALTH_FILE=/tmp/health MAX_RUN_AGE=4200 /app/infrastructure/healthcheck-scheduler.sh
#
# Environment Variables:
#   HEALTH_FILE      - Path to health status file (default: /tmp/scheduler_health)
#   LAST_RUN_FILE    - Path to last run timestamp file (default: /tmp/last_run)
#   MAX_RUN_AGE      - Maximum seconds since last run before unhealthy (default: 4200 = 70 min)
#   MAX_HEALTH_AGE   - Maximum seconds for health file freshness (default: 300 = 5 min)
#   GRACE_PERIOD     - Seconds after startup before requiring last_run file (default: 900 = 15 min)
#   SERVICE_NAME     - Name for log messages (default: Scheduler)

# Configuration with defaults
HEALTH_FILE=${HEALTH_FILE:-/tmp/scheduler_health}
LAST_RUN_FILE=${LAST_RUN_FILE:-/tmp/last_run}
MAX_RUN_AGE=${MAX_RUN_AGE:-4200}
MAX_HEALTH_AGE=${MAX_HEALTH_AGE:-300}
GRACE_PERIOD=${GRACE_PERIOD:-900}
SERVICE_NAME=${SERVICE_NAME:-Scheduler}

# Check health file exists
if [ ! -f "$HEALTH_FILE" ]; then
    echo "ERROR: ${SERVICE_NAME} health file not found"
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

# Validate timestamp
if ! [[ "$health_time" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid health timestamp"
    exit 1
fi

# Check health file freshness
current_time=$(date +%s)
health_age=$((current_time - health_time))

if [ $health_age -gt $MAX_HEALTH_AGE ]; then
    echo "ERROR: Health status is stale (${health_age}s old, threshold: ${MAX_HEALTH_AGE}s)"
    exit 1
fi

# Check for error state
if [ "$status" = "error" ]; then
    echo "ERROR: ${SERVICE_NAME} is in error state"
    exit 1
fi

# Check last run timestamp
if [ ! -f "$LAST_RUN_FILE" ]; then
    echo "WARNING: No runs completed yet"
    # Allow grace period after startup
    if [ $health_age -lt $GRACE_PERIOD ]; then
        echo "OK: ${SERVICE_NAME} status: $status (startup grace period)"
        exit 0
    fi
    echo "ERROR: No runs completed after grace period"
    exit 1
fi

last_run=$(cat "$LAST_RUN_FILE" 2>/dev/null)
if ! [[ "$last_run" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid last run timestamp"
    exit 1
fi

# Check if last run was recent enough
run_age=$((current_time - last_run))
if [ $run_age -gt $MAX_RUN_AGE ]; then
    echo "ERROR: Last run was ${run_age}s ago (threshold: ${MAX_RUN_AGE}s)"
    exit 1
fi

echo "OK: ${SERVICE_NAME} status: $status, last run: ${run_age}s ago, health age: ${health_age}s"
exit 0
