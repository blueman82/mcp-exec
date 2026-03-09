"""
channel_info_ops.py

This module contains the ChannelInfoOps class, which is used to lookup
details for a single Slack channel.
"""

from typing import Dict, Optional, Tuple

import orjson

from packages.core.constants import MAX_RETRIES
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import (
    BackoffStrategy,
    ExponentialBackoffStrategy,
    with_exponential_backoff,
)
from packages.slack.config.slack_config import SlackConfig
from packages.slack.core.slack_async_client import SlackAsyncClient
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class ChannelInfoOps(SlackAsyncClient):
    """
    This class is used to lookup details for a single Slack channel.
    Relies on injected dependencies for posting messages.
    """

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ):
        """
        Initialize the Slack channel info operations.

        Args:
            posting_handler: Handler for posting messages.
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
        self.posting_handler = posting_handler
        logger.info("ChannelInfoOps initialized with injected dependencies.")

    async def get_channel_info_from_api(self, channel_id: str) -> Optional[Dict]:
        """
        Fetches channel information directly from the Slack conversations.info API.

        This method encapsulates the API call logic.

        Args:
            channel_id: The Slack channel ID to query.

        Returns:
            A dictionary containing the channel object from the API response
            if successful and 'ok' is True, otherwise None.
        """
        logger.info("Fetching channel info directly from API for %s", channel_id)
        try:
            url = f"{await self.get_api_base_url()}/conversations.info"
            headers = self.headers  # Access as property
            params = {"channel": channel_id}

            response = await self._make_api_request(url, "GET", headers=headers, params=params)
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                return response_data.get("channel")
            else:
                logger.warning(
                    "API call to conversations.info failed for %s: %s",
                    channel_id,
                    response_data.get("error"),
                )
                return None
        except Exception as e:
            logger.error(
                "Exception during conversations.info API call for %s: %s",
                channel_id,
                e,
                exc_info=True,
            )
            return None

    # --- get_channel_details methods ---

    async def _handle_bot_not_member(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str],
        channel_name: str,
        is_archived: bool,
        is_private: bool,
    ) -> Tuple[str, bool, bool, bool]:
        """Handles the case where the bot is not a member of the channel."""
        logger.warning("Bot is not a member of channel %s. Informing user.", channel_id)
        try:
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message=f"I am not currently a member of channel `{channel_id}`. Please invite me by typing `@Ketchup` in that channel.",
                response_url=response_url,
            )
        except Exception as post_error:
            logger.error("Failed to send 'not a member' message to user: %s", post_error)
        # Return details indicating bot is not member, regardless of posting success
        return channel_name, False, is_archived, is_private

    async def _handle_channel_lookup_error(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str],
        api_error: Optional[str],
    ):
        """Handles API errors during channel lookup and notifies the user."""
        error_message_to_user = (
            f"Error accessing channel `{channel_id}`. Please check the ID or my permissions."
        )
        if api_error == "channel_not_found":
            error_message_to_user = f"Error: Could not find channel `{channel_id}`. Please verify the channel ID is correct."
            logger.error("Channel %s not found.", channel_id)
        elif api_error == "not_in_channel":
            error_message_to_user = f"I am not currently a member of channel `{channel_id}`. Please invite me by typing `@Ketchup` in that channel."
            logger.warning("Bot is not in channel %s (API error).", channel_id)
        else:
            logger.error("Slack API error when looking up channel %s: %s", channel_id, api_error)

        # Attempt to post the error message
        try:
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message=error_message_to_user,
                response_url=response_url,
            )
        except Exception as post_error:
            logger.error("Failed to send API error '%s' to user: %s", api_error, post_error)
        return None

    async def _fetch_channel_details_core(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str],
    ) -> Optional[Tuple[str, bool, bool, bool]]:
        """Core logic for fetching channel details via API."""
        logger.info("Fetching details for channel %s", channel_id)
        try:
            url = f"{await self.get_api_base_url()}/conversations.info"
            headers = self.headers  # Access as property
            params = {"channel": channel_id}

            response = await self._make_api_request(url, "GET", headers=headers, params=params)
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                channel_data = response_data.get("channel", {})
                channel_name = channel_data.get("name", "Unknown Channel")
                is_member = channel_data.get("is_member", False)
                is_archived = channel_data.get("is_archived", False)
                is_private = channel_data.get("is_private", False)

                logger.info(
                    "Channel %s details: Name='%s', Member=%s, Archived=%s, Private=%s",
                    channel_id,
                    channel_name,
                    is_member,
                    is_archived,
                    is_private,
                )

                if not is_member:
                    # Delegate "not a member" handling
                    return await self._handle_bot_not_member(
                        user_id,
                        channel_id,
                        dm_channel_id,
                        response_url,
                        channel_name,
                        is_archived,
                        is_private,
                    )
                else:
                    # Bot is a member, return details
                    return channel_name, is_member, is_archived, is_private
            else:
                # Delegate API error handling
                return await self._handle_channel_lookup_error(
                    user_id,
                    channel_id,
                    dm_channel_id,
                    response_url,
                    response_data.get("error"),
                )

        except Exception as e:
            logger.error("Error retrieving channel info for %s: %s", channel_id, e, exc_info=True)
            # Attempt to post a generic error message
            try:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=dm_channel_id,
                    message=f"An unexpected error occurred while retrieving info for channel `{channel_id}`.",
                    response_url=response_url,
                )
            except Exception as post_error:
                logger.error("Failed to send general error message to user: %s", post_error)
            return None

    @with_exponential_backoff()
    async def get_channel_details(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str] = None,
    ) -> Optional[Tuple[str, bool, bool, bool]]:
        """
        Retrieve details about a specific Slack channel. Applies backoff strategy.

        Args:
            user_id: The ID of the user requesting the details.
            channel_id: The Slack channel ID to get details for.
            dm_channel_id: The channel ID where the command was issued (for fallback messages).
            response_url: Optional response URL for posting asynchronous messages.

        Returns:
            A tuple containing (channel_name, is_member, is_archived, is_private) or None if fails.
        """
        logger.info("Starting get_channel_details for channel %s", channel_id)
        # Use the backoff strategy to handle retries for the core logic
        return await self._backoff_strategy.execute(  # type: ignore[arg-type]
            self._fetch_channel_details_core,
            user_id=user_id,
            channel_id=channel_id,
            dm_channel_id=dm_channel_id,
            response_url=response_url,
        )
