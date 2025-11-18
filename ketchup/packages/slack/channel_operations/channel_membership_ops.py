"""
channel_membership_ops.py

This module contains the ChannelMembershipOps class, which is used to lookup
channels the bot is a member of.
"""

from typing import Dict, List, Optional, Tuple

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

# Note: PostingHandler and ArchiveOps are not needed for these methods

logger = setup_logger(__name__)


class ChannelMembershipOps(SlackAsyncClient):
    """
    This class is used to lookup channels the bot is a member of.
    Relies on injected Slack config.
    """

    def __init__(
        self,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ):
        """
        Initialize the Slack channel membership operations.

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
        logger.info("ChannelMembershipOps initialized.")

    # --- lookup_membership_of_channels methods ---

    async def _fetch_channel_page(
        self, cursor: Optional[str] = None
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        Fetches a single page of channel results from users.conversations API.

        Args:
            cursor: The pagination cursor from the previous response, if any.

        Returns:
            A tuple containing (list of channels on the page, next cursor).
            Returns (None, None) if the API call fails.
        """
        try:
            params = {
                "types": "public_channel",
                "exclude_archived": "true",
                "limit": self._batch_sizer.get_size(),
            }
            if cursor:
                params["cursor"] = cursor

            url = f"{await self.get_api_base_url()}/users.conversations"
            headers = self.headers  # Access as property

            response = await self._make_api_request(
                url, "GET", headers=headers, params=params
            )
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                self._batch_sizer.increase_size()  # Success, increase batch size
                channel_list = response_data.get("channels", [])
                next_cursor = response_data.get("response_metadata", {}).get(
                    "next_cursor"
                )
                logger.info("Fetched %d channels from page.", len(channel_list))
                return channel_list, next_cursor
            else:
                error = response_data.get("error", "Unknown error")
                self._batch_sizer.decrease_size()  # Error, decrease batch size
                logger.error("Slack API error fetching channel page: %s", error)
                return None, None
        except Exception as e:
            self._batch_sizer.decrease_size()  # Error, decrease batch size
            logger.error("Exception fetching channel page: %s", str(e))
            # Let the retry decorator handle the retry by raising it
            raise

    async def _fetch_all_channel_memberships(self) -> List[Dict[str, str]]:
        """Core logic for fetching all channels the bot is a member of, handling pagination."""
        logger.info("Starting _fetch_all_channel_memberships")
        all_channels = []
        cursor = None
        self._batch_sizer.current_size = 200  # Start with a larger batch size

        try:
            while True:
                # Use the helper to fetch one page
                channel_page, next_cursor = await self._fetch_channel_page(cursor)

                # If fetching a page failed, stop pagination
                if channel_page is None:
                    logger.error("Stopping pagination due to error fetching page.")
                    break

                # Process channels from the successful page fetch
                for channel in channel_page:
                    all_channels.append(
                        {
                            "id": channel.get("id"),
                            "name": channel.get("name"),
                            "is_private": channel.get("is_private", False),
                        }
                    )

                logger.info(
                    "Processed page, total channels so far: %s", len(all_channels)
                )

                # Check if we are done paginating
                if not next_cursor:
                    logger.info("No more pages to fetch.")
                    break

                cursor = next_cursor
                logger.info("Next page cursor: %s", cursor)

        except Exception as e:
            # Log error from the main loop (though page fetch errors are handled in helper)
            logger.error("Error during channel membership pagination loop: %s", str(e))
            # Depending on resilience needs, might want to return partial results or raise

        logger.info(
            "Finished fetching channel memberships, found %s channels",
            len(all_channels),
        )
        return all_channels

    @with_exponential_backoff()
    async def lookup_membership_of_channels(self) -> List[Dict[str, str]]:
        """
        Retrieve a list of Slack channels the bot is a member of. Applies backoff strategy.

        Returns:
            A list of dictionaries, each containing the 'id', 'name', and 'is_private' of a channel.
        """
        logger.info("Starting lookup_membership_of_channels")
        # Call the execute method of the stored backoff strategy
        return await self._backoff_strategy.execute(  # Call strategy's execute
            self._fetch_all_channel_memberships  # Pass the async method
        )
