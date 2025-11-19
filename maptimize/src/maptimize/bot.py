"""Slack bot application using slack-bolt framework.

Initializes and configures the Slack bot application instance with
event handlers, middleware, and Socket Mode connection for real-time
event delivery.

The bot uses Socket Mode which provides a persistent WebSocket connection
without requiring the application to expose a public HTTP endpoint.
"""

from slack_bolt.app import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from maptimize.config import get_slack_tokens
from maptimize.handlers import (
    handle_app_mention as process_app_mention,
    handle_message as process_message,
)

__all__ = [
    "app",
    "handle_app_mention",
    "handle_slash_command",
    "create_socket_handler",
]


# Get tokens from AWS Secrets Manager
BOT_TOKEN, APP_TOKEN = get_slack_tokens()

# Initialize slack-bolt app with token validation disabled for testing
app = App(token=BOT_TOKEN, token_verification_enabled=False)


@app.event("app_mention")
def handle_app_mention(body, say):
    """Handle app mention events.

    Called when the bot is mentioned in a message. Routes the event
    to the appropriate handler for processing.

    Args:
        body: Event payload from Slack
        say: Callable for sending messages to the channel
    """
    process_app_mention(body, say)


@app.command("/maptimize")
def handle_slash_command(ack, body, say):
    """Handle /maptimize slash command.

    Called when user executes the /maptimize slash command.
    Acknowledges the command immediately and routes to handler.

    Args:
        ack: Callable to acknowledge command receipt
        body: Command payload from Slack
        say: Callable for sending messages
    """
    ack()
    process_message(body, say)


def create_socket_handler():
    """Create SocketModeHandler for persistent WebSocket connection.

    Creates and returns a SocketModeHandler instance configured with
    the app and app token. The handler manages the WebSocket connection
    with automatic reconnection using exponential backoff.

    Returns:
        SocketModeHandler: Configured handler for Socket Mode connection

    Example:
        handler = create_socket_handler()
        handler.start()
    """
    return SocketModeHandler(app, APP_TOKEN)


if __name__ == "__main__":
    # Start Socket Mode handler
    handler = create_socket_handler()
    handler.start()
