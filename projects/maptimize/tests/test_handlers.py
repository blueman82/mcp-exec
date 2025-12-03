"""Tests for Slack bot event handlers.

Tests for handle_app_mention and handle_slash_command event handlers,
including event parsing, configuration loading, response formatting,
and error handling.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_mention_event():
    """Provide mock app_mention event."""
    return {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@U_BOT> hello",
            "ts": "1234567890.000001",
            "channel": "C123456",
        },
        "team_id": "T123456",
    }


@pytest.fixture
def mock_command_event():
    """Provide mock slash command event."""
    return {
        "type": "slash_commands",
        "command": "/maptimize",
        "user_id": "U123456",
        "team_id": "T123456",
        "channel_id": "C123456",
        "response_url": "https://hooks.slack.com/commands/...",
    }


@pytest.fixture
def mock_say():
    """Provide mock say callable."""
    return MagicMock()


@pytest.fixture
def mock_ack():
    """Provide mock ack callable."""
    return MagicMock()


@pytest.fixture
def mock_respond():
    """Provide mock respond callable for slash commands."""
    return MagicMock()


@pytest.fixture
def mock_slack_client():
    """Provide mock Slack Web API client."""
    client = MagicMock()
    client.files_upload = MagicMock(
        return_value={
            "ok": True,
            "file": {
                "permalink": "https://files.slack.com/files/T123/F123/image.png",
                "id": "F123",
            },
        }
    )
    client.chat_postMessage = MagicMock(return_value={"ok": True})
    return client


@pytest.fixture
def mock_screenshot_bytes():
    """Return sample PNG bytes."""
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class TestHandleAppMention:
    """Tests for handle_app_mention handler."""

    def test_handle_app_mention_success(self, mock_mention_event, mock_say):
        """Test successful app_mention handling."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            # Setup mock to return process config
            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            # Call handler
            handle_app_mention(mock_mention_event, mock_say)

            # Verify say was called with ephemeral response
            mock_say.assert_called_once()
            call_kwargs = mock_say.call_args[1]
            assert call_kwargs.get("response_type") == "ephemeral"
            assert "text" in call_kwargs
            assert call_kwargs["text"] is not None

    def test_handle_app_mention_extracts_user_id(self, mock_mention_event, mock_say):
        """Test that handler extracts user ID from event."""
        with patch("maptimize.handlers.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            handle_app_mention(mock_mention_event, mock_say)

            # Verify load_processes was called
            mock_load.assert_called_once()

    def test_handle_app_mention_handles_missing_event_key(self, mock_say):
        """Test error handling for missing event key."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            # Event without 'event' key
            invalid_event = {"type": "event_callback"}

            handle_app_mention(invalid_event, mock_say)

            # Should handle gracefully and still send ephemeral response
            mock_say.assert_called_once()
            call_kwargs = mock_say.call_args[1]
            assert call_kwargs.get("response_type") == "ephemeral"

    def test_handle_app_mention_loads_processes(self, mock_mention_event, mock_say):
        """Test that handler loads process configuration."""
        with patch("maptimize.handlers.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            handle_app_mention(mock_mention_event, mock_say)

            mock_load.assert_called_once()

    def test_handle_app_mention_config_load_failure(self, mock_mention_event, mock_say):
        """Test handling of config load failures."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            # Simulate config load failure
            mock_load.side_effect = RuntimeError("Failed to load config")

            handle_app_mention(mock_mention_event, mock_say)

            # Should still send ephemeral error message
            mock_say.assert_called_once()
            call_kwargs = mock_say.call_args[1]
            assert call_kwargs.get("response_type") == "ephemeral"

    def test_handle_app_mention_with_empty_processes(self, mock_mention_event, mock_say):
        """Test handling with empty process configuration."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            mock_load.return_value = {}

            handle_app_mention(mock_mention_event, mock_say)

            # Should still respond gracefully
            mock_say.assert_called_once()
            call_kwargs = mock_say.call_args[1]
            assert call_kwargs.get("response_type") == "ephemeral"

    def test_handle_app_mention_say_failure_handled(self, mock_mention_event, mock_say):
        """Test that say() failure is handled gracefully."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            # Make say raise an exception
            mock_say.side_effect = Exception("Slack API error")

            # Should not raise
            handle_app_mention(mock_mention_event, mock_say)


class TestHandlerLogging:
    """Tests for handler logging behavior."""

    def test_handle_mention_logs_event(self, mock_mention_event, mock_say):
        """Test that mention events are logged."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_app_mention

            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            # Just verify it runs without error
            handle_app_mention(mock_mention_event, mock_say)
            mock_say.assert_called_once()

    def test_handle_command_logs_event(self, mock_command_event, mock_respond, mock_slack_client):
        """Test that command events are logged."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_slash_command

            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            # Just verify it runs without error
            handle_slash_command(mock_command_event, mock_respond, mock_slack_client)
            mock_slack_client.chat_postMessage.assert_called_once()
