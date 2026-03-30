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


class TestLinkifyJiraTickets:
    """Tests for _linkify_jira_tickets() function."""

    from packages.agent.rag.engine import _linkify_jira_tickets
    from packages.core.jira_constants import VALID_JIRA_PROJECTS

    def test_bare_ticket_gets_linkified(self):
        """Plain JIRA ticket reference should be converted to Slack mrkdwn link."""
        from packages.agent.rag.engine import _linkify_jira_tickets

        text = "See CPGNTT-12345 for details."
        result = _linkify_jira_tickets(text)
        assert (
            result
            == "See <https://jira.corp.adobe.com/browse/CPGNTT-12345|CPGNTT-12345> for details."
        )

    def test_already_linked_ticket_unchanged(self):
        """Ticket already inside a Slack link should not be re-linkified."""
        from packages.agent.rag.engine import _linkify_jira_tickets

        text = "See <https://jira.corp.adobe.com/browse/CPGNTT-123|CPGNTT-123> for details."
        result = _linkify_jira_tickets(text)
        assert result == text

    def test_all_valid_projects_linkified(self):
        """All VALID_JIRA_PROJECTS keys should be linkified."""
        from packages.agent.rag.engine import _linkify_jira_tickets
        from packages.core.jira_constants import VALID_JIRA_PROJECTS

        for project in VALID_JIRA_PROJECTS:
            text = f"Reference {project}-999 in the text."
            result = _linkify_jira_tickets(text)
            expected = f"Reference <https://jira.corp.adobe.com/browse/{project}-999|{project}-999> in the text."
            assert result == expected, f"Failed for project {project}"

    def test_invalid_project_not_linkified(self):
        """Tickets with invalid project prefixes should not be linkified."""
        from packages.agent.rag.engine import _linkify_jira_tickets

        text = "See INVALID-123 and ABC-999 for reference."
        result = _linkify_jira_tickets(text)
        assert result == text

    def test_ticket_at_string_boundaries(self):
        """Tickets at start and end of string should be linkified."""
        from packages.agent.rag.engine import _linkify_jira_tickets

        text = "CPGNTT-111 and more text CPGNTT-222"
        result = _linkify_jira_tickets(text)
        expected = "<https://jira.corp.adobe.com/browse/CPGNTT-111|CPGNTT-111> and more text <https://jira.corp.adobe.com/browse/CPGNTT-222|CPGNTT-222>"
        assert result == expected

    def test_ticket_adjacent_to_punctuation(self):
        """Tickets adjacent to punctuation should be linkified correctly."""
        from packages.agent.rag.engine import _linkify_jira_tickets

        # Period after ticket
        text1 = "See CPGNTT-123."
        result1 = _linkify_jira_tickets(text1)
        assert result1 == "See <https://jira.corp.adobe.com/browse/CPGNTT-123|CPGNTT-123>."

        # Parentheses around ticket
        text2 = "(CPGNTT-456)"
        result2 = _linkify_jira_tickets(text2)
        assert result2 == "(<https://jira.corp.adobe.com/browse/CPGNTT-456|CPGNTT-456>)"

        # Comma after ticket
        text3 = "Tickets: CPGNTT-789, and more"
        result3 = _linkify_jira_tickets(text3)
        assert (
            result3
            == "Tickets: <https://jira.corp.adobe.com/browse/CPGNTT-789|CPGNTT-789>, and more"
        )

    def test_multiple_tickets_in_text(self):
        """Text with multiple different tickets should linkify all of them."""
        from packages.agent.rag.engine import _linkify_jira_tickets

        text = "Fixed in CPGNTT-100, see also NEO-200 and CAMP-300 for context."
        result = _linkify_jira_tickets(text)
        expected = "Fixed in <https://jira.corp.adobe.com/browse/CPGNTT-100|CPGNTT-100>, see also <https://jira.corp.adobe.com/browse/NEO-200|NEO-200> and <https://jira.corp.adobe.com/browse/CAMP-300|CAMP-300> for context."
        assert result == expected
