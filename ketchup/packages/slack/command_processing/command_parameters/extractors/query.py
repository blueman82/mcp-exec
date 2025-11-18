"""
Query command parameter extraction.

This module provides utilities for extracting parameters from query commands.
"""

from packages.core.constants import (
    SLACK_CHANNEL_ID_REGEX,
    SLACK_CHANNEL_MENTION_REGEX,
    SLACK_CHANNEL_NAME_REGEX,
)
from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    QueryCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)

logger = setup_logger(__name__)


def extract_query_params(
    command: str, context: CommandContext, incoming_channel: str
) -> QueryCommandParams:
    """
    Extract parameters for query commands.

    Args:
        command: The full command string
        context: The command context (DM or public channel)
        incoming_channel: Channel where the command was issued

    Returns:
        Extracted query command parameters

    Raises:
        ValidationError: If parameters are invalid
    """
    parts = command.split()

    if context == CommandContext.DIRECT_MESSAGE:
        # DM format: /ketchup query <channel_parameter> <question>
        # Supports: channel_id, <#channel_id|name>, #channel_name
        if len(parts) < 3:
            raise ValidationError(
                "Missing channel parameter for query command in DM",
                "In direct messages, use one of:\n"
                "• `/ketchup query C1234567890 your question` (channel ID)\n"
                "• `/ketchup query <#C1234567890|channel-name> your question` (channel mention)\n"
                "• `/ketchup query #channel-name your question` (channel name)",
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

        if len(parts) < 4:
            raise ValidationError(
                "Missing question for query command",
                "Please provide a question after the channel parameter: `/ketchup query <channel_parameter> <question>`",
            )

        # Store the raw parameter - it will be resolved later in the command handler
        channel_id = channel_param
        query_text = " ".join(parts[3:])
    else:
        # Public channel format: /ketchup query <question>
        if len(parts) < 3:
            raise ValidationError(
                "Missing question for query command",
                "Please provide a question: `/ketchup query <question>`",
            )

        # Check for mistakenly included channel parameter
        if (
            SLACK_CHANNEL_ID_REGEX.match(parts[2])
            or SLACK_CHANNEL_MENTION_REGEX.match(parts[2])
            or SLACK_CHANNEL_NAME_REGEX.match(parts[2])
        ):
            raise ValidationError(
                "Channel parameter should not be included in public channel query",
                "In channels, use `/ketchup query <question>` without specifying a channel",
            )

        channel_id = incoming_channel
        query_text = " ".join(parts[2:])

    return QueryCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id=channel_id,  # Channel to query about (extracted from command or incoming channel)
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.QUERY,
        context=context,
        query_text=query_text,
        target_channel_id=channel_id,  # Channel to query about (extracted from command)
    )
