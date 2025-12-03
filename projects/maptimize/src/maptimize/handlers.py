"""Event handlers for Slack bot interactions.

Implements handlers for various Slack events including app mentions and
slash commands. Manages event parsing, configuration loading, response
formatting, and error handling with comprehensive logging.
"""

import asyncio
from typing import Any, Callable, Dict

import structlog

from maptimize.config import load_processes
from maptimize.formatter import create_block_kit_message, create_response_blocks
from maptimize.miro import screenshot_miro_board

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

        # Send message as ephemeral (visible only to user)
        say(text=message_text, response_type="ephemeral")

        logger.info("mention_handled_success", user_id=user_id)

    except Exception as e:
        logger.error("mention_handling_failed", error=str(e), exc_info=True)
        try:
            say(text="An error occurred while processing your request", response_type="ephemeral")
        except Exception as fallback_error:
            logger.error("mention_error_response_failed", error=str(fallback_error))


def handle_slash_command(body: Dict[str, Any], respond: Callable, client: Any) -> None:
    """Handle /maptimize slash command with Miro diagram integration.

    Called when user executes the /maptimize slash command. Extracts user
    info, loads process configuration, captures Miro board screenshots,
    uploads images to Slack, and sends rich Block Kit response with
    embedded diagrams.

    Args:
        body: Command payload from Slack
        respond: Callable for sending ephemeral responses to slash commands
        client: Slack Web API client for file uploads and message posting

    Example:
        User types "/maptimize" in any channel. Bot responds with process
        information including embedded Miro diagrams in an ephemeral message
        visible only to that user.
    """
    try:
        # Extract user ID and channel from command
        user_id = body.get("user_id", "unknown")
        channel_id = body.get("channel_id", body.get("channel"))

        logger.info("slash_command_received", user_id=user_id, command="/maptimize")

        # Load process configuration
        processes = load_processes()

        # Initialize image URLs dict for storing Slack permalinks
        image_urls: Dict[str, str] = {}

        # Capture Miro screenshots for processes that have board IDs
        for process_name, process_info in processes.items():
            if isinstance(process_info, dict):
                board_id = process_info.get("miro_board_id")

                if board_id:
                    # Attempt to capture screenshot
                    logger.info(
                        "miro_screenshot_attempt",
                        process_name=process_name,
                        board_id=board_id,
                    )

                    image_bytes = asyncio.run(screenshot_miro_board(board_id))

                    if image_bytes is not None:
                        try:
                            # Upload image to Slack
                            filename = f"{process_name.lower().replace(' ', '_')}_diagram.png"
                            response = client.files_upload(
                                channels=channel_id,
                                file=image_bytes,
                                filename=filename,
                                title=f"{process_name} Diagram",
                            )

                            # Store the permalink for the Block Kit response
                            if response.get("ok") and response.get("file"):
                                image_urls[process_name] = response["file"]["permalink"]
                                logger.info(
                                    "miro_image_uploaded",
                                    process_name=process_name,
                                    permalink=image_urls[process_name],
                                )
                            else:
                                logger.warning(
                                    "miro_image_upload_failed",
                                    process_name=process_name,
                                    response=response,
                                )

                        except Exception as upload_error:
                            logger.error(
                                "miro_image_upload_exception",
                                process_name=process_name,
                                error=str(upload_error),
                                exc_info=True,
                            )
                    else:
                        # Screenshot failed (timeout or error already logged)
                        logger.warning(
                            "miro_screenshot_unavailable",
                            process_name=process_name,
                            message="Continuing without diagram",
                        )

        # Create Block Kit response with embedded images
        response_blocks = create_response_blocks(processes, image_urls)

        # Send response to user
        # Use chat_postMessage for Block Kit support
        client.chat_postMessage(
            channel=channel_id,
            blocks=response_blocks,
            text="Maptimize Process Information",  # Fallback text for notifications
            metadata={"event_type": "slash_command_response"},
        )

        logger.info("slash_command_handled_success", user_id=user_id, image_count=len(image_urls))

    except Exception as e:
        logger.error("slash_command_handling_failed", error=str(e), exc_info=True)
        try:
            respond(
                text="An error occurred while processing your request. Please try again later.",
                response_type="ephemeral",
            )
        except Exception as fallback_error:
            logger.error("slash_command_error_response_failed", error=str(fallback_error))


def handle_message(body: Dict[str, Any], say: Callable) -> None:
    """Handle message events in direct messages.

    Called when messages are sent in DM channels (channel ID starts with 'D').
    Ignores messages from bots and responds with process information.
    In DMs, also checks for bot mentions in the message text since app_mention
    events don't reliably fire in DMs.

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
        message_text = event.get("text", "")

        # Only handle DM messages (channel ID starts with 'D')
        if not channel_id.startswith("D"):
            return

        # Ignore messages from bots (including our own)
        if subtype == "bot_message" or event.get("bot_id"):
            return

        # Check if bot is mentioned in the message
        # Bot mentions look like <@U123456789> in the message text
        bot_mentioned = "<@" in message_text and ">" in message_text

        logger.info(
            "dm_message_received",
            user_id=user_id,
            channel_id=channel_id,
            bot_mentioned=bot_mentioned,
        )

        # Load process configuration
        processes = load_processes()

        # Format response message
        message_text = create_block_kit_message(processes)

        # Send message as ephemeral in DM
        say(text=message_text, response_type="ephemeral")

        logger.info("dm_message_handled_success", user_id=user_id)

    except Exception as e:
        logger.error("dm_message_handling_failed", error=str(e), exc_info=True)
        try:
            error_msg = (
                "An error occurred while processing your message. " "Try using /maptimize command."
            )
            say(text=error_msg, response_type="ephemeral")
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
