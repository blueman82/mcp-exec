"""
Summary command parameter extraction.

This module provides utilities for extracting parameters from summary commands.
"""

from typing import Literal, cast

from packages.core.constants import (
    SLACK_CHANNEL_ID_REGEX,
    SLACK_CHANNEL_MENTION_REGEX,
    SLACK_CHANNEL_NAME_REGEX,
)
from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    SummaryCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)

logger = setup_logger(__name__)


def extract_summary_params(
    command: str, context: CommandContext, incoming_channel: str
) -> SummaryCommandParams:
    """
    Extract parameters for short/long summary commands.

    Args:
        command: The full command string
        context: The command context (DM or public channel)
        incoming_channel: Channel where the command was issued

    Returns:
        Extracted summary command parameters

    Raises:
        ValidationError: If parameters are invalid
    """
    parts = command.split()
    summary_type = CommandType(parts[1].lower())

    if context == CommandContext.DIRECT_MESSAGE:
        # DM format: /ketchup short|long <channel_id>
        if len(parts) < 3:
            if summary_type == CommandType.SHORT:
                raise ValidationError(
                    "Missing channel ID for short command in DM",
                    ":warning: 'Short' command has been replaced by Status. In direct messages, use `/ketchup status channel-id`",
                )
            elif summary_type == CommandType.LONG:
                raise ValidationError(
                    "Missing channel ID for long command in DM",
                    ":warning: 'Long' command has been replaced by Report. In direct messages, use `/ketchup report channel-id`",
                )
            else:
                raise ValidationError(
                    "Missing channel ID for summary command in DM",
                    "In direct messages, use `/ketchup status|report channel-id`",
                )

        channel_param = parts[2]

        # Validate the channel parameter format
        if not (
            SLACK_CHANNEL_ID_REGEX.match(channel_param)
            or SLACK_CHANNEL_MENTION_REGEX.match(channel_param)
            or SLACK_CHANNEL_NAME_REGEX.match(channel_param)
        ):
            raise ValidationError(
                f"Invalid channel format: {channel_param}",
                "Use one of these formats:\n"
                "• Channel ID: `C1234567890`\n"
                "• Channel mention: `<#C1234567890|channel-name>`\n"
                "• Channel name: `#channel-name`",
            )

        # Store the raw parameter - it will be resolved later in the command handler
        channel_id = channel_param
    else:
        # Public channel format: /ketchup short|long
        if len(parts) > 2:
            if summary_type == CommandType.SHORT:
                raise ValidationError(
                    "Too many arguments for short command in public channel",
                    ":warning: 'Short' command has been replaced by Status. In public channels, use `/ketchup status`",
                )
            elif summary_type == CommandType.LONG:
                raise ValidationError(
                    "Too many arguments for long command in public channel",
                    ":warning: 'Long' command has been replaced by Report. In public channels, use `/ketchup report`",
                )
            else:
                raise ValidationError(
                    "Too many arguments for short|long command in public channel",
                    ":warning: 'Short' command has been replaced by Status. In public channels, use `/ketchup status`",
                )

        channel_id = incoming_channel

    return SummaryCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=summary_type,
        context=context,
        target_channel_id=channel_id,
        summary_type=cast(Literal["short", "long"], summary_type.value),
    )
