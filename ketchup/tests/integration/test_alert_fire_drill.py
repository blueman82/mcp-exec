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

        # Use TypedDI
        from packages.core.typed_di_integration import get_unified_container

        try:
            self.container = await get_unified_container()
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

        # Run health checks (would need access operations to be mockable)
        issues = await self.monitor.run_health_checks()

        # Send alert if issues found
        if issues:
            print(f"   Found {len(issues)} issues!")
            await self.monitor.send_alert(issues)
            print("   🚨 ALERT SENT to #ketchup-alerts!")

        self.scenarios_run.append("high_pending_requests")

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

    async def send_drill_announcement(self):
        """Send announcement that this is a drill."""
        try:
            from packages.slack.clients.async_client import SlackAsyncClient

            slack_client = await self.container.aget(SlackAsyncClient)

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
            from packages.slack.clients.async_client import SlackAsyncClient

            slack_client = await self.container.aget(SlackAsyncClient)

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
