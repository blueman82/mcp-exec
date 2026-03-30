"""
Command parameter parsing utilities.

This module provides utilities for parsing and routing commands to appropriate extractors.
"""

from typing import Any, Callable, Dict, Optional, cast

from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.extractors.access import (
    extract_access_params,
)
from packages.slack.command_processing.command_parameters.extractors.archive import (
    extract_archive_params,
)
from packages.slack.command_processing.command_parameters.extractors.feature import (
    extract_feature_params,
)
from packages.slack.command_processing.command_parameters.extractors.list import (
    extract_list_params,
)
from packages.slack.command_processing.command_parameters.extractors.metrics import (
    extract_metrics_params,
)
from packages.slack.command_processing.command_parameters.extractors.query import (
    extract_query_params,
)
from packages.slack.command_processing.command_parameters.extractors.status_report import (
    extract_status_report_params,
)
from packages.slack.command_processing.command_parameters.models import (
    CommandParams,
    CommandType,
    StatusReportCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
    get_command_context,
)

logger = setup_logger(__name__)


def extract_command_type(command: str) -> Optional[CommandType]:
    """
    Extract command type from the command string.

    Args:
        command: The full command string

    Returns:
        The command type if recognized, None otherwise
    """
    parts = command.split()
    if len(parts) < 2 or parts[0] != "/ketchup":
        return None

    subcommand = parts[1].lower()
    try:
        return CommandType(subcommand)
    except ValueError:
        return None


def extract_command_params(
    command: str,
    channel_name: Optional[str],
    incoming_channel: str,
    response_url: Optional[str] = None,
) -> CommandParams:
    """
    Extract parameters from a command string.

    Args:
        command: The full command string
        channel_name: The name of the channel where command was issued
        incoming_channel: The channel ID where command was issued
        response_url: URL for response from Slack

    Returns:
        The extracted command parameters

    Raises:
        ValidationError: If command validation fails
    """
    # Get context from channel name
    context = get_command_context(channel_name)

    # Extract command type
    command_type = extract_command_type(command)
    if not command_type:
        user_help_text = """Invalid command. Use `/ketchup` to see available commands.
Please use one of the following:
`/ketchup access` - Check your access status or request access to Ketchup
`/ketchup list` - List all channels that Ketchup is a member of
`/ketchup status <Channel ID>` - Get the current status of the incident
`/ketchup report <Channel ID>` - Get detailed report of the incident
`/ketchup query <Channel ID> <question>` - Ask a query
`/ketchup archive <days>` - Retreive archived channels from the last X days (1-180)
"""
        raise ValidationError(
            message=f"Invalid command type extracted from: {command}",
            user_message=user_help_text,
        )

    # Map command types to their extraction functions
    def _extract_deprecated_short_long() -> StatusReportCommandParams:
        """Extract params for deprecated short/long commands, preserving original command_type."""
        # Re-use status_report extractor with the equivalent command
        mapped = "status" if command_type == CommandType.SHORT else "report"
        rewritten = command.replace(f" {command_type.value} ", f" {mapped} ", 1)
        params_obj = extract_status_report_params(rewritten, context, incoming_channel)
        # Override command_type back to SHORT/LONG so the router can detect and redirect
        params_obj.command_type = command_type  # type: ignore[assignment]
        params_obj.original_command = command  # Keep original command text
        return params_obj

    extractors: Dict[CommandType, Callable[[], CommandParams]] = {
        CommandType.SHORT: _extract_deprecated_short_long,
        CommandType.LONG: _extract_deprecated_short_long,
        CommandType.QUERY: lambda: extract_query_params(command, context, incoming_channel),
        CommandType.STATUS: lambda: extract_status_report_params(
            command, context, incoming_channel
        ),
        CommandType.REPORT: lambda: extract_status_report_params(
            command, context, incoming_channel
        ),
        CommandType.ARCHIVE: lambda: extract_archive_params(command, context),
        CommandType.LIST: lambda: extract_list_params(command, context),
        CommandType.ACCESS: lambda: extract_access_params(command, context),
        CommandType.FEATURE: lambda: extract_feature_params(command, context),
        CommandType.METRICS: lambda: extract_metrics_params(command, context),
    }

    # Get the appropriate extractor and extract parameters
    extractor = extractors.get(command_type)
    if not extractor:
        raise ValidationError(
            f"Invalid command: {command}. Available commands: ",
            f"Unsupported command: `{command}`. Use `/ketchup` to see available commands.",
        )

    params = extractor()

    # Add response_url to params if params is not None
    if params:
        # Cast to Any to satisfy mypy
        cast(Any, params).response_url = response_url

    return params
