"""
channel_processor.py

This module contains the ChannelProcessor class that manages
channel data processing for metadata extraction.
"""

import asyncio
from typing import Dict, List, Set

from packages.core.constants import MAX_RETRIES, USE_PIPELINE_PROCESSING
from packages.core.logging import setup_logger


class ChannelProcessor:
    """Processes Slack channels for metadata extraction."""

    def __init__(
        self,
        channel_msg_ops=None,
        dynamodb_store=None,
        max_concurrency: int = 10,
    ):
        """Initialize with required channel operations dependency.

        Args:
            channel_msg_ops: An initialized SlackChannelMessageOps instance.
            dynamodb_store: An initialized DynamoDBStore instance.
            max_concurrency: Maximum concurrent channel processing.
        """
        if not channel_msg_ops:
            raise ValueError(
                "An initialized SlackChannelMessageOps instance is required."
            )
        self.channel_msg_ops = channel_msg_ops
        self.dynamodb_store = dynamodb_store
        self.logger = setup_logger(__name__)

        # Concurrency controls
        self.semaphore = asyncio.Semaphore(max_concurrency)

        # Tracking for processed channels
        self.processed_channels: Set[str] = set()

    async def fetch_channel_messages(self, channel_id: str) -> List[str]:
        """
        Fetch recent messages from a Slack channel.

        Args:
            channel_id: The Slack channel ID

        Returns:
            List of message texts from the channel
        """
        self.logger.info("Fetching messages for channel %s", channel_id)

        retry_count = 0
        last_error = None

        while retry_count < MAX_RETRIES:
            try:
                # Using channel_msg_ops to fetch messages - already returns formatted strings
                # Include bot messages for metadata extraction to capture all relevant information
                # Include system messages to capture topic changes with customer names
                if USE_PIPELINE_PROCESSING:
                    messages = await self.channel_msg_ops.fetch_channel_messages_collected(
                        channel_id=channel_id,
                        include_bot_messages=True,
                        include_system_messages=True
                    )
                else:
                    messages = await self.channel_msg_ops.fetch_channel_messages(
                        channel_id=channel_id,
                        include_bot_messages=True,
                        include_system_messages=True
                    )

                self.logger.info(
                    "Retrieved %d messages from channel %s",
                    len(messages),
                    channel_id,
                )

                return messages

            except Exception as e:
                last_error = e
                retry_count += 1
                error_str = str(e).lower()
                error_data = getattr(e, "response_data", {})
                # Handle channel_not_found or not_in_channel - delete from DB
                if "channel_not_found" in error_str or "not_in_channel" in error_str or (
                    isinstance(error_data, dict)
                    and error_data.get("error") in ["channel_not_found", "not_in_channel"]
                ):
                    self.logger.warning(
                        "Channel %s not found or bot not in channel. Deleting from DB.", channel_id
                    )
                    # Use DI'd DynamoDBStore for deletion
                    if self.dynamodb_store:
                        await self.dynamodb_store.delete_channel_if_exists(channel_id)
                    else:
                        self.logger.error("No DynamoDBStore available for deletion!")
                    return []  # Always return a list, never True
                self.logger.error(
                    "Error extracting metadata for channel %s: %s",
                    channel_id,
                    str(e),
                    exc_info=True,
                )
                if retry_count < MAX_RETRIES:
                    await asyncio.sleep(2**retry_count)

        # If all retries failed, log error and return empty list
        self.logger.error(
            "Failed to fetch messages for channel %s after %d retries: %s",
            channel_id,
            MAX_RETRIES,
            str(last_error),
            exc_info=True,
        )
        return []

    async def process_channels_batch(
        self, channel_ids: List[str], process_function
    ) -> Dict[str, int]:
        """
        Process multiple channels concurrently using TaskGroup.

        Args:
            channel_ids: List of channel IDs to process
            process_function: Async function to process each channel

        Returns:
            Statistics of processing results
        """
        stats = {"total": len(channel_ids), "success": 0, "failure": 0, "skipped": 0}
        self.processed_channels = set()

        unique_channels = set(channel_ids)
        if len(unique_channels) < len(channel_ids):
            self.logger.info(
                "Removed %d duplicate channel IDs",
                len(channel_ids) - len(unique_channels),
            )

        try:
            # Use TaskGroup for concurrent processing
            async with asyncio.TaskGroup() as task_group:
                for channel_id in unique_channels:
                    # Create task for each channel with error handling wrapper
                    task_group.create_task(
                        self._safe_process_channel(channel_id, stats, process_function)
                    )

            self.logger.info("Batch processing complete. Stats: %s", stats)
            return stats
        except Exception as e:
            self.logger.error(
                "Error during batch processing: %s", str(e), exc_info=True
            )
            return stats

    async def _safe_process_channel(
        self, channel_id: str, stats: Dict[str, int], process_function
    ) -> None:
        """
        Process a channel with error handling.

        Args:
            channel_id: Channel ID to process
            stats: Statistics dictionary to update
            process_function: Async function to process the channel
        """
        # Avoid processing the same channel twice in a batch
        if channel_id in self.processed_channels:
            self.logger.info(
                "Channel %s already processed in this batch, skipping", channel_id
            )
            stats["skipped"] = stats.get("skipped", 0) + 1
            return

        self.processed_channels.add(channel_id)

        # Use semaphore to control concurrency
        async with self.semaphore:
            try:
                result = await process_function(channel_id)
                if result:
                    stats["success"] = stats.get("success", 0) + 1
                else:
                    stats["failure"] = stats.get("failure", 0) + 1
            except Exception as e:
                stats["failure"] = stats.get("failure", 0) + 1
                self.logger.error(
                    "Unhandled exception processing channel %s: %s",
                    channel_id,
                    str(e),
                    exc_info=True,
                )

    async def cleanup(self) -> None:
        """Clean up channel operations resources."""
        try:
            if hasattr(self.channel_msg_ops, "cleanup"):
                await self.channel_msg_ops.cleanup()
        except Exception as e:
            self.logger.error("Error cleaning up channel operations: %s", str(e))
