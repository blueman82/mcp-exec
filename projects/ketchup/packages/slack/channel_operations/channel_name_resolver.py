"""
channel_name_resolver.py

This module provides utilities for resolving channel names to channel IDs.
It supports both direct channel names and Slack channel mentions.
"""

from typing import Optional, Tuple

from packages.core.constants import (
    MAX_RETRIES,
    SLACK_CHANNEL_ID_REGEX,
    SLACK_CHANNEL_MENTION_REGEX,
    SLACK_CHANNEL_NAME_REGEX,
)
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import (
    BackoffStrategy,
    ExponentialBackoffStrategy,
    with_exponential_backoff,
)
from packages.slack.config.slack_config import SlackConfig
from packages.slack.core.slack_async_client import SlackAsyncClient

logger = setup_logger(__name__)


class ChannelNameResolver(SlackAsyncClient):
    """
    Utility class for resolving channel names and mentions to channel IDs.
    """

    def __init__(
        self,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ):
        """
        Initialize the ChannelNameResolver.

        Args:
            slack_config: Pre-initialized SlackConfig instance (required).
            max_concurrent_requests: Maximum number of concurrent requests.
            backoff_strategy: Strategy for handling retries and backoff (optional).
        """
        super().__init__(
            slack_config=slack_config,
            max_concurrent_requests=max_concurrent_requests,
            backoff_strategy=backoff_strategy
            or ExponentialBackoffStrategy(max_retries=MAX_RETRIES),
        )
        logger.info("ChannelNameResolver initialized.")

    async def resolve_channel_parameter(self, channel_param: str) -> Tuple[Optional[str], str]:
        """
        Resolve a channel parameter to a channel ID.

        Supports multiple formats (examples):
        - Direct channel ID: C1234567890
        - Channel mention: <#C1234567890|channel-name>
        - Channel name: #channel-name

        Args:
            channel_param: The channel parameter to resolve

        Returns:
            Tuple of (channel_id, format_type) where format_type describes what was matched
            Returns (None, error_message) if resolution fails
        """
        channel_param = channel_param.strip()

        # Check if it's already a valid channel ID
        if SLACK_CHANNEL_ID_REGEX.match(channel_param):
            logger.info("Channel parameter is already a valid channel ID: %s", channel_param)
            return channel_param, "channel_id"

        # Check if it's a channel mention format <#CHANNEL_ID|channel-name>
        mention_match = SLACK_CHANNEL_MENTION_REGEX.match(channel_param)
        if mention_match:
            channel_id = mention_match.group(1)
            channel_name = mention_match.group(2)
            logger.info("Parsed channel mention: ID=%s, Name=%s", channel_id, channel_name)
            return channel_id, "channel_mention"

        # Check if it's a channel name format #channel-name
        name_match = SLACK_CHANNEL_NAME_REGEX.match(channel_param)
        if name_match:
            channel_name = name_match.group(1)  # Extract name without #
            logger.info("Attempting to resolve channel name: %s", channel_name)

            # Resolve channel name to ID using Slack API
            channel_id = await self._resolve_channel_name_to_id(channel_name)
            if channel_id:
                return channel_id, "channel_name"
            else:
                return (
                    None,
                    f"Channel name '#{channel_name}' not found or not accessible",
                )

        # Invalid format
        return (
            None,
            f"Invalid channel format: '{channel_param}'. Use channel ID (C1234567890), mention (<#C1234567890|name>), or name (#channel-name)",
        )

    @with_exponential_backoff()
    async def _resolve_channel_name_to_id(self, channel_name: str) -> Optional[str]:
        """
        Resolve a channel name to channel ID using the Slack API.

        Args:
            channel_name: The channel name (without #)

        Returns:
            Channel ID if found, None otherwise
        """
        try:
            # Use conversations.list to search for the channel
            url = f"{await self.get_api_base_url()}/conversations.list"
            headers = self.headers

            # Search through public channels first
            params = {
                "types": "public_channel",
                "exclude_archived": "true",
                "limit": 1000,  # Max limit for better chance of finding the channel
            }

            cursor = None
            while True:
                if cursor:
                    params["cursor"] = cursor

                response = await self._make_api_request("GET", url, headers=headers, params=params)

                if not response or not response.get("ok"):
                    logger.warning("Failed to fetch channels list: %s", response)
                    break

                channels = response.get("channels", [])

                # Search for matching channel name
                for channel in channels:
                    if channel.get("name") == channel_name:
                        channel_id = channel.get("id")
                        logger.info(
                            "Resolved channel name '%s' to ID: %s",
                            channel_name,
                            channel_id,
                        )
                        return channel_id

                # Check if there are more pages
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # If not found in public channels, try private channels the bot is a member of
            params["types"] = "private_channel"
            cursor = None

            while True:
                if cursor:
                    params["cursor"] = cursor

                response = await self._make_api_request("GET", url, headers=headers, params=params)

                if not response or not response.get("ok"):
                    logger.warning("Failed to fetch private channels list: %s", response)
                    break

                channels = response.get("channels", [])

                # Search for matching channel name
                for channel in channels:
                    if channel.get("name") == channel_name:
                        channel_id = channel.get("id")
                        logger.info(
                            "Resolved private channel name '%s' to ID: %s",
                            channel_name,
                            channel_id,
                        )
                        return channel_id

                # Check if there are more pages
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            logger.warning("Channel name '%s' not found in accessible channels", channel_name)
            return None

        except Exception as e:
            logger.error(
                "Error resolving channel name '%s': %s",
                channel_name,
                str(e),
                exc_info=True,
            )
            return None
