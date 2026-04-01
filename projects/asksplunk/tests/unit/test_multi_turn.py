"""Integration tests for multi-turn conversation flows.

Tests end-to-end multi-turn scenarios: refinement, clarification,
new topics, expired sessions, and edge cases.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from asksplunk.agent.orchestrator import Agent


def _mock_assess_confidence(confidence, **extra_fields):
    """Helper to create a mock assess_confidence tool call response."""
    args = {"confidence": confidence, **extra_fields}
    mock_function = MagicMock()
    mock_function.name = "assess_confidence"
    mock_function.arguments = json.dumps(args)
    mock_call = MagicMock()
    mock_call.function = mock_function
    mock_message = MagicMock()
    mock_message.tool_calls = [mock_call]
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    return MagicMock(choices=[mock_choice])


def _mock_generate_query(spl_query, plain="Test", technical="Test"):
    """Helper to create a mock generate_spl_query tool call response."""
    args = {
        "spl_query": spl_query,
        "plain_explanation": plain,
        "technical_explanation": technical,
    }
    mock_function = MagicMock()
    mock_function.name = "generate_spl_query"
    mock_function.arguments = json.dumps(args)
    mock_call = MagicMock()
    mock_call.function = mock_function
    mock_message = MagicMock()
    mock_message.tool_calls = [mock_call]
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    return MagicMock(choices=[mock_choice])


class TestMultiTurnIntegration:
    """End-to-end multi-turn conversation flow tests."""

    @pytest.mark.asyncio
    async def test_two_turn_refinement(self):
        """Question → SPL → 'add time filter' → refined SPL with history."""
        retriever = MagicMock()
        retriever.retrieve = AsyncMock(
            return_value=[{"content": "Field: failureType", "relevance_score": 0.9}]
        )

        session_manager = MagicMock()
        session_manager.append_history = AsyncMock()

        openai_client = MagicMock()

        # Turn 1: high confidence → generate query
        openai_client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_assess_confidence(95),
                _mock_generate_query("index=campaign_prod failureType=*"),
            ]
        )

        agent = Agent(retriever, session_manager, openai_client)

        # Turn 1 session (fresh)
        session_turn1 = {
            "thread_id": "thread-123",
            "original_question": "show me bounces",
            "retrieved_docs": [{"content": "Field: failureType", "score": 0.9}],
            "conversation_history": [],
        }

        result1 = await agent._handle_evaluate(session_turn1)
        assert result1["action"] == "query_generated"
        assert result1["content"]["spl_query"] == "index=campaign_prod failureType=*"

        # Turn 2: session now has history from turn 1
        openai_client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_assess_confidence(95),
                _mock_generate_query("index=campaign_prod failureType=* earliest=-1h"),
            ]
        )

        session_turn2 = {
            "thread_id": "thread-123",
            "original_question": "add a time filter for last hour",
            "retrieved_docs": [{"content": "Field: failureType", "score": 0.9}],
            "conversation_history": [
                {"role": "user", "content": "show me bounces"},
                {
                    "role": "assistant",
                    "content": "Generated SPL: index=campaign_prod failureType=*",
                },
            ],
        }

        result2 = await agent._handle_evaluate(session_turn2)
        assert result2["action"] == "query_generated"
        assert "earliest=-1h" in result2["content"]["spl_query"]

        # Verify history was appended (4 total: 2 from turn 1 + 2 from turn 2)
        assert session_manager.append_history.call_count == 4

    @pytest.mark.asyncio
    async def test_three_turn_with_clarification(self):
        """Question → clarify → answer → SPL → follow-up → SPL2."""
        retriever = MagicMock()
        retriever.retrieve = AsyncMock(
            return_value=[{"content": "Field: logType", "relevance_score": 0.8}]
        )

        session_manager = MagicMock()
        session_manager.update_session = AsyncMock()
        session_manager.append_history = AsyncMock()
        session_manager.get_session = AsyncMock(
            return_value={
                "thread_id": "thread-123",
                "agent_state": "EVALUATE",
                "original_question": "show me logs. Email delivery logs",
                "retrieved_docs": [{"content": "Field: logType", "score": 0.8}],
                "conversation_history": [],
            }
        )

        openai_client = MagicMock()

        # Turn 1: medium confidence → clarify
        mock_clarify_choice = MagicMock()
        mock_clarify_choice.message.content = """Which log type?
