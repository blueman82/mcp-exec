"""
channel_restore_ops.py

This module contains the SlackChannelRestoreOps class, which is used to temporarily
unarchive channels for Ketchup commands, then re-archive them.
"""

from typing import Any, Dict, List, Optional, Tuple

import orjson

from packages.core.logging import setup_logger
from packages.core.resilience.backoff import with_exponential_backoff
from packages.core.utils import (
    invite_ketchup_to_channel as core_invite_ketchup_to_channel,
)
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_bot_membership_ops import (
    SlackChannelBotMembershipOps,
)
from packages.slack.channel_operations.restore_state_manager import RestoreStateManager
from packages.slack.config.slack_config import SlackConfig
from packages.slack.core.slack_async_client import SlackAsyncClient
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SlackChannelRestoreOps(SlackAsyncClient):
    """
    This class handles temporary unarchiving of Slack channels for command execution.
    It now delegates bot membership checks and invites to SlackChannelBotMembershipOps.
    """

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        archive_ops: SlackChannelArchiveOps,
        secrets_manager: SecretsManager,
        dynamodb_store: DynamoDBStore,
        restore_state_manager: RestoreStateManager,
        bot_membership_ops: SlackChannelBotMembershipOps,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
    ):
        """
        Initialize the Slack channel restore operations.

        Args:
            posting_handler: Handler for posting messages
            archive_ops: Operations for channel archive
            secrets_manager: Manager for secrets
            dynamodb_store: Store for DynamoDB operations
            restore_state_manager: Manager for restoring state
            bot_membership_ops: Operations for bot membership handling
            slack_config: Pre-initialized SlackConfig instance (required).
            max_concurrent_requests: Maximum number of concurrent requests
        """
        # Require a pre-initialized SlackConfig instance
        super().__init__(slack_config, max_concurrent_requests)

        # Store injected dependencies
        self.posting_handler = posting_handler
        self.archive_ops = archive_ops
        self.secrets_manager = secrets_manager
        self.dynamodb_store = dynamodb_store
        self.restore_state_manager = restore_state_manager
        self.bot_membership_ops = bot_membership_ops
        self._slack_token = (
            None  # Initialize token attribute (used by _init_slack_token)
        )
        logger.info(
            "SlackChannelRestoreOps initialized with injected dependencies (including BotMembershipOps)."
        )

    async def _post_direct_channel_message(
        self,
        channel_id: str,
        message: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Post a message directly to a channel using chat.postMessage API.

        This bypasses the ephemeral fallback in SlackPostingHandler.post_message.

        Args:
            channel_id: The Slack channel ID to post in
            message: The message content
            blocks: Optional Block Kit blocks to include in the message

        Returns:
            The response from the Slack API
        """
        await self._init_slack_token()

        logger.info("Posting direct message to channel %s", channel_id)

        url = f"{self.config.get_api_base_url()}/chat.postMessage"
        headers = self.config.get_headers()

        # Prepare basic payload
        payload: Dict[str, Any] = {
            "channel": channel_id,
            "text": message,
        }

        # Add blocks if provided
        if blocks:
            payload["blocks"] = blocks

        response = await self._make_api_request(url, "POST", headers, None, payload)
        # Response is now a SafeResponse dict, parse the body
        response_data = orjson.loads(response["body"])
        logger.info("Direct channel message response: %s", response_data)
        return response_data

    async def _init_slack_token(self):
        """Initialize and cache the Slack API token."""
        if not self._slack_token:
            self._slack_token = await self.secrets_manager.get_slack_api_token_async()
            if not self._slack_token:
                logger.error("Failed to retrieve Slack API token from Secrets Manager.")
                raise ValueError("Slack API token is not configured.")

    async def _get_and_validate_channel_info(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Fetches channel info and validates it, sending error messages if needed."""
        channel_info = await self.archive_ops.get_channel_info(channel_id)
        if not channel_info.get("ok", False):
            error_message = channel_info.get("error", "unknown error")
            logger.error(
                "Failed to get channel info for %s: %s", channel_id, error_message
            )
            # Check for the specific error
            if error_message == "channel_not_found":
                user_friendly_message = f"Error: Could not find channel `{channel_id}`. Please verify the channel ID is correct."
            else:
                user_friendly_message = f"Error accessing channel `{channel_id}`: {error_message}. Please check permissions or try again later."

            # Prioritize response_url for sending feedback if available
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message=user_friendly_message,
                response_url=response_url,
            )
            return None
        return channel_info

    async def _unarchive_and_log(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str],
    ) -> bool:
        """Performs the unarchive operation and handles failures."""
        unarchive_response = await self.archive_ops.unarchive_channel(channel_id)
        if not unarchive_response:
            error_message = "Failed to unarchive channel"
            logger.error(
                "Failed to unarchive channel %s: %s", channel_id, error_message
            )
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message=f"Failed to temporarily unarchive channel `{channel_id}` for command execution: {error_message}",
                response_url=response_url,
            )
            # Use the state manager to clean up state
            await self.restore_state_manager.cleanup_state(channel_id)
            return False
        return True

    async def _ensure_bot_membership_after_unarchive(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        channel_name: str,
        response_url: Optional[str],
    ) -> bool:
        """Checks bot membership and invites/verifies if necessary after unarchiving."""
        bot_user_id = await self.secrets_manager.get_bot_slack_user_id_async()
        if not bot_user_id:
            logger.error("Failed to get bot user ID from secrets manager")
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message="Failed to get bot user ID, cannot join the channel after unarchiving.",
                response_url=response_url,
            )
            # Re-archive the channel since we can't proceed
            await self.archive_ops.archive_channel(
                user_id=None, channel_id=channel_id, incoming_channel=dm_channel_id
            )
            # Use the state manager to clean up state
            await self.restore_state_manager.cleanup_state(channel_id)
            return False

        # Delegate membership check to the new Ops class
        is_member = await self.bot_membership_ops.check_bot_channel_membership(
            channel_id
        )
        if not is_member:
            logger.info(
                "Bot is not a member of the unarchived channel %s, attempting to join",
                channel_id,
            )
            # Use the public wrapper method instead of the private one
            invite_result = await self.invite_ketchup_to_channel(
                channel_id=channel_id,
                bot_user_id=bot_user_id,
                channel_name=channel_name,
            )
            # Check the 'ok' status from the wrapper method's return dict
            if not invite_result.get("ok"):
                logger.error(
                    "Bot could not join the unarchived channel %s despite invite (via public wrapper). Error: %s",
                    channel_id,
                    invite_result.get("error", "Unknown failure"),
                )
                # Note: Error message posting is now handled within the delegate
                # Re-archive the channel since we can't proceed
                await self.archive_ops.archive_channel(
                    user_id=None, channel_id=channel_id, incoming_channel=dm_channel_id
                )
                # Use the state manager to clean up state
                await self.restore_state_manager.cleanup_state(channel_id)
                return False

            # Verify bot is actually in the channel after invite
            # (Slack invite API is async, poll with backoff until bot joins)
            import asyncio
            max_attempts = 5
            wait_times = [0.2, 0.5, 1.0, 2.0, 3.0]  # Total: ~6.7 seconds max

            is_member_after_invite = False
            for attempt in range(max_attempts):
                is_member_after_invite = await self.bot_membership_ops.check_bot_channel_membership(
                    channel_id
                )
                if is_member_after_invite:
                    logger.info(
                        "Verified bot membership in channel %s after invite (attempt %d/%d)",
                        channel_id, attempt + 1, max_attempts
                    )
                    break

                if attempt < max_attempts - 1:  # Don't wait after last attempt
                    wait_time = wait_times[attempt]
                    logger.warning(
                        "Bot not yet in channel %s after invite (attempt %d/%d) - waiting %.1fs",
                        channel_id, attempt + 1, max_attempts, wait_time
                    )
                    await asyncio.sleep(wait_time)

            if not is_member_after_invite:
                logger.error(
                    "Bot still not in channel %s after %d attempts over ~7 seconds",
                    channel_id, max_attempts
                )
                await self.archive_ops.archive_channel(
                    user_id=None, channel_id=channel_id, incoming_channel=dm_channel_id
                )
                await self.restore_state_manager.cleanup_state(channel_id)
                return False
        return True

    @with_exponential_backoff()
    async def restore_archived_channel(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str] = None,
    ) -> Tuple[bool, bool]:
        """
        Restore an archived channel if needed for running a command. (Refactored)
        """
        # 1. Get and validate channel info
        channel_info_response = await self._get_and_validate_channel_info(
            user_id, channel_id, dm_channel_id, response_url
        )
        if not channel_info_response:
            return False, False  # Failure, not originally archived (or unknown)

        channel_data = channel_info_response.get("channel", {})
        channel_name = channel_data.get("name", "unknown")
        is_archived = channel_data.get("is_archived", False)

        # 2. Check if already unarchived
        if not is_archived:
            return True, False  # Success, not originally archived

        # 3. Store original state and attempt unarchive
        logger.info(
            "Found archived channel %s (%s), attempting to unarchive temporarily",
            channel_id,
            channel_name,
        )
        # Use the state manager to store state
        await self.restore_state_manager.store_state(channel_id)

        unarchive_success = await self._unarchive_and_log(
            user_id, channel_id, dm_channel_id, response_url
        )
        if not unarchive_success:
            # If unarchive fails, clean up the state we just stored
            await self.restore_state_manager.cleanup_state(channel_id)
            return False, True  # Failure, but was originally archived

        # 4. Ensure bot membership (THIS CALL NOW USES THE DELEGATED LOGIC)
        membership_success = await self._ensure_bot_membership_after_unarchive(
            user_id, channel_id, dm_channel_id, channel_name, response_url
        )
        if not membership_success:
            # Error messages and re-archive handled within helper
            # Clean up state since we failed after unarchiving
            await self.restore_state_manager.cleanup_state(channel_id)
            return False, True  # Failure, but was originally archived

        # 5. Notify user of success
        logger.info(
            "Successfully unarchived channel %s and ensured bot membership", channel_id
        )
        await self.posting_handler.post_message(
            user_id=user_id,
            channel_id=dm_channel_id,
            message=f"Temporarily unarchived channel <#{channel_id}> for command execution.",
            response_url=response_url,
        )
        return True, True  # Success, was originally archived

    async def _notify_user_of_rearchive(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        channel_name: str,
        response_url: Optional[str],
    ) -> None:
        """Notifies the user via DM that the channel is being re-archived."""
        channel_ref = f"<#{channel_id}>" if channel_name else channel_id
        await self.posting_handler.post_message(
            user_id=user_id,
            channel_id=dm_channel_id,
            message=f"Archiving {channel_ref}",
            response_url=response_url,
        )

    async def _notify_channel_of_rearchive(self, channel_id: str) -> None:
        """Posts a message directly to the channel being re-archived."""
        try:
            await self._post_direct_channel_message(
                channel_id=channel_id,
                message="This channel is being re-archived after command execution. It was temporarily unarchived to run a Ketchup command.",
            )
        except Exception as msg_e:
            logger.warning(
                "Could not post final message to channel %s before archiving: %s",
                channel_id,
                str(msg_e),
            )

    async def _perform_rearchive_and_update_db(
        self, channel_id: str, dm_channel_id: str
    ) -> bool:
        """Performs the channel archive and updates the DB status."""
        # Retrieve original archived_at timestamp before archiving
        original_archived_at = None
        try:
            channel_item = await self.dynamodb_store.get_channel_details(channel_id)
            original_archived_at = (
                channel_item.get("archived_at") if channel_item else None
            )
        except Exception as db_e:
            logger.warning(
                "Could not retrieve original archived_at value before re-archiving %s: %s",
                channel_id,
                str(db_e),
            )

        # Archive the channel
        archive_success = await self.archive_ops.archive_channel(
            user_id=None, channel_id=channel_id, incoming_channel=dm_channel_id
        )

        if not archive_success:
            logger.error("Failed to re-archive channel %s via API", channel_id)
            return False

        # Restore the original archived_at value if it was available
        if original_archived_at:
            try:
                await self.dynamodb_store.update_channel_archived_status(
                    channel_id=channel_id,
                    archived=True,
                    archived_at=original_archived_at,
                )
                logger.info(
                    "Restored original archived_at value for %s: %s",
                    channel_id,
                    original_archived_at,
                )
            except Exception:
                logger.error(
                    "Failed to restore original archived_at value for %s: %s",
                    channel_id,
                    original_archived_at,
                    exc_info=True,
                )
        else:
            # Even if we couldn't retrieve the original, update status to archived
            try:
                await self.dynamodb_store.update_channel_archived_status(
                    channel_id=channel_id, archived=True
                )
                logger.info(
                    "Updated DB status to archived for %s (no original timestamp restored).",
                    channel_id,
                )
            except Exception:
                logger.error(
                    "Failed to update DB status to archived for %s",
                    channel_id,
                    exc_info=True,
                )

        return True

    async def _notify_user_rearchive_complete(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        channel_name: str,
        response_url: Optional[str],
    ) -> None:
        """Notifies the user via DM that the channel re-archive is complete."""
        channel_ref = f"<#{channel_id}>" if channel_name else channel_id
        await self.posting_handler.post_message(
            user_id=user_id,
            channel_id=dm_channel_id,
            message=f"Channel {channel_ref} is archived :file_folder:",
            response_url=response_url,
        )

    @with_exponential_backoff()
    async def rearchive_channel_if_needed(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: str,
        response_url: Optional[str] = None,
        notify_channel: bool = False,
    ) -> bool:
        """
        Re-archive a channel if it was originally archived. (Refactored)
        """
        logger.info("Starting rearchive_channel_if_needed for channel %s", channel_id)

        # 1. Check if re-archive is necessary using the state manager
        if not await self.restore_state_manager.is_rearchive_needed(channel_id):
            logger.info(
                "Restore state not set for channel %s, no re-archive needed.",
                channel_id,
            )
            return True

        # If state IS set, proceed with re-archiving logic
        logger.info(
            "Restore state is set for channel %s, proceeding with re-archive.",
            channel_id,
        )

        try:
            # 2. Get channel name for messages
            channel_name_opt = await self._get_channel_name(channel_id)
            channel_name_str = (
                channel_name_opt if channel_name_opt is not None else channel_id
            )

            # 3. Notify user we are starting
            await self._notify_user_of_rearchive(
                user_id, channel_id, dm_channel_id, channel_name_str, response_url
            )

            # 4. Notify channel if requested
            if notify_channel:
                await self._notify_channel_of_rearchive(channel_id)

            # 5. Perform re-archive and DB update
            archive_success = await self._perform_rearchive_and_update_db(
                channel_id, dm_channel_id
            )

            if not archive_success:
                # Notify user of failure
                channel_ref = f"<#{channel_id}>" if channel_name_opt else channel_id
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=dm_channel_id,
                    message=f"Failed to re-archive channel {channel_ref}.",
                    response_url=response_url,
                )
                # Clean up state even on failure to avoid repeated attempts
                await self.restore_state_manager.cleanup_state(channel_id)
                return False

            # 6. Notify user of completion
            await self._notify_user_rearchive_complete(
                user_id, channel_id, dm_channel_id, channel_name_str, response_url
            )

            # 7. Clean up tracking state using the state manager
            await self.restore_state_manager.cleanup_state(channel_id)

            return True

        except Exception as e:
            logger.error(
                "Error in rearchive_channel_if_needed for %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            # Notify user of error
            try:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=dm_channel_id,
                    message=f"Unexpected error during re-archiving channel <#{channel_id}>: {str(e)}",
                    response_url=response_url,
                )
            except Exception as post_err:
                logger.error(
                    "Failed to notify user about rearchive exception: %s", post_err
                )
            # Clean up state even on error using the state manager
            await self.restore_state_manager.cleanup_state(channel_id)
            return False

    async def _get_channel_name(self, channel_id: str) -> Optional[str]:
        """
        Get the name of a channel given its ID.

        Args:
            channel_id: The ID of the channel to get the name for

        Returns:
            str: The name of the channel, or None if it couldn't be retrieved
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
                return response_data["channel"].get("name")
            else:
                logger.warning(
                    "Error getting channel name for %s: %s",
                    channel_id,
                    response_data.get("error"),
                )
                return None
        except Exception as e:
            logger.warning("Exception getting channel name: %s", str(e))
            return None

    async def cleanup(self) -> None:
        """
        Clean up resources used by the SlackChannelRestoreOps instance,
        primarily the inherited SlackAsyncClient session.
        """
        logger.info(
            "Cleaning up SlackChannelRestoreOps (calling parent SlackAsyncClient cleanup)"
        )
        # Call the base class cleanup to close the session
        await super().cleanup()
        # No need to call cleanup on restore_state_manager, as TTL handles its items
        # and the manager itself doesn't own resources requiring explicit cleanup here.
        logger.info("SlackChannelRestoreOps cleanup completed.")

    async def invite_ketchup_to_channel(
        self,
        channel_id: str,
        bot_user_id: str,
        channel_name: str,
    ) -> Dict[str, Any]:
        """
        Calls the main invite function to add Ketchup (the bot) to a Slack channel after restoring it. Used when a channel is unarchived and we need to make sure the bot is present.
        """
        try:
            # Ensure session is initialized
            await self.setup()

            # Use the core utils version with injected dependencies
            return await core_invite_ketchup_to_channel(
                channel_id=channel_id,
                user_id=bot_user_id,
                channel_name=channel_name,
                secrets_manager=self.secrets_manager,
                http_session=self._session,
            )
        except Exception as e:
            logger.error("Exception inviting bot to channel %s: %s", channel_id, str(e))
            return {"ok": False, "error": str(e)}
