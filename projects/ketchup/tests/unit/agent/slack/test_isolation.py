"""Tests for cross-feature isolation."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.slack.isolation import AgentThreadFilter


@pytest.fixture
def mock_conversation_store():
    store = AsyncMock()
    store.get_agent_thread_ts_set.return_value = {"100.0", "200.0"}
    return store


@pytest.fixture
def filter_instance(mock_conversation_store):
    return AgentThreadFilter(conversation_store=mock_conversation_store)


class TestGetAgentThreads:
    @pytest.mark.asyncio
    async def test_returns_thread_set(self, filter_instance):
        result = await filter_instance.get_agent_threads("C123")
        assert result == {"100.0", "200.0"}

    @pytest.mark.asyncio
    async def test_always_fetches_fresh(self, filter_instance, mock_conversation_store):
        await filter_instance.get_agent_threads("C123")
        await filter_instance.get_agent_threads("C123")
        # Always fetches fresh data to detect newly registered threads
        assert mock_conversation_store.get_agent_thread_ts_set.call_count == 2


class TestIsAgentThreadMessage:
    def test_message_in_agent_thread(self, filter_instance):
        msg = {"text": "hello", "thread_ts": "100.0"}
        assert filter_instance.is_agent_thread_message(msg, {"100.0", "200.0"}) is True

    def test_message_not_in_agent_thread(self, filter_instance):
        msg = {"text": "hello", "thread_ts": "999.0"}
        assert filter_instance.is_agent_thread_message(msg, {"100.0"}) is False

    def test_message_without_thread(self, filter_instance):
        msg = {"text": "hello"}
        assert filter_instance.is_agent_thread_message(msg, {"100.0"}) is False


class TestClearCache:
    @pytest.mark.asyncio
    async def test_clear_specific_channel(self, filter_instance):
        await filter_instance.get_agent_threads("C123")
        filter_instance.clear_cache("C123")
        assert "C123" not in filter_instance._cache

    @pytest.mark.asyncio
    async def test_clear_all(self, filter_instance):
        await filter_instance.get_agent_threads("C123")
        filter_instance.clear_cache()
        assert len(filter_instance._cache) == 0
