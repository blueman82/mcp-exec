"""
Metrics command parameter extraction.

This module provides utilities for extracting parameters from metrics commands.
"""

from datetime import datetime, timezone
from time import time

from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    MetricsCommandParams,
)
from packages.slack.command_processing.command_parameters.time_period_parser import (
    get_month_start_end,
    get_quarter_start_end,
    is_ongoing_period,
    parse_month_name,
    parse_quarter,
    parse_year,
)
from packages.slack.command_processing.command_parameters.time_period_validator import (
    validate_time_period,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)

logger = setup_logger(__name__)


def extract_metrics_params(command: str, context: CommandContext) -> MetricsCommandParams:
    """
    Extract parameters for metrics command.

    The metrics command generates a comprehensive HTML dashboard covering
    executive CSO management metrics and technical system health.

    Format:
    - /ketchup metrics (DM only) → Last 7 days
    - /ketchup metrics september 25 → Monthly
    - /ketchup metrics q1 25 → Quarterly

    Args:
        command: The full command string
        context: The command context (DM or public channel)

    Returns:
        Extracted metrics command parameters

    Raises:
        ValidationError: If command format is invalid or validation fails
    """
    # Metrics command is restricted to direct messages only for security
    if context != CommandContext.DIRECT_MESSAGE:
        raise ValidationError(
            message=f"Metrics command must be used in direct messages only (context: {context})",
            user_message="🔒 The `/ketchup metrics` command is only available in direct messages for security reasons. Please send me a DM to use this command.",
        )

    # Split command into tokens (skip "ketchup" and "metrics")
    tokens = command.strip().split()

    # Find where "metrics" appears
    try:
        metrics_index = next(i for i, t in enumerate(tokens) if t.lower() == "metrics")
        args = tokens[metrics_index + 1 :]  # Everything after "metrics"
    except StopIteration:
        args = []

    # No arguments = default 7-day mode
    if len(args) == 0:
        return _create_7_day_params(command, context)

    # Must have exactly 2 arguments (period year)
    if len(args) != 2:
        raise ValidationError(
            message=f"Invalid metrics command format: {command}",
            user_message=(
                "❌ Invalid time period format\n\n"
                "Valid formats:\n"
                "• /ketchup metrics (last 7 days)\n"
                "• /ketchup metrics september 25\n"
                "• /ketchup metrics q1 25"
            ),
        )

    period_arg = args[0]
    year_arg = args[1]

    # Parse year
    year = parse_year(year_arg)
    if year is None:
        raise ValidationError(
            message=f"Invalid year: {year_arg}",
            user_message=(
                f"❌ Invalid year '{year_arg}'\n\n" "Year must be 2-digit (25) or 4-digit (2025)"
            ),
        )

    # Try parsing as quarter first
    quarter = parse_quarter(period_arg)
    if quarter is not None:
        return _create_quarterly_params(command, context, quarter, year)

    # Try parsing as month
    month = parse_month_name(period_arg)
    if month is not None:
        return _create_monthly_params(command, context, month, year)

    # Couldn't parse period
    raise ValidationError(
        message=f"Invalid time period: {period_arg}",
        user_message=(
            f"❌ Invalid time period '{period_arg}'\n\n"
            "Valid formats:\n"
            "• /ketchup metrics (last 7 days)\n"
            "• /ketchup metrics september 25\n"
            "• /ketchup metrics q1 25"
        ),
    )


def _create_7_day_params(command: str, context: CommandContext) -> MetricsCommandParams:
    """Create parameters for 7-day default mode."""
    now = datetime.now(timezone.utc)
    start = datetime.fromtimestamp(int(time()) - (7 * 24 * 60 * 60), tz=timezone.utc)

    return MetricsCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.METRICS,
        context=context,
        time_period_type="7_days",
        month=None,
        quarter=None,
        year=now.year,
        start_date=start,
        end_date=now,
        is_partial=False,
    )


def _create_monthly_params(
    command: str, context: CommandContext, month: int, year: int
) -> MetricsCommandParams:
    """Create parameters for monthly mode."""
    # Calculate date range
    start, end = get_month_start_end(year, month)

    # Check if ongoing BEFORE validation (ongoing periods have future end dates)
    is_partial = is_ongoing_period(start, end)
    if is_partial:
        # Adjust end to current time for ongoing periods
        end = datetime.now(timezone.utc)

    # Validate (now with adjusted end date for ongoing periods)
    is_valid, error_msg = validate_time_period(year, end)
    if not is_valid:
        raise ValidationError(
            message=f"Invalid time period: {month}/{year}",
            user_message=error_msg,
        )

    return MetricsCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.METRICS,
        context=context,
        time_period_type="monthly",
        month=month,
        quarter=None,
        year=year,
        start_date=start,
        end_date=end,
        is_partial=is_partial,
    )


def _create_quarterly_params(
    command: str, context: CommandContext, quarter: int, year: int
) -> MetricsCommandParams:
    """Create parameters for quarterly mode."""
    # Calculate date range
    start, end = get_quarter_start_end(year, quarter)

    # Check if ongoing BEFORE validation (ongoing periods have future end dates)
    is_partial = is_ongoing_period(start, end)
    if is_partial:
        # Adjust end to current time for ongoing periods
        end = datetime.now(timezone.utc)

    # Validate (now with adjusted end date for ongoing periods)
    is_valid, error_msg = validate_time_period(year, end)
    if not is_valid:
        raise ValidationError(
            message=f"Invalid time period: Q{quarter} {year}",
            user_message=error_msg,
        )

    return MetricsCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.METRICS,
        context=context,
        time_period_type="quarterly",
        month=None,
        quarter=quarter,
        year=year,
        start_date=start,
        end_date=end,
        is_partial=is_partial,
    )
