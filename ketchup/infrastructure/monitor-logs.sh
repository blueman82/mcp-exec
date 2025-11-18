#!/usr/bin/env bash
#
# monitor-logs.sh - Live log monitoring for all Ketchup containers
#
# Monitors logs from all containers on prod1 and prod2 in real-time
# and saves them to timestamped log files for analysis.
#

set -euo pipefail

# Timestamp for log files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="logs/deployment_${TIMESTAMP}"

# Create log directory
mkdir -p "$LOG_DIR"

echo "📊 Starting log monitoring for all Ketchup containers..."
echo "Logs will be saved to: $LOG_DIR"
echo ""

# Function to monitor a container
monitor_container() {
    local server=$1
    local container=$2
    local log_file="$LOG_DIR/${server}_${container}.log"
    
    echo "🔍 Monitoring $server:$container -> $log_file"
    
    # Tail logs in background, prepend with timestamp and container info
    ssh "$server" "sudo docker logs -f --tail=50 $container 2>&1" | \
        while IFS= read -r line; do
            echo "[$(date +'%Y-%m-%d %H:%M:%S')] [$server:$container] $line"
        done > "$log_file" 2>&1 &
    
    # Store PID for cleanup
    echo $! >> "$LOG_DIR/monitor_pids.txt"
}

# Monitor all containers on prod1
echo "📡 PROD1 Containers:"
for container in ketchup-ketchup-app-1 ketchup-ketchup-app-2 ketchup-mcp-jira-1 ketchup-ketchup-metadata-updater-1 ketchup-ketchup-access-monitor-1; do
    monitor_container "ketchup-prod1" "$container"
done

echo ""
echo "📡 PROD2 Containers:"
# Monitor all containers on prod2
for container in ketchup-ketchup-app-1 ketchup-ketchup-app-2 ketchup-mcp-jira-1 ketchup-ketchup-metadata-updater-1 ketchup-ketchup-access-monitor-1 ketchup-ketchup-status-updater-1 ketchup-ketchup-jira-reporter-1; do
    monitor_container "ketchup-prod2" "$container"
done

echo ""
echo "✅ All log monitors started!"
echo ""
echo "📁 Log files location: $LOG_DIR"
echo "🔍 View specific logs: tail -f $LOG_DIR/prod1_ketchup-ketchup-app-1.log"
echo "🛑 Stop monitoring: kill \$(cat $LOG_DIR/monitor_pids.txt)"
echo ""
echo "⏰ Monitoring in background... Press Ctrl+C to stop this script (monitors will continue)"
echo ""

# Keep script running and show summary
while true; do
    sleep 30
    echo "[$(date +'%H:%M:%S')] ⏰ Monitoring active - $(wc -l $LOG_DIR/*.log | tail -1)"
done
