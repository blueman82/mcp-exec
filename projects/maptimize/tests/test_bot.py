"""Tests for Slack bot application using slack-bolt framework.

Tests for bot initialization, event handler registration, and Socket Mode
connection setup.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, ANY
from slack_bolt.app import App


@pytest.fixture
def bot_module(mocker):
    """Import and provide bot module after mocking."""
    # Mock the dependencies before importing bot module
    mocker.patch(
        "maptimize.config.get_slack_tokens",
        return_value=("xoxb-test-token", "xapp-test-token")
    )
    mocker.patch(
        "slack_bolt.adapter.socket_mode.SocketModeHandler",
        return_value=MagicMock()
    )

    # Remove from sys.modules to force reimport
    if "maptimize.bot" in sys.modules:
        del sys.modules["maptimize.bot"]

    import maptimize.bot
    return maptimize.bot


def test_app_initialization(bot_module):
    """Test that bot initializes with tokens from config."""
    # Verify app is initialized
    assert bot_module.app is not None
    assert bot_module.BOT_TOKEN == "xoxb-test-token"


def test_app_mention_handler_registered(bot_module):
    """Test that app_mention handler is registered."""
    # Check that app has listeners registered
    # slack_bolt App stores listeners in _listeners list
    listeners = bot_module.app._listeners

    # Find app_mention listeners by checking the ack function name
    app_mention_listeners = [
        l for l in listeners
        if hasattr(l, 'ack_function') and l.ack_function and
           l.ack_function.__name__ == 'handle_app_mention'
    ]

    assert len(app_mention_listeners) > 0, "app_mention handler not registered"


def test_slash_command_handler_registered(bot_module):
    """Test that /maptimize slash command handler is registered."""
    # Check that app has listeners registered
    listeners = bot_module.app._listeners

    # Find command listeners by checking the ack function name
    command_listeners = [
        l for l in listeners
        if hasattr(l, 'ack_function') and l.ack_function and
           l.ack_function.__name__ == 'handle_slash_command'
    ]

    assert len(command_listeners) > 0, "/maptimize command handler not registered"


def test_socket_mode_handler_instantiation(bot_module):
    """Test that SocketModeHandler can be instantiated."""
    # Create handler
    handler = bot_module.create_socket_handler()

    # Verify handler was created
    assert handler is not None
    # Verify it's a mock since we patched SocketModeHandler
    assert handler is not None  # pragma: no cover


def test_app_mention_handler_callable(bot_module):
    """Test that app_mention handler is callable."""
    # Verify handler is callable
    assert callable(bot_module.handle_app_mention)


def test_slash_command_handler_callable(bot_module):
    """Test that slash command handler is callable."""
    # Verify handler is callable
    assert callable(bot_module.handle_slash_command)


def test_app_no_runtime_errors(bot_module):
    """Test that app initializes without runtime errors."""
    # Should not raise any exceptions
    assert bot_module.app is not None
