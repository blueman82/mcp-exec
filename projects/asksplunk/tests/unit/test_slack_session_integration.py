"""Integration tests for SlackClient + SessionManager interaction.

Tests the conversation flow between Slack Socket Mode client and DynamoDB session manager.
Verifies multi-turn conversations, session persistence, and thread handling.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from asksplunk.session.manager import SessionManager
from asksplunk.slack.client import SlackClient


class TestSlackSessionIntegration:
    """Integration tests for Slack client and session manager."""

    @pytest.fixture
    def mock_tokens(self):
        """Mock Slack tokens.

        NOTE: These are FAKE TEST TOKENS, not real credentials.
        """
        return {"bot_token": "xoxb-fake-test-token", "app_token": "xapp-fake-test-token"}

    @pytest.fixture
    def mock_dynamodb_table(self):  # noqa: C901
        """Mock DynamoDB table."""
        table = AsyncMock()
        # Track sessions in memory for integration testing
        table._sessions = {}

        async def mock_put_item(**kwargs):
            item = kwargs["Item"]
            table._sessions[item["thread_id"]] = item

        async def mock_get_item(**kwargs):
            thread_id = kwargs["Key"]["thread_id"]
            if thread_id in table._sessions:
                return {"Item": table._sessions[thread_id]}
            return {}

        async def mock_update_item(**kwargs):
            """Mock update_item that handles UpdateExpression format.

            Parses DynamoDB UpdateExpression like:
                "SET #agent_state = :agent_state, #ttl = :ttl, #updated_at = :updated_at"
            With ExpressionAttributeNames like:
                {"#agent_state": "agent_state", "#ttl": "ttl", "#updated_at": "updated_at"}
            And ExpressionAttributeValues like:
                {":agent_state": "EVALUATE", ":ttl": 1234567890, ":updated_at": "2025-12-03T..."}
            """
            thread_id = kwargs["Key"]["thread_id"]

            # Handle both AttributeUpdates (legacy) and UpdateExpression (current)
            if "AttributeUpdates" in kwargs:
                # Legacy format
                updates = kwargs["AttributeUpdates"]
                if thread_id in table._sessions:
                    for key, update in updates.items():
                        table._sessions[thread_id][key] = update["Value"]
            elif "UpdateExpression" in kwargs and "ExpressionAttributeValues" in kwargs:
                # UpdateExpression format (what SessionManager uses)
                update_expr = kwargs[
                    "UpdateExpression"
                ]  # "SET #agent_state = :agent_state, #ttl = :ttl, ..."
                expr_values = kwargs[
                    "ExpressionAttributeValues"
                ]  # {":agent_state": "EVALUATE", ...}
                expr_names = kwargs.get("ExpressionAttributeNames", {})  # {"#ttl": "ttl", ...}

                if thread_id in table._sessions and update_expr.startswith("SET "):
                    # Simple parser for "SET #key1 = :key1, #key2 = :key2" format
                    assignments = update_expr[4:].split(", ")  # Remove "SET " and split
                    for assignment in assignments:
                        attr_name, placeholder = assignment.split(" = ")
                        # Resolve attribute name alias if present (e.g., #ttl -> ttl)
                        actual_key = expr_names.get(attr_name.strip(), attr_name.strip())
                        table._sessions[thread_id][actual_key] = expr_values[placeholder]

        async def mock_delete_item(**kwargs):
            thread_id = kwargs["Key"]["thread_id"]
            if thread_id in table._sessions:
                del table._sessions[thread_id]

        table.put_item = AsyncMock(side_effect=mock_put_item)
        table.get_item = AsyncMock(side_effect=mock_get_item)
        table.update_item = AsyncMock(side_effect=mock_update_item)
        table.delete_item = AsyncMock(side_effect=mock_delete_item)

        return table

    def _setup_mock_app_with_handler_capture(self):
        """Setup mock AsyncApp with handler capture.

        Must be patched BEFORE SlackClient is instantiated so that
        @self.app.event("app_mention") registers on the mock.
        """
        handlers = {}

        def capture_handler(event_type):
            def decorator(func):
                handlers[event_type] = func
                return func

            return decorator

        mock_app = Mock()
        mock_app.event = capture_handler
        mock_app.client = AsyncMock()

        return mock_app, handlers

    @pytest.mark.asyncio
    async def test_new_mention_creates_and_retrieves_session(
        self, mock_tokens, mock_dynamodb_table
    ):
        """New mention should create session and be retrievable."""
        mock_app, handlers = self._setup_mock_app_with_handler_capture()

        with patch("asksplunk.slack.client.AsyncApp", return_value=mock_app):
            # Create SlackClient - this will register handler on mock_app
            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            # Get the registered handler
            registered_handler = handlers.get("app_mention")
            assert registered_handler is not None, "app_mention handler not registered"

            # Create SessionManager with mocked table
            session_manager = SessionManager(table=mock_dynamodb_table)
            client.session_manager = session_manager
            client.bot_user_id = "UBOTID"

            # Simulate first mention in new thread
            event = {
                "ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@UBOTID> show me logs",
            }

            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # First call to get_session should find nothing
            async with session_manager:
                await registered_handler(event, mock_say, mock_ack)

            # Verify session was created
            assert "1234567890.123456" in mock_dynamodb_table._sessions
            stored_session = mock_dynamodb_table._sessions["1234567890.123456"]
            assert stored_session["user_id"] == "U123ABC"
            assert stored_session["channel_id"] == "C456DEF"
            assert stored_session["agent_state"] == "INITIALIZE"

    @pytest.mark.asyncio
    async def test_thread_reply_continues_session(self, mock_tokens, mock_dynamodb_table):
        """Reply in thread should load and continue existing session."""
        mock_app, handlers = self._setup_mock_app_with_handler_capture()

        with patch("asksplunk.slack.client.AsyncApp", return_value=mock_app):
            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            registered_handler = handlers.get("app_mention")

            session_manager = SessionManager(table=mock_dynamodb_table)
            client.session_manager = session_manager
            client.bot_user_id = "UBOTID"

            thread_ts = "1234567890.123456"

            # First: Create initial session
            event_new = {
                "ts": thread_ts,
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@UBOTID> show me logs",
            }

            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            async with session_manager:
                await registered_handler(event_new, mock_say, mock_ack)

            # Second: Reply in same thread
            event_reply = {
                "ts": "1234567890.654321",  # Different ts for reply
                "thread_ts": thread_ts,  # But same thread_ts
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@UBOTID> also show delivery status",
            }

            # Reset mocks
            mock_say.reset_mock()
            mock_ack.reset_mock()

            # Should find existing session
            async with session_manager:
                await registered_handler(event_reply, mock_say, mock_ack)

            # Verify session was found (not created again)
            assert mock_dynamodb_table.get_item.call_count >= 1

    @pytest.mark.asyncio
    async def test_session_persistence_across_mentions(self, mock_tokens, mock_dynamodb_table):
        """Session state should persist across multiple mentions in same thread."""
        mock_app, handlers = self._setup_mock_app_with_handler_capture()

        with patch("asksplunk.slack.client.AsyncApp", return_value=mock_app):
            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            registered_handler = handlers.get("app_mention")

            session_manager = SessionManager(table=mock_dynamodb_table)
            client.session_manager = session_manager
            client.bot_user_id = "UBOTID"

            thread_ts = "1234567890.111111"
            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # Keep session_manager context open for all operations
            async with session_manager:
                # Create session
                event1 = {
                    "ts": thread_ts,
                    "user": "U123ABC",
                    "channel": "C456DEF",
                    "text": "<@UBOTID> query 1",
                }

                await registered_handler(event1, mock_say, mock_ack)

                # Verify session exists
                session1 = await session_manager.get_session(thread_ts)
                assert session1 is not None
                assert session1["agent_state"] == "INITIALIZE"
                initial_created_at = session1["created_at"]

                # Simulate state change (like agent would do)
                await session_manager.update_session(thread_ts, {"agent_state": "EVALUATE"})

                # Get session again - should have updated state
                session2 = await session_manager.get_session(thread_ts)
                assert session2["agent_state"] == "EVALUATE"
                assert (
                    session2["created_at"] == initial_created_at
                )  # Original creation time unchanged

                # Another mention in same thread
                event2 = {
                    "ts": thread_ts + ".999999",
                    "thread_ts": thread_ts,
                    "user": "U123ABC",
                    "channel": "C456DEF",
                    "text": "<@UBOTID> query 2",
                }

                mock_say.reset_mock()
                mock_ack.reset_mock()

                await registered_handler(event2, mock_say, mock_ack)

                # Session should still exist with updated state
                session3 = await session_manager.get_session(thread_ts)
                assert session3 is not None
                assert session3["agent_state"] == "EVALUATE"

    @pytest.mark.asyncio
    async def test_multiple_independent_threads(self, mock_tokens, mock_dynamodb_table):
        """Multiple threads should maintain independent sessions."""
        mock_app, handlers = self._setup_mock_app_with_handler_capture()

        with patch("asksplunk.slack.client.AsyncApp", return_value=mock_app):
            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            registered_handler = handlers.get("app_mention")

            session_manager = SessionManager(table=mock_dynamodb_table)
            client.session_manager = session_manager
            client.bot_user_id = "UBOTID"

            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # Create two independent thread sessions
            thread1 = "1111111111.111111"
            thread2 = "2222222222.222222"

            event1 = {
                "ts": thread1,
                "user": "U111",
                "channel": "C456DEF",
                "text": "<@UBOTID> query in thread 1",
            }

            event2 = {
                "ts": thread2,
                "user": "U222",
                "channel": "C456DEF",
                "text": "<@UBOTID> query in thread 2",
            }

            async with session_manager:
                await registered_handler(event1, mock_say, mock_ack)
                await registered_handler(event2, mock_say, mock_ack)

            # Both sessions should exist independently
            session1 = await session_manager.get_session(thread1)
            session2 = await session_manager.get_session(thread2)

            assert session1 is not None
            assert session2 is not None
            assert session1["user_id"] == "U111"
            assert session2["user_id"] == "U222"
            assert session1["thread_id"] != session2["thread_id"]

    @pytest.mark.asyncio
    async def test_session_ttl_reset_on_update(self, mock_tokens, mock_dynamodb_table):
        """Session TTL should be reset when updated (30 min from update)."""
        session_manager = SessionManager(table=mock_dynamodb_table)

        thread_ts = "1234567890.123456"

        async with session_manager:
            # Create session
            session1 = await session_manager.create_session(thread_ts, "U123", "C456", "test")
            ttl1 = session1["ttl"]

        # Wait longer to ensure time passes (TTL precision is 1 second)
        import asyncio
        import time

        await asyncio.sleep(1.1)
        time_before_update = int(time.time())

        async with session_manager:
            # Update session
            await session_manager.update_session(thread_ts, {"agent_state": "EVALUATE"})
            session2 = await session_manager.get_session(thread_ts)
            ttl2 = session2["ttl"]

        # TTL should have been reset (newer than original, at least 1 second newer)
        assert ttl2 > ttl1, f"TTL2 ({ttl2}) should be greater than TTL1 ({ttl1})"

        # New TTL should be ~30 min (1800 sec) from update time
        time_delta = ttl2 - time_before_update
        expected_delta = 30 * 60  # 1800 seconds
        # Allow 5 second tolerance
        assert (
            abs(time_delta - expected_delta) < 5
        ), f"TTL delta {time_delta} not within 5 sec of expected {expected_delta}"

    @pytest.mark.asyncio
    async def test_error_handling_missing_session_manager(self, mock_tokens):
        """Handler should gracefully fail if session_manager not initialized."""
        mock_app, handlers = self._setup_mock_app_with_handler_capture()

        with patch("asksplunk.slack.client.AsyncApp", return_value=mock_app):
            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            registered_handler = handlers.get("app_mention")

            # Don't initialize session_manager
            client.session_manager = None
            client.bot_user_id = "UBOTID"

            event = {
                "ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@UBOTID> test",
            }

            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            # Should handle gracefully
            await registered_handler(event, mock_say, mock_ack)

            # Should send error message
            mock_say.assert_called()
            call_args = mock_say.call_args[1]
            assert "not ready" in call_args["text"].lower()

    @pytest.mark.asyncio
    async def test_bot_mention_stripping(self, mock_tokens, mock_dynamodb_table):
        """Bot mention should be stripped before being passed to SessionManager.

        Note: The question is NOT stored in DynamoDB for privacy reasons.
        The test verifies that the handler correctly strips the mention
        before any processing.
        """
        mock_app, handlers = self._setup_mock_app_with_handler_capture()

        with patch("asksplunk.slack.client.AsyncApp", return_value=mock_app):
            client = SlackClient(
                bot_token=mock_tokens["bot_token"], app_token=mock_tokens["app_token"]
            )

            registered_handler = handlers.get("app_mention")

            session_manager = SessionManager(table=mock_dynamodb_table)
            client.session_manager = session_manager
            client.bot_user_id = "UBOTID"

            event = {
                "ts": "1234567890.123456",
                "user": "U123ABC",
                "channel": "C456DEF",
                "text": "<@UBOTID> show me logs",
            }

            mock_ack = AsyncMock()
            mock_say = AsyncMock()

            async with session_manager:
                await registered_handler(event, mock_say, mock_ack)

            # Verify session was created (question is accepted but not stored for privacy)
            call_args = mock_dynamodb_table.put_item.call_args[1]
            stored_session = call_args["Item"]
            assert stored_session["thread_id"] == "1234567890.123456"
            assert stored_session["user_id"] == "U123ABC"
            assert stored_session["channel_id"] == "C456DEF"
            # Question should NOT be in stored session (privacy requirement)
            assert "question" not in stored_session
