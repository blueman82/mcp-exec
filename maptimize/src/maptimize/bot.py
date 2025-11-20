"""Slack bot application using slack-bolt framework.

Initializes and configures the Slack bot application instance with
event handlers, middleware, and Socket Mode connection for real-time
event delivery.

The bot uses Socket Mode which provides a persistent WebSocket connection
without requiring the application to expose a public HTTP endpoint.
"""

import logging
from typing import Any, Callable

from slack_bolt.adapter.socket_mode import (  # type: ignore[import-not-found]
    SocketModeHandler,
)
from slack_bolt.app import App  # type: ignore[import-not-found]

from maptimize.config import get_slack_tokens

# Enable logging for slack-bolt
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("slack_bolt").setLevel(logging.DEBUG)
logging.getLogger("slack_sdk").setLevel(logging.DEBUG)
from maptimize.handlers import (
    handle_app_mention as process_app_mention,
)
from maptimize.handlers import (
    handle_slash_command as process_slash_command,
)

__all__ = [
    "app",
    "handle_app_mention",
    "handle_slash_command",
    "create_socket_handler",
]


# Get tokens and signing secret from AWS Secrets Manager
BOT_TOKEN, APP_TOKEN, SIGNING_SECRET = get_slack_tokens()

# Initialize slack-bolt app with request signature verification enabled
# The signing secret is required to verify that incoming requests actually came from Slack
# This prevents attackers from forging Slack events and impersonating the bot
app = App(
    token=BOT_TOKEN,
    signing_secret=SIGNING_SECRET,
    token_verification_enabled=True,
)


@app.event("app_mention")
def handle_app_mention(body: Any, say: Callable[..., Any]) -> None:
    """Handle app mention events.

    Called when the bot is mentioned in a message. Routes the event
    to the appropriate handler for processing.

    Args:
        body: Event payload from Slack
        say: Callable for sending messages to the channel
    """
    try:
        print("DEBUG: app_mention event received", flush=True)
        process_app_mention(body, say)
        print("DEBUG: app_mention handled successfully", flush=True)
    except Exception as e:
        print(f"ERROR: app_mention handler failed: {e}", flush=True)
        import traceback
        traceback.print_exc()


@app.command("/maptimize")
def handle_slash_command(ack: Callable[[], None], body: Any, say: Callable[..., Any]) -> None:
    """Handle /maptimize slash command.

    Called when user executes the /maptimize slash command.
    Acknowledges the command immediately and routes to handler.

    Args:
        ack: Callable to acknowledge command receipt
        body: Command payload from Slack
        say: Callable for sending messages
    """
    try:
        print("DEBUG: slash_command /maptimize received", flush=True)
        ack()
        process_slash_command(body, say)
        print("DEBUG: slash_command handled successfully", flush=True)
    except Exception as e:
        print(f"ERROR: slash_command handler failed: {e}", flush=True)
        import traceback
        traceback.print_exc()


def create_socket_handler() -> SocketModeHandler:
    """Create SocketModeHandler for persistent WebSocket connection.

    Creates and returns a SocketModeHandler instance configured with
    the app and app token. The handler manages the WebSocket connection
    with automatic reconnection using exponential backoff.

    Returns:
        Configured handler for Socket Mode connection.

    Example:
        handler = create_socket_handler()
        handler.start()
    """
    return SocketModeHandler(app, APP_TOKEN)


if __name__ == "__main__":
    # Start Socket Mode handler
    try:
        print("Starting Socket Mode handler...", flush=True)
        handler = create_socket_handler()
        print("Socket Mode handler created, starting connection...", flush=True)
        print(f"APP_TOKEN present: {bool(APP_TOKEN)}", flush=True)
        handler.start()
        print("Socket Mode handler started", flush=True)
    except Exception as e:
        print(f"ERROR starting Socket Mode handler: {e}", flush=True)
        import traceback
        traceback.print_exc()
