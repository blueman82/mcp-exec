"""Event handlers for Slack bot interactions.

Implements handlers for various Slack events including app mentions and
slash commands. Manages event parsing, configuration loading, response
formatting, and error handling with comprehensive logging.
"""

from typing import Any, Callable, Dict

import structlog

from maptimize.config import load_processes
from maptimize.formatter import create_block_kit_message

__all__ = [
    "handle_app_mention",
    "handle_message",
    "handle_shortcut",
    "handle_slash_command",
    "register_handlers",
]

logger = structlog.get_logger(__name__)


def handle_app_mention(body: Dict[str, Any], say: Callable) -> None:
    """Handle app mention events.

    Called when the bot is mentioned in a message. Extracts user info,
    loads process configuration, formats response, and sends ephemeral
    message (visible only to the user).

    Args:
        body: Event payload from Slack
        say: Callable for sending messages to the channel

    Example:
        The handler processes mentions like "@maptimize show processes"
        and responds with process information in an ephemeral message.
    """
    try:
        # Extract user ID from event
        event = body.get("event", {})
        user_id = event.get("user", "unknown")

        logger.info("mention_received", user_id=user_id)

        # Load process configuration
        processes = load_processes()

        # Format response message
        message_text = create_block_kit_message(processes)

        # Send message to channel
        say(text=message_text)

        logger.info("mention_handled_success", user_id=user_id)

    except Exception as e:
        logger.error("mention_handling_failed", error=str(e), exc_info=True)
        try:
            say(text="An error occurred while processing your request")
        except Exception as fallback_error:
            logger.error("mention_error_response_failed", error=str(fallback_error))


def handle_slash_command(body: Dict[str, Any], respond: Callable) -> None:
    """Handle /maptimize slash command.

    Called when user executes the /maptimize slash command. Extracts user
    info, loads process configuration, formats response, and sends ephemeral
    message (visible only to the user).

    Args:
        body: Command payload from Slack
        respond: Callable for sending ephemeral responses to slash commands

    Example:
        User types "/maptimize" in any channel. Bot responds with process
        information in an ephemeral message visible only to that user.
    """
    try:
        # Extract user ID from command
        user_id = body.get("user_id", "unknown")

        logger.info("slash_command_received", user_id=user_id, command="/maptimize")

        # Load process configuration
        processes = load_processes()

        # Format response message
        message_text = create_block_kit_message(processes)

        # Send ephemeral response (visible only to user who invoked the command)
        respond(text=message_text, response_type="ephemeral")

        logger.info("slash_command_handled_success", user_id=user_id)

    except Exception as e:
        logger.error("slash_command_handling_failed", error=str(e), exc_info=True)
        try:
            respond(text="An error occurred while processing your request", response_type="ephemeral")
        except Exception as fallback_error:
            logger.error("slash_command_error_response_failed", error=str(fallback_error))


def handle_message(body: Dict[str, Any], say: Callable) -> None:
    """Handle message events in direct messages.

    Called when messages are sent in DM channels (channel ID starts with 'D').
    Ignores messages from bots and responds with process information.

    Args:
        body: Event payload from Slack
        say: Callable for sending messages to the channel
    """
    try:
        # Extract event details
        event = body.get("event", {})
        channel_id = event.get("channel", "")
        user_id = event.get("user", "unknown")
        subtype = event.get("subtype")
        
        # Only handle DM messages (channel ID starts with 'D')
        if not channel_id.startswith("D"):
            return
        
        # Ignore messages from bots (including our own)
        if subtype == "bot_message" or event.get("bot_id"):
            return
        
        logger.info("dm_message_received", user_id=user_id, channel_id=channel_id)
        
        # Load process configuration
        processes = load_processes()
        
        # Format response message
        message_text = create_block_kit_message(processes)
        
        # Send message in DM
        say(text=message_text)
        
        logger.info("dm_message_handled_success", user_id=user_id)
        
    except Exception as e:
        logger.error("dm_message_handling_failed", error=str(e), exc_info=True)
        try:
            say(text="An error occurred while processing your message. Try using /maptimize command.")
        except Exception as fallback_error:
            logger.error("dm_message_error_response_failed", error=str(fallback_error))


def handle_shortcut(body: Dict[str, Any], ack: Callable, say: Callable) -> None:
    """Handle shortcut events.

    Called when shortcuts are triggered.

    Args:
        body: Shortcut payload from Slack
        ack: Callable to acknowledge shortcut receipt
        say: Callable for sending messages
    """
    pass


def register_handlers() -> None:
    """Register all event handlers with the app.

    This is a placeholder for centralized handler registration
    if needed in the future.
    """
    pass
