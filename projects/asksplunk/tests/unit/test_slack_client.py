"""Unit tests for Slack Socket Mode client.

Tests SlackClient initialization, event handler registration,
and graceful connection lifecycle.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from asksplunk.slack.client import SlackClient


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
