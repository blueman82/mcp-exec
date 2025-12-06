"""Command Flag Processor Module.

Handles command flag processing by delegating to specialized modules.
Provides lightweight orchestration for command flagging functionality.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.interactive_elements.flag_review.api_client import (
    FlagReviewApiClient,
)
from packages.slack.interactive_elements.flag_review.block_builder import (
    BlockBuilder,
)
from packages.slack.interactive_elements.flag_review.modal_orchestrator import (
    ModalOrchestrator,
)
from packages.slack.interactive_elements.flag_review.notification_sender import (
    NotificationSender,
)
from packages.slack.interactive_elements.flag_review.review_poster import (
    ReviewPoster,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class CommandFlagProcessor:
    """Lightweight orchestrator for command flag processing."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        db_store: DynamoDBStore,
        secrets_manager,
    ):
        """Initialize with dependencies and delegate modules."""
        self.posting_handler = posting_handler
        self.db_store = db_store
        self.secrets_manager = secrets_manager

        # Initialize delegate modules
        # Create a dependency container with getter methods as expected by modules
        dependency_container = type(
            "Container",
            (),
            {
                "get_posting_handler": lambda self: posting_handler,
                "get_db_store": lambda self: db_store,
                "get_secrets_manager": lambda self: secrets_manager,
            },
        )()

        self.modal_orchestrator = ModalOrchestrator(posting_handler, secrets_manager)
        self.api_client = FlagReviewApiClient(dependency_container)
        self.notification_sender = NotificationSender(dependency_container)
        self.block_builder = BlockBuilder(dependency_container)
        self.review_poster = ReviewPoster(dependency_container)

    async def process_command_flag_action(self, payload: Dict[str, Any]) -> bool:
        """Route command flag actions to appropriate handlers.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            payload_type = payload.get("type")

            if payload_type == "block_actions":
                action = payload.get("actions", [{}])[0]
                action_id = action.get("action_id")

                if action_id in ["flag_status_review", "flag_command_review"]:
                    return await self.handle_command_flag_button_click(payload)
                elif action_id == "acknowledge_command_feedback":
                    return await self.handle_command_acknowledgment(payload)
                elif action_id == "reply_to_command_feedback":
                    return await self.handle_command_reply_button_click(payload)

            elif payload_type == "view_submission":
                callback_id = payload.get("view", {}).get("callback_id")
                if callback_id == "command_flag_review_modal":
                    return await self.handle_command_flag_submission(payload)
                elif callback_id == "reply_command_feedback_modal":
                    return await self.handle_command_reply_submission(payload)

            return False

        except Exception as e:
            logger.error(f"Error processing command flag action: {e}", exc_info=True)
            return False

    async def handle_command_flag_button_click(self, payload: Dict[str, Any]) -> bool:
        """Handle flag button click by showing modal."""
        try:
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")
            original_channel = payload.get("channel", {}).get("id")

            parts = value.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid command flag button value: {value}")
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            command_type = parts[2]

            return await self.modal_orchestrator.show_command_feedback_modal(
                payload=payload,
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                command_type=command_type,
                original_channel=original_channel,
            )

        except Exception as e:
            logger.error(f"Error handling command flag button click: {e}")
            return False

    async def handle_command_flag_submission(self, payload: Dict[str, Any]) -> bool:
        """Handle command flag modal submission."""
        try:
            user_id = payload.get("user", {}).get("id")
            user_name = payload.get("user", {}).get("username", "Unknown")

            # Extract form data
            values = payload.get("view", {}).get("state", {}).get("values", {})
            feedback_text = (
                values.get("feedback_block", {}).get("feedback_input", {}).get("value", "")
            )

            # Extract metadata
            private_metadata = payload.get("view", {}).get("private_metadata", "")
            parts = private_metadata.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid private_metadata: {private_metadata}")
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            command_type = parts[2]
            original_channel = parts[3] if len(parts) > 3 else channel_id

            # Store flag in database
            success = await self.api_client.store_command_flag(
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                user_id=user_id,
                user_name=user_name,
                original_text=feedback_text,
                command_type=command_type,
                original_channel=original_channel,
            )

            if not success:
                return False

            # Post to review channel
            await self.post_command_to_review_channel(
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                command_type=command_type,
                user_id=user_id,
                user_name=user_name,
                feedback_text=feedback_text,
            )

            # Send success notification
            await self.notification_sender.send_dm_confirmation(
                user_id=user_id,
                confirmation_message=f"Thank you! Your feedback for the /ketchup {command_type} command has been received and will be reviewed by our team.",
            )

            return True

        except Exception as e:
            logger.error(f"Error handling command flag submission: {e}")
            return False

    async def handle_command_acknowledgment(self, payload: Dict[str, Any]) -> bool:
        """Handle admin acknowledgment of command feedback."""
        try:
            admin_id = payload.get("user", {}).get("id")
            admin_name = payload.get("user", {}).get("username", "Unknown")
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")

            parts = value.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid acknowledgment value: {value}")
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            original_user_id = parts[2]

            # Update database status
            await self.update_command_feedback_status(
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                original_user_id=original_user_id,
                status="acknowledged",
                acknowledged_by=admin_id,
            )

            # Update review message
            await self.update_review_message(payload, admin_id)

            # Send ephemeral feedback
            await self.posting_handler.post_message(
                channel_id=payload.get("channel", {}).get("id"),
                user_id=admin_id,
                message="✅ Command feedback acknowledged successfully!",
            )

            # Send DM to original user
            await self.send_command_acknowledgment_dm(
                flagged_user_id=original_user_id,
                admin_name=admin_name,
                channel_id=channel_id,
            )

            return True

        except Exception as e:
            logger.error(f"Error handling command acknowledgment: {e}")
            return False

    async def handle_command_reply_button_click(self, payload: Dict[str, Any]) -> bool:
        """Handle reply button click by showing reply modal."""
        try:
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")

            parts = value.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid reply button value: {value}")
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            flagged_user_id = parts[2]

            return await self.modal_orchestrator.show_command_reply_modal(
                payload=payload,
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                flagged_user_id=flagged_user_id,
            )

        except Exception as e:
            logger.error(f"Error handling reply button click: {e}")
            return False

    async def handle_command_reply_submission(self, payload: Dict[str, Any]) -> bool:
        """Handle reply modal submission."""
        try:
            admin_id = payload.get("user", {}).get("id")
            admin_name = payload.get("user", {}).get("username", "Unknown")

            # Extract reply text
            values = payload.get("view", {}).get("state", {}).get("values", {})
            reply_text = values.get("reply_block", {}).get("reply_input", {}).get("value", "")

            # Extract metadata
            private_metadata = payload.get("view", {}).get("private_metadata", "")
            parts = private_metadata.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid reply metadata: {private_metadata}")
                return False

            channel_id = parts[0]
            command_execution_id = parts[1]
            flagged_user_id = parts[2]

            # Send reply DM
            success = await self.send_command_reply_dm(
                flagged_user_id=flagged_user_id,
                admin_name=admin_name,
                reply_text=reply_text,
                channel_id=channel_id,
            )

            if success:
                # Update review message
                await self.update_command_review_message_with_reply(payload, admin_id)

                # Update database
                await self.update_command_feedback_status(
                    channel_id=channel_id,
                    command_execution_id=command_execution_id,
                    original_user_id=flagged_user_id,
                    status="replied",
                    acknowledged_by=admin_id,
                )

            return success

        except Exception as e:
            logger.error(f"Error handling reply submission: {e}")
            return False

    # Helper methods delegate to specialized modules

    async def post_command_to_review_channel(
        self,
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
    ) -> None:
        """Post command feedback to review channel."""
        # Use block_builder for correct command flag buttons (acknowledge_command_feedback)
        blocks = self.block_builder._create_command_review_blocks(
            channel_id=channel_id,
            command_execution_id=command_execution_id,
            command_type=command_type,
            user_id=user_id,
            feedback_text=feedback_text,
            command_output=None,  # Command output not needed in review message
            validation_issues=[],
        )

        # Post to review channel with proper command flag buttons
        await self.posting_handler.post_message(
            channel_id="C095LQ0H4KB",  # REVIEW_CHANNEL_ID
            message=f"Command flagged for review: /ketchup {command_type}",
            blocks=blocks,
        )

    async def update_command_feedback_status(
        self,
        channel_id: str,
        command_execution_id: str,
        original_user_id: str,
        status: str,
        acknowledged_by: str,
    ) -> None:
        """Update command feedback status in database."""
        await self.db_store.client.update_item(
            table_name=self.db_store.table_name,
            key={
                "PK": {"S": f"FEEDBACK#{channel_id}#{command_execution_id}"},
                "SK": {"S": f"COMMAND_FLAG#{original_user_id}"},
            },
            update_expression="SET #status = :status, acknowledged_by = :admin, acknowledged_at = :time",
            expression_attribute_names={"#status": "status"},
            expression_attribute_values={
                ":status": {"S": status},
                ":admin": {"S": acknowledged_by},
                ":time": {"S": datetime.now(timezone.utc).isoformat()},
            },
        )

    async def update_review_message(self, payload: Dict[str, Any], admin_id: str) -> None:
        """Update review message after acknowledgment."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        updater = MessageUpdater(self.posting_handler)
        await updater.update_review_message(payload, admin_id)

    async def update_command_review_message_with_reply(
        self, payload: Dict[str, Any], admin_id: str
    ) -> None:
        """Update review message after reply."""
        from packages.slack.interactive_elements.flag_review.message_updater import (
            MessageUpdater,
        )

        updater = MessageUpdater(self.posting_handler)
        await updater.update_review_message_with_reply(payload, admin_id)

    async def send_command_acknowledgment_dm(
        self, flagged_user_id: str, admin_name: str, channel_id: str
    ) -> bool:
        """Send acknowledgment DM to user."""
        from packages.slack.interactive_elements.flag_review.dm_handler import (
            FlagReviewDMHandler,
        )

        # Note: command_execution_id not available here, so pass None
        # DM will be sent without "View" link (which is correct for commands)
        return await FlagReviewDMHandler(self.posting_handler).send_dm_to_requester(
            user_id=flagged_user_id,
            dm_type="acknowledgment",
            admin_name=admin_name,
            channel_id=channel_id,
            command_execution_id=None,
        )

    async def send_command_reply_dm(
        self, flagged_user_id: str, admin_name: str, reply_text: str, channel_id: str
    ) -> bool:
        """Send reply DM to user."""
        from packages.slack.interactive_elements.flag_review.dm_handler import (
            FlagReviewDMHandler,
        )

        return await FlagReviewDMHandler(self.posting_handler).send_dm_to_requester(
            user_id=flagged_user_id,
            dm_type="reply",
            admin_name=admin_name,
            channel_id=channel_id,
            command_execution_id=None,
            reply_text=reply_text,
        )
