"""
processor.py

This module contains the AutoStatusProcessor class, which is responsible for
processing all channels eligible for auto-status.

Migrated from ketchup_status_updater/processor.py
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from ketchup_unified_scheduler.services.status.generator import AutoStatusGenerator
from packages.core.config.feature_flags import FeatureFlags
from packages.core.constants import FEEDBACK_CHANNEL, TEST_CHANNEL
from packages.core.distributed_lock import DistributedLock
from packages.core.logging import setup_logger
from packages.core.schedulers import BaseScheduler
from packages.core.typed_di.exceptions import MissingDependencyError
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations.protocols.command_protocols import (
    FeatureServiceProtocol,
)
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
    SlackConfigProtocol,
    SlackPostingHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
    OpenAIHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
    MCPClientProtocol,
)
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    ChannelOperationsProtocol,
    SlackChannelMessageOpsProtocol,
)
from packages.core.typed_di_integration import get_unified_container

logger = setup_logger(__name__)

# TEST MODE: Set this to a specific channel ID to only process that channel
# Set to None or empty string to process all channels normally
TEST_CHANNEL_ID = ""  # Empty string = process all channels normally


class AutoStatusProcessor:
    def __init__(
        self,
        db_store,
        mcp_client,
        secrets_manager,
        slack_config,
        openai_handler,
        channel_info_ops,
        channel_msg_ops,
        posting_handler,
        channel_operations,
        channel_membership_ops,
        feature_service=None,
    ):
        self.db_store = db_store
        self.mcp_client = mcp_client
        self.secrets_manager = secrets_manager
        self.slack_config = slack_config
        self.openai_handler = openai_handler
        self.channel_info_ops = channel_info_ops
        self.channel_msg_ops = channel_msg_ops
        self.posting_handler = posting_handler
        self.channel_operations = channel_operations
        self.channel_membership_ops = channel_membership_ops
        self.feature_service = feature_service

    async def process_all_channels(self) -> Dict[str, Any]:
        """Process all channels eligible for auto-status."""
        results = {"processed": 0, "failed": 0, "skipped": 0, "errors": []}

        try:
            # Check if status updater is enabled on this server
            if os.environ.get("KETCHUP_STATUS_UPDATER_ENABLED", "false").lower() != "true":
                logger.info("Status updater disabled on this server")
                return results

            # Check if feature is enabled
            if not FeatureFlags.is_status_updater_enabled():
                logger.info("Status updater feature is disabled")
                return results

            # Check for global pause flag
            try:
                # Use the dynamodb client from db_store if available
                if hasattr(self.db_store, "client"):
                    response = await self.db_store.client.get_item(
                        key={"PK": {"S": "SYSTEM_SETTINGS"}, "SK": {"S": "AUTO_STATUS_CONFIG"}},
                        table_name=self.db_store.table_name,
                    )
                    # Check if item exists and if paused flag is true
                    if response.get("Item") and response["Item"].get("paused", {}).get(
                        "BOOL", False
                    ):
                        logger.info("Auto-status is paused globally")
                        return {
                            "processed": 0,
                            "skipped": 0,
                            "failed": 0,
                            "errors": ["Auto-status is paused"],
                        }
                else:
                    # For tests, check if get_item method exists and use it
                    try:
                        pause_settings = await self.db_store.get_item(
                            "SYSTEM_SETTINGS", "AUTO_STATUS_CONFIG"
                        )
                        if pause_settings and pause_settings.get("paused"):
                            logger.info("Auto-status is paused globally")
                            return {
                                "processed": 0,
                                "skipped": 0,
                                "failed": 0,
                                "errors": ["Auto-status is paused"],
                            }
                    except Exception:
                        # If get_item method doesn't exist or fails, continue
                        pass
            except Exception as e:
                logger.info(f"No pause settings found: {e}")
                # Continue if no settings exist

            # Get all active channels
            all_channels = await self.channel_operations.query_ops.get_all_active_channels()

            # Filter channels based on feature flags
            channels_to_process = []

            # Check for TEST_CHANNEL_ID first
            if TEST_CHANNEL_ID:
                logger.info(f"TEST MODE: Processing only channel {TEST_CHANNEL_ID}")
                test_channel = next(
                    (ch for ch in all_channels if ch.get("channel_id") == TEST_CHANNEL_ID), None
                )
                if test_channel:
                    channels_to_process = [test_channel]
                else:
                    logger.error(f"TEST_CHANNEL_ID {TEST_CHANNEL_ID} not found in active channels")
            elif FeatureFlags.is_status_updater_global():
                # Global mode - process all active channels
                channels_to_process = all_channels
                logger.info(
                    f"Global mode: Processing all {len(channels_to_process)} active channels"
                )
            else:
                # Check each channel for feature flag
                if self.feature_service:
                    for channel in all_channels:
                        channel_id = channel.get("channel_id")
                        if await self.feature_service.is_status_updater_enabled_for_channel(
                            channel_id
                        ):
                            channels_to_process.append(channel)

                    logger.info(f"Processing {len(channels_to_process)} enabled channels")
                else:
                    logger.warning(
                        "Feature service not available, falling back to TEST_CHANNEL only"
                    )

                # Fallback to TEST_CHANNEL if no channels enabled (for backward compatibility)
                if not channels_to_process:
                    logger.warning("No channels enabled, falling back to TEST_CHANNEL")
                    test_channel = next(
                        (ch for ch in all_channels if ch.get("channel_id") == TEST_CHANNEL), None
                    )
                    if test_channel:
                        channels_to_process = [test_channel]

            for channel in channels_to_process:
                channel_id = channel.get("channel_id")

                # Skip feedback channel
                if channel_id == FEEDBACK_CHANNEL:
                    logger.info(f"Skipping feedback channel {channel_id}")
                    results["skipped"] += 1
                    continue

                try:
                    # In global mode, process all channels regardless of timing
                    # In non-global mode, respect the 55-minute frequency check
                    should_process = (
                        FeatureFlags.is_status_updater_global()
                        or await self._should_process_channel(channel)
                    )

                    if should_process:
                        if FeatureFlags.is_status_updater_global():
                            logger.info(
                                f"Global mode: Processing channel {channel_id} (ignoring timing)"
                            )
                        success = await self._process_channel(channel)
                        if success:
                            results["processed"] += 1
                        else:
                            results["failed"] += 1
                    else:
                        logger.info(f"Channel {channel_id} not due for update, skipping")
                        results["skipped"] += 1

                except Exception as e:
                    logger.error(f"Error processing channel {channel_id}: {e}")
                    results["failed"] += 1
                    results["errors"].append(str(e))

                # Brief delay between channels to avoid rate limits
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error in process_all_channels: {e}")
            results["errors"].append(str(e))

        return results

    async def _should_process_channel(self, channel: Dict[str, Any]) -> bool:
        """Check if channel is due for status update."""
        last_run = channel.get("auto_status_last_run", 0)

        # Handle both int and string representations
        try:
            last_run = int(last_run) if last_run else 0
        except (ValueError, TypeError):
            last_run = 0

        # Use 30-minute frequency
        frequency_minutes = 30  # 30 minutes frequency

        if last_run == 0:
            logger.info(
                f"Channel {channel.get('channel_id')} has never been updated, processing now"
            )
            return True

        last_run_time = datetime.fromtimestamp(last_run)
        next_run_time = last_run_time + timedelta(minutes=frequency_minutes)

        should_process = datetime.now() >= next_run_time

        if should_process:
            logger.info(
                f"Channel {channel.get('channel_id')} is due for update (last run: {last_run_time.strftime('%H:%M:%S')})"
            )

        return should_process

    async def _process_channel(self, channel: Dict[str, Any]) -> bool:
        """Process a single channel for auto-status."""
        channel_id = channel.get("channel_id")
        if not channel_id:
            logger.error(f"No channel_id in channel data: {channel}")
            return False

        channel_name = channel.get("channel_name", "unknown")

        logger.info(f"Processing auto-status for channel {channel_id} ({channel_name})")

        try:
            # Check if bot is member of channel before processing
            try:
                all_channels = await self.channel_membership_ops.lookup_membership_of_channels()
                if channel_id not in [ch["id"] for ch in all_channels]:
                    logger.warning(f"Bot not member of channel {channel_id}, skipping")
                    return False
            except Exception as e:
                logger.warning(f"Could not check channel membership for {channel_id}: {e}")
                # Continue processing if membership check fails (assume bot is member for tests)

            # Generate status using existing components
            generator = AutoStatusGenerator(
                db_store=self.db_store,
                mcp_client=self.mcp_client,
                secrets_manager=self.secrets_manager,
                slack_config=self.slack_config,
                openai_handler=self.openai_handler,
                channel_info_ops=self.channel_info_ops,
                channel_msg_ops=self.channel_msg_ops,
                posting_handler=self.posting_handler,
                channel_operations=self.channel_operations,
            )

            # ALWAYS check for activity first, regardless of attempt count
            activity_check = await generator.check_for_activity(
                channel_id=channel_id, channel_config=channel
            )

            # Update timestamp to the latest message we've seen (from activity check)
            # This ensures we don't re-check the same messages next time
            latest_message_ts = activity_check.get(
                "latest_message_ts", channel.get("auto_status_last_message_ts", "0")
            )
            latest_thread_ts = activity_check.get(
                "latest_thread_ts", channel.get("auto_status_last_thread_ts", "0")
            )

            # Store timestamps as integers to avoid precision mismatches with Slack API
            # This fixes the issue where decimal timestamps aren't properly compared with integer message timestamps
            latest_message_ts_int = (
                int(float(latest_message_ts)) if latest_message_ts != "0" else "0"
            )
            latest_thread_ts_int = int(float(latest_thread_ts)) if latest_thread_ts != "0" else "0"

            logger.info(
                f"Updating timestamps for {channel_id} - message: {latest_message_ts} -> {latest_message_ts_int}, thread: {latest_thread_ts} -> {latest_thread_ts_int}"
            )
            await self.channel_operations.update_channel_fields(
                channel_id=channel_id,
                updates={
                    "auto_status_last_message_ts": latest_message_ts_int,
                    "auto_status_last_thread_ts": latest_thread_ts_int,
                },
            )

            # Check if this is a first run (no auto_status_last_message_ts field)
            is_first_run = "auto_status_last_message_ts" not in channel

            if not activity_check["has_activity"] and not is_first_run:
                logger.info(
                    f"No activity detected for channel {channel_id} - "
                    f"no new Slack messages and no new JIRA comments. Skipping status post."
                )
                # Update last run timestamp even when skipping
                await self.channel_operations.update_channel_fields(
                    channel_id=channel_id,
                    updates={
                        "auto_status_last_run": int(time.time()),
                        "auto_status_attempt_count": 0,  # Reset attempts on successful skip
                    },
                )
                return True
            elif is_first_run:
                logger.info(
                    f"First run for channel {channel_id} - posting status regardless of activity detection"
                )

            # Activity detected, check attempt count
            attempt_count = int(channel.get("auto_status_attempt_count", 0))

            if attempt_count >= 5:
                # After 5 failures, skip posting even with activity
                logger.warning(
                    f"Channel {channel_id} has {attempt_count} failed attempts. "
                    f"Skipping status generation despite activity to prevent errors."
                )
                # Don't increment attempt count further, just update last run
                await self.channel_operations.update_channel_fields(
                    channel_id=channel_id, updates={"auto_status_last_run": int(time.time())}
                )
                return True  # Return true to indicate we handled it (by skipping)

            # Activity detected, generate and post status
            logger.info(
                f"Activity detected for channel {channel_id} - "
                f"new messages: {activity_check['has_new_messages']}, "
                f"new JIRA: {activity_check['has_jira_updates']}"
            )

            success = await generator.generate_and_post_status(
                channel_id=channel_id,
                channel_name=channel_name,
                channel_config=channel,  # Pass the full channel config
                activity_check=activity_check,  # Pass the activity check results
            )

            if success:
                # Update last run timestamp and reset attempts
                await self.channel_operations.update_channel_fields(
                    channel_id=channel_id,
                    updates={
                        "auto_status_last_run": int(time.time()),
                        "auto_status_attempt_count": 0,
                    },
                )
                return True
            else:
                # Increment attempt count on failure
                await self.channel_operations.update_channel_fields(
                    channel_id=channel_id, updates={"auto_status_attempt_count": attempt_count + 1}
                )
                return False

        except Exception as e:
            logger.error(f"Failed to process channel {channel_id}: {e}")
            return False


async def run_auto_status(
    container: Optional[TypedServiceRegistry] = None,
):
    """Run the auto-status update process with distributed locking.

    Args:
        container: Optional pre-initialized TypedDI container. If None,
                  creates a new container via get_unified_container().
    """
    try:
        logger.info(f"Starting auto-status update at {datetime.now()}")

        # Initialize DI container if not provided (supports passthrough pattern)
        if container is None:
            logger.info("Initializing DI container...")
            container = await get_unified_container()

        # Get DynamoDB store using TypedDI
        db_store = await container.aget(DynamoDBStoreProtocol)
        distributed_lock = DistributedLock(db_store.client, db_store.table_name)

        # Use distributed lock instead of local file lock
        async with distributed_lock.acquire_lock(
            "AUTO_STATUS_GLOBAL", timeout_seconds=120
        ) as lock_acquired:
            if not lock_acquired:
                logger.warning("Another server is running auto-status, exiting")
                return

            logger.info("Distributed lock acquired, proceeding with status update")

            # Get required services using TypedDI
            mcp_client = await container.aget(MCPClientProtocol)
            secrets_manager = await container.aget(SecretsManagerProtocol)
            slack_config = await container.aget(SlackConfigProtocol)
            openai_handler = await container.aget(OpenAIHandlerProtocol)
            channel_info_ops = await container.aget(ChannelInfoOpsProtocol)
            channel_msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
            posting_handler = await container.aget(SlackPostingHandlerProtocol)
            channel_operations = await container.aget(ChannelOperationsProtocol)
            channel_membership_ops = await container.aget(ChannelMembershipOpsProtocol)

            # Handle optional feature_service with error handling
            feature_service = None
            if FeatureFlags.is_status_updater_enabled():
                try:
                    feature_service = await container.aget(FeatureServiceProtocol)
                except MissingDependencyError:
                    logger.info("Feature service not available - using default settings")
                except Exception as e:
                    logger.warning(f"Could not get feature_service: {e}")

            processor = AutoStatusProcessor(
                db_store=db_store,
                mcp_client=mcp_client,
                secrets_manager=secrets_manager,
                slack_config=slack_config,
                openai_handler=openai_handler,
                channel_info_ops=channel_info_ops,
                channel_msg_ops=channel_msg_ops,
                posting_handler=posting_handler,
                channel_operations=channel_operations,
                channel_membership_ops=channel_membership_ops,
                feature_service=feature_service,
            )

            # Process all eligible channels
            results = await processor.process_all_channels()

            logger.info(f"Auto-status update completed: {results}")

    except Exception as e:
        logger.error(f"Auto-status update failed: {e}", exc_info=True)
        raise


class StatusUpdaterScheduler(BaseScheduler):
    """Scheduler for running status updates reliably in Docker."""

    def __init__(self):
        super().__init__(
            health_file_prefix="scheduler",
            base_path="/tmp",
            interval_minutes=55,
            run_on_start=True,
            scheduler_name="Status Updater Scheduler",
        )
        # Override for backward compatibility (original was /tmp/last_run)
        self.last_run_file = Path("/tmp/last_run")

    async def run_task(self) -> None:
        """Execute the status update task."""
        await run_auto_status()


async def async_main():
    """Async main entry point."""
    scheduler = StatusUpdaterScheduler()
    await scheduler.start()


def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
