"""
channel_bot_membership_ops.py

Handles checking and managing the Slack bot's membership in channels.
"""

from typing import Any, Dict, Optional

import orjson

from packages.core.async_client import AsyncClient
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import with_exponential_backoff
from packages.core.utils import invite_ketchup_to_channel as core_invite_ketchup_to_channel
from packages.secrets.manager import SecretsManager
from packages.slack.config.slack_config import SlackConfig
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SlackChannelBotMembershipOps(AsyncClient):
    """
    Operations related to the bot's membership in Slack channels,
    such as checking membership and inviting the bot.
    """

    def __init__(
        self,
        secrets_manager: SecretsManager,
        posting_handler: SlackPostingHandler,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
    ):
        """
        Initialize the bot membership operations.

        Args:
            secrets_manager: Manager for secrets (needed for bot user ID).
            posting_handler: Handler for posting status messages.
            slack_config: Pre-initialized SlackConfig instance (required).
            max_concurrent_requests: Max concurrent requests.
        """
        super().__init__(slack_config, max_concurrent_requests)

        self.secrets_manager = secrets_manager  # Keep stored instance
        self.posting_handler = posting_handler
        self._slack_token: Optional[str] = None  # Define instance var used by _init_slack_token
        logger.info("SlackChannelBotMembershipOps initialized.")

    async def _init_slack_token(self):
        """Initialize and cache the Slack API token."""
        if not self._slack_token:
            self._slack_token = await self.secrets_manager.get_slack_api_token_async()
            if not self._slack_token:
                logger.error("Failed to retrieve Slack API token from Secrets Manager.")
                raise ValueError("Slack API token is not configured.")

    # Methods related to bot membership will be moved here in the next step

    @with_exponential_backoff()
    async def invite_ketchup_to_channel(
        self, channel_id: str, bot_user_id: str, channel_name: str = ""
    ) -> Dict[str, Any]:
        """
        Calls the main invite function to add Ketchup (the bot) to a Slack channel. This method is used inside this class and adds retry logic if something goes wrong.

        Args:
            channel_id: The ID of the channel to invite the bot to
            bot_user_id: The user ID of the bot
            channel_name: The name of the channel (for logging purposes)

        Returns:
            dict: The response from the API call
        """
        logger.info(
            "Inviting bot %s to channel %s (%s)",
            bot_user_id,
            channel_name or "unknown",
            channel_id,
        )

        try:
            # Initialize the Slack token if needed
            await self._init_slack_token()

            # Ensure session is initialized
            await self.setup()

            # Use the core utils version with injected dependencies
            return await core_invite_ketchup_to_channel(
                channel_id=channel_id,
                user_id=bot_user_id,
                channel_name=channel_name or "unknown",
                secrets_manager=self.secrets_manager,
                http_session=self._session,
            )
        except Exception as e:
            logger.error("Exception inviting bot to channel %s: %s", channel_id, str(e))
            return {"ok": False, "error": str(e)}

    @with_exponential_backoff()
    async def check_bot_channel_membership(self, channel_id: str) -> bool:
        """
        Check if the bot is a member of the specified channel.

        Args:
            channel_id: The ID of the channel to check

        Returns:
            bool: True if the bot is a member, False otherwise
        """
        try:
            # Initialize the Slack token if needed
            await self._init_slack_token()

            # Prepare the API request
            url = f"{self.config.get_api_base_url()}/conversations.info"
            headers = self.config.get_headers()
            params = {"channel": channel_id}

            # Make the API request
            response = await self._make_api_request(url, "GET", headers, params=params)
            response_data = orjson.loads(response["body"])

            # Check the result
            if not response_data.get("ok", False):
                logger.error(
                    "Failed to get channel info for %s: %s",
                    channel_id,
                    response_data.get("error", "unknown error"),
                )
                return False

            channel_info = response_data.get("channel", {})
            is_member = channel_info.get("is_member", False)
            return is_member

        except Exception as e:
            logger.error("Error checking bot channel membership: %s", str(e))
            return False
