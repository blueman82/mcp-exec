"""Tests for agent engine (single-pass retrieval, no re-ranking)."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.rag.engine import AgentEngine


@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    r.retrieve.return_value = [
        {"id": "1", "text": "context text", "metadata": {}, "score": 0.9},
    ]
    return r


@pytest.fixture
def mock_context_builder():
    cb = AsyncMock()
    cb.build_context.return_value = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "question"},
    ]
    return cb


@pytest.fixture
def mock_conversation_store():
    store = AsyncMock()
    return store


@pytest.fixture
def mock_api_executor():
    executor = AsyncMock()
    executor.execute_request.return_value = {
        "choices": [{"message": {"content": "Here is the answer."}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    return executor


@pytest.fixture
def engine(mock_retriever, mock_context_builder, mock_conversation_store, mock_api_executor):
    return AgentEngine(
        retriever=mock_retriever,
        context_builder=mock_context_builder,
        conversation_store=mock_conversation_store,
        api_executor=mock_api_executor,
        system_prompt="You are a helpful agent.",
    )


class TestAnswer:
    @pytest.mark.asyncio
    async def test_returns_response(self, engine):
        result = await engine.answer("What happened?", "C123", "1234.5678", "U456")
        assert result == "Here is the answer."

    @pytest.mark.asyncio
    async def test_stores_both_turns(self, engine, mock_conversation_store):
        await engine.answer("What happened?", "C123", "1234.5678", "U456")
        assert mock_conversation_store.store_turn.call_count == 2
        calls = mock_conversation_store.store_turn.call_args_list
        assert calls[0][0][0].role == "user"
        assert calls[1][0][0].role == "assistant"

    @pytest.mark.asyncio
    async def test_calls_retriever_with_channel(self, engine, mock_retriever):
        await engine.answer("question", "C456", "ts", "U1")
        mock_retriever.retrieve.assert_called_once()
        assert mock_retriever.retrieve.call_args[1]["channel_id"] == "C456"

    @pytest.mark.asyncio
    async def test_single_pass_retrieval(self, engine, mock_retriever):
        """No rerank_top_k parameter — single retrieval pass."""
        await engine.answer("question", "C123", "ts")
        call_kwargs = mock_retriever.retrieve.call_args[1]
        assert "rerank_top_k" not in call_kwargs
        assert "top_k" in call_kwargs

    @pytest.mark.asyncio
    async def test_fallback_on_empty_response(self, engine, mock_api_executor):
        mock_api_executor.execute_request.return_value = {"choices": []}
        result = await engine.answer("question", "C123", "ts")
        assert "wasn't able to generate" in result.lower()
