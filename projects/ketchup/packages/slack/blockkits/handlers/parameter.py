"""
parameter.py

Specialized handler for formatting and sending parameter help messages.

This module contains the ParameterMessageHandler class for handling
parameter help and command usage messages.
"""

from typing import Any, Callable, Dict, Optional

from packages.core.logging import setup_logger
from packages.slack.blockkits.handlers.blockkit_message_utils import (
    create_context_tooltip_block,
    create_message_blocks,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class ParameterMessageHandler:
    """
    Handles formatting and sending of parameter help messages.

    Responsibilities:
    - Format command parameter descriptions
    - Display usage examples and help text
    - Send parameter help messages to Slack
    """

    def __init__(self):
        """Initialize the ParameterMessageHandler."""
        self._posting_handler = None
        self._channel_details_getter = None

    def configure(
        self, posting_handler: SlackPostingHandler, channel_details_getter: Callable
    ) -> None:
        """
        Configure the handler with dependencies.

        Args:
            posting_handler: Handler for posting messages to Slack
            channel_details_getter: Function to get channel details
        """
        self._posting_handler = posting_handler
        self._channel_details_getter = channel_details_getter

    async def send_message(
        self,
        response_url: str,
        parameters: Dict[str, Any],
        command_type: str,
        help_text: Optional[str] = None,
    ) -> None:
        """
        Send a formatted parameter help message to Slack.

        Args:
            response_url: URL to send the response to
            parameters: Dictionary of parameter information
            command_type: The type of command needing help
            help_text: Optional additional help text
        """
        # Build all message blocks
        message_blocks = self._build_message_blocks(
            command_type, parameters, help_text
        )

        # Send the message with error handling
        try:
            await self._send_parameter_message(
                response_url, command_type, message_blocks
            )
        except Exception as e:
            logger.error("Failed to send parameter help message: %s", str(e))
            await self._handle_message_fallback(
                response_url, command_type, parameters, help_text
            )

    def _build_message_blocks(
        self,
        command_type: str,
        parameters: Dict[str, Any],
        help_text: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """
        Build all message blocks for the parameter help message.

        Args:
            command_type: The type of command needing help
            parameters: Dictionary of parameter information
            help_text: Optional additional help text

        Returns:
            List of message blocks for Slack
        """
        title = f"Ketchup {command_type.title()} Command Help"
        message_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*"},
            }
        ]

        # Add parameter information
        if parameters:
            param_text = self._format_parameters(parameters, command_type)
            param_blocks = create_message_blocks(param_text)
            message_blocks.extend(param_blocks)

        # Add additional help text if provided
        if help_text:
            help_blocks = create_message_blocks(help_text)
            message_blocks.extend(help_blocks)

        # Add usage examples
        usage_examples = self._get_usage_examples(command_type)
        if usage_examples:
            message_blocks.append({"type": "divider"})
            example_blocks = create_message_blocks(usage_examples)
            message_blocks.extend(example_blocks)

        # Add context tooltip
        message_blocks.append(create_context_tooltip_block())

        return message_blocks

    async def _send_parameter_message(
        self,
        response_url: str,
        command_type: str,
        message_blocks: list[Dict[str, Any]],
    ) -> None:
        """
        Send the parameter help message to Slack.

        Args:
            response_url: URL to send the response to or channel ID
            command_type: The type of command for logging
            message_blocks: Pre-built message blocks to send

        Raises:
            Exception: If message sending fails
        """
        message_text = f"Help for {command_type} command"

        if response_url.startswith("http"):
            logger.info("Posting parameter help message to response URL")
            await self._posting_handler.post_message(
                response_url=response_url,
                message=message_text,
                blocks=message_blocks,
            )
        else:
            # Use as channel ID
            logger.info("Posting parameter help message to channel ID")
            await self._posting_handler.post_message(
                channel_id=response_url,
                message=message_text,
                blocks=message_blocks,
            )

    async def _handle_message_fallback(
        self,
        response_url: str,
        command_type: str,
        parameters: Dict[str, Any],
        help_text: Optional[str] = None,
    ) -> None:
        """
        Handle fallback when primary message sending fails.

        Args:
            response_url: URL to send the response to or channel ID
            command_type: The type of command needing help
            parameters: Dictionary of parameter information
            help_text: Optional additional help text
        """
        try:
            fallback_text = self._create_fallback_text(
                command_type, parameters, help_text
            )
            if response_url.startswith("http"):
                await self._posting_handler.post_message(
                    response_url=response_url, message=fallback_text
                )
            else:
                await self._posting_handler.post_message(
                    channel_id=response_url, message=fallback_text
                )
            logger.info("Sent parameter help message as text-only fallback")
        except Exception as fallback_error:
            logger.error("Text-only fallback also failed: %s", str(fallback_error))

    def _format_parameters(self, parameters: Dict[str, Any], command_type: str) -> str:
        """
        Format parameters into readable text.

        Args:
            parameters: Dictionary of parameter information
            command_type: The command type for context

        Returns:
            Formatted parameter text
        """
        if not parameters:
            return f"No specific parameters required for {command_type} command."

        param_lines = ["**Parameters:**"]

        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                description = param_info.get("description", "No description provided")
                required = param_info.get("required", False)
                default = param_info.get("default", None)

                param_line = f"• `{param_name}` - {description}"
                if required:
                    param_line += " *(required)*"
                if default is not None:
                    param_line += f" *(default: {default})*"

                param_lines.append(param_line)
            else:
                # Simple string description
                param_lines.append(f"• `{param_name}` - {param_info}")

        return "\n".join(param_lines)

    def _get_usage_examples(self, command_type: str) -> Optional[str]:
        """
        Get usage examples for different command types.

        Args:
            command_type: The command type

        Returns:
            Usage examples text or None
        """
        examples = {
            "query": (
                "**Usage Examples:**\n"
                "• `/ketchup query #channel-name What's the latest status?`\n"
                "• `/ketchup query C1234567890 Show me recent activity`\n"
                "• `/ketchup query #incident-channel Any blockers?`"
            ),
            "status": (
                "**Usage Examples:**\n"
                "• `/ketchup status #channel-name`\n"
                "• `/ketchup status C1234567890`\n"
                "• `/ketchup status #incident-channel`"
            ),
            "report": (
                "**Usage Examples:**\n"
                "• `/ketchup report #channel-name`\n"
                "• `/ketchup report C1234567890`\n"
                "• `/ketchup report #incident-channel`"
            ),
            "list": (
                "**Usage Examples:**\n"
                "• `/ketchup list` - Show all channels\n"
                "• `/ketchup list active` - Show only active channels\n"
                "• `/ketchup list archived` - Show archived channels"
            ),
            "archive": (
                "**Usage Examples:**\n"
                "• `/ketchup archive #channel-name`\n"
                "• `/ketchup archive C1234567890`"
            ),
        }

        return examples.get(command_type.lower())

    def _create_fallback_text(
        self,
        command_type: str,
        parameters: Dict[str, Any],
        help_text: Optional[str] = None,
    ) -> str:
        """
        Create simple text fallback for parameter help.

        Args:
            command_type: The command type
            parameters: Dictionary of parameter information
            help_text: Optional additional help text

        Returns:
            Fallback text
        """
        lines = [f"Help for {command_type} command:"]

        if parameters:
            param_text = self._format_parameters(parameters, command_type)
            lines.append(param_text)

        if help_text:
            lines.append(help_text)

        usage_examples = self._get_usage_examples(command_type)
        if usage_examples:
            lines.append(usage_examples)

        return "\n\n".join(lines)