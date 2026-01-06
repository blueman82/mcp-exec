"""
block_builder.py

Handles Block Kit UI construction, component assembly, and layout management
for flag review interactions. Provides specialized UI building functionality for
command feedback modals, review blocks, and action buttons.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from packages.slack.formatters.utils import normalize_text


class BlockBuilder:
    """Handles Block Kit UI construction, component assembly, and layouts.

    Provides methods for creating modal views, message blocks, action buttons,
    and other UI components used in the flag review workflow.
    """

    def __init__(self, dependency_container):
        """Initialize the BlockBuilder with dependency injection container.

        Args:
            dependency_container: TypedDI container for dependency access.
        """
        self.container = dependency_container

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
            Dictionary containing the modal view structure.
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

    def _create_command_review_blocks(
        self,
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        user_id: str,
        feedback_text: str,
        command_output: Optional[str],
        validation_issues: List[str],
    ) -> List[Dict[str, Any]]:
        """Create blocks for command review message.

        Args:
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            command_type: The type of command that was executed.
            user_id: The ID of the user who flagged the command.
            feedback_text: The user's feedback text.
            command_output: The command output text, if available.
            validation_issues: List of validation issues found in the feedback.

        Returns:
            List of block dictionaries for the message.
        """
        time_str = datetime.now(timezone.utc).strftime("%H:%M")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Command Flagged for Review*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Command Used:*\n/ketchup {command_type}",
                    },
                    {"type": "mrkdwn", "text": f"*Channel:*\n<#{channel_id}>"},
                    {"type": "mrkdwn", "text": f"*Flagged by:*\n<@{user_id}>"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{time_str}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*User's Feedback:*"},
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": feedback_text,
                },
            },
        ]

        # Add command output blocks
        if command_output:
            blocks.extend(self._create_command_output_blocks(command_output))

        # Add validation warnings
        if validation_issues:
            blocks.append(self._create_validation_warning_block(validation_issues))

        # Add action buttons
        blocks.append(
            self._create_command_action_buttons(channel_id, command_execution_id, user_id)
        )

        return blocks

    def _create_command_output_blocks(self, command_output: str) -> List[Dict[str, Any]]:
        """Create blocks for command output display.

        Args:
            command_output: The command output text to display.

        Returns:
            List of block dictionaries for displaying command output.
        """
        max_length = 2500  # Leave room for other blocks
        truncated_output = (
            command_output[:max_length] + "..."
            if len(command_output) > max_length
            else command_output
        )

        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Command Output:*"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": normalize_text(truncated_output),
                },
            },
        ]

    def _create_validation_warning_block(self, validation_issues: List[str]) -> Dict[str, Any]:
        """Create validation warning context block.

        Args:
            validation_issues: List of validation issues to display.

        Returns:
            Block dictionary containing validation warnings.
        """
        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⚠️ Validation notes: {', '.join(validation_issues)}",
                }
            ],
        }

    def _create_command_action_buttons(
        self, channel_id: str, command_execution_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Create action buttons for command review.

        Args:
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            user_id: The ID of the user who flagged the command.

        Returns:
            Dictionary containing action buttons block structure.
        """
        return {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Acknowledge Review",
                        "emoji": True,
                    },
                    "action_id": "acknowledge_command_feedback",
                    "value": f"{channel_id}|{command_execution_id}|{user_id}",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":speech_balloon: Reply",
                        "emoji": True,
                    },
                    "action_id": "reply_to_command_feedback",
                    "value": f"{channel_id}|{command_execution_id}|{user_id}",
                },
            ],
        }

    def _create_text_only_flag_message(
        self,
        command_type: str,
        channel_id: str,
        user_id: str,
        feedback_text: str,
        command_output: str,
        validation_issues: List[str],
    ) -> str:
        """Create a text-only version of the flag review message for fallback.

        Args:
            command_type: The type of command that was executed.
            channel_id: The channel ID where the command was executed.
            user_id: The ID of the user who flagged the command.
            feedback_text: The user's feedback text.
            command_output: The command output text.
            validation_issues: List of validation issues found in the feedback.

        Returns:
            Text-only message string for fallback posting.
        """
        # Format time as HH:MM
        flag_time = datetime.now(timezone.utc)
        time_str = flag_time.strftime("%H:%M")

        # Build compact text message
        parts = [
            "*Command Flagged for Review*",
            f"*Command:* /ketchup {command_type} | *Channel:* <#{channel_id}> | "
            f"*By:* <@{user_id}> | *Time:* {time_str}",
            f"*Feedback:* {feedback_text}",
        ]

        if command_output:
            max_len = 1500
            output = (
                command_output[:max_len] + "..."
                if len(command_output) > max_len
                else command_output
            )
            parts.append(f"*Output:* {normalize_text(output)}")

        if validation_issues:
            parts.append(f"⚠️ Issues: {', '.join(validation_issues)}")

        parts.append("*Actions:* Reply with 'ACK' to acknowledge or provide response")

        return "\n\n".join(parts)

    def _create_summary_review_blocks(
        self,
        channel_id: str,
        message_ts: str,
        user_id: str,
        feedback_text: str,
        validation_issues: List[str],
    ) -> List[Dict[str, Any]]:
        """Create blocks for summary review message.

        Args:
            channel_id: The channel ID where the feedback originated.
            message_ts: The timestamp of the message being flagged.
            user_id: The ID of the user who provided feedback.
            feedback_text: The user's feedback text.
            validation_issues: List of validation issues found in the feedback.

        Returns:
            List of block dictionaries for the summary review message.
        """
        time_str = datetime.now(timezone.utc).strftime("%H:%M")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Summary Flagged for Review*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Channel:*\n<#{channel_id}>"},
                    {"type": "mrkdwn", "text": f"*Flagged by:*\n<@{user_id}>"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{time_str}"},
                    {
                        "type": "mrkdwn",
                        "text": "*Original Message:*\nView message in channel",
                    },
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*User's Feedback:*"},
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": feedback_text,
                },
            },
        ]

        # Add validation warnings
        if validation_issues:
            blocks.append(self._create_validation_warning_block(validation_issues))

        # Add action buttons
        blocks.append(self._create_summary_action_buttons(channel_id, message_ts, user_id))

        return blocks

    def _create_summary_action_buttons(
        self, channel_id: str, message_ts: str, user_id: str
    ) -> Dict[str, Any]:
        """Create action buttons for summary review.

        Args:
            channel_id: The channel ID where the summary was posted.
            message_ts: The timestamp of the message being reviewed.
            user_id: The ID of the user who flagged the summary.

        Returns:
            Dictionary containing action buttons block structure.
        """
        return {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Acknowledge Review"},
                    "action_id": "acknowledge_feedback",
                    "value": f"{channel_id}|{message_ts}|{user_id}",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "💬 Reply"},
                    "action_id": "reply_to_feedback",
                    "value": f"{channel_id}|{message_ts}|{user_id}",
                },
            ],
        }
