"""
Status and report command parameter extraction.

This module provides utilities for extracting parameters from status and report commands.
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
    StatusReportCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)

logger = setup_logger(__name__)


def extract_status_report_params(
    command: str, context: CommandContext, incoming_channel: str
) -> StatusReportCommandParams:
    """
    Extract parameters for status/report commands.

    Args:
        command: The full command string
        context: The command context (DM or public channel)
        incoming_channel: Channel where the command was issued

    Returns:
        Extracted status/report command parameters

    Raises:
        ValidationError: If parameters are invalid
    """
    parts = command.split()
    report_type = CommandType(parts[1].lower())

    if context == CommandContext.DIRECT_MESSAGE:
        # DM format: /ketchup status|report <channel_parameter>
        # Supports: channel_id, <#channel_id|name>, #channel_name
        if len(parts) < 3:
            raise ValidationError(
                "Missing channel parameter for status|report command in DM",
                "In direct messages, use one of:\n"
                "• `/ketchup status|report C1234567890` (channel ID)\n"
                "• `/ketchup status|report <#C1234567890|channel-name>` (channel mention)\n"
                "• `/ketchup status|report #channel-name` (channel name)",
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
        # Public channel format: /ketchup status|report
        if len(parts) > 2:
            raise ValidationError(
                "Too many arguments for status|report command in public channel",
                "In public channels, use `/ketchup status|report` without additional arguments",
            )

        channel_id = incoming_channel

    return StatusReportCommandParams(
        original_command=command,
        context=context,
        command_type=report_type,
        target_channel_id=channel_id,
        report_type=cast(Literal["status", "report"], report_type.value),
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
    )
