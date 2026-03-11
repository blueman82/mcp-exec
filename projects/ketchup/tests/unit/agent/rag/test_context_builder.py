"""Tests for context builder."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.rag.context_builder import ContextBuilder


@pytest.fixture
def mock_conversation_store():
    store = AsyncMock()
    store.get_history.return_value = []
    return store


@pytest.fixture
def builder(mock_conversation_store):
    return ContextBuilder(conversation_store=mock_conversation_store)


class TestBuildContext:
    @pytest.mark.asyncio
    async def test_minimal_context(self, builder):
        messages = await builder.build_context(
            question="What happened?",
            channel_id="C123",
            thread_ts="1234.5678",
            retrieved_chunks=[],
            system_prompt="You are a helpful agent.",
        )
        # Should have system prompt + user question
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "What happened?"

    @pytest.mark.asyncio
    async def test_includes_context_chunks(self, builder):
        chunks = [
            {"text": "User A said hello at 10am", "metadata": {}},
            {"text": "User B replied at 11am", "metadata": {}},
        ]
        messages = await builder.build_context(
            question="What happened?",
            channel_id="C123",
            thread_ts="1234.5678",
            retrieved_chunks=chunks,
            system_prompt="System prompt",
        )
        # system + context block + question = 3
        assert len(messages) == 3
        assert "relevant context" in messages[1]["content"].lower()

    @pytest.mark.asyncio
    async def test_includes_conversation_history(self, builder, mock_conversation_store):
        from packages.agent.conversation.models import ConversationTurn

        mock_conversation_store.get_history.return_value = [
            ConversationTurn(
                channel_id="C123",
                thread_ts="1234.5678",
                timestamp="100",
                role="user",
                content="first question",
            ),
            ConversationTurn(
                channel_id="C123",
                thread_ts="1234.5678",
                timestamp="101",
                role="assistant",
                content="first answer",
            ),
        ]

        messages = await builder.build_context(
            question="Follow up?",
            channel_id="C123",
            thread_ts="1234.5678",
            retrieved_chunks=[],
            system_prompt="System prompt",
        )
        # system + 2 history + question = 4
        assert len(messages) == 4
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
