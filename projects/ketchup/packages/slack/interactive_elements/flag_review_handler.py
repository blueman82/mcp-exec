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
