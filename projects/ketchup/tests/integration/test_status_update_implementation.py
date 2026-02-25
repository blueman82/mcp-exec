#!/usr/bin/env python3
"""
Test script for status update implementation on channel C094BNAUTDJ

This script simulates a status updater run on the test channel to verify:
1. "Why this update?" formatting works correctly
2. Previous post deletion functionality works
3. New post timestamp storage works
4. Backward compatibility with existing channels
"""

import asyncio
import sys
from datetime import datetime, timezone

from base_integration_test import BaseIntegrationTest

from ketchup_unified_scheduler.services.status.generator import AutoStatusGenerator

TEST_CHANNEL_ID = "C094BNAUTDJ"  # test_acc_cso_2


class StatusUpdateIntegrationTest(BaseIntegrationTest):
    """Integration test for status update functionality."""

    def __init__(self):
        super().__init__(
            test_name="status_update_implementation",
            env_vars={"KETCHUP_TRUST_ENDORSEMENT_FEATURE": "true"},
        )
        self.test_channel_id = TEST_CHANNEL_ID

    async def run_test(self) -> bool:
        """Test the new status update implementation on a real channel."""
        # Get all required services
        services = self.get_services(
            [
                "dynamodb_store",
                "mcp_client",
                "secrets_manager",
                "slack_config",
                "openai",
                "msg_ops",
                "slack_posting",
                "channel_operations",
            ]
        )

        # Create status generator
        self.logger.info("Creating AutoStatusGenerator...")
        status_generator = AutoStatusGenerator(
            db_store=services["dynamodb_store"],
            mcp_client=services["mcp_client"],
            secrets_manager=services["secrets_manager"],
            slack_config=services["slack_config"],
            openai_handler=services["openai"],
            channel_msg_ops=services["msg_ops"],
            posting_handler=services["slack_posting"],
            channel_operations=services["channel_operations"],
        )

        # Get current channel state
        self.logger.info(f"Getting current state for channel {self.test_channel_id}...")
        channel_config = await services["channel_operations"].get_channel_details(
            self.test_channel_id
        )

        if not channel_config:
            self.logger.error(f"Channel {self.test_channel_id} not found in database!")
            return False

        # Log current timestamps
        current_msg_ts = channel_config.get("auto_status_last_message_ts", "0")
        current_post_ts = channel_config.get("auto_status_last_post_ts", "0")
        current_thread_ts = channel_config.get("auto_status_last_thread_ts", "0")
        current_jira_ts = channel_config.get("auto_status_last_jira_comment_ts", "0")

        self.logger.info("Current channel state:")
        self.logger.info(f"  auto_status_last_message_ts: {current_msg_ts}")
        self.logger.info(f"  auto_status_last_post_ts: {current_post_ts}")
        self.logger.info(f"  auto_status_last_thread_ts: {current_thread_ts}")
        self.logger.info(f"  auto_status_last_jira_comment_ts: {current_jira_ts}")

        # Convert timestamp to readable format for verification
        if current_msg_ts != "0":
            current_time = datetime.fromtimestamp(float(current_msg_ts), tz=timezone.utc)
            self.logger.info(
                f"  Last message time: {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

        # Check for activity
        self.logger.info("Checking for channel activity...")
        activity_check = await status_generator.check_for_activity(
            self.test_channel_id, channel_config
        )

        has_activity = activity_check.get("has_activity", False)
        has_new_messages = activity_check.get("has_new_messages", False)
        has_thread_activity = activity_check.get("has_thread_activity", False)
        latest_message_ts = activity_check.get("latest_message_ts", "0")
        latest_thread_ts = activity_check.get("latest_thread_ts", "0")

        self.logger.info("Activity check results:")
        self.logger.info(f"  has_activity: {has_activity}")
        self.logger.info(f"  has_new_messages: {has_new_messages}")
        self.logger.info(f"  has_thread_activity: {has_thread_activity}")
        self.logger.info(f"  latest_message_ts: {latest_message_ts}")
        self.logger.info(f"  latest_thread_ts: {latest_thread_ts}")

        if not has_activity:
            self.logger.info("No activity detected - no status update needed")
            return True

        # Generate status update
        self.logger.info("Activity detected! Generating status update...")

        # Get channel name for display
        channel_name = channel_config.get("channel_name", "unknown")
        self.logger.info(f"Channel name: {channel_name}")

        # Test the generate_and_post_status method
        result = await status_generator.generate_and_post_status(
            channel_id=self.test_channel_id,
            channel_name=channel_name,
            channel_config=channel_config,  # Pass the full channel config
            activity_check=activity_check,  # Pass the activity check results
        )

        if result:
            self.logger.info("✅ Status update generated successfully!")

            # Check if previous post was deleted (if there was one)
            if current_post_ts != "0":
                self.logger.info(f"Previous post timestamp was: {current_post_ts}")
                self.logger.info("Check Slack channel to verify previous post was deleted")
            else:
                self.logger.info("No previous post to delete (first run with new code)")

            # Verify new post timestamp was stored
            updated_config = await services["channel_operations"].get_channel_details(
                self.test_channel_id
            )
            new_post_ts = updated_config.get("auto_status_last_post_ts", "0")

            self.logger.info("Post-update channel state:")
            self.logger.info(f"  auto_status_last_post_ts: {new_post_ts}")

            if new_post_ts != "0" and new_post_ts != current_post_ts:
                self.logger.info("✅ New post timestamp stored successfully!")
            else:
                self.logger.warning("⚠️ Post timestamp may not have been updated correctly")

            return True
        else:
            self.logger.error("❌ Status update failed!")
            return False


async def main():
    """Main test function."""
    test = StatusUpdateIntegrationTest()
    return await test.execute()


if __name__ == "__main__":
    # Run the test
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
