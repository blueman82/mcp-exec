#!/bin/bash
# Health check script for Maintenance Fetcher scheduler
# Checks if scheduler is running and has executed recently

# Check scheduler health file
if [ ! -f /tmp/maintenance_fetcher_health ]; then
    echo "ERROR: Maintenance fetcher health file not found"
    exit 1
fi

# Read health status
health_data=$(cat /tmp/maintenance_fetcher_health 2>/dev/null)
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
    echo "ERROR: Maintenance fetcher is in error state"
    exit 1
fi

# Check last maintenance fetch timestamp
if [ ! -f /tmp/last_maintenance_fetch ]; then
    echo "WARNING: No maintenance fetches completed yet"
    # Don't fail during startup period
    if [ $health_age -lt 900 ]; then  # 15 minutes grace period
        exit 0
    fi
    exit 1
fi

last_fetch=$(cat /tmp/last_maintenance_fetch 2>/dev/null)
if ! [[ "$last_fetch" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Invalid last fetch timestamp"
    exit 1
fi

# Maintenance fetcher runs once daily, so check if last fetch was recent enough (within 25 hours)
fetch_age=$((current_time - last_fetch))
if [ $fetch_age -gt 90000 ]; then  # 25 hours = 90000 seconds
    echo "ERROR: Last fetch was ${fetch_age} seconds ago (threshold: 90000 seconds)"
    exit 1
fi

echo "OK: Maintenance fetcher status: $status, last fetch: ${fetch_age} seconds ago"
exit 0