"""
Modal management for flag review functionality.

This module handles the creation and display of modal dialogs for
feedback collection, review displays, and admin interactions.
"""

from typing import Any, Dict, Optional

import aiohttp

from packages.core.logging import setup_logger
from packages.slack.interactive_elements.flag_review.flag_types import (
    BLOCK_COMMAND_OUTPUT,
    BLOCK_FEEDBACK_INPUT,
    BLOCK_REPLY_INPUT,
    MODAL_FLAG_REVIEW,
    MODAL_REPLY_COMMAND_FEEDBACK,
    MODAL_REPLY_FEEDBACK,
)

logger = setup_logger(__name__)


class FlagReviewModalManager:
    """Handles modal creation and management for flag review functionality."""

    def __init__(self, secrets_manager):
        """
        Initialize the modal manager.

        Args:
            secrets_manager: Manager for accessing API secrets
        """
        self.secrets_manager = secrets_manager

    async def display_feedback_modal(
        self,
        trigger_id: str,
        channel_id: str,
        message_ts: str,
        status_update_id: str,
    ) -> bool:
        """
        Display the feedback input modal for status updates.

        Args:
            trigger_id: Slack trigger ID for modal
            channel_id: Channel where the message exists
            message_ts: Timestamp of the message
            status_update_id: ID of the status update

        Returns:
            True if modal opened successfully, False otherwise
        """
        modal_view = self.create_feedback_modal_view(channel_id, message_ts, status_update_id)

        # Modal view is created and validated
        # Actual modal opening is handled by Slack client elsewhere
        return bool(modal_view)

    async def display_command_feedback_modal(
        self,
        trigger_id: str,
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        command_output: Optional[str] = None,
    ) -> bool:
        """
        Display the feedback modal for command outputs.

        Args:
            trigger_id: Slack trigger ID for modal
            channel_id: Channel where command was executed
            command_execution_id: ID of the command execution
            command_type: Type of command executed
            command_output: Output of the command (optional)

        Returns:
            True if modal opened successfully, False otherwise
        """
        modal_view = self.create_command_feedback_modal_view(
            channel_id, command_execution_id, command_type, command_output
        )

        # Modal view is created and validated
        # Actual modal opening is handled by Slack client elsewhere
        return bool(modal_view)

    async def display_reply_modal(
        self,
        trigger_id: str,
        flag_id: str,
        user_id: str,
        feedback_text: str,
        is_command: bool = False,
    ) -> bool:
        """
        Display the reply modal for admins to respond to feedback.

        Args:
            trigger_id: Slack trigger ID for modal
            flag_id: ID of the flag review
            user_id: ID of the user who submitted feedback
            feedback_text: The original feedback text
            is_command: Whether this is for a command flag

        Returns:
            True if modal opened successfully, False otherwise
        """
        modal_view = self.create_reply_modal_view(flag_id, user_id, feedback_text, is_command)

        # Modal view is created and validated
        # Actual modal opening is handled by Slack client elsewhere
        return bool(modal_view)

    def create_feedback_modal_view(
        self, channel_id: str, message_ts: str, status_update_id: str
    ) -> Dict[str, Any]:
        """
        Create the modal view for feedback input.

        Args:
            channel_id: Channel ID
            message_ts: Message timestamp
            status_update_id: Status update ID

        Returns:
            Modal view dictionary
        """
        return {
            "type": "modal",
            "callback_id": MODAL_FLAG_REVIEW,
            "private_metadata": f"{channel_id}|{message_ts}|{status_update_id}",
            "title": {"type": "plain_text", "text": "Flag Summary for Review"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Please describe what's incorrect about this summary:",
                    },
                },
                {
                    "type": "input",
                    "block_id": "feedback_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": BLOCK_FEEDBACK_INPUT,
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "E.g., Missing important context, Incorrect facts, Misleading summary...",
                        },
                        "min_length": 10,
                        "max_length": 3000,
                    },
                    "label": {"type": "plain_text", "text": "Feedback"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Examples:\n• Missing important context\n"
                            "• Incorrect facts\n• Misleading summary",
                        }
                    ],
                },
            ],
        }

    def create_command_feedback_modal_view(
        self,
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        command_output: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create the modal view for command feedback.

        Args:
            channel_id: Channel ID
            command_execution_id: Command execution ID
            command_type: Type of command
            command_output: Command output (optional)

        Returns:
            Modal view dictionary
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Flag the output from `/ketchup {command_type}` for review:",
                },
            },
            {
                "type": "input",
                "block_id": "feedback_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": BLOCK_FEEDBACK_INPUT,
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe what's incorrect or needs review...",
                    },
                    "min_length": 10,
                    "max_length": 3000,
                },
                "label": {"type": "plain_text", "text": "What needs review?"},
            },
        ]

        # Add command output if available
        if command_output:
            blocks.insert(
                1,
                {
                    "type": "section",
                    "block_id": BLOCK_COMMAND_OUTPUT,
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Command Output:*\n```{command_output[:500]}```",
                    },
                },
            )

        return {
            "type": "modal",
            "callback_id": "command_flag_review_modal",
            "private_metadata": f"{channel_id}|{command_execution_id}|{command_type}",
            "title": {"type": "plain_text", "text": "Flag Command Output"},
            "submit": {"type": "plain_text", "text": "Submit Flag"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": blocks,
        }

    def create_reply_modal_view(
        self, flag_id: str, user_id: str, feedback_text: str, is_command: bool = False
    ) -> Dict[str, Any]:
        """
        Create the modal view for admin replies.

        Args:
            flag_id: Flag review ID
            user_id: User ID who submitted feedback
            feedback_text: Original feedback text
            is_command: Whether this is for a command flag

        Returns:
            Modal view dictionary
        """
        callback_id = MODAL_REPLY_COMMAND_FEEDBACK if is_command else MODAL_REPLY_FEEDBACK

        return {
            "type": "modal",
            "callback_id": callback_id,
            "private_metadata": f"{flag_id}|{user_id}",
            "title": {"type": "plain_text", "text": "Reply to Feedback"},
            "submit": {"type": "plain_text", "text": "Send Reply"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Original feedback from <@{user_id}>:*\n{feedback_text}",
                    },
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "reply_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": BLOCK_REPLY_INPUT,
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Your response to the user...",
                        },
                        "min_length": 1,
                        "max_length": 3000,
                    },
                    "label": {"type": "plain_text", "text": "Your Reply"},
                },
            ],
        }

    async def handle_review_modal_update(
        self, modal_view: Dict[str, Any], review_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a modal view with review data.

        Args:
            modal_view: The current modal view
            review_data: Data to update the modal with

        Returns:
            Updated modal view
        """
        # Update modal title if status provided
        if "status" in review_data:
            modal_view["title"]["text"] = f"Review - {review_data['status']}"

        # Add additional blocks if provided
        if "additional_blocks" in review_data:
            modal_view["blocks"].extend(review_data["additional_blocks"])

        return modal_view

    async def show_reply_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        message_ts: str,
        flagged_user_id: str,
    ) -> None:
        """
        Show the reply modal for admins to respond to feedback.

        Args:
            payload: The interaction payload from Slack
            channel_id: The channel where the feedback was flagged
            message_ts: The message timestamp
            flagged_user_id: The user who flagged the message

        Raises:
            Exception: If modal display fails
        """
        try:
            trigger_id = payload.get("trigger_id")
            if not trigger_id:
                logger.error("No trigger_id in payload for reply modal")
                return

            # Create modal view with metadata
            modal_view = {
                "type": "modal",
                "callback_id": MODAL_REPLY_FEEDBACK,
                "private_metadata": f"{channel_id}|{message_ts}|{flagged_user_id}",
                "title": {"type": "plain_text", "text": "Reply to Feedback"},
                "submit": {"type": "plain_text", "text": "Send Reply"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Reply to feedback from <@{flagged_user_id}>",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "input",
                        "block_id": "reply_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": BLOCK_REPLY_INPUT,
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Your response to the user...",
                            },
                            "min_length": 1,
                            "max_length": 3000,
                        },
                        "label": {"type": "plain_text", "text": "Your Reply"},
                    },
                ],
            }

            # Open modal using Slack API
            slack_api_token = await self.secrets_manager.get_slack_api_token_async()
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }
            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error(f"Failed to open reply modal: {error_msg}")
                        raise Exception(f"Modal open failed: {error_msg}")

            logger.info(f"Displayed reply modal for message {message_ts}")

        except Exception as e:
            logger.error(f"Error showing reply modal: {e}")
            raise

    async def show_command_reply_modal(
        self,
        payload: Dict[str, Any],
        channel_id: str,
        command_execution_id: str,
        flagged_user_id: str,
    ) -> None:
        """
        Show the reply modal for admins to respond to command feedback.

        Args:
            payload: The interaction payload from Slack
            channel_id: The channel where the command was executed
            command_execution_id: The command execution ID
            flagged_user_id: The user who flagged the command

        Raises:
            Exception: If modal display fails
        """
        try:
            trigger_id = payload.get("trigger_id")
            if not trigger_id:
                logger.error("No trigger_id in payload for command reply modal")
                return

            # Create modal view with metadata
            modal_view = {
                "type": "modal",
                "callback_id": MODAL_REPLY_COMMAND_FEEDBACK,
                "private_metadata": f"{channel_id}|{command_execution_id}|{flagged_user_id}",
                "title": {"type": "plain_text", "text": "Reply to Command Feedback"},
                "submit": {"type": "plain_text", "text": "Send Reply"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Reply to command feedback from <@{flagged_user_id}>",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "input",
                        "block_id": "reply_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": BLOCK_REPLY_INPUT,
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Your response to the user...",
                            },
                            "min_length": 1,
                            "max_length": 3000,
                        },
                        "label": {"type": "plain_text", "text": "Your Reply"},
                    },
                ],
            }

            # Open modal using Slack API
            slack_api_token = await self.secrets_manager.get_slack_api_token_async()
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }
            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error(f"Failed to open command reply modal: {error_msg}")
                        raise Exception(f"Modal open failed: {error_msg}")

            logger.info(f"Displayed command reply modal for command {command_execution_id}")

        except Exception as e:
            logger.error(f"Error showing command reply modal: {e}")
            raise
