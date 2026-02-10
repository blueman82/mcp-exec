"""Unit tests for Slack Socket Mode client.

Tests SlackClient initialization, event handler registration,
and graceful connection lifecycle.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from asksplunk.slack.client import SlackClient, _is_fatal_slack_error
from asksplunk.usage import UsageTracker


def _make_slack_api_error(error_code: str) -> SlackApiError:
    """Create a SlackApiError with the given error code for testing."""
    mock_response = AsyncSlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/auth.test",
        req_args={},
        data={"ok": False, "error": error_code},
        headers={},
        status_code=200,
    )
    return SlackApiError(message=f"The request to the Slack API failed. (error: {error_code})", response=mock_response)


class TestSlackClient:
    """Test Slack Socket Mode client initialization and lifecycle."""

    @pytest.fixture
    def mock_tokens(self):
        """Mock Slack tokens.

        NOTE: These are FAKE TEST TOKENS, not real credentials.
        """
        return {"bot_token": "xoxb-fake-test-token", "app_token": "xapp-fake-test-token"}

    @pytest.mark.asyncio
    async def test_initializes_with_tokens(self, mock_tokens):
        """SlackClient should initialize with bot and app tokens."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            MockApp.assert_called_once_with(token=mock_tokens["bot_token"])
            assert client.app_token == mock_tokens["app_token"]
            assert client.handler is None
            assert client.is_running is False

    @pytest.mark.asyncio
    async def test_registers_app_mention_handler(self, mock_tokens):
        """Should register handler for app_mention events."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            _client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Verify event decorator was called with "app_mention" and "message"
            assert mock_app.event.call_count == 2
            event_calls = [call[0][0] for call in mock_app.event.call_args_list]
            assert "app_mention" in event_calls
            assert "message" in event_calls

    @pytest.mark.asyncio
    async def test_handle_mention_sends_echo_response(self, mock_tokens):
        """app_mention handler should acknowledge and send echo response."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            # Capture the registered handler
            registered_handler = None

            def capture_handler(event_type):
                def decorator(func):
                    nonlocal registered_handler
                    # Capture the app_mention handler, ignore message handler
                    if event_type == "app_mention":
                        registered_handler = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Mock session_manager
            mock_session_manager = AsyncMock()
            mock_session_manager.get_session = AsyncMock(return_value=None)
            mock_session_manager.create_session = AsyncMock()
            client.session_manager = mock_session_manager

            # Simulate app_mention event
            event = {
                "user": "U123ABC",
                "channel": "C456DEF",
                "ts": "1234567890.123456",
                "text": "<@BOT> help me",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            await registered_handler(event, mock_say, mock_ack)

            mock_ack.assert_called_once()
            mock_say.assert_called_once()
            assert (
                "Starting" in mock_say.call_args[1]["text"]
                or "new" in mock_say.call_args[1]["text"]
            )
            assert mock_say.call_args[1]["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_handle_mention_with_thread_ts(self, mock_tokens):
        """app_mention handler should use thread_ts when present."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handler = None

            def capture_handler(event_type):
                def decorator(func):
                    nonlocal registered_handler
                    # Capture the app_mention handler, ignore message handler
                    if event_type == "app_mention":
                        registered_handler = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Mock session_manager with existing session
            mock_session_manager = AsyncMock()
            mock_session_manager.get_session = AsyncMock(
                return_value={"thread_id": "1234567890.123456", "agent_state": "WAIT"}
            )
            mock_session_manager.create_session = AsyncMock()
            client.session_manager = mock_session_manager

            # Event in a thread
            event = {
                "user": "U123ABC",
                "channel": "C456DEF",
                "ts": "1234567890.999999",
                "thread_ts": "1234567890.123456",  # Original thread message
                "text": "<@BOT> follow up question",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            await registered_handler(event, mock_say, mock_ack)

            mock_say.assert_called_once()
            assert mock_say.call_args[1]["thread_ts"] == "1234567890.123456"  # Should use thread_ts
            # When no agent and existing session, should send "Continuing conversation..."
            assert "Continuing" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_start_creates_socket_mode_handler(self, mock_tokens):
        """start() should create and start AsyncSocketModeHandler."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
        ):

            mock_app = Mock()
            # Mock auth_test for bot_user_id initialization
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            # Mock SessionManager as async context manager
            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            await client.start()

            MockHandler.assert_called_once_with(mock_app, mock_tokens["app_token"])
            mock_handler_instance.start_async.assert_called_once()
            assert client.is_running is True
            assert client.handler is mock_handler_instance

    @pytest.mark.asyncio
    async def test_graceful_shutdown_closes_connection(self, mock_tokens):
        """shutdown() should gracefully close WebSocket connection."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
        ):

            mock_app = Mock()
            # Mock auth_test for bot_user_id initialization
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            # Mock SessionManager as async context manager
            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            await client.start()
            await client.shutdown()

            mock_handler_instance.close_async.assert_called_once()
            assert client.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_when_not_started(self, mock_tokens):
        """shutdown() should handle case when handler is None."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Should not raise error when handler is None
            await client.shutdown()

            assert client.is_running is False

    @pytest.mark.asyncio
    async def test_start_initializes_bot_user_id(self, mock_tokens):
        """start() should initialize bot_user_id via auth_test API call."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
        ):

            mock_app = Mock()
            # Mock the auth_test method
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            # Mock SessionManager as async context manager
            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Before start, bot_user_id should be None
            assert client.bot_user_id is None

            await client.start()

            # After start, bot_user_id should be set
            assert client.bot_user_id == "U123BOT"
            mock_app.client.auth_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_mention_handler_catches_exceptions(self, mock_tokens):
        """handle_mention should catch exceptions and send user-friendly error message."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.logger") as mock_logger,
        ):

            mock_app = Mock()
            MockApp.return_value = mock_app

            # Capture the registered handler
            registered_handler = None

            def capture_handler(event_type):
                def decorator(func):
                    nonlocal registered_handler
                    # Capture the app_mention handler, ignore message handler
                    if event_type == "app_mention":
                        registered_handler = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Mock session_manager to raise exception
            mock_session_manager = AsyncMock()
            mock_session_manager.create_session = AsyncMock(side_effect=Exception("DynamoDB error"))
            mock_session_manager.get_session = AsyncMock(return_value=None)
            client.session_manager = mock_session_manager

            # Simulate app_mention event
            event = {
                "user": "U123ABC",
                "channel": "C456DEF",
                "ts": "1234567890.123456",
                "text": "<@BOT> help me",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # Call handler - should NOT raise exception
            await registered_handler(event, mock_say, mock_ack)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert error_call[0][0] == "mention_handler_error"
            assert "error" in error_call[1]
            assert "DynamoDB error" in error_call[1]["error"]
            assert error_call[1]["thread_ts"] == "1234567890.123456"
            assert error_call[1]["exc_info"] is True

            # Verify user-friendly message sent to Slack
            mock_say.assert_called_once()
            assert (
                mock_say.call_args[1]["text"]
                == "Sorry, I encountered an error processing your message. Please try again."
            )
            assert mock_say.call_args[1]["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_mention_handler_strips_bot_mention(self, mock_tokens):
        """handle_mention should strip bot mention from text before processing."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handler = None

            def capture_handler(event_type):
                def decorator(func):
                    nonlocal registered_handler
                    if event_type == "app_mention":
                        registered_handler = func
                    return func

                return decorator

            mock_app.event = capture_handler

            # Mock agent to verify clean text
            mock_agent = AsyncMock()
            mock_agent.process_question = AsyncMock(
                return_value={"action": "query_generated", "content": {}}
            )

            client = SlackClient(
                bot_token=mock_tokens["bot_token"],
                app_token=mock_tokens["app_token"],
                agent=mock_agent,
            )

            # Set bot_user_id for mention stripping
            client.bot_user_id = "U123BOT"

            mock_session_manager = AsyncMock()
            mock_session_manager.get_session = AsyncMock(return_value=None)
            client.session_manager = mock_session_manager

            event = {
                "user": "U123ABC",
                "channel": "C456DEF",
                "ts": "1234567890.123456",
                "text": "<@U123BOT> show me bounces",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            await registered_handler(event, mock_say, mock_ack)

            # Verify agent received clean text without bot mention
            mock_agent.process_question.assert_called_once()
            call_args = mock_agent.process_question.call_args[0]
            assert call_args[0] == "show me bounces"  # Cleaned text

    @pytest.mark.asyncio
    async def test_dm_handler_processes_direct_messages(self, mock_tokens):
        """handle_dm should process direct messages to the bot."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_session_manager = AsyncMock()
            mock_session_manager.get_session = AsyncMock(return_value=None)
            mock_session_manager.create_session = AsyncMock()
            client.session_manager = mock_session_manager

            # DM event (channel_type="im")
            event = {
                "user": "U123ABC",
                "channel": "D789XYZ",  # DM channel
                "channel_type": "im",
                "ts": "1234567890.123456",
                "text": "help me with bounces",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            mock_ack.assert_called_once()
            mock_say.assert_called_once()
            assert "Starting" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_dm_handler_ignores_non_dm_messages(self, mock_tokens):
        """handle_dm should ignore non-DM messages."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Channel message (not DM)
            event = {
                "user": "U123ABC",
                "channel": "C456DEF",
                "channel_type": "channel",
                "ts": "1234567890.123456",
                "text": "some message",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            # Should not acknowledge or respond
            mock_ack.assert_not_called()
            mock_say.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_handler_ignores_bot_messages(self, mock_tokens):
        """handle_dm should ignore messages from bots."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Bot message
            event = {
                "bot_id": "B123BOT",
                "channel": "D789XYZ",
                "channel_type": "im",
                "ts": "1234567890.123456",
                "text": "bot message",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            # Should not acknowledge or respond
            mock_ack.assert_not_called()
            mock_say.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_handler_with_agent(self, mock_tokens):
        """handle_dm should process DMs with agent when available."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            mock_agent = AsyncMock()
            mock_agent.process_question = AsyncMock(
                return_value={"action": "query_generated", "content": {}}
            )

            client = SlackClient(
                bot_token=mock_tokens["bot_token"],
                app_token=mock_tokens["app_token"],
                agent=mock_agent,
            )

            mock_session_manager = AsyncMock()
            client.session_manager = mock_session_manager

            event = {
                "user": "U123ABC",
                "channel": "D789XYZ",
                "channel_type": "im",
                "ts": "1234567890.123456",
                "text": "show me bounces",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            mock_agent.process_question.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_agent_response_query_generated(self, mock_tokens):
        """_send_agent_response should format and send query results."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_say = AsyncMock()
            result = {
                "action": "query_generated",
                "content": {
                    "spl_query": "index=campaign_prod | stats count",
                    "plain_explanation": "Shows total count",
                    "technical_explanation": "Uses stats command",
                },
            }

            await client._send_agent_response(mock_say, result, "1234.5678")

            mock_say.assert_called_once()
            assert "index=campaign_prod" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_agent_response_clarify(self, mock_tokens):
        """_send_agent_response should format and send clarifying questions."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_say = AsyncMock()
            result = {
                "action": "clarify",
                "content": {
                    "question": "Which type?",
                    "options": ["Option 1", "Option 2"],
                },
            }

            await client._send_agent_response(mock_say, result, "1234.5678")

            mock_say.assert_called_once()
            assert "Which type?" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_agent_response_uncertain(self, mock_tokens):
        """_send_agent_response should handle uncertain responses."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_say = AsyncMock()
            result = {
                "action": "uncertain",
                "content": {
                    "missing_info": "Need more details",
                },
            }

            await client._send_agent_response(mock_say, result, "1234.5678")

            mock_say.assert_called_once()
            assert "enough information" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_agent_response_blocked(self, mock_tokens):
        """_send_agent_response should handle blocked content."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_say = AsyncMock()
            result = {
                "action": "blocked",
                "content": {
                    "message": "Cannot process that request",
                },
            }

            await client._send_agent_response(mock_say, result, "1234.5678")

            mock_say.assert_called_once()
            assert "Cannot process" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_agent_response_unknown_action(self, mock_tokens):
        """_send_agent_response should handle unknown actions."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_say = AsyncMock()
            result = {
                "action": "unknown_action",
            }

            await client._send_agent_response(mock_say, result, "1234.5678")

            mock_say.assert_called_once()
            assert "Processing" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_dm_handler_catches_exceptions(self, mock_tokens):
        """handle_dm should catch exceptions and send user-friendly error."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.logger") as mock_logger,
        ):

            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_session_manager = AsyncMock()
            mock_session_manager.get_session = AsyncMock(side_effect=Exception("Error"))
            client.session_manager = mock_session_manager

            event = {
                "user": "U123ABC",
                "channel": "D789XYZ",
                "channel_type": "im",
                "ts": "1234567890.123456",
                "text": "help",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            # Verify error logged and friendly message sent
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert error_call[0][0] == "dm_handler_error"
            mock_say.assert_called_once()
            assert "error processing" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_mention_handler_when_session_manager_not_initialized(self, mock_tokens):
        """handle_mention should handle case when session_manager is None."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handler = None

            def capture_handler(event_type):
                def decorator(func):
                    nonlocal registered_handler
                    if event_type == "app_mention":
                        registered_handler = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Don't initialize session_manager (None)
            event = {
                "user": "U123ABC",
                "channel": "C456DEF",
                "ts": "1234567890.123456",
                "text": "help",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            await registered_handler(event, mock_say, mock_ack)

            mock_say.assert_called_once()
            assert "not ready" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_dm_handler_when_session_manager_not_initialized(self, mock_tokens):
        """handle_dm should handle case when session_manager is None."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Don't initialize session_manager (None)
            event = {
                "user": "U123ABC",
                "channel": "D789XYZ",
                "channel_type": "im",
                "ts": "1234567890.123456",
                "text": "help",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            mock_say.assert_called_once()
            assert "not ready" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_dm_handler_records_usage_event(self, mock_tokens):
        """handle_dm should call usage_tracker.record_event when receiving a DM."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            # Create mock usage tracker
            mock_usage_tracker = AsyncMock(spec=UsageTracker)
            mock_usage_tracker.record_event = AsyncMock()

            client = SlackClient(
                bot_token=mock_tokens["bot_token"],
                app_token=mock_tokens["app_token"],
                usage_tracker=mock_usage_tracker,
            )

            mock_session_manager = AsyncMock()
            mock_session_manager.get_session = AsyncMock(return_value=None)
            mock_session_manager.create_session = AsyncMock()
            client.session_manager = mock_session_manager

            # DM event
            event = {
                "user": "U123ABC",
                "channel": "D789XYZ",
                "channel_type": "im",
                "ts": "1234567890.123456",
                "text": "help me",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            # Verify record_event was called
            mock_usage_tracker.record_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_handler_continues_when_usage_tracking_fails(self, mock_tokens):
        """handle_dm should continue processing even if usage_tracker.record_event fails."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            registered_handlers = {}

            def capture_handler(event_type):
                def decorator(func):
                    registered_handlers[event_type] = func
                    return func

                return decorator

            mock_app.event = capture_handler

            # Create mock usage tracker that fails
            mock_usage_tracker = AsyncMock(spec=UsageTracker)
            mock_usage_tracker.record_event = AsyncMock(side_effect=Exception("DynamoDB error"))

            client = SlackClient(
                bot_token=mock_tokens["bot_token"],
                app_token=mock_tokens["app_token"],
                usage_tracker=mock_usage_tracker,
            )

            mock_session_manager = AsyncMock()
            mock_session_manager.get_session = AsyncMock(return_value=None)
            mock_session_manager.create_session = AsyncMock()
            client.session_manager = mock_session_manager

            # DM event
            event = {
                "user": "U123ABC",
                "channel": "D789XYZ",
                "channel_type": "im",
                "ts": "1234567890.123456",
                "text": "help me",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            message_handler = registered_handlers["message"]
            await message_handler(event, mock_say, mock_ack)

            # Verify DM was still processed despite usage tracking failure
            mock_say.assert_called_once()
            assert "Starting" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_usage_tracker_initialized_in_start(self, mock_tokens):
        """start() should initialize UsageTracker when not provided."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
            patch("asksplunk.slack.client.UsageTracker") as MockUsageTracker,
        ):

            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            mock_usage_tracker = AsyncMock()
            mock_usage_tracker.__aenter__ = AsyncMock(return_value=mock_usage_tracker)
            mock_usage_tracker.__aexit__ = AsyncMock(return_value=None)
            MockUsageTracker.return_value = mock_usage_tracker

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            await client.start()

            # Verify UsageTracker was created and entered
            MockUsageTracker.assert_called_once()
            mock_usage_tracker.__aenter__.assert_called_once()
            assert client.usage_tracker is mock_usage_tracker

    @pytest.mark.asyncio
    async def test_usage_tracker_not_created_when_provided(self, mock_tokens):
        """start() should not create UsageTracker when one is provided."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
            patch("asksplunk.slack.client.UsageTracker") as MockUsageTracker,
        ):

            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            # Provide a pre-configured usage tracker
            provided_tracker = AsyncMock(spec=UsageTracker)

            client = SlackClient(
                bot_token=mock_tokens["bot_token"],
                app_token=mock_tokens["app_token"],
                usage_tracker=provided_tracker,
            )

            await client.start()

            # Verify UsageTracker was NOT created (we provided one)
            MockUsageTracker.assert_not_called()
            assert client.usage_tracker is provided_tracker

    @pytest.mark.asyncio
    async def test_shutdown_closes_usage_tracker_when_created_internally(self, mock_tokens):
        """shutdown() should close UsageTracker only if created internally."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
            patch("asksplunk.slack.client.UsageTracker") as MockUsageTracker,
        ):

            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            mock_usage_tracker = AsyncMock()
            mock_usage_tracker.__aenter__ = AsyncMock(return_value=mock_usage_tracker)
            mock_usage_tracker.__aexit__ = AsyncMock(return_value=None)
            MockUsageTracker.return_value = mock_usage_tracker

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            await client.start()
            await client.shutdown()

            # Verify UsageTracker was closed
            mock_usage_tracker.__aexit__.assert_called_once_with(None, None, None)
            assert client.usage_tracker is None

    @pytest.mark.asyncio
    async def test_shutdown_does_not_close_provided_usage_tracker(self, mock_tokens):
        """shutdown() should NOT close UsageTracker when it was provided externally."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
        ):

            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            # Provide a pre-configured usage tracker
            provided_tracker = AsyncMock(spec=UsageTracker)
            provided_tracker.__aexit__ = AsyncMock(return_value=None)

            client = SlackClient(
                bot_token=mock_tokens["bot_token"],
                app_token=mock_tokens["app_token"],
                usage_tracker=provided_tracker,
            )

            await client.start()
            await client.shutdown()

            # Verify provided tracker was NOT closed (caller's responsibility)
            provided_tracker.__aexit__.assert_not_called()
            # usage_tracker should still be set (we didn't clear it)
            assert client.usage_tracker is provided_tracker

    @pytest.mark.asyncio
    async def test_send_agent_response_handles_usage_report(self, mock_tokens):
        """_send_agent_response should handle usage_report action with bar_chart emoji."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_say = AsyncMock()
            result = {
                "action": "usage_report",
                "content": {
                    "message": "Usage report: 42 queries from 2024-01-01 00:00 to 2024-01-07 23:59 UTC",
                },
            }

            await client._send_agent_response(mock_say, result, "1234.5678")

            mock_say.assert_called_once()
            assert ":bar_chart:" in mock_say.call_args[1]["text"]
            assert "42 queries" in mock_say.call_args[1]["text"]
            assert mock_say.call_args[1]["thread_ts"] == "1234.5678"

    @pytest.mark.asyncio
    async def test_send_agent_response_usage_report_default_message(self, mock_tokens):
        """_send_agent_response should use default message when content is empty."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            mock_say = AsyncMock()
            result = {
                "action": "usage_report",
                "content": {},
            }

            await client._send_agent_response(mock_say, result, "1234.5678")

            mock_say.assert_called_once()
            assert ":bar_chart:" in mock_say.call_args[1]["text"]
            assert "No usage data available" in mock_say.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_init_accepts_usage_tracker_parameter(self, mock_tokens):
        """SlackClient should accept usage_tracker parameter in __init__."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            mock_tracker = AsyncMock(spec=UsageTracker)

            client = SlackClient(
                bot_token=mock_tokens["bot_token"],
                app_token=mock_tokens["app_token"],
                usage_tracker=mock_tracker,
            )

            assert client.usage_tracker is mock_tracker


class TestIsFatalSlackError:
    """Test _is_fatal_slack_error module-level helper."""

    def test_fatal_errors(self):
        """Should return True for invalid_auth, account_inactive, token_revoked, not_authed."""
        for code in ("invalid_auth", "account_inactive", "token_revoked", "not_authed"):
            error = _make_slack_api_error(code)
            assert _is_fatal_slack_error(error) is True

    def test_transient_errors(self):
        """Should return False for transient Slack errors."""
        for code in ("ratelimited", "request_timeout", "service_unavailable"):
            error = _make_slack_api_error(code)
            assert _is_fatal_slack_error(error) is False

    def test_unknown_errors(self):
        """Should return False for non-SlackApiError exceptions."""
        assert _is_fatal_slack_error(RuntimeError("network")) is False
        assert _is_fatal_slack_error(TimeoutError()) is False


class TestShutdownResilience:
    """Test shutdown() continues cleanup when individual steps fail."""

    @pytest.fixture
    def mock_tokens(self):
        return {"bot_token": "xoxb-fake-test-token", "app_token": "xapp-fake-test-token"}

    @pytest.mark.asyncio
    async def test_shutdown_continues_when_session_manager_cleanup_fails(self, mock_tokens):
        """shutdown() should still close secrets manager and handler when session manager __aexit__ fails."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Set up context managers
            client._session_manager_context = AsyncMock()
            client._session_manager_context.__aexit__ = AsyncMock(
                side_effect=RuntimeError("session cleanup boom")
            )
            client.session_manager = AsyncMock()

            client._secrets_manager_context = AsyncMock()
            client._secrets_manager_context.__aexit__ = AsyncMock(return_value=None)
            client.access_validator = AsyncMock()

            client.handler = AsyncMock()

            await client.shutdown()

            # Secrets manager should still have been cleaned up
            client._secrets_manager_context.__aexit__.assert_called_once()
            assert client._secrets_manager_context is None
            assert client.access_validator is None
            # Handler should still have been closed
            client.handler.close_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_continues_when_secrets_manager_cleanup_fails(self, mock_tokens):
        """shutdown() should still close handler when secrets manager __aexit__ fails."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            client._secrets_manager_context = AsyncMock()
            client._secrets_manager_context.__aexit__ = AsyncMock(
                side_effect=RuntimeError("secrets cleanup boom")
            )
            client.access_validator = AsyncMock()

            client.handler = AsyncMock()

            await client.shutdown()

            # Handler should still have been closed
            client.handler.close_async.assert_called_once()
            assert client._secrets_manager_context is None
            assert client.access_validator is None

    @pytest.mark.asyncio
    async def test_shutdown_continues_when_handler_close_fails(self, mock_tokens):
        """shutdown() should complete without raising when handler.close_async() fails."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            client.handler = AsyncMock()
            client.handler.close_async = AsyncMock(side_effect=RuntimeError("handler boom"))
            client.is_running = True

            # Should not raise
            await client.shutdown()
            assert client.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_nulls_references_even_on_error(self, mock_tokens):
        """shutdown() should null all references even when __aexit__ fails."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # All three context managers fail
            client._session_manager_context = AsyncMock()
            client._session_manager_context.__aexit__ = AsyncMock(side_effect=RuntimeError("boom1"))
            client.session_manager = AsyncMock()

            client._secrets_manager_context = AsyncMock()
            client._secrets_manager_context.__aexit__ = AsyncMock(side_effect=RuntimeError("boom2"))
            client.access_validator = AsyncMock()

            client._usage_tracker_context = AsyncMock()
            client._usage_tracker_context.__aexit__ = AsyncMock(side_effect=RuntimeError("boom3"))
            client.usage_tracker = AsyncMock()

            await client.shutdown()

            assert client._session_manager_context is None
            assert client.session_manager is None
            assert client._secrets_manager_context is None
            assert client.access_validator is None
            assert client._usage_tracker_context is None
            assert client.usage_tracker is None


class TestAuthTestWithRetry:
    """Test _auth_test_with_retry method."""

    @pytest.fixture
    def mock_tokens(self):
        return {"bot_token": "xoxb-fake-test-token", "app_token": "xapp-fake-test-token"}

    @pytest.mark.asyncio
    async def test_succeeds_first_attempt(self, mock_tokens):
        """Should return auth response on first successful attempt."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            result = await client._auth_test_with_retry()
            assert result == {"user_id": "U123BOT"}
            mock_app.client.auth_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_succeeds_after_transient_failure(self, mock_tokens):
        """Should retry and succeed after transient errors."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(
                side_effect=[
                    _make_slack_api_error("ratelimited"),
                    {"user_id": "U123BOT"},
                ]
            )
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            result = await client._auth_test_with_retry()
            assert result == {"user_id": "U123BOT"}
            assert mock_app.client.auth_test.call_count == 2
            mock_sleep.assert_called_once_with(1.0)  # backoff base * 2^0

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self, mock_tokens):
        """Should raise after exhausting all retries."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(
                side_effect=_make_slack_api_error("ratelimited")
            )
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            with pytest.raises(SlackApiError):
                await client._auth_test_with_retry()
            assert mock_app.client.auth_test.call_count == 3

    @pytest.mark.asyncio
    async def test_timeout(self, mock_tokens):
        """Should handle asyncio.TimeoutError as transient and retry."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(side_effect=asyncio.TimeoutError())
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            with pytest.raises(asyncio.TimeoutError):
                await client._auth_test_with_retry()
            assert mock_app.client.auth_test.call_count == 3

    @pytest.mark.asyncio
    async def test_fatal_error_no_retry(self, mock_tokens):
        """Should raise immediately on fatal errors without retrying."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(
                side_effect=_make_slack_api_error("invalid_auth")
            )
            MockApp.return_value = mock_app

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            with pytest.raises(SlackApiError):
                await client._auth_test_with_retry()
            mock_app.client.auth_test.assert_called_once()


class TestStartLifecycle:
    """Test start() structured logging and error handling."""

    @pytest.fixture
    def mock_tokens(self):
        return {"bot_token": "xoxb-fake-test-token", "app_token": "xapp-fake-test-token"}

    @pytest.mark.asyncio
    async def test_start_logs_lifecycle_events(self, mock_tokens):
        """start() should emit socket_mode_handler_starting and socket_mode_connected."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
            patch("asksplunk.slack.client.logger") as mock_logger,
        ):
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            await client.start()

            log_events = [call[0][0] for call in mock_logger.info.call_args_list]
            assert "socket_mode_handler_starting" in log_events
            assert "socket_mode_connected" in log_events

    @pytest.mark.asyncio
    async def test_start_logs_transient_error_as_warning(self, mock_tokens):
        """start() should log transient errors at warning level."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
            patch("asksplunk.slack.client.logger") as mock_logger,
        ):
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            mock_handler_instance.start_async = AsyncMock(
                side_effect=ConnectionError("WebSocket 408")
            )
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            with pytest.raises(ConnectionError):
                await client.start()

            mock_logger.warning.assert_any_call(
                "socket_mode_transient_error", error="WebSocket 408"
            )

    @pytest.mark.asyncio
    async def test_start_logs_fatal_error(self, mock_tokens):
        """start() should log fatal Slack errors at error level with exc_info."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
            patch("asksplunk.slack.client.logger") as mock_logger,
        ):
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            fatal_error = _make_slack_api_error("invalid_auth")
            mock_handler_instance = AsyncMock()
            mock_handler_instance.start_async = AsyncMock(side_effect=fatal_error)
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            with pytest.raises(SlackApiError):
                await client.start()

            mock_logger.error.assert_any_call(
                "socket_mode_fatal_error", error=str(fatal_error), exc_info=True
            )

    @pytest.mark.asyncio
    async def test_start_sets_is_running_false_on_error(self, mock_tokens):
        """start() should set is_running to False when start_async() raises."""
        with (
            patch("asksplunk.slack.client.AsyncApp") as MockApp,
            patch("asksplunk.slack.client.AsyncSocketModeHandler") as MockHandler,
            patch("asksplunk.slack.client.SessionManager") as MockSessionManager,
        ):
            mock_app = Mock()
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
            MockApp.return_value = mock_app

            mock_handler_instance = AsyncMock()
            mock_handler_instance.start_async = AsyncMock(
                side_effect=ConnectionError("connection refused")
            )
            MockHandler.return_value = mock_handler_instance

            mock_session_mgr = AsyncMock()
            mock_session_mgr.__aenter__ = AsyncMock(return_value=mock_session_mgr)
            mock_session_mgr.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_mgr

            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            with pytest.raises(ConnectionError):
                await client.start()

            assert client.is_running is False
