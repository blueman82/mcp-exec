"""
channel_archive_ops.py

This module contains the SlackChannelArchiveOps class, which is used to archive and unarchive Slack channels.
"""

from typing import Any, Dict, Optional

import orjson

from packages.core.logging import setup_logger
from packages.core.resilience.backoff import with_exponential_backoff
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.channel_operations.restore_state_manager import RestoreStateManager
from packages.slack.config.slack_config import SlackConfig
from packages.slack.core.slack_async_client import SlackAsyncClient
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SlackChannelArchiveOps(SlackAsyncClient):
    """
    This class handles Slack channel archive and unarchive operations.
    Relies on injected dependencies.
    """

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        secrets_manager: "SecretsManager",
        dynamodb_store: DynamoDBStore,
        state_manager: RestoreStateManager,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
    ):
        """
        Initialize the Slack channel archive operations.

        Args:
            posting_handler: Handler for posting messages.
            secrets_manager: Manager for secrets (needed for user token fetching).
            dynamodb_store: Facade for DynamoDB operations.
            state_manager: Manager for temporary restore state.
            slack_config: Pre-initialized SlackConfig instance (required).
            max_concurrent_requests: Maximum number of concurrent requests.
        """
        super().__init__(slack_config, max_concurrent_requests)
        self.posting_handler = posting_handler
        self._secrets_manager = secrets_manager
        self._db_store = dynamodb_store
        self._state_manager = state_manager
        self._restore_ops = self._db_store.restore_ops
        self._slack_user_token = None
        logger.info("SlackChannelArchiveOps initialized with injected dependencies.")

    async def _init_user_slack_token(self):
        """Initialize and cache the Slack user API token."""
        if not hasattr(self, "_slack_user_token") or not self._slack_user_token:
            self._slack_user_token = await self._secrets_manager.get_slack_user_api_token()

    async def get_user_api_headers(self) -> Dict[str, str]:
        """
        Get headers for Slack API requests using the user API token.

        This is required for certain privileged operations like unarchiving channels.

        Returns:
            Dict with Authorization and Content-Type headers using user token
        """
        await self._init_user_slack_token()
        return {
            "Authorization": f"Bearer {self._slack_user_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    @with_exponential_backoff()
    async def check_channel_archived(self, channel_id: str) -> bool:
        """
        Check if a Slack channel is already archived.

        Args:
            channel_id: The channel ID to check

        Returns:
            True if channel is archived, False if not or if an error occurred
        """
        try:
            url = f"{self.config.get_api_base_url()}/conversations.info"
            headers = self.config.get_headers()
            payload = {
                "channel": channel_id,
            }

            response = await self._make_api_request(url, "GET", headers, payload)
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                is_archived = response_data["channel"].get("is_archived", False)
                return is_archived
            else:
                error = response_data.get("error")
                logger.warning("Error checking if channel %s is archived: %s", channel_id, error)
                return False
        except Exception as e:
            logger.warning("Exception checking if channel %s is archived: %s", channel_id, e)
            return False

    @with_exponential_backoff()
    async def archive_channel(
        self,
        user_id: Optional[str],
        channel_id: str,
        incoming_channel: str,
        response_url: Optional[str] = None,
        skip_status_check: bool = False,
    ) -> bool:
        """
        Archive a Slack channel.

        If the RestoreStateManager indicates this channel was temporarily unarchived
        by the bot, it will clear the restore state marker after successful archival.

        Args:
            user_id: The user ID requesting the archive (can be None for system operations)
            channel_id: The channel ID to archive
            incoming_channel: The channel where the request originated
            response_url: The response URL for the posted message
            skip_status_check: If True, skip checking if channel is already archived (use when caller has already verified)

        Returns:
            True if successful, False otherwise
        """
        start_message = f"Starting archive_channel for channel {channel_id}"
        logger.info(start_message)

        # Check if this channel needs re-archiving according to the state manager
        # This check happens *before* potentially skipping due to already being archived
        needs_rearchive_by_bot = await self._state_manager.is_rearchive_needed(channel_id)
        if needs_rearchive_by_bot:
            logger.info(
                "RestoreStateManager indicates channel %s was temporarily unarchived by bot.",
                channel_id,
            )
        else:
            logger.info(
                "RestoreStateManager indicates channel %s was NOT temporarily unarchived by bot.",
                channel_id,
            )

        # Check if channel is already archived in Slack (unless explicitly told to skip)
        if not skip_status_check:
            is_archived = await self.check_channel_archived(channel_id)
            if is_archived:
                logger.info(
                    "Channel %s is already archived in Slack, skipping archive operation.",
                    channel_id,
                )
                # Even if already archived, if the bot *thought* it needed re-archiving,
                # clear the state marker now as the channel is correctly archived.
                if needs_rearchive_by_bot:
                    logger.info(
                        "Clearing restore state for already-archived channel %s as bot intended to archive.",
                        channel_id,
                    )
                    await self._restore_ops.clear_restore_state(channel_id)
                return True

        try:
            url = f"{self.config.get_api_base_url()}/conversations.archive"
            # Use the user API token for archiving which requires elevated permissions
            headers = await self.get_user_api_headers()
            payload = {
                "channel": channel_id,
            }

            response = await self._make_api_request(url, "POST", headers, None, payload)
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                success_message = f"Successfully archived channel {channel_id}"
                logger.info(success_message)
                # Only post a message if user_id is provided (user-initiated action)
                if user_id:
                    await self.posting_handler.post_message(
                        user_id=user_id,
                        channel_id=incoming_channel,
                        message=f"Channel <#{channel_id}> has been archived. :file_folder:",
                        response_url=response_url,
                    )
                # ---- Clear restore state if needed ----
                if needs_rearchive_by_bot:
                    logger.info(
                        "Clearing restore state for successfully archived channel %s.",
                        channel_id,
                    )
                    await self._restore_ops.clear_restore_state(channel_id)
                # --------------------------------------
                return True
            else:
                error = response_data.get("error")
                error_message = f"Failed to archive channel {channel_id}. Error: {error}"
                logger.error(error_message)
                # Only post a message if user_id is provided (user-initiated action)
                if user_id:
                    await self.posting_handler.post_message(
                        user_id=user_id,
                        channel_id=incoming_channel,
                        message=f"Failed to archive channel <#{channel_id}>: {error}",
                        response_url=response_url,
                    )
                return False
        except Exception as e:
            error_message = f"Error archiving channel: {e}"
            logger.error(error_message)
            # Only post a message if user_id is provided (user-initiated action)
            if user_id:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=f"Error archiving channel <#{channel_id}>: {str(e)}",
                    response_url=response_url,
                )
            return False

    @with_exponential_backoff()
    async def unarchive_channel(self, channel_id: str) -> bool:
        """
        Unarchive a Slack channel.

        If successful, this method (when called by the bot for temporary reasons)
        will mark the channel in the RestoreState database for later re-archival.

        Args:
            channel_id: The channel ID to unarchive

        Returns:
            True if successful, False otherwise
        """
        start_message = f"Starting unarchive_channel for channel {channel_id}"
        logger.info(start_message)

        try:
            url = f"{self.config.get_api_base_url()}/conversations.unarchive"
            # Use the user API token for unarchiving which requires elevated permissions
            headers = await self.get_user_api_headers()
            payload = {
                "channel": channel_id,
            }

            response = await self._make_api_request(url, "POST", headers, None, payload)
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                success_message = f"Successfully unarchived channel {channel_id}"
                logger.info(success_message)
                # ---- Set restore state marker ----
                logger.info("Setting restore state marker for channel %s.", channel_id)
                await self._restore_ops.set_restore_state(channel_id)
                # ----------------------------------
                return True
            else:
                error = response_data.get("error")
                error_message = f"Failed to unarchive channel {channel_id}. Error: {error}"
                logger.error(error_message)
                return False
        except Exception as e:
            error_message = f"Error unarchiving channel: {e}"
            logger.error(error_message)
            return False

    @with_exponential_backoff()
    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """
        Get information about a Slack channel.

        Args:
            channel_id: The ID of the channel to get information for

        Returns:
            Dict containing the API response with channel information
        """
        try:
            logger.info("Getting channel info for %s", channel_id)

            url = f"{self.config.get_api_base_url()}/conversations.info"
            headers = self.config.get_headers()
            params = {
                "channel": channel_id,
            }

            response = await self._make_api_request(url, "GET", headers, params=params)
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                logger.info("Successfully got info for channel %s", channel_id)
            else:
                error = response_data.get("error", "Unknown error")
                logger.warning("Error getting channel info for %s: %s", channel_id, error)

            return response_data
        except Exception as e:
            logger.error("Exception getting channel info: %s", str(e))
            return {"ok": False, "error": str(e)}
