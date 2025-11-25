"""
List command parameter extraction.

This module provides utilities for extracting parameters from list commands.
"""

from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    ListCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)

logger = setup_logger(__name__)


def extract_list_params(command: str, context: CommandContext) -> ListCommandParams:
    """
    Extract parameters for list commands.

    The list command currently only supports listing all channels, but in the
    future could be extended to support filtering by various criteria.

    Args:
        command: The full command string
        context: The command context (DM or public channel)

    Returns:
        Extracted list command parameters

    Raises:
        ValidationError: If parameters are invalid
    """
    parts = command.split()

    # Verify list commands can only be run in DMs
    if context != CommandContext.DIRECT_MESSAGE:
        raise ValidationError(
            "List command not allowed in public channels",
            "The `/ketchup list` command is only available in direct messages",
        )

    # Format: /ketchup list (no additional parameters)
    if len(parts) > 2:
        raise ValidationError(
            "Too many arguments for list command",
            "Use `/ketchup list` without additional arguments",
        )

    # Currently we only support listing all channels
    # Future implementation could parse additional flags to filter channels

    return ListCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.LIST,
        context=context,
        list_type="all",
    )
