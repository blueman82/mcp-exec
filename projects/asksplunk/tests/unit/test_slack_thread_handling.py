"""Unit tests for Slack thread-based session management.

Tests SlackClient integration with SessionManager for conversation continuity.
Verifies proper handling of new mentions vs thread replies.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from asksplunk.slack.client import SlackClient


class TestSlackThreadHandling:
    """Test thread-based session management."""

    @pytest.fixture
    def mock_tokens(self):
        """Mock Slack tokens.

        NOTE: These are FAKE TEST TOKENS, not real credentials.
        """
        return {"bot_token": "xoxb-fake-test-token", "app_token": "xapp-fake-test-token"}

    @pytest.fixture
    def mock_session_manager(self):
        """Mock SessionManager."""
        manager = AsyncMock()
        manager.get_session = AsyncMock(return_value=None)
        manager.create_session = AsyncMock(
            return_value={
                "thread_id": "1234567890.123456",
                "user_id": "U123ABC",
                "channel_id": "C456DEF",
                "agent_state": "INITIALIZE",
                "created_at": "2025-01-13T12:00:00",
                "ttl": 1736776800,
            }
        )
        return manager

    @pytest.mark.asyncio
    async def test_new_mention_creates_session(self, mock_tokens, mock_session_manager):
        """New @mention should create new session."""
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
            client.session_manager = mock_session_manager
            client.bot_user_id = "UBOTID"  # Set bot_user_id for mention stripping

            # Simulate new mention event (no thread_ts)
            event = {
                "ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@UBOTID> show me logs",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # Mock session_manager returns None (no existing session)
            mock_session_manager.get_session.return_value = None

            await registered_handler(event, mock_say, mock_ack)

            # Should check for existing session
            mock_session_manager.get_session.assert_called_once_with("1234567890.123456")

            # Should create new session
            mock_session_manager.create_session.assert_called_once_with(
                thread_id="1234567890.123456",
                user_id="U123ABC",
                channel_id="C456DEF",
                question="show me logs",
            )

    @pytest.mark.asyncio
    async def test_thread_reply_loads_existing_session(self, mock_tokens, mock_session_manager):
        """Thread reply should load existing session."""
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
            client.session_manager = mock_session_manager

            # Simulate thread reply event
            event = {
                "ts": "1234567890.999999",
                "thread_ts": "1234567890.123456",  # Existing thread
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@BOT> follow up question",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # Mock session_manager returns existing session
            existing_session = {
                "thread_id": "1234567890.123456",
                "user_id": "U123ABC",
                "channel_id": "C456DEF",
                "agent_state": "WAIT",
                "created_at": "2025-01-13T12:00:00",
                "ttl": 1736776800,
            }
            mock_session_manager.get_session.return_value = existing_session

            await registered_handler(event, mock_say, mock_ack)

            # Should load existing session using thread_ts
            mock_session_manager.get_session.assert_called_once_with("1234567890.123456")

            # Should NOT create new session
            mock_session_manager.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_ts_as_thread_id_when_not_in_thread(self, mock_tokens, mock_session_manager):
        """Should use ts as thread_id when not in thread."""
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
            client.session_manager = mock_session_manager

            # Event without thread_ts (new conversation in channel)
            event = {
                "ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@BOT> new question",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            mock_session_manager.get_session.return_value = None

            await registered_handler(event, mock_say, mock_ack)

            # Should use ts as session key
            mock_session_manager.get_session.assert_called_once_with("1234567890.123456")
            mock_session_manager.create_session.assert_called_once()
            assert (
                mock_session_manager.create_session.call_args[1]["thread_id"] == "1234567890.123456"
            )

    @pytest.mark.asyncio
    async def test_uses_thread_ts_when_in_thread(self, mock_tokens, mock_session_manager):
        """Should use thread_ts as session key when in thread."""
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
            client.session_manager = mock_session_manager

            # Event with thread_ts (reply in existing thread)
            event = {
                "ts": "1234567890.999999",
                "thread_ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@BOT> follow up",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            mock_session_manager.get_session.return_value = None

            await registered_handler(event, mock_say, mock_ack)

            # Should use thread_ts as session key
            mock_session_manager.get_session.assert_called_once_with("1234567890.123456")
            mock_session_manager.create_session.assert_called_once()
            assert (
                mock_session_manager.create_session.call_args[1]["thread_id"] == "1234567890.123456"
            )

    @pytest.mark.asyncio
    async def test_strips_bot_mention_from_question(self, mock_tokens, mock_session_manager):
        """Should strip bot mention from question text."""
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
            client.session_manager = mock_session_manager
            client.bot_user_id = "UBOTID"

            event = {
                "ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@UBOTID> show me logs",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            mock_session_manager.get_session.return_value = None

            await registered_handler(event, mock_say, mock_ack)

            # Should strip <@UBOTID> from question
            mock_session_manager.create_session.assert_called_once()
            call_args = mock_session_manager.create_session.call_args
            assert call_args[1]["question"] == "show me logs"

    @pytest.mark.asyncio
    async def test_sends_appropriate_response_for_new_conversation(
        self, mock_tokens, mock_session_manager
    ):
        """Should send 'starting new query' message for new conversation."""
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
            client.session_manager = mock_session_manager

            event = {
                "ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@BOT> new question",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            mock_session_manager.get_session.return_value = None

            await registered_handler(event, mock_say, mock_ack)

            # Should send new conversation message
            mock_say.assert_called_once()
            call_args = mock_say.call_args
            assert "Starting" in call_args[1]["text"] or "new" in call_args[1]["text"]
            assert call_args[1]["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_sends_appropriate_response_for_continuing_conversation(
        self, mock_tokens, mock_session_manager
    ):
        """Should send 'continuing conversation' message for thread reply."""
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
            client.session_manager = mock_session_manager

            event = {
                "ts": "1234567890.999999",
                "thread_ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@BOT> follow up",
            }
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # Existing session
            mock_session_manager.get_session.return_value = {
                "thread_id": "1234567890.123456",
                "agent_state": "WAIT",
            }

            await registered_handler(event, mock_say, mock_ack)

            # Should send continuing conversation message
            mock_say.assert_called_once()
            call_args = mock_say.call_args
            assert "Continuing" in call_args[1]["text"] or "continuing" in call_args[1]["text"]
            assert call_args[1]["thread_ts"] == "1234567890.123456"
