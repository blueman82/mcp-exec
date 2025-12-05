"""
modal_orchestrator.py

Handles modal display, validation, and API interactions for flag review functionality.
Provides centralized modal lifecycle management and Slack API communication.
"""

from typing import Any, Dict

import aiohttp

from packages.core.logging import setup_logger
from packages.slack.formatters.utils import normalize_text
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class ModalOrchestrator:
    """Handles modal display, validation, and API interactions."""

    def __init__(self, posting_handler: SlackPostingHandler, secrets_manager):
        """Initialize the modal orchestrator.

        Args:
            posting_handler: Handler for posting messages to Slack.
            secrets_manager: Secrets manager for API tokens.
        """
        self.posting_handler = posting_handler
        self.secrets_manager = secrets_manager

    async def create_and_display_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        original_channel: str = None,
    ) -> bool:
        """Create and display a command feedback modal.

        Args:
            payload: The interaction payload from Slack.
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            command_type: The type of command that was executed.
            original_channel: The original channel where button was clicked.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        trigger_id = payload.get("trigger_id")

        # Validate trigger_id
        if not self._validate_trigger_id(trigger_id):
            return False

        # Create modal view
        modal_view = self._create_command_feedback_modal_view(
            channel_id,
            command_execution_id,
            command_type,
            original_channel or channel_id,
        )

        # Display modal via API call
        return await self._display_modal_via_api(trigger_id, modal_view, "command flag review")

    def _validate_trigger_id(self, trigger_id: str) -> bool:
        """Validate Slack trigger ID format and length.

        Args:
            trigger_id: The Slack trigger ID to validate.

        Returns:
            True if trigger ID is valid, False otherwise.
        """
        if not trigger_id or len(trigger_id) < 25:
            logger.error(
                f"Invalid trigger_id: {trigger_id} (length: {len(trigger_id) if trigger_id else 0})"
            )
            return False
        return True

    def _create_command_feedback_modal_view(
        self,
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        original_channel: str,
    ) -> Dict[str, Any]:
        """Create modal view structure for command feedback.

        Args:
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            command_type: The type of command that was executed.
            original_channel: The original channel where button was clicked.

        Returns:
            Dictionary containing the modal view structure for Slack.
        """
        return {
            "type": "modal",
            "callback_id": "command_flag_review_modal",
            "private_metadata": f"{channel_id}|{command_execution_id}|{command_type}|{original_channel}",
            "title": {"type": "plain_text", "text": "Flag Command for Review"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Please describe the issue with this {normalize_text(command_type)} command output:",
                    },
                },
                {
                    "type": "input",
                    "block_id": "feedback_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "feedback_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "The output is incorrect because...",
                        },
                        "min_length": 10,
                        "max_length": 3000,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "What's wrong with this output?",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Your feedback helps us improve Ketchup's responses",
                        }
                    ],
                },
            ],
        }

    async def _display_modal_via_api(
        self, trigger_id: str, modal_view: Dict[str, Any], modal_type: str
    ) -> bool:
        """Display modal using direct Slack API call.

        Args:
            trigger_id: The Slack trigger ID for opening the modal.
            modal_view: The modal view structure to display.
            modal_type: The type of modal being displayed (for logging).

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        try:
            slack_api_token = await self.secrets_manager.get_slack_api_token_async()

            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            return await self._make_modal_api_request(url, headers, api_payload, modal_type)

        except Exception as e:
            logger.error(f"Error displaying {modal_type} modal: {e}")
            return False

    async def _make_modal_api_request(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        modal_type: str,
    ) -> bool:
        """Make the actual API request to display modal.

        Args:
            url: The Slack API URL to make the request to.
            headers: HTTP headers for the request.
            payload: The request payload containing trigger_id and view.
            modal_type: The type of modal being displayed (for logging).

        Returns:
            True if API request succeeded, False otherwise.
        """
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                logger.info(
                    f"Received response status: {response.status} from Slack API views.open"
                )
                response_data = await response.json()

                if not response_data.get("ok"):
                    error_msg = response_data.get("error", "unknown")
                    logger.error(f"Failed to open {modal_type} modal: {error_msg}")
                    logger.error(f"Full response: {response_data}")
                    logger.error(f"Trigger ID used: {payload.get('trigger_id')}")
                    return False
                else:
                    logger.info(f"{modal_type.capitalize()} modal opened successfully")
                    return True

    def create_command_feedback_modal_view(
        self, channel_id: str, command_execution_id: str, command_type: str, original_channel: str
    ) -> Dict[str, Any]:
        """Create modal view for command feedback."""
        return {
            "type": "modal",
            "callback_id": "command_flag_review_modal",
            "private_metadata": f"{channel_id}|{command_execution_id}|{command_type}|{original_channel}",
            "title": {"type": "plain_text", "text": "Flag Command for Review"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Please describe the issue with this {normalize_text(command_type)} command output:",
                    },
                },
                {
                    "type": "input",
                    "block_id": "feedback_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "feedback_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "The output is incorrect because...",
                        },
                        "min_length": 10,
                        "max_length": 3000,
                    },
                    "label": {"type": "plain_text", "text": "What's wrong with this output?"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Your feedback helps us improve Ketchup's responses",
                        }
                    ],
                },
            ],
        }

    def create_command_reply_modal_view(
        self, channel_id: str, command_execution_id: str, flagged_user_id: str
    ) -> Dict[str, Any]:
        """Create modal view for replying to command feedback."""
        return {
            "type": "modal",
            "callback_id": "reply_command_feedback_modal",
            "private_metadata": f"{channel_id}|{command_execution_id}|{flagged_user_id}",
            "title": {"type": "plain_text", "text": "Reply to Feedback"},
            "submit": {"type": "plain_text", "text": "Send Reply"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Send a direct message reply to <@{flagged_user_id}>:",
                    },
                },
                {
                    "type": "input",
                    "block_id": "reply_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reply_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Thank you for your feedback. Here's our response...",
                        },
                        "min_length": 1,
                        "max_length": 3000,
                    },
                    "label": {"type": "plain_text", "text": "Your Reply"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "This will be sent as a direct message to the user.",
                        }
                    ],
                },
            ],
        }

    async def show_command_feedback_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        original_channel: str = None,
    ) -> bool:
        """Show the command feedback input modal.

        Args:
            payload: The interaction payload from Slack.
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            command_type: The type of command that was executed.
            original_channel: The original channel where button was clicked.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        trigger_id = payload.get("trigger_id")

        if not self._validate_trigger_id(trigger_id):
            return False

        modal_view = self.create_command_feedback_modal_view(
            channel_id,
            command_execution_id,
            command_type,
            original_channel or channel_id,
        )

        return await self._display_modal_via_api(trigger_id, modal_view, "command flag review")

    async def show_command_reply_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        command_execution_id: str,
        flagged_user_id: str,
    ) -> bool:
        """Show the reply input modal for command feedback.

        Args:
            payload: The interaction payload from Slack.
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            flagged_user_id: The ID of the user who flagged the command.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        trigger_id = payload.get("trigger_id")

        if not trigger_id or len(trigger_id) < 25:
            logger.error(f"Invalid trigger_id: {len(trigger_id) if trigger_id else 0}")
            return False

        modal_view = self.create_command_reply_modal_view(
            channel_id, command_execution_id, flagged_user_id
        )

        return await self._display_modal_via_api(trigger_id, modal_view, "command reply")
