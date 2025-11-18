"""
Command validation utilities.

This module provides utilities for validating command parameters.
"""

from typing import Optional

from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import CommandContext

logger = setup_logger(__name__)


class ValidationError(Exception):
    """Exception raised when command validation fails."""

    def __init__(self, message: str, user_message: str):
        """
        Initialize validation error.

        Args:
            message: Technical error message for logging
            user_message: User-friendly message to display in Slack
        """
        self.message = message
        self.user_message = user_message
        super().__init__(message)


def get_command_context(channel_name: Optional[str]) -> CommandContext:
    """
    Determine command context based on channel name.

    Args:
        channel_name: The name of the channel where command was issued

    Returns:
        The command context (DM or public channel)
    """
    return (
        CommandContext.DIRECT_MESSAGE
        if channel_name == "directmessage"
        else CommandContext.PUBLIC_CHANNEL
    )
