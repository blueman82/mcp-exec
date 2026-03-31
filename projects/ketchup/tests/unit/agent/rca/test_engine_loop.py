"""Tests for AgentEngine tool-calling loop (RCA Historian mode)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

import pytest
from unittest.mock import AsyncMock

from packages.agent.rag.engine import AgentEngine, RCA_MAX_ITERATIONS

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    r.retrieve.return_value = []
    return r


@pytest.fixture
def mock_context_builder():
    cb = AsyncMock()
    cb.build_context.return_value = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "test question"},
    ]
    return cb


@pytest.fixture
def mock_conversation_store():
    cs = AsyncMock()
    return cs


@pytest.fixture
def mock_api_executor():
    ae = AsyncMock()
    return ae


@pytest.fixture
def mock_tool_executor():
    te = AsyncMock()
    te.execute.return_value = '{"result": "tool output"}'
    return te


def _make_engine(retriever, context_builder, conversation_store, api_executor, tools=None, tool_executor=None):
    return AgentEngine(
        retriever=retriever,
        context_builder=context_builder,
        conversation_store=conversation_store,
        api_executor=api_executor,
        system_prompt="test system prompt",
        tools=tools,
        tool_executor=tool_executor,
    )


@pytest.mark.asyncio
async def test_single_turn_no_tools(mock_retriever, mock_context_builder, mock_conversation_store, mock_api_executor):
    """Verify single-turn RAG works without tools (existing behavior)."""
    mock_api_executor.execute_request.return_value = {
        "choices": [{"message": {"content": "answer without tools"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }

    engine = _make_engine(mock_retriever, mock_context_builder, mock_conversation_store, mock_api_executor)
    result = await engine.answer("test question", "C123", "1234.5678")

    assert "answer without tools" in result
    assert mock_api_executor.execute_request.call_count == 1


@pytest.mark.asyncio
async def test_tool_calling_loop(mock_retriever, mock_context_builder, mock_conversation_store, mock_api_executor, mock_tool_executor):
    """Verify tool-calling loop executes tools and gets final answer."""
    tools = [{"type": "function", "function": {"name": "test_tool"}}]

    # First response has tool_calls, second has final answer
    mock_api_executor.execute_request.side_effect = [
        {
            "choices": [{"message": {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "search_similar_incidents", "arguments": '{"query": "test"}'},
                }]
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
        {
            "choices": [{"message": {"content": "Final RCA answer"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
    ]

    engine = _make_engine(mock_retriever, mock_context_builder, mock_conversation_store, mock_api_executor, tools=tools, tool_executor=mock_tool_executor)
    result = await engine.answer("test question", "C123", "1234.5678")

    assert "Final RCA answer" in result
    assert mock_api_executor.execute_request.call_count == 2
    mock_tool_executor.execute.assert_called_once_with("search_similar_incidents", {"query": "test"})


@pytest.mark.asyncio
async def test_tool_loop_caps_at_max_iterations(mock_retriever, mock_context_builder, mock_conversation_store, mock_api_executor, mock_tool_executor):
    """Verify loop stops at RCA_MAX_ITERATIONS."""
    tools = [{"type": "function", "function": {"name": "test_tool"}}]

    # Always return tool_calls (never a final answer)
    tool_response = {
        "choices": [{"message": {
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "function": {"name": "search_similar_incidents", "arguments": '{"query": "test"}'},
            }]
        }}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }

    # After RCA_MAX_ITERATIONS loops, the final call should have no tool_calls
    final_response = {
        "choices": [{"message": {"content": "forced stop answer"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }

    responses = [tool_response] * RCA_MAX_ITERATIONS + [final_response]
    mock_api_executor.execute_request.side_effect = responses

    engine = _make_engine(mock_retriever, mock_context_builder, mock_conversation_store, mock_api_executor, tools=tools, tool_executor=mock_tool_executor)
    result = await engine.answer("test question", "C123", "1234.5678")

    # Should be initial call + RCA_MAX_ITERATIONS retries = RCA_MAX_ITERATIONS + 1
    assert mock_api_executor.execute_request.call_count == RCA_MAX_ITERATIONS + 1