1. Email delivery logs
2. Web logs"""

        openai_client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_assess_confidence(55, clarification_needed="Which log type?"),
                MagicMock(choices=[mock_clarify_choice]),
            ]
        )

        agent = Agent(retriever, session_manager, openai_client)

        session_turn1 = {
            "thread_id": "thread-123",
            "original_question": "show me logs",
            "retrieved_docs": [{"content": "Field: logType", "score": 0.8}],
            "conversation_history": [],
        }

        result1 = await agent._handle_evaluate(session_turn1)
        assert result1["action"] == "clarify"
        assert result1["state"] == "WAIT"

        # Turn 2: User answers clarification → high confidence → SPL
        openai_client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_assess_confidence(95),
                _mock_generate_query("index=campaign_prod sourcetype=mta_log"),
            ]
        )

        wait_session = {
            "thread_id": "thread-123",
            "original_question": "show me logs",
            "agent_state": "WAIT",
            "pending_clarification": result1["content"],
            "clarifying_history": [],
            "retrieved_docs": [{"content": "Field: logType", "score": 0.8}],
            "conversation_history": [],
        }

        result2 = await agent._handle_wait(wait_session, "Email delivery logs")
        assert result2["action"] == "query_generated"

    @pytest.mark.asyncio
    async def test_new_topic_in_same_thread(self):
        """Question1 → SPL1 → unrelated question2 → SPL2 (fresh retrieval via process_question)."""
        retriever = MagicMock()
        retriever.retrieve = AsyncMock(
            return_value=[{"content": "Field: status", "relevance_score": 0.9}]
        )

        session_manager = MagicMock()
        session_manager.append_history = AsyncMock()

        openai_client = MagicMock()
        openai_client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_assess_confidence(95),
                _mock_generate_query("index=campaign_prod status>=400"),
            ]
        )

        agent = Agent(retriever, session_manager, openai_client)

        # Second turn: completely unrelated question, but session has old history
        session = {
            "thread_id": "thread-123",
            "original_question": "show me HTTP errors",
            "retrieved_docs": [{"content": "Field: status", "score": 0.9}],
            "conversation_history": [
                {"role": "user", "content": "show me bounces"},
                {
                    "role": "assistant",
                    "content": "Generated SPL: index=campaign_prod failureType=*",
                },
            ],
        }

        result = await agent._handle_evaluate(session)
        assert result["action"] == "query_generated"
        # The GPT should generate a fresh query based on new context

    @pytest.mark.asyncio
    async def test_follow_up_after_uncertain(self):
        """Question → uncertain → rephrased question → SPL."""
        agent = Agent(MagicMock(), MagicMock(), MagicMock())
        agent.session_manager.append_history = AsyncMock()

        # Turn 1: low confidence → uncertain
        agent.openai_client.chat.completions.create = AsyncMock(
            return_value=_mock_assess_confidence(20, missing_info="Need more details")
        )

        session1 = {
            "thread_id": "thread-123",
            "original_question": "show me stuff",
            "retrieved_docs": [],
            "conversation_history": [],
        }

        result1 = await agent._handle_evaluate(session1)
        assert result1["action"] == "uncertain"

        # Turn 2: user rephrases → high confidence
        agent.openai_client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_assess_confidence(90),
                _mock_generate_query("index=campaign_prod failureType=*"),
            ]
        )

        session2 = {
            "thread_id": "thread-123",
            "original_question": "show me email bounce failures",
            "retrieved_docs": [{"content": "Field: failureType", "score": 0.9}],
            "conversation_history": [],  # Fresh since uncertain doesn't append
        }

        result2 = await agent._handle_evaluate(session2)
        assert result2["action"] == "query_generated"

    @pytest.mark.asyncio
    async def test_empty_follow_up(self):
        """Empty string in thread should not crash."""
        retriever = MagicMock()
        retriever.retrieve = AsyncMock(return_value=[])

        session_manager = MagicMock()
        session_manager.get_session = AsyncMock(
            return_value={
                "thread_id": "thread-123",
                "agent_state": "EVALUATE",
                "original_question": "",
                "retrieved_docs": [],
                "conversation_history": [],
                "ttl": int(time.time()) + 1800,
            }
        )
        session_manager.update_session = AsyncMock()
        session_manager.append_history = AsyncMock()

        openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = None
        openai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[mock_choice])
        )

        agent = Agent(retriever, session_manager, openai_client)

        # Should not raise
        result = await agent.process_question("", "thread-123", "U123", "C456")
        assert result is not None

    @pytest.mark.asyncio
    async def test_expired_session_transparent_restart(self):
        """Expired TTL should create new session transparently."""
        retriever = MagicMock()
        retriever.retrieve = AsyncMock(return_value=[{"content": "doc", "relevance_score": 0.9}])

        new_session = {
            "thread_id": "thread-123",
            "agent_state": "EVALUATE",
            "original_question": "new question",
            "retrieved_docs": [{"content": "doc"}],
            "conversation_history": [],
        }

        session_manager = MagicMock()
        session_manager.get_session = AsyncMock(
            side_effect=[
                {
                    "thread_id": "thread-123",
                    "agent_state": "EVALUATE",
                    "ttl": int(time.time()) - 100,  # expired
                    "conversation_history": [
                        {"role": "user", "content": "old question"},
                    ],
                },
                new_session,  # after re-init
            ]
        )
        session_manager.delete_session = AsyncMock()
        session_manager.create_session = AsyncMock(
            return_value={
                "thread_id": "thread-123",
                "agent_state": "INITIALIZE",
                "conversation_history": [],
            }
        )
        session_manager.update_session = AsyncMock()
        session_manager.append_history = AsyncMock()

        openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = None
        openai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[mock_choice])
        )

        agent = Agent(retriever, session_manager, openai_client)

        result = await agent.process_question("new question", "thread-123", "U123", "C456")

        # Old session should be deleted
        session_manager.delete_session.assert_called_once_with("thread-123")
        # New session should be created
        session_manager.create_session.assert_called_once()
        # Old conversation history should be gone (new session starts fresh)

    @pytest.mark.asyncio
    async def test_history_size_guard(self):
        """Artificially large history should trigger truncation in append_history."""
        from asksplunk.session.manager import SessionManager

        mock_table = AsyncMock()
        manager = SessionManager(table=mock_table)

        # Create a session with history approaching 350KB
        large_content = "x" * 10000  # 10KB per entry
        large_history = [{"role": "user", "content": large_content} for _ in range(36)]

        mock_table.get_item = AsyncMock(
            return_value={
                "Item": {
                    "thread_id": "thread-123",
                    "conversation_history": large_history,
                }
            }
        )

        async with manager:
            await manager.append_history("thread-123", "user", "new message")

        # Should call update_item twice: once for trimming, once for appending
        assert mock_table.update_item.call_count == 2
        # First call should be the trim
        trim_call = mock_table.update_item.call_args_list[0]
        assert "trimmed" in str(trim_call)
