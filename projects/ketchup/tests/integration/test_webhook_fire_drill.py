#!/usr/bin/env python3
"""
Fire drill test using webhook URL for alerts.

This bypasses the complex DI container and sends alerts directly via webhook.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ketchup_access_request_monitor.monitor import AccessRequestHealthMonitor


async def run_webhook_fire_drill():
    """Run fire drill with webhook alerts."""
    # Get webhook from environment (for testing only)
    # In production, this should come from AWS Secrets Manager
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("❌ No webhook URL configured!")
        print("   Set SLACK_WEBHOOK_URL environment variable")
        print("   Or add slack_webhook_url to AWS Secrets Manager")
        return

    print("\n" + "=" * 60)
    print("🚨 ACCESS REQUEST MONITOR - WEBHOOK FIRE DRILL 🚨")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("Webhook: Configured")
    print("=" * 60 + "\n")

    # Create monitor (minimal setup)
    monitor = AccessRequestHealthMonitor()

    # Test various alert scenarios
    print("🔥 Sending test alerts via webhook...")

    # Scenario 1: High pending requests
    print("\n📌 Alert 1: High Pending Requests")
    issues1 = [
        {
            "severity": "warning",
            "category": "high_pending_count",
            "message": "High number of pending requests: 75",
            "details": {"count": 75, "threshold": 50},
        }
    ]
    await monitor.send_webhook_alert(issues1, webhook_url)
    await asyncio.sleep(2)

    # Scenario 2: Old pending requests
    print("\n📌 Alert 2: Old Pending Requests")
    issues2 = [
        {
            "severity": "warning",
            "category": "old_pending_requests",
            "message": "5 requests pending > 12h (oldest: 48.0 hours)",
            "details": {
                "count": 5,
                "oldest_age_hours": 48.0,
                "user_ids": ["UOLD001", "UOLD002", "UOLD003", "UOLD004", "UOLD005"],
            },
        }
    ]
    await monitor.send_webhook_alert(issues2, webhook_url)
    await asyncio.sleep(2)

    # Scenario 3: High error rate
    print("\n📌 Alert 3: High Error Rate")
    issues3 = [
        {
            "severity": "warning",
            "category": "high_error_rate",
            "message": "High error rate: 25.0%",
            "details": {"error_rate": 25.0, "total_errors": 50, "total_requests": 200},
        },
        {
            "severity": "info",
            "category": "rate_limiting_active",
            "message": "15 users rate limited",
            "details": {"rate_limited_count": 15},
        },
    ]
    await monitor.send_webhook_alert(issues3, webhook_url)
    await asyncio.sleep(2)

    # Scenario 4: Critical service outage
    print("\n📌 Alert 4: CRITICAL - Service Outage")
    issues4 = [
        {
            "severity": "critical",
            "category": "service_unavailable",
            "message": "Service unavailable: access_request_operations",
            "details": {"service": "access_request_operations"},
        },
        {
            "severity": "error",
            "category": "check_failed",
            "message": "Failed to check pending requests",
            "details": {"error": "Service connection failed"},
        },
    ]
    await monitor.send_webhook_alert(issues4, webhook_url)
    await asyncio.sleep(2)

    # Scenario 5: Multiple issues cascade
    print("\n📌 Alert 5: Multiple Simultaneous Issues")
    issues5 = [
        {
            "severity": "critical",
            "category": "monitor_failure",
            "message": "Monitor failing repeatedly: 3 consecutive errors",
            "details": {"last_error": "Database connection timeout"},
        },
        {
            "severity": "warning",
            "category": "high_pending_count",
            "message": "High number of pending requests: 63",
            "details": {"count": 63, "threshold": 50},
        },
        {
            "severity": "warning",
            "category": "old_pending_requests",
            "message": "3 requests pending > 12h",
            "details": {"count": 3, "oldest_age_hours": 15.5},
        },
        {
            "severity": "warning",
            "category": "high_error_rate",
            "message": "High error rate: 18.0%",
            "details": {"error_rate": 18.0},
        },
        {
            "severity": "info",
            "category": "rate_limiting_active",
            "message": "25 users rate limited",
            "details": {"rate_limited_count": 25},
        },
    ]
    await monitor.send_webhook_alert(issues5, webhook_url)

    print("\n" + "=" * 60)
    print("✅ WEBHOOK FIRE DRILL COMPLETE!")
    print("Check #ketchup-alerts channel for the test alerts")
    print("=" * 60 + "\n")


async def main():
    """Run the webhook fire drill."""
    try:
        await run_webhook_fire_drill()
    except Exception as e:
        print(f"❌ Fire drill failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
