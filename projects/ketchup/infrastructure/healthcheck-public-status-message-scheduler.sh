#!/bin/bash
# Health check script for Python scheduler
# Checks if scheduler is running and has executed recently

# Check scheduler health file
if [ ! -f /tmp/scheduler_health ]; then
    echo "ERROR: Scheduler health file not found"
    exit 1
fi

# Read health status
health_data=$(cat /tmp/scheduler_health 2>/dev/null)
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

# Check if health status is recent (updated within last 5 minutes)
current_time=$(date +%s)
health_age=$((current_time - health_time))

if [ $health_age -gt 300 ]; then
    echo "ERROR: Health status is stale (${health_age} seconds old)"
    exit 1
fi

# Check scheduler status
if [ "$status" = "error" ]; then
    echo "ERROR: Scheduler is in error state"
    exit 1
fi

# Check last run timestamp
if [ ! -f /tmp/last_run ]; then
    echo "WARNING: No runs completed yet"
    # Don't fail during startup period
    if [ $health_age -lt 900 ]; then  # 15 minutes grace period
        exit 0
    fi
    exit 1
fi

last_run=$(cat /tmp/last_run 2>/dev/null)
if ! [[ "$last_run" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid last run timestamp"
    exit 1
fi

# Check if last run was recent enough (within 70 minutes)
run_age=$((current_time - last_run))
if [ $run_age -gt 4200 ]; then  # 70 minutes = 4200 seconds
    echo "ERROR: Last run was ${run_age} seconds ago (threshold: 4200 seconds)"
    exit 1
fi

echo "OK: Scheduler status: $status, last run: ${run_age} seconds ago"
exit 0