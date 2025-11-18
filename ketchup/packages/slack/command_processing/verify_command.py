"""
verify_command.py

This module contains functions for verifying Slack command formats and
ensuring they meet the required specifications.
"""

from typing import Optional

from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import CommandParams
from packages.slack.command_processing.command_parameters.parser import (
    extract_command_params,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
    get_command_context,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


async def send_validation_error(
    user_id: str,
    channel_id: str,
    error_message: str,
    slack_posting_handler: SlackPostingHandler,
    response_url: Optional[str] = None,
) -> None:
    """
    Send a validation error message using the provided posting handler.

    Args:
        user_id: The user ID to send the message to
        channel_id: The channel ID where the message should be sent
        error_message: The error message to display to the user
        slack_posting_handler: Handler for posting messages to Slack
        response_url: Optional response URL for interactive components
    """
    logging_prefix = f"ValidationError to {user_id} in {channel_id}: "
    logger.info("%s Sending error message", logging_prefix)

    try:
        await slack_posting_handler.post_message(
            user_id=user_id,
            channel_id=channel_id,
            message=error_message,
            response_url=response_url,
        )
        logger.info("%s Error message sent successfully", logging_prefix)
    except Exception as e:
        logger.error("%s Failed to send error message: %s", logging_prefix, str(e))


async def verify_and_extract_command(
    command: str,
    user_id: str,
    incoming_channel: str,
    response_url: str,
    slack_posting_handler: SlackPostingHandler,
    channel_name: str,
) -> Optional[CommandParams]:
    """
    Verify and extract parameters from a command.

    This function validates the command string and extracts the parameters
    needed for processing. If validation fails, it sends an error message
    to the user.

    Args:
        command: The command string to parse
        user_id: Slack user ID for the requester
        incoming_channel: Channel ID where the command was received
        response_url: URL for response
        slack_posting_handler: Handler for posting messages to Slack
        channel_name: Name of the channel where the command was received

    Returns:
        CommandParams object with the extracted parameters, or None if validation failed
    """
    context = get_command_context(channel_name)
    logger.info("Command context: %s", context)

    try:
        # Extract command parameters
        params = extract_command_params(
            command, channel_name, incoming_channel, response_url
        )

        if params:
            # Command successfully parsed
            return params

    except ValidationError as error:
        # Command validation failed, send error message using provided handler
        await send_validation_error(
            user_id=user_id,
            channel_id=incoming_channel,
            error_message=error.user_message,
            slack_posting_handler=slack_posting_handler,
            response_url=response_url,
        )
        return None
    except Exception as e:
        # Unknown error occurred, send generic message using provided handler
        logger.error("Error parsing command %s: %s", command, str(e))
        await send_validation_error(
            user_id=user_id,
            channel_id=incoming_channel,
            error_message="Sorry, there was an error processing your command. Please try again.",
            slack_posting_handler=slack_posting_handler,
            response_url=response_url,
        )
        return None

    # Explicitly return None if no valid params were extracted and no exception occurred
    return None
