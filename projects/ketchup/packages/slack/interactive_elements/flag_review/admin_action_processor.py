"""Admin Action Processor for Flag Review System.

Handles administrative actions including acknowledgments, replies, and workflow management.
"""

from datetime import datetime, timezone
from typing import Any, Dict


from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.interactive_elements.flag_review.admin_response_handler import AdminResponseHandler

logger = setup_logger(__name__)


class AdminActionProcessor:
    """Handles admin actions and workflows for flag review operations."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        db_store: DynamoDBStore,
        secrets_manager: SecretsManager,
    ):
        """Initialize admin action processor."""
        self.posting_handler = posting_handler
        self.db_store = db_store
        self.secrets_manager = secrets_manager
        self.response_handler = AdminResponseHandler(
            posting_handler, db_store, secrets_manager
        )

    async def handle_acknowledgment(self, payload: Dict[str, Any]) -> bool:
        """Handle admin acknowledgment of feedback.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            admin_id = payload.get("user", {}).get("id")
            admin_name = payload.get("user", {}).get("username", "Unknown")
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")

            # Extract channel_id, message_ts, and optionally user_id from button value
            parts = value.split("|")
            if len(parts) < 2:
                logger.error(f"Invalid acknowledgment value: {value}")
                return False

            channel_id = parts[0]
            message_ts = parts[1]
            flagged_user_id = parts[2] if len(parts) >= 3 else None

            # Check if original message still exists
            message_exists = await self.response_handler.check_message_exists(channel_id, message_ts)

            # Update database
            await self.response_handler.update_feedback_status(
                channel_id=channel_id,
                message_ts=message_ts,
                status="acknowledged",
                acknowledged_by=admin_id,
                acknowledged_at=datetime.now(timezone.utc).isoformat(),
            )

            if message_exists:
                # Update original message in source channel
                await self.response_handler.update_acknowledged_message(
                    channel_id=channel_id,
                    message_ts=message_ts,
                    admin_id=admin_id,
                    user_id=flagged_user_id,
                )

                # Update review message
                await self.response_handler.update_review_message(payload, admin_id)

                # Send ephemeral feedback to admin
                await self.posting_handler.post_message(
                    channel_id=payload.get("channel", {}).get("id"),
                    user_id=admin_id,
                    message="✅ Feedback acknowledged successfully!",
                )
            else:
                # Message no longer exists - send DM to user who flagged it
                await self.response_handler.update_review_message_orphaned(
                    payload, admin_id, channel_id
                )

                # Send acknowledgment DM to the user who flagged the status update
                if flagged_user_id:
                    await self.response_handler.send_acknowledgment_dm(
                        flagged_user_id=flagged_user_id,
                        admin_name=admin_name,
                        channel_id=channel_id,
                        message_ts=message_ts,
                    )
                    logger.info(
                        f"Sent acknowledgment DM to {flagged_user_id} for orphaned message {message_ts}"
                    )

            return True

        except Exception as e:
            logger.error(f"Error handling acknowledgment: {e}")
            return False

    async def handle_reply_button_click(self, payload: Dict[str, Any]) -> bool:
        """Handle admin clicking reply button.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")

            # Extract channel_id, message_ts, and user_id from button value
            parts = value.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid reply button value: {value}")
                return False

            channel_id = parts[0]
            message_ts = parts[1]
            flagged_user_id = parts[2]

            # Show reply modal
            await self.response_handler.show_reply_modal(
                payload=payload,
                channel_id=channel_id,
                message_ts=message_ts,
                flagged_user_id=flagged_user_id,
            )

            return True

        except Exception as e:
            logger.error(f"Error handling reply button click: {e}")
            return False

    async def handle_reply_submission(self, payload: Dict[str, Any]) -> bool:
        """Handle the reply modal submission.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            admin_id = payload.get("user", {}).get("id")
            admin_name = payload.get("user", {}).get("username", "Unknown")

            # Extract form data
            values = payload.get("view", {}).get("state", {}).get("values", {})
            reply_text = (
                values.get("reply_block", {}).get("reply_input", {}).get("value", "")
            )

            # Extract metadata from private_metadata
            private_metadata = payload.get("view", {}).get("private_metadata", "")
            parts = private_metadata.split("|")
            if len(parts) < 3:
                logger.error(
                    f"Invalid reply private_metadata format: {private_metadata}"
                )
                return False

            channel_id = parts[0]
            message_ts = parts[1]
            flagged_user_id = parts[2]

            # Send reply as DM to the user who flagged
            success = await self.response_handler.send_reply_dm(
                flagged_user_id=flagged_user_id,
                admin_name=admin_name,
                reply_text=reply_text,
                channel_id=channel_id,
                message_ts=message_ts,
            )

            if success:
                # Update the review message to show reply was sent
                await self.response_handler.update_review_message_with_reply(payload, admin_id)

                # Update database
                await self.response_handler.update_feedback_status(
                    channel_id=channel_id,
                    message_ts=message_ts,
                    status="replied",
                    acknowledged_by=admin_id,
                    acknowledged_at=datetime.now(timezone.utc).isoformat(),
                )

            return True

        except Exception as e:
            logger.error(f"Error handling reply submission: {e}")
            return False

    async def handle_command_reply_submission(self, payload: Dict[str, Any]) -> bool:
        """Handle the command reply modal submission.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            admin_id = payload.get("user", {}).get("id")
            admin_name = payload.get("user", {}).get("username", "Unknown")

            # Extract form data
            values = payload.get("view", {}).get("state", {}).get("values", {})
            reply_text = (
                values.get("reply_block", {}).get("reply_input", {}).get("value", "")
            )

            # Extract metadata from private_metadata
            private_metadata = payload.get("view", {}).get("private_metadata", "")
            parts = private_metadata.split("|")
            if len(parts) < 3:
                logger.error(
                    f"Invalid command reply private_metadata format: {private_metadata}"
                )
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            flagged_user_id = parts[2]

            # Send reply as DM to the user who flagged
            success = await self.response_handler.send_command_reply_dm(
                flagged_user_id=flagged_user_id,
                admin_name=admin_name,
                reply_text=reply_text,
                channel_id=channel_id,
                command_execution_id=command_execution_id,
            )

            if success:
                # Update the review message to show reply was sent
                await self.response_handler.update_command_review_message_with_reply(payload, admin_id)

                # Update database
                await self.response_handler.update_command_feedback_status(
                    channel_id=channel_id,
                    command_execution_id=command_execution_id,
                    original_user_id=flagged_user_id,
                    status="replied",
                    acknowledged_by=admin_id,
                    acknowledged_at=datetime.now(timezone.utc).isoformat(),
                )

            return True

        except Exception as e:
            logger.error(f"Error handling command reply submission: {e}")
            return False

    async def handle_command_acknowledgment(self, payload: Dict[str, Any]) -> bool:
        """Handle admin acknowledgment of command feedback.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            admin_id = payload.get("user", {}).get("id")
            admin_name = payload.get("user", {}).get("username", "Unknown")
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")

            # Extract channel_id, command_execution_id, and original user_id from button value
            parts = value.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid command acknowledgment value: {value}")
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            original_user_id = parts[2]

            # Update feedback status
            await self.response_handler.update_command_feedback_status(
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                original_user_id=original_user_id,
                status="acknowledged",
                acknowledged_by=admin_id,
                acknowledged_at=datetime.now(timezone.utc).isoformat(),
            )

            # Update review message
            await self.response_handler.update_review_message(payload, admin_id)

            # Send ephemeral feedback to admin
            await self.posting_handler.post_message(
                channel_id=payload.get("channel", {}).get("id"),
                user_id=admin_id,
                message="✅ Command feedback acknowledged successfully!",
            )

            # Send acknowledgment notification to original user
            await self.response_handler.send_command_acknowledgment_dm(
                flagged_user_id=original_user_id,
                admin_name=admin_name,
                channel_id=channel_id,
                command_execution_id=command_execution_id,
            )

            return True

        except Exception as e:
            logger.error(f"Error handling command acknowledgment: {e}")
            return False

    async def handle_command_reply_button_click(self, payload: Dict[str, Any]) -> bool:
        """Handle admin clicking reply button for command feedback.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")

            # Extract channel_id, command_execution_id, and user_id from button value
            parts = value.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid command reply button value: {value}")
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            flagged_user_id = parts[2]

            # Show reply modal
            await self.response_handler.show_command_reply_modal(
                payload=payload,
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                flagged_user_id=flagged_user_id,
            )

            return True

        except Exception as e:
            logger.error(f"Error handling command reply button click: {e}")
            return False

    async def handle_mark_completed(self, payload: Dict[str, Any]) -> bool:
        """Handle admin marking review as completed.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            admin_id = payload.get("user", {}).get("id")
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")

            # Extract channel_id, message_ts, and user_id from button value
            parts = value.split("|")
            if len(parts) < 2:
                logger.error(f"Invalid mark completed value: {value}")
                return False

            channel_id = parts[0]
            message_ts = parts[1]
            parts[2] if len(parts) >= 3 else None

            # Update database with completed status
            await self.response_handler.update_completed_status(
                channel_id=channel_id,
                message_ts=message_ts,
                completed_by=admin_id,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

            # Update review message with completion styling
            await self.response_handler.update_review_message_completed(
                payload, admin_id
            )

            # Send ephemeral feedback to admin
            await self.posting_handler.post_message(
                channel_id=payload.get("channel", {}).get("id"),
                user_id=admin_id,
                message="✅ Review marked as completed successfully!",
            )

            return True

        except Exception as e:
            logger.error(f"Error handling mark completed: {e}")
            return False


