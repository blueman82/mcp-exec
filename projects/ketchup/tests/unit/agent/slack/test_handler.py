"""Tests for AgentSlackHandler."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from packages.agent.slack.handler import (
    AgentSlackHandler,
    is_agent_enabled,
    strip_bot_mention,
)


class TestStripBotMention:
    def test_strips_mention(self):
        assert strip_bot_mention("<@U123> hello", "U123") == "hello"

    def test_no_mention(self):
        assert strip_bot_mention("hello world", "U123") == "hello world"

    def test_multiple_mentions(self):
        result = strip_bot_mention("<@U123> hello <@U123>", "U123")
        assert result == "hello"


class TestIsAgentEnabled:
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert is_agent_enabled() is False

    def test_enabled(self):
        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            assert is_agent_enabled() is True


class TestHandleMention:
    @pytest.fixture
    def handler(self):
        return AgentSlackHandler(
            agent_engine=AsyncMock(),
            conversation_store=AsyncMock(),
            thread_manager=AsyncMock(),
            posting_handler=AsyncMock(),
            secrets_manager=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self, handler):
        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "false"}):
            await handler.handle_mention({"text": "test?", "channel": "C1"})
            handler._agent_engine.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_empty_question(self, handler):
        handler._secrets_manager.get_bot_slack_user_id_async.return_value = "UBOT"

        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            await handler.handle_mention(
                {
                    "channel": "C123",
                    "user": "U456",
                    "text": "<@UBOT>",
                    "ts": "1234.5678",
                }
            )

        handler._agent_engine.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_new_conversation(self, handler):
        """Any non-empty mention triggers a new agent conversation — no regex filtering."""
        handler._secrets_manager.get_bot_slack_user_id_async.return_value = "UBOT"
        handler._conversation_store.is_agent_thread.return_value = False
        handler._thread_manager.post_thinking_indicator.return_value = "msg_ts"
        handler._agent_engine.answer.return_value = "Here is the answer"

        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            await handler.handle_mention(
                {
                    "channel": "C123",
                    "user": "U456",
                    "text": "<@UBOT> what happened today?",
                    "ts": "1234.5678",
                }
            )

        handler._thread_manager.register_thread.assert_called_once()
        handler._agent_engine.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_non_question_mention(self, handler):
        """Elimination routing: even non-question mentions go to the agent."""
        handler._secrets_manager.get_bot_slack_user_id_async.return_value = "UBOT"
        handler._thread_manager.post_thinking_indicator.return_value = "msg_ts"
        handler._agent_engine.answer.return_value = "Response"

        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            await handler.handle_mention(
                {
                    "channel": "C123",
                    "user": "U456",
                    "text": "<@UBOT> CPGNTT-1234",
                    "ts": "1234.5678",
                }
            )

        # No regex filtering — agent handles it
        handler._agent_engine.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_thread_reply_to_existing(self, handler):
        handler._secrets_manager.get_bot_slack_user_id_async.return_value = "UBOT"
        handler._conversation_store.is_agent_thread.return_value = True
        handler._thread_manager.post_thinking_indicator.return_value = "msg_ts"
        handler._agent_engine.answer.return_value = "Follow-up answer"

        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            await handler.handle_mention(
                {
                    "channel": "C123",
                    "user": "U456",
                    "text": "<@UBOT> follow up question",
                    "ts": "1234.5679",
                    "thread_ts": "1234.5678",
                }
            )

        # Should NOT register a new thread (it's an existing one)
        handler._thread_manager.register_thread.assert_not_called()
        handler._agent_engine.answer.assert_called_once()
