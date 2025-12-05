"""
Archive command parameter extraction.

This module provides utilities for extracting parameters from archive commands.
"""

from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import (
    ArchiveCommandParams,
    CommandContext,
    CommandType,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)

logger = setup_logger(__name__)


def extract_archive_params(command: str, context: CommandContext) -> ArchiveCommandParams:
    """
    Extract parameters for archive commands.

    Args:
        command: The full command string
        context: The command context (DM or public channel)

    Returns:
        Extracted archive command parameters

    Raises:
        ValidationError: If parameters are invalid
    """
    parts = command.split()

    if context != CommandContext.DIRECT_MESSAGE:
        raise ValidationError(
            "Archive command not allowed in public channels",
            "The `/ketchup archive` command is only available in direct messages",
        )

    # DM format: /ketchup archive <days>
    if len(parts) < 3:
        raise ValidationError(
            "Missing days parameter for archive command",
            "Please specify the number of days: `/ketchup archive <days>`",
        )

    if not parts[2].isdigit():
        raise ValidationError(
            f"Invalid days value: {parts[2]} is not a number",
            f"Invalid days value: '{parts[2]}' is not a valid number",
        )

    days = int(parts[2])
    if not (1 <= days <= 180):
        raise ValidationError(
            f"Days value out of range: {days}",
            f"Number of days must be between 1 and 180, got {days}",
        )

    return ArchiveCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.ARCHIVE,
        context=context,
        archive_days=days,
    )
