"""Admin Response Handler for Flag Review System.

Handles DM sending, modal display, and related database operations for admin responses.
"""

from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class AdminResponseHandler:
    """Handles admin response operations including DMs, modals, and status updates."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        db_store: DynamoDBStore,
        secrets_manager: SecretsManager,
    ):
        """Initialize admin response handler."""
        self.posting_handler = posting_handler
        self.db_store = db_store
        self.secrets_manager = secrets_manager

    async def send_acknowledgment_dm(
        self,
        flagged_user_id: str,
        admin_name: str,
        channel_id: str,
        message_ts: str,
    ) -> bool:
        """Send acknowledgment DM to flagged user for status updates.

        Args:
            flagged_user_id: ID of user who flagged the status update.
            admin_name: Name of admin acknowledging the feedback.
            channel_id: Channel where the original status update was posted.
            message_ts: Timestamp of the original status update message.

        Returns:
            True if DM sent successfully, False otherwise.
        """
        from packages.slack.interactive_elements.flag_review.dm_handler import (
            FlagReviewDMHandler,
        )

        return await FlagReviewDMHandler(self.posting_handler).send_dm_to_requester(
            user_id=flagged_user_id,
            dm_type="acknowledgment",
            admin_name=admin_name,
            channel_id=channel_id,
            message_ts=message_ts,
        )

    async def send_reply_dm(
        self,
        flagged_user_id: str,
        admin_name: str,
        reply_text: str,
        channel_id: str,
        message_ts: str,
    ) -> bool:
        """Send reply DM to flagged user."""
        from packages.slack.interactive_elements.flag_review.dm_handler import (
            FlagReviewDMHandler,
        )

        # Check if original message still exists
        message_exists = await self.check_message_exists(channel_id, message_ts)

        return await FlagReviewDMHandler(self.posting_handler).send_dm_to_requester(
            user_id=flagged_user_id,
            dm_type="reply",
            admin_name=admin_name,
            channel_id=channel_id,
            message_ts=message_ts,
            reply_text=reply_text,
            message_exists=message_exists,
        )

    async def send_command_acknowledgment_dm(
        self,
        flagged_user_id: str,
        admin_name: str,
        channel_id: str,
        command_execution_id: str,
    ) -> bool:
        """Send command acknowledgment DM to flagged user."""
        from packages.slack.interactive_elements.flag_review.dm_handler import (
            FlagReviewDMHandler,
        )

        return await FlagReviewDMHandler(self.posting_handler).send_dm_to_requester(
            user_id=flagged_user_id,
            dm_type="acknowledgment",
            admin_name=admin_name,
            channel_id=channel_id,
            command_execution_id=command_execution_id,
        )

    async def send_command_reply_dm(
        self,
        flagged_user_id: str,
        admin_name: str,
        reply_text: str,
        channel_id: str,
        command_execution_id: str,
    ) -> bool:
        """Send command reply DM to flagged user."""
        from packages.slack.interactive_elements.flag_review.dm_handler import (
            FlagReviewDMHandler,
        )

        return await FlagReviewDMHandler(self.posting_handler).send_dm_to_requester(
            user_id=flagged_user_id,
            dm_type="reply",
            admin_name=admin_name,
            channel_id=channel_id,
            command_execution_id=command_execution_id,
            reply_text=reply_text,
        )

    async def show_reply_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        message_ts: str,
        flagged_user_id: str,
    ) -> None:
        """Show reply modal for admin to respond to flagged message."""
        from packages.slack.interactive_elements.flag_review.modals import (
            FlagReviewModalManager,
        )

        await FlagReviewModalManager(self.secrets_manager).show_reply_modal(
            payload, channel_id, message_ts, flagged_user_id
        )

    async def show_command_reply_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        command_execution_id: str,
        flagged_user_id: str,
    ) -> None:
        """Show command reply modal for admin to respond to flagged command."""
        from packages.slack.interactive_elements.flag_review.modals import (
            FlagReviewModalManager,
        )

        await FlagReviewModalManager(self.secrets_manager).show_command_reply_modal(
            payload, channel_id, command_execution_id, flagged_user_id
        )

    async def check_message_exists(self, channel_id: str, message_ts: str) -> bool:
        """Check if a message still exists in the channel."""
        try:
            result = await self.posting_handler.api_call(
                "conversations.history",
                {
                    "channel": channel_id,
                    "latest": message_ts,
                    "limit": 1,
                    "inclusive": True,
                },
            )
            messages = result.get("messages", [])
            return bool(messages and messages[0].get("ts") == message_ts)
        except Exception as e:
            logger.error(f"Error checking message existence: {e}")
            return False

    async def update_feedback_status(
        self,
        channel_id: str,
        message_ts: str,
        status: str,
        acknowledged_by: str,
        acknowledged_at: str,
    ) -> None:
        """Update feedback status in database."""
        from packages.slack.interactive_elements.flag_review.database import (
            FlagReviewDatabaseOperations,
        )

        await FlagReviewDatabaseOperations(self.db_store).update_feedback_status(
            channel_id, message_ts, status, acknowledged_by, acknowledged_at
        )

    async def update_command_feedback_status(
        self,
        channel_id: str,
        command_execution_id: str,
        original_user_id: str,
        status: str,
        acknowledged_by: str,
        acknowledged_at: str,
    ) -> None:
        """Update command feedback status in database."""
        from packages.slack.interactive_elements.flag_review.database import (
            FlagReviewDatabaseOperations,
        )

        await FlagReviewDatabaseOperations(self.db_store).update_command_feedback_status(
            channel_id,
            command_execution_id,
            original_user_id,
            status,
            acknowledged_by,
            acknowledged_at,
        )

    async def update_acknowledged_message(
        self,
        channel_id: str,
        message_ts: str,
        admin_id: str,
        user_id: str = None,
    ) -> None:
        """Update acknowledged message in channel."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        # If user_id not provided, try to look it up (backward compatibility)
        if not user_id:

            # Construct flag_id and lookup (fallback - scan by channel/message)
            # This is less efficient but maintains backward compatibility
            result = await self.db_store.client.scan(
                table_name=self.db_store.table_name,
                filter_expression="channel_id = :channel_id AND message_ts = :message_ts",
                expression_attribute_values={
                    ":channel_id": {"S": channel_id},
                    ":message_ts": {"S": message_ts},
                },
                limit=1,
            )
            items = result.get("Items", [])
            user_id = items[0].get("user_id", {}).get("S", "") if items else ""

        await MessageUpdater(self.posting_handler).update_acknowledged_message(
            channel_id, message_ts, admin_id, user_id
        )

    async def update_review_message(
        self,
        payload: Dict[str, Any],
        admin_id: str,
    ) -> None:
        """Update review message with admin action."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        await MessageUpdater(self.posting_handler).update_review_message(payload, admin_id)

    async def update_review_message_orphaned(
        self,
        payload: Dict[str, Any],
        admin_id: str,
        channel_id: str,
    ) -> None:
        """Update review message for orphaned content."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        await MessageUpdater(self.posting_handler).update_review_message_orphaned(
            payload, admin_id, channel_id
        )

    async def update_review_message_with_reply(
        self,
        payload: Dict[str, Any],
        admin_id: str,
    ) -> None:
        """Update review message to show reply was sent."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        await MessageUpdater(self.posting_handler).update_review_message_with_reply(
            payload, admin_id
        )

    async def update_command_review_message_with_reply(
        self,
        payload: Dict[str, Any],
        admin_id: str,
    ) -> None:
        """Update command review message to show reply was sent."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        # Use the same method as regular reply - it should handle both
        await MessageUpdater(self.posting_handler).update_review_message_with_reply(
            payload, admin_id
        )

    async def update_completed_status(
        self,
        channel_id: str,
        message_ts: str,
        completed_by: str,
        completed_at: str,
    ) -> None:
        """Update feedback status to completed in database."""
        from packages.slack.interactive_elements.flag_review.database import (
            FlagReviewDatabaseOperations,
        )

        await FlagReviewDatabaseOperations(self.db_store).update_feedback_status(
            channel_id=channel_id,
            message_ts=message_ts,
            status="completed",
            acknowledged_by=completed_by,
            acknowledged_at=completed_at,
        )

    async def update_review_message_completed(
        self,
        payload: Dict[str, Any],
        admin_id: str,
    ) -> None:
        """Update review message to show completion with visual styling."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        await MessageUpdater(self.posting_handler).update_review_message_completed(
            payload, admin_id
        )
