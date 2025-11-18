#!/usr/bin/env python3
"""
Integration test: Fire drill for AccessRequestHealthMonitor alerting.

This test simulates various alert scenarios and sends REAL alerts to Slack.
Run this to see the alerting system in action!

Requirements:
- AWS_PROFILE=campaign_prod_v7
- Access to Slack bot token from AWS Secrets Manager
- Permission to post to #ketchup-alerts channel
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ketchup_access_request_monitor.monitor import AccessRequestHealthMonitor
from packages.core.constants import ACCESS_REQUEST_STATUS, KETCHUP_ALERTS_CHANNEL


class AlertFireDrill:
    """Fire drill simulator for testing alerts."""

    def __init__(self):
        """Initialize the fire drill."""
        self.monitor = None
        self.container = None
        self.scenarios_run = []

    async def setup(self):
        """Set up TypedDI container and monitor."""
        print("🔧 Setting up AccessRequestHealthMonitor with REAL Slack integration...")

        # Use TypedDI instead of legacy DIContainer
        from packages.core.typed_di_integration import get_container

        try:
            self.container = await get_container()
            print("✅ TypedDI container initialized")

        except Exception as e:
            print(f"❌ Container init error: {e}")
            raise

        # Create monitor with TypedDI container
        self.monitor = AccessRequestHealthMonitor()
        self.monitor.container = self.container

        # Override check interval for faster testing
        self.monitor.check_interval = 30  # 30 seconds instead of 5 minutes
        self.monitor.alert_cooldown = 60  # 1 minute cooldown for testing

        print("✅ Monitor initialized with real Slack bot token")
        print(f"📢 Alerts will be sent to: {KETCHUP_ALERTS_CHANNEL} (#ketchup-alerts)")

    async def simulate_high_pending_requests(self):
        """Simulate scenario: Too many pending requests."""
        print("\n🔥 SCENARIO 1: High Pending Requests")
        print("   Simulating 75 pending access requests...")

        # Mock the access operations to return many pending requests
        mock_ops = AsyncMock()
        mock_requests = []

        for i in range(75):
            mock_request = MagicMock()
            mock_request.user_id = f"U{i:06d}"
            mock_request.request_timestamp = time.time() - (
                i * 60
            )  # Stagger timestamps
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            mock_request.decision_timestamp = None
            mock_requests.append(mock_request)

        mock_ops.get_all_pending_requests = AsyncMock(return_value=mock_requests)
        mock_ops.get_user_request_history = AsyncMock(return_value=[])

        # Temporarily replace the service
        original_get = self.container.get_by_name

        def mock_get(name):
            if name == "access_request_operations":
                return mock_ops
            return original_get(name)

        self.container.get_by_name = mock_get

        # Run health checks
        issues = await self.monitor.run_health_checks()

        # Send alert if issues found
        if issues:
            print(f"   Found {len(issues)} issues!")
            await self.monitor.send_alert(issues)
            print("   🚨 ALERT SENT to #ketchup-alerts!")

        # Restore original
        self.container.get_by_name = original_get
        self.scenarios_run.append("high_pending_requests")

    async def simulate_old_pending_requests(self):
        """Simulate scenario: Requests pending too long."""
        print("\n🔥 SCENARIO 2: Old Pending Requests")
        print("   Simulating requests pending for 24+ hours...")

        mock_ops = AsyncMock()
        current_time = time.time()
        mock_requests = []

        # Create some very old requests
        for i in range(5):
            mock_request = MagicMock()
            mock_request.user_id = f"UOLD{i:03d}"
            mock_request.request_timestamp = (
                current_time - (24 * 3600) - (i * 3600)
            )  # 24-29 hours old
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            mock_request.decision_timestamp = None
            mock_requests.append(mock_request)

        # Add some normal requests
        for i in range(10):
            mock_request = MagicMock()
            mock_request.user_id = f"UNORM{i:03d}"
            mock_request.request_timestamp = current_time - (2 * 3600)  # 2 hours old
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            mock_request.decision_timestamp = None
            mock_requests.append(mock_request)

        mock_ops.get_all_pending_requests = AsyncMock(return_value=mock_requests)
        mock_ops.get_user_request_history = AsyncMock(return_value=[])

        # Temporarily replace the service
        original_get = self.container.get_by_name

        def mock_get(name):
            if name == "access_request_operations":
                return mock_ops
            return original_get(name)

        self.container.get_by_name = mock_get

        # Run health checks
        issues = await self.monitor.run_health_checks()

        if issues:
            print(f"   Found {len(issues)} issues!")
            await self.monitor.send_alert(issues)
            print("   🚨 ALERT SENT to #ketchup-alerts!")

        self.container.get_by_name = original_get
        self.scenarios_run.append("old_pending_requests")

    async def simulate_high_error_rate(self):
        """Simulate scenario: High error rate."""
        print("\n🔥 SCENARIO 3: High Error Rate")
        print("   Simulating 25% error rate in access requests...")

        # Mock metrics service with high error rate
        mock_metrics = AsyncMock()
        mock_metrics.get_stats_summary = AsyncMock(
            return_value={
                "error_rate": 0.25,  # 25% error rate!
                "error": 50,
                "created": 200,
                "rate_limited": 15,  # Also trigger rate limiting alert
                "approved": 100,
                "rejected": 50,
            }
        )

        # Mock other services normally
        mock_ops = AsyncMock()
        mock_ops.get_all_pending_requests = AsyncMock(return_value=[])
        mock_ops.get_user_request_history = AsyncMock(return_value=[])

        original_get = self.container.get_by_name

        def mock_get(name):
            if name == "access_request_monitor":
                return mock_metrics
            elif name == "access_request_operations":
                return mock_ops
            return original_get(name)

        self.container.get_by_name = mock_get

        # Run health checks
        issues = await self.monitor.run_health_checks()

        if issues:
            print(f"   Found {len(issues)} issues!")
            await self.monitor.send_alert(issues)
            print("   🚨 ALERT SENT to #ketchup-alerts!")

        self.container.get_by_name = original_get
        self.scenarios_run.append("high_error_rate")

    async def simulate_service_outage(self):
        """Simulate scenario: Critical service down."""
        print("\n🔥 SCENARIO 4: Critical Service Outage")
        print("   Simulating access_request_operations service failure...")

        # Make critical service unavailable
        original_get = self.container.get_by_name

        def mock_get(name):
            if name == "access_request_operations":
                return None  # Service is DOWN!
            elif name == "access_request_monitor":
                # Return mock metrics to avoid double failure
                mock_metrics = AsyncMock()
                mock_metrics.get_stats_summary = AsyncMock(
                    return_value={
                        "error_rate": 0.05,
                        "error": 5,
                        "created": 100,
                        "rate_limited": 0,
                    }
                )
                return mock_metrics
            return original_get(name)

        self.container.get_by_name = mock_get

        # Run health checks
        issues = await self.monitor.run_health_checks()

        if issues:
            print(f"   Found {len(issues)} issues!")
            critical_count = sum(1 for i in issues if i["severity"] == "critical")
            print(f"   Including {critical_count} CRITICAL issues!")
            await self.monitor.send_alert(issues)
            print("   🚨 CRITICAL ALERT SENT to #ketchup-alerts!")

        self.container.get_by_name = original_get
        self.scenarios_run.append("service_outage")

    async def simulate_multiple_issues(self):
        """Simulate scenario: Multiple simultaneous issues."""
        print("\n🔥 SCENARIO 5: Multiple Simultaneous Issues")
        print("   Simulating cascade failure with multiple problems...")

        # Create a complex scenario with multiple issues
        current_time = time.time()

        # Mock operations with various issues
        mock_ops = AsyncMock()
        mock_requests = []

        # Old requests
        for i in range(3):
            mock_request = MagicMock()
            mock_request.user_id = f"USTUCK{i:03d}"
            mock_request.request_timestamp = current_time - (48 * 3600)  # 2 days old!
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            mock_request.decision_timestamp = None
            mock_requests.append(mock_request)

        # Many pending requests
        for i in range(60):
            mock_request = MagicMock()
            mock_request.user_id = f"UPEND{i:03d}"
            mock_request.request_timestamp = current_time - (i * 300)  # Various ages
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            mock_request.decision_timestamp = None
            mock_requests.append(mock_request)

        mock_ops.get_all_pending_requests = AsyncMock(return_value=mock_requests)

        # Mock metrics with high error rate
        mock_metrics = AsyncMock()
        mock_metrics.get_stats_summary = AsyncMock(
            return_value={
                "error_rate": 0.18,  # 18% error rate
                "error": 36,
                "created": 200,
                "rate_limited": 25,  # Many users rate limited
                "approved": 80,
                "rejected": 84,
            }
        )

        original_get = self.container.get_by_name

        def mock_get(name):
            if name == "access_request_operations":
                return mock_ops
            elif name == "access_request_monitor":
                return mock_metrics
            return original_get(name)

        self.container.get_by_name = mock_get

        # Run health checks
        issues = await self.monitor.run_health_checks()

        if issues:
            print(f"   Found {len(issues)} issues!")
            by_severity = {}
            for issue in issues:
                severity = issue["severity"]
                by_severity[severity] = by_severity.get(severity, 0) + 1

            print(f"   Breakdown: {by_severity}")
            await self.monitor.send_alert(issues)
            print("   🚨 MULTI-ISSUE ALERT SENT to #ketchup-alerts!")

        self.container.get_by_name = original_get
        self.scenarios_run.append("multiple_issues")

    async def run_fire_drill(self):
        """Run the complete fire drill."""
        print("\n" + "=" * 60)
        print("🚨 ACCESS REQUEST MONITOR - FIRE DRILL 🚨")
        print("=" * 60)
        print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Target Channel: {KETCHUP_ALERTS_CHANNEL} (#ketchup-alerts)")
        print("=" * 60)

        try:
            # Set up real connections
            await self.setup()

            # Announce the drill
            await self.send_drill_announcement()

            # Run scenarios with delays between them
            print("\n🎬 Starting fire drill scenarios...")

            await self.simulate_high_pending_requests()
            await asyncio.sleep(5)  # Brief pause between alerts

            await self.simulate_old_pending_requests()
            await asyncio.sleep(5)

            await self.simulate_high_error_rate()
            await asyncio.sleep(5)

            await self.simulate_service_outage()
            await asyncio.sleep(5)

            await self.simulate_multiple_issues()

            # Send completion message
            await self.send_drill_completion()

            print("\n" + "=" * 60)
            print("✅ FIRE DRILL COMPLETE!")
            print(f"Scenarios run: {', '.join(self.scenarios_run)}")
            print("Check #ketchup-alerts channel for the alerts!")
            print("=" * 60)

        except Exception as e:
            print(f"\n❌ Fire drill failed: {e}")
            import traceback

            traceback.print_exc()
        finally:
            if self.container:
                await self.container.cleanup()

    async def send_drill_announcement(self):
        """Send announcement that this is a drill."""
        try:
            slack_client = self.container.get_by_name("slack_async_client")

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🎯 FIRE DRILL - Testing Alert System",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*This is a TEST of the Access Request monitoring alerts*\n\n"
                        "The following alerts are SIMULATED for testing purposes.\n"
                        "No actual issues are occurring in the system.\n\n"
                        "_Fire drill started by test_alert_fire_drill.py_",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Drill started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                        }
                    ],
                },
            ]

            await slack_client.api_call(
                "chat.postMessage",
                {
                    "channel": KETCHUP_ALERTS_CHANNEL,
                    "blocks": blocks,
                    "text": "🎯 FIRE DRILL - Testing Alert System",
                },
            )
            print("📢 Drill announcement sent to Slack")

        except Exception as e:
            print(f"⚠️  Could not send drill announcement: {e}")

    async def send_drill_completion(self):
        """Send message that drill is complete."""
        try:
            slack_client = self.container.get_by_name("slack_async_client")

            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "✅ Fire Drill Complete"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Alert testing complete!*\n\n"
                        f"Scenarios tested: {len(self.scenarios_run)}\n"
                        f"• High pending requests\n"
                        f"• Old pending requests\n"
                        f"• High error rate\n"
                        f"• Service outage\n"
                        f"• Multiple simultaneous issues\n\n"
                        f"_All alerts above were simulated for testing._",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Drill completed at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                        }
                    ],
                },
            ]

            await slack_client.api_call(
                "chat.postMessage",
                {
                    "channel": KETCHUP_ALERTS_CHANNEL,
                    "blocks": blocks,
                    "text": "✅ Fire Drill Complete",
                },
            )
            print("📢 Drill completion message sent to Slack")

        except Exception as e:
            print(f"⚠️  Could not send completion message: {e}")


async def main():
    """Run the fire drill."""
    # Check AWS profile
    if os.environ.get("AWS_PROFILE") != "campaign_prod_v7":
        print("❌ Please set AWS_PROFILE=campaign_prod_v7")
        print("   export AWS_PROFILE=campaign_prod_v7")
        return

    # Check for non-interactive mode
    if os.environ.get("FIRE_DRILL_AUTO_RUN") == "true":
        print("⚠️  Running in automated mode - sending REAL alerts to #ketchup-alerts!")
    else:
        print("⚠️  WARNING: This will send REAL alerts to #ketchup-alerts!")
        print("Press Enter to continue or Ctrl+C to cancel...")
        try:
            input()
        except EOFError:
            print("\n❌ Running in non-interactive environment.")
            print("   Set FIRE_DRILL_AUTO_RUN=true to run automatically")
            return

    drill = AlertFireDrill()
    await drill.run_fire_drill()


if __name__ == "__main__":
    asyncio.run(main())
