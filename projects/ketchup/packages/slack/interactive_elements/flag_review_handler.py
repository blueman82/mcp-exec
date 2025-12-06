"""flag_review_handler.py

Core orchestrator for flag for review interactions for AI-generated summaries.
Thin orchestration layer that routes requests to specialized delegate modules.
Maintains backward compatibility while providing clean modular architecture.
"""

from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.interactive_elements.flag_review.admin_action_processor import (
    AdminActionProcessor,
)
from packages.slack.interactive_elements.flag_review.command_flag_processor import (
    CommandFlagProcessor,
)
from packages.slack.interactive_elements.flag_review.modal_orchestrator import (
    ModalOrchestrator,
)
from packages.slack.interactive_elements.flag_review.status_flag_processor import (
    StatusFlagProcessor,
)
from packages.slack.interactive_elements.flag_review.validators import (
    FlagReviewValidator,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class FlagReviewHandler:
    """Core orchestrator for flag for review interactions."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        db_store: DynamoDBStore,
        secrets_manager,
    ):
        """Initialize the flag review handler orchestrator.

        Args:
            posting_handler: Handler for posting messages to Slack.
            db_store: DynamoDB store for data persistence.
            secrets_manager: Secrets manager for API tokens.
        """
        # Store core dependencies
        self.posting_handler = posting_handler
        self.db_store = db_store
        self.secrets_manager = secrets_manager

        # Initialize validator for rate limiting
        self.validators = FlagReviewValidator()

        # Initialize delegate modules for different responsibilities
        self.status_flag_processor = StatusFlagProcessor(posting_handler, db_store, secrets_manager)
        self.command_flag_processor = CommandFlagProcessor(
            posting_handler, db_store, secrets_manager
        )
        self.admin_action_processor = AdminActionProcessor(
            posting_handler, db_store, secrets_manager
        )
        self.modal_orchestrator = ModalOrchestrator(posting_handler, secrets_manager)

        # Backward compatibility attributes for tests
        # These ensure tests continue to pass until they're updated
        from packages.slack.interactive_elements.flag_review.database import (
            FlagReviewDatabaseOperations,
        )

        self.database = FlagReviewDatabaseOperations(db_store)

    async def process_flag_action(self, payload: Dict[str, Any]) -> bool:
        """Process a flag review action from a button click or modal submission.

        Routes requests to appropriate delegate modules based on action type.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            payload_type = payload.get("type")
            user_id = payload.get("user", {}).get("id")

            if payload_type == "block_actions":
                # Handle button click - check rate limit first
                if not self.validators.check_rate_limit(user_id):
                    await self._show_rate_limit_error(payload)
                    return False

                action = payload.get("actions", [{}])[0]
                action_id = action.get("action_id")

                if action_id == "flag_status_review":
                    return await self.status_flag_processor.handle_flag_button_click(payload)
                elif action_id == "acknowledge_feedback":
                    return await self.admin_action_processor.handle_acknowledgment(payload)
                elif action_id == "reply_to_feedback":
                    return await self.admin_action_processor.handle_reply_button_click(payload)
                elif action_id == "mark_review_completed":
                    return await self.admin_action_processor.handle_mark_completed(payload)

            elif payload_type == "view_submission":
                # Handle modal submission
                callback_id = payload.get("view", {}).get("callback_id")
                if callback_id == "flag_review_modal":
                    return await self.status_flag_processor.handle_flag_submission(payload)
                elif callback_id == "reply_feedback_modal":
                    return await self.admin_action_processor.handle_reply_submission(payload)
                elif callback_id == "reply_command_feedback_modal":
                    return await self.admin_action_processor.handle_command_reply_submission(
                        payload
                    )

            return False

        except Exception as e:
            logger.error(f"Error processing flag action: {e}", exc_info=True)
            return False

    async def process_command_flag_action(self, payload: Dict[str, Any]) -> bool:
        """Process a flag review action for a command.

        Delegates all command flag processing to CommandFlagProcessor.

        Args:
            payload: The interaction payload from Slack.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            # Delegate all command flag processing to the specialized processor
            return await self.command_flag_processor.process_command_flag_action(payload)

        except Exception as e:
            logger.error(f"Error processing command flag action: {e}", exc_info=True)
            return False

    async def _show_rate_limit_error(self, payload: Dict[str, Any]) -> None:
        """Show rate limit error modal to user.

        Args:
            payload: The interaction payload containing trigger_id.
        """
        try:
            trigger_id = payload.get("trigger_id")
            if not trigger_id:
                logger.error("No trigger_id found in payload for rate limit error")
                return

            # Create error modal view
            error_view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": "Rate Limit Exceeded"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "⚠️ You're submitting feedback too quickly. Please wait a moment before trying again.",
                        },
                    }
                ],
            }

            # Use modal orchestrator to display the error
            await self.modal_orchestrator._display_modal_via_api(
                trigger_id, error_view, "rate limit error"
            )

        except Exception as e:
            logger.error(f"Error showing rate limit error: {e}", exc_info=True)


# Legacy Compatibility Methods - TEMPORARY FOR TESTS
# TODO: Remove after updating test files
# Verified: No production code calls these methods (2025-09-18)
# Only tests use these methods


class FlagReviewHandlerLegacyCompatibility(FlagReviewHandler):
    """Extends FlagReviewHandler with legacy method compatibility.

    Provides backward compatibility for methods that may be called directly
    from external code, routing them to appropriate delegate modules.
    """

    async def _handle_flag_button_click(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for flag button clicks."""
        return await self.status_flag_processor.handle_flag_button_click(payload)

    async def _handle_flag_submission(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for flag submissions."""
        return await self.status_flag_processor.handle_flag_submission(payload)

    async def _handle_acknowledgment(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for acknowledgments."""
        return await self.admin_action_processor.handle_acknowledgment(payload)

    async def _handle_reply_button_click(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for reply button clicks."""
        return await self.admin_action_processor.handle_reply_button_click(payload)

    async def _handle_reply_submission(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for reply submissions."""
        return await self.admin_action_processor.handle_reply_submission(payload)

    async def _handle_command_flag_button_click(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for command flag button clicks."""
        return await self.command_flag_processor.handle_command_flag_button_click(payload)

    async def _handle_command_flag_submission(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for command flag submissions."""
        return await self.command_flag_processor.handle_command_flag_submission(payload)

    async def _handle_command_acknowledgment(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for command acknowledgments."""
        return await self.admin_action_processor.handle_command_acknowledgment(payload)

    async def _handle_command_reply_button_click(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for command reply button clicks."""
        return await self.admin_action_processor.handle_command_reply_button_click(payload)

    async def _handle_command_reply_submission(self, payload: Dict[str, Any]) -> bool:
        """Legacy compatibility method for command reply submissions."""
        return await self.admin_action_processor.handle_command_reply_submission(payload)

    async def _show_feedback_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        message_ts: str,
        summary_text: str,
    ) -> None:
        """Legacy compatibility method for showing feedback modals."""
        await self.modal_orchestrator.create_and_display_modal(
            payload=payload,
            modal_type="feedback",
            channel_id=channel_id,
            message_ts=message_ts,
            summary_text=summary_text,
        )

    async def _show_command_feedback_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        original_channel: str,
    ) -> None:
        """Legacy compatibility method for showing command feedback modals."""
        await self.modal_orchestrator.show_command_feedback_modal(
            payload=payload,
            channel_id=channel_id,
            command_execution_id=command_execution_id,
            command_type=command_type,
            original_channel=original_channel,
        )

    async def _show_reply_modal(
        self,
        payload: Dict[str, Any],
        feedback_id: str,
        feedback_text: str,
        user_id: str,
        modal_type: str = "reply",
    ) -> None:
        """Legacy compatibility method for showing reply modals."""
        await self.modal_orchestrator.create_and_display_modal(
            payload=payload,
            modal_type=modal_type,
            feedback_id=feedback_id,
            feedback_text=feedback_text,
            user_id=user_id,
        )

    async def _show_command_reply_modal(
        self,
        payload: Dict[str, Any],
        feedback_id: str,
        feedback_text: str,
        user_id: str,
    ) -> None:
        """Legacy compatibility method for showing command reply modals."""
        await self.modal_orchestrator.create_and_display_modal(
            payload=payload,
            modal_type="command_reply",
            feedback_id=feedback_id,
            feedback_text=feedback_text,
            user_id=user_id,
        )

    # Add methods that tests expect to exist
    def _validate_feedback(self, text: str, user_id: str, channel_id: str) -> dict:
        """Legacy validation method for tests."""
        validator = FlagReviewValidator()
        return validator.validate_flag_input(text, user_id, channel_id)

    async def _get_feedback_data(self, channel_id: str, message_ts: str):
        """Legacy method to get feedback data."""
        return await self.database.get_feedback_data(channel_id, message_ts)

    def _update_flag_display_in_blocks(self, blocks: list, flag_text: str) -> list:
        """Legacy method to update flag display."""
        # Look for existing flag display section
        flag_block_found = False
        for i, block in enumerate(blocks):
            if block.get("type") == "section":
                text = block.get("text", {}).get("text", "")
                if "⚠️ Flagged for review by:" in text or "✅ Reviewed:" in text:
                    # Update existing flag block
                    block["text"]["text"] = flag_text
                    flag_block_found = True
                    break

        # If no flag block found, add one after the first section
        if not flag_block_found:
            # Find first section block to add flag display after it
            insert_index = 0
            for i, block in enumerate(blocks):
                if block.get("type") == "section":
                    insert_index = i + 1
                    break

            # Insert flag display block
            flag_block = {"type": "section", "text": {"type": "mrkdwn", "text": flag_text}}
            blocks.insert(insert_index, flag_block)

        return blocks

    async def _add_flag_atomically(self, **kwargs):
        """Legacy method for atomic flag creation."""
        return await self.database.add_flag_atomically(**kwargs)

    async def _add_flag(
        self,
        channel_id: str,
        message_ts: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: list,
    ):
        """Legacy method to add flag."""
        return await self.database.add_flag_atomically(
            channel_id=channel_id,
            message_ts=message_ts,
            user_id=user_id,
            user_name=user_name,
            feedback_text=feedback_text,
            validation_issues=validation_issues,
        )

    async def _get_flag_status(self, channel_id: str, message_ts: str):
        """Legacy method to get flag status."""
        return await self.database.get_flag_status(channel_id, message_ts)


# For maximum compatibility, make the legacy compatibility class the default export
FlagReviewHandler = FlagReviewHandlerLegacyCompatibility
