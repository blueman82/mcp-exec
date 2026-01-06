#!/bin/bash
# Health check script for CSOPM Notifier service
#
# This is a thin wrapper that delegates to the parameterized healthcheck-scheduler.sh
# with CSOPM-specific configuration.
#
# Health File: /tmp/csopm_notifier_health (format: timestamp:status)
# Last Run File: /tmp/csopm_notifier_last_run
#
# The CSOPM notifier runs at 08:00 and 16:00 UTC (every 8 hours),
# so MAX_RUN_AGE is set to 9 hours (32400 seconds) to allow for some buffer.
#
# Usage:
#   /app/infrastructure/healthcheck-csopm-notifier.sh
#
# Alternatively, use the parameterized script directly in docker-compose:
#   HEALTH_FILE=/tmp/csopm_notifier_health \
#   LAST_RUN_FILE=/tmp/csopm_notifier_last_run \
#   MAX_RUN_AGE=32400 \
#   MAX_HEALTH_AGE=600 \
#   SERVICE_NAME=CSOPMNotifier \
#   /app/infrastructure/healthcheck-scheduler.sh

# CSOPM Notifier specific configuration
export HEALTH_FILE="${HEALTH_FILE:-/tmp/csopm_notifier_health}"
export LAST_RUN_FILE="${LAST_RUN_FILE:-/tmp/csopm_notifier_last_run}"
export MAX_RUN_AGE="${MAX_RUN_AGE:-32400}"      # 9 hours (runs every 8 hours)
export MAX_HEALTH_AGE="${MAX_HEALTH_AGE:-600}"  # 10 minutes
export GRACE_PERIOD="${GRACE_PERIOD:-900}"     # 15 minutes startup grace
export SERVICE_NAME="${SERVICE_NAME:-CSOPMNotifier}"

# Delegate to the parameterized healthcheck script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${SCRIPT_DIR}/healthcheck-scheduler.sh"
