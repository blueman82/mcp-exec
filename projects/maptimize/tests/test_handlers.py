"""Tests for Slack bot event handlers.

Tests for handle_app_mention and handle_slash_command event handlers,
including event parsing, configuration loading, response formatting,
and error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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
    client.files_upload = MagicMock(return_value={
        "ok": True,
        "file": {
            "permalink": "https://files.slack.com/files/T123/F123/image.png",
            "id": "F123",
        }
    })
    client.chat_postMessage = MagicMock(return_value={"ok": True})
    return client


@pytest.fixture
def mock_screenshot_bytes():
    """Return sample PNG bytes."""
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'


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


@pytest.mark.asyncio
class TestHandleSlashCommandAsync:
    """Tests for async handle_slash_command with Miro integration."""

    async def test_async_slash_command_with_miro_success(
        self,
        mock_command_event,
        mock_respond,
        mock_slack_client,
        mock_screenshot_bytes,
    ):
        """Test successful async slash command with Miro screenshot."""
        with patch("maptimize.handlers.load_processes") as mock_load, \
             patch("maptimize.handlers.screenshot_miro_board") as mock_screenshot, \
             patch("maptimize.handlers.create_response_blocks") as mock_create_blocks:

            from maptimize.handlers import handle_slash_command

            # Setup mocks
            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize",
                    "description": "8-step process for reviews",
                    "miro_board_id": "uXjVJ2FVjGM",
                }
            }
            mock_screenshot.return_value = mock_screenshot_bytes
            mock_create_blocks.return_value = [
                {"type": "header", "text": {"type": "plain_text", "text": "Test Header"}},
                {"type": "image", "image_url": "https://files.slack.com/files/T123/F123/image.png", "alt_text": "Test"},
            ]

            # Call async handler
            await handle_slash_command(mock_command_event, mock_respond, mock_slack_client)

            # Verify screenshot was called
            mock_screenshot.assert_called_once_with("uXjVJ2FVjGM")

            # Verify file upload was called with correct parameters
            mock_slack_client.files_upload.assert_called_once()
            upload_call = mock_slack_client.files_upload.call_args
            assert upload_call[1]["channels"] == "C123456"
            assert upload_call[1]["file"] == mock_screenshot_bytes
            assert "service_review_process" in upload_call[1]["filename"]
            assert upload_call[1]["filename"].endswith(".png")

            # Verify chat_postMessage was called with blocks
            mock_slack_client.chat_postMessage.assert_called_once()
            post_call = mock_slack_client.chat_postMessage.call_args
            assert post_call[1]["channel"] == "C123456"
            assert "blocks" in post_call[1]
            assert post_call[1]["blocks"] is not None

            # Verify create_response_blocks was called with image URLs
            mock_create_blocks.assert_called_once()
            call_args = mock_create_blocks.call_args
            processes = call_args[0][0]
            image_urls = call_args[0][1]
            assert "Service Review Process" in image_urls
            assert "https://files.slack.com/files/T123/F123/image.png" in image_urls["Service Review Process"]

    async def test_async_slash_command_with_miro_screenshot_fails(
        self,
        mock_command_event,
        mock_respond,
        mock_slack_client,
    ):
        """Test async slash command when Miro screenshot fails."""
        with patch("maptimize.handlers.load_processes") as mock_load, \
             patch("maptimize.handlers.screenshot_miro_board") as mock_screenshot, \
             patch("maptimize.handlers.create_response_blocks") as mock_create_blocks:

            from maptimize.handlers import handle_slash_command

            # Setup mocks - screenshot returns None (failure)
            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize",
                    "miro_board_id": "uXjVJ2FVjGM",
                }
            }
            mock_screenshot.return_value = None
            mock_create_blocks.return_value = [
                {"type": "section", "text": {"type": "mrkdwn", "text": "Test"}},
            ]

            # Call async handler - should not crash
            await handle_slash_command(mock_command_event, mock_respond, mock_slack_client)

            # Verify screenshot was attempted
            mock_screenshot.assert_called_once_with("uXjVJ2FVjGM")

            # Verify file upload was NOT called
            mock_slack_client.files_upload.assert_not_called()

            # Verify message was still posted (without image)
            mock_slack_client.chat_postMessage.assert_called_once()

            # Verify create_response_blocks was called with empty image_urls
            mock_create_blocks.assert_called_once()
            call_args = mock_create_blocks.call_args
            image_urls = call_args[0][1]
            assert "Service Review Process" not in image_urls

    async def test_async_slash_command_without_miro_board_id(
        self,
        mock_command_event,
        mock_respond,
        mock_slack_client,
    ):
        """Test async slash command with process that has no miro_board_id."""
        with patch("maptimize.handlers.load_processes") as mock_load, \
             patch("maptimize.handlers.screenshot_miro_board") as mock_screenshot, \
             patch("maptimize.handlers.create_response_blocks") as mock_create_blocks:

            from maptimize.handlers import handle_slash_command

            # Setup mocks - no miro_board_id
            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize",
                    "description": "Process without diagram",
                }
            }
            mock_create_blocks.return_value = [
                {"type": "section", "text": {"type": "mrkdwn", "text": "Test"}},
            ]

            # Call async handler
            await handle_slash_command(mock_command_event, mock_respond, mock_slack_client)

            # Verify screenshot was NOT called
            mock_screenshot.assert_not_called()

            # Verify file upload was NOT called
            mock_slack_client.files_upload.assert_not_called()

            # Verify message was still posted (text-only fallback)
            mock_slack_client.chat_postMessage.assert_called_once()

    async def test_async_slash_command_file_upload_error(
        self,
        mock_command_event,
        mock_respond,
        mock_slack_client,
        mock_screenshot_bytes,
    ):
        """Test async slash command when file upload fails."""
        with patch("maptimize.handlers.load_processes") as mock_load, \
             patch("maptimize.handlers.screenshot_miro_board") as mock_screenshot, \
             patch("maptimize.handlers.create_response_blocks") as mock_create_blocks:

            from maptimize.handlers import handle_slash_command

            # Setup mocks
            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize",
                    "miro_board_id": "uXjVJ2FVjGM",
                }
            }
            mock_screenshot.return_value = mock_screenshot_bytes

            # Make files_upload raise exception
            mock_slack_client.files_upload.side_effect = Exception("Upload failed")

            mock_create_blocks.return_value = [
                {"type": "section", "text": {"type": "mrkdwn", "text": "Test"}},
            ]

            # Call async handler - should not crash
            await handle_slash_command(mock_command_event, mock_respond, mock_slack_client)

            # Verify screenshot was called
            mock_screenshot.assert_called_once()

            # Verify file upload was attempted
            mock_slack_client.files_upload.assert_called_once()

            # Verify message was still posted (fallback without image)
            mock_slack_client.chat_postMessage.assert_called_once()

    async def test_async_slash_command_creates_correct_blocks(
        self,
        mock_command_event,
        mock_respond,
        mock_slack_client,
        mock_screenshot_bytes,
    ):
        """Test that async slash command creates correct Block Kit structure."""
        with patch("maptimize.handlers.load_processes") as mock_load, \
             patch("maptimize.handlers.screenshot_miro_board") as mock_screenshot:

            from maptimize.handlers import handle_slash_command

            # Setup mocks
            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize",
                    "description": "8-step process",
                    "miro_board_id": "uXjVJ2FVjGM",
                }
            }
            mock_screenshot.return_value = mock_screenshot_bytes

            # Call async handler
            await handle_slash_command(mock_command_event, mock_respond, mock_slack_client)

            # Verify chat_postMessage was called
            mock_slack_client.chat_postMessage.assert_called_once()

            # Extract blocks from call
            post_call = mock_slack_client.chat_postMessage.call_args
            blocks = post_call[1]["blocks"]

            # Verify block structure
            assert isinstance(blocks, list)
            assert len(blocks) > 0

            # First block should be header
            assert blocks[0]["type"] == "header"
            assert blocks[0]["text"]["type"] == "plain_text"
            assert "Maptimize" in blocks[0]["text"]["text"]

            # Should have divider after header
            assert blocks[1]["type"] == "divider"

            # Should contain image block (since we successfully uploaded)
            image_blocks = [b for b in blocks if b.get("type") == "image"]
            assert len(image_blocks) > 0

            # Image block should have correct structure
            image_block = image_blocks[0]
            assert "image_url" in image_block
            assert "alt_text" in image_block
            assert "https://files.slack.com/files/T123/F123/image.png" in image_block["image_url"]

    async def test_async_slash_command_multiple_processes_with_mixed_miro(
        self,
        mock_command_event,
        mock_respond,
        mock_slack_client,
        mock_screenshot_bytes,
    ):
        """Test async slash command with multiple processes, some with Miro boards."""
        with patch("maptimize.handlers.load_processes") as mock_load, \
             patch("maptimize.handlers.screenshot_miro_board") as mock_screenshot, \
             patch("maptimize.handlers.create_response_blocks") as mock_create_blocks:

            from maptimize.handlers import handle_slash_command

            # Setup mocks - multiple processes
            mock_load.return_value = {
                "Process With Miro": {
                    "wiki_url": "https://wiki.corp.adobe.com/process1",
                    "miro_board_id": "board1",
                },
                "Process Without Miro": {
                    "wiki_url": "https://wiki.corp.adobe.com/process2",
                },
                "Another With Miro": {
                    "wiki_url": "https://wiki.corp.adobe.com/process3",
                    "miro_board_id": "board2",
                },
            }
            mock_screenshot.return_value = mock_screenshot_bytes
            mock_create_blocks.return_value = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]

            # Call async handler
            await handle_slash_command(mock_command_event, mock_respond, mock_slack_client)

            # Verify screenshot was called twice (for two processes with miro_board_id)
            assert mock_screenshot.call_count == 2
            mock_screenshot.assert_any_call("board1")
            mock_screenshot.assert_any_call("board2")

            # Verify file upload was called twice
            assert mock_slack_client.files_upload.call_count == 2

            # Verify create_response_blocks was called with two image URLs
            mock_create_blocks.assert_called_once()
            call_args = mock_create_blocks.call_args
            image_urls = call_args[0][1]
            assert len(image_urls) == 2
            assert "Process With Miro" in image_urls
            assert "Another With Miro" in image_urls
            assert "Process Without Miro" not in image_urls

    async def test_async_slash_command_exception_handling(
        self,
        mock_command_event,
        mock_respond,
        mock_slack_client,
    ):
        """Test that async slash command handles exceptions gracefully."""
        with patch("maptimize.handlers.load_processes") as mock_load:
            from maptimize.handlers import handle_slash_command

            # Make load_processes raise exception
            mock_load.side_effect = Exception("Config load failed")

            # Call async handler - should not raise
            await handle_slash_command(mock_command_event, mock_respond, mock_slack_client)

            # Verify error response was sent
            mock_respond.assert_called_once()
            call_args = mock_respond.call_args
            assert "error occurred" in call_args[1]["text"].lower()
            assert call_args[1].get("response_type") == "ephemeral"


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

    def test_handle_command_logs_event(self, mock_command_event, mock_say):
        """Test that command events are logged."""
        with patch("maptimize.config.load_processes") as mock_load:
            from maptimize.handlers import handle_slash_command

            mock_load.return_value = {
                "Service Review Process": {
                    "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Maptimize"
                }
            }

            # Just verify it runs without error
            handle_slash_command(mock_command_event, mock_say)
            mock_say.assert_called_once()
