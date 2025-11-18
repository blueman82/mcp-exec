"""
Slack Async Client

This module provides a specialized client for asynchronous interaction with Slack API,
with improved connection management, concurrency control, and retry logic.
"""

import json
from typing import Dict, Optional

import aiohttp
import orjson

from packages.core.async_client import AsyncClient
from packages.core.constants import SLACK_API_TIMEOUT
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import BackoffStrategy
from packages.slack.config.slack_config import SlackConfig

logger = setup_logger(__name__)


class SlackAsyncClient(AsyncClient[SlackConfig, aiohttp.ClientResponse]):
    """Specialized client for asynchronous interactions with Slack API."""

    def __init__(
        self,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
        request_timeout: Optional[
            float
        ] = (  # Use .total as SLACK_API_TIMEOUT is ClientTimeout
            SLACK_API_TIMEOUT.total if SLACK_API_TIMEOUT else None
        ),
        backoff_strategy: Optional[BackoffStrategy] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize the Slack async client.

        Args:
            slack_config: Slack configuration object
            max_concurrent_requests: Max concurrent requests allowed
            request_timeout: Request timeout in seconds
            backoff_strategy: Custom backoff strategy (optional)
            aiohttp_session: Optional pre-configured aiohttp ClientSession
        """
        # Determine the integer timeout value to pass to the base class
        timeout_value: int
        if request_timeout is not None:
            timeout_value = int(request_timeout)
        elif SLACK_API_TIMEOUT and SLACK_API_TIMEOUT.total is not None:
            timeout_value = int(SLACK_API_TIMEOUT.total)
        else:
            # Default to 30 seconds if constant is not available
            logger.warning(
                "SLACK_API_TIMEOUT constant not found or invalid, using default 30s timeout."
            )
            timeout_value = 30

        super().__init__(
            config=slack_config,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=timeout_value,  # Pass the guaranteed int
            backoff_strategy=backoff_strategy,
        )
        # The session is now managed by the AsyncClient base class (setup/close)
        self.slack_config: SlackConfig = slack_config

        # Assign the provided aiohttp_session if it's valid (exists and open).
        # The base AsyncClient.setup() method will detect and use this session,
        # otherwise it will create a new one.
        if aiohttp_session and not aiohttp_session.closed:
            self._session = aiohttp_session
            logger.info(
                "Using provided aiohttp session for %s", self.__class__.__name__
            )
        # Base AsyncClient.setup() handles session creation if none is provided or invalid.

    @property
    def headers(self) -> Dict[str, str]:
        """Generate API request headers."""
        return self.slack_config.get_headers()

    async def get_api_base_url(self) -> str:
        """Get base URL for Slack API requests.

        Returns:
            Base URL for Slack API endpoints
        """
        return self.slack_config.get_api_base_url()

    async def check_bot_channel_membership(self, channel_id: str) -> bool:
        """Check if the bot is a member of a specified channel.

        This method calls conversations.info to determine if the bot has
        successfully joined the channel.

        Args:
            channel_id: The Slack channel ID to check for membership

        Returns:
            bool: True if the bot is a member of the channel, False otherwise
        """
        try:
            url = f"{await self.get_api_base_url()}/conversations.info"
            headers = self.slack_config.get_headers()
            payload = {
                "channel": channel_id,
            }

            response = await self._make_api_request(url, "GET", headers, payload)

            try:
                response_data = orjson.loads(response["body"])
            except (orjson.JSONDecodeError, json.JSONDecodeError) as e:
                logger.error(
                    "Failed to parse JSON for bot membership check in channel %s: %s",
                    channel_id,
                    str(e),
                )
                return False

            if response_data.get("ok"):
                # Check if the bot is a member of the channel
                is_member = response_data.get("channel", {}).get("is_member", False)
                logger.info(
                    "Bot membership status for channel %s: %s",
                    channel_id,
                    "Member" if is_member else "Not a member",
                )
                return is_member
            else:
                error = response_data.get("error")
                logger.warning(
                    "Error checking bot membership for channel %s: %s",
                    channel_id,
                    error,
                )
                return False
        except Exception as e:
            logger.warning(
                "Exception checking bot membership for channel %s: %s", channel_id, e
            )
            return False

    async def cleanup(self) -> None:
        """Clean up shared resources including HTTP sessions and caches.

        Overrides the parent cleanup method to also clean up Slack-specific resources.
        """
        # Call parent cleanup to handle session
        logger.info("Cleaning up SlackAsyncClient resources")
        await super().cleanup()

    async def api_call(self, endpoint: str, payload: dict) -> dict:
        """
        Make a generic POST request to a Slack API endpoint.

        Args:
            endpoint: Slack API endpoint (e.g., 'views.publish')
            payload: JSON payload to send

        Returns:
            Parsed JSON response from Slack
        """
        url = f"{await self.get_api_base_url()}/{endpoint}"
        headers = self.headers
        response = await self._make_api_request(
            url, method="POST", headers=headers, json_data=payload
        )
        try:
            return orjson.loads(response["body"])
        except (orjson.JSONDecodeError, json.JSONDecodeError) as e:
            logger.error(
                "Failed to parse JSON response from API call to %s: %s",
                endpoint,
                str(e),
            )
            # Re-raise as this is a critical error for API calls
            raise
