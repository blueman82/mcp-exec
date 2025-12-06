"""
shortcuts.py

This module processes Slack shortcuts such as the feedback report shortcut using a handler class.
"""

from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class ShortcutHandler:
    """Handles processing of Slack shortcuts."""

    def __init__(
        self,
        feedback_report_handler: FeedbackReportHandler,
        posting_handler: SlackPostingHandler,
    ):
        """
        Initializes the ShortcutHandler.

        Args:
            feedback_report_handler: Handler for feedback report modals.
            posting_handler: Handler for posting messages to Slack.
        """
        self._feedback_report_handler = feedback_report_handler
        self._posting_handler = posting_handler
        logger.info("ShortcutHandler initialized.")

    async def handle_shortcut(self, slack_payload: Dict[str, Any]) -> bool:
        """
        Process Slack shortcuts.

        This function handles various types of shortcuts, with special handling for
        the feedback report shortcut.

        Args:
            slack_payload: The parsed Slack payload dictionary

        Returns:
            Boolean indicating whether the shortcut was processed successfully
        """
        # Extract user and channel info for sending messages
        user_id = slack_payload.get("user", {}).get("id")
        # For shortcuts, we may not always have a channel
        channel_id = (
            slack_payload.get("channel", {}).get("id") if slack_payload.get("channel") else None
        )

        callback_id = slack_payload.get("callback_id")
        logger.info("Processing shortcut with callback_id: %s", callback_id)

        # Handle feedback report shortcut
        if callback_id == "feedback_report":
            # Extract trigger ID
            trigger_id = slack_payload.get("trigger_id")

            if not trigger_id:
                logger.error("Missing trigger_id for feedback report shortcut")
                if user_id and channel_id:
                    # Use injected posting handler
                    await self._posting_handler.post_message(
                        user_id=user_id,
                        channel_id=channel_id,
                        message="Error: Missing information to open feedback form.",
                    )
                return False

            # Use the injected feedback report handler's method
            success = await self._feedback_report_handler.open_feedback_report_modal(trigger_id)
            if not success and user_id and channel_id:
                # Use injected posting handler
                await self._posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message="Error opening feedback form. Please try again.",
                )
            return success

        # Add additional shortcut handlers here as needed

        # If we get here, no specific shortcut handler was triggered
        logger.warning("Unhandled shortcut callback_id: %s", callback_id)
        if user_id and channel_id:
            # Use injected posting handler
            await self._posting_handler.post_message(
                user_id=user_id,
                channel_id=channel_id,
                message=f"Shortcut '{callback_id}' not handled.",
            )
        return True
