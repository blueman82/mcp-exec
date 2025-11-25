"""
Access command parameter extraction.

This module provides utilities for extracting parameters from access commands.
"""

from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import (
    AccessCommandParams,
    CommandContext,
    CommandType,
)

logger = setup_logger(__name__)


def extract_access_params(command: str, context: CommandContext) -> AccessCommandParams:
    """
    Extract parameters for access command.

    The access command allows users to check their access status and request access
    if they don't have it. It works in both DMs and channels.

    Format: /ketchup access

    Args:
        command: The full command string
        context: The command context (DM or public channel)

    Returns:
        Extracted access command parameters
    """
    # Access command is simple - no additional parameters needed
    # Works in both DMs and channels

    return AccessCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.ACCESS,
        context=context,
    )
