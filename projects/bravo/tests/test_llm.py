"""Tests for the LLM scoring service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bravo.config import LLMSettings
from bravo.services.llm import LLMScore, LLMService


def _make_settings(**overrides) -> LLMSettings:
    """Create LLMSettings with test defaults."""
    defaults = {
        "model": "test-model",
        "api_key": "test-key",
        "endpoint": "https://test.openai.azure.com/",
        "api_version": "2024-12-01-preview",
    }
    return LLMSettings(**(defaults | overrides))


def _mock_response(content: str) -> MagicMock:
    """Create a mock API response with given content."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestScoreTicket:
    """Tests for LLMService.score_ticket()."""

    async def test_score_ticket_success(self):
        service = LLMService(_make_settings())
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            '{"clarity": 4.5, "completeness": 3.5, "root_cause": 2.0, "actionability": 5.0}'
        )
        service._client = mock_client

        score = await service.score_ticket("TEST-1", "summary", ["comment"])

        assert score.clarity == 4.5
        assert score.completeness == 3.5
        assert score.root_cause == 2.0
        assert score.actionability == 5.0

    async def test_score_ticket_uses_reasoning_effort(self):
        service = LLMService(_make_settings(reasoning_effort="medium"))
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            '{"clarity": 3.0, "completeness": 3.0, "root_cause": 3.0, "actionability": 3.0}'
        )
        service._client = mock_client

        await service.score_ticket("TEST-1", "summary", ["comment"])

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["reasoning_effort"] == "medium"

    async def test_score_ticket_api_error_returns_fallback(self):
        service = LLMService(_make_settings())
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        service._client = mock_client

        score = await service.score_ticket("TEST-1", "summary", ["comment"])

        assert score == LLMScore(
            clarity=3.0, completeness=3.0, root_cause=3.0, actionability=3.0
        )

    async def test_score_ticket_bad_json_returns_fallback(self):
        service = LLMService(_make_settings())
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response("not json")
        service._client = mock_client

        score = await service.score_ticket("TEST-1", "summary", ["comment"])

        assert score == LLMScore(
            clarity=3.0, completeness=3.0, root_cause=3.0, actionability=3.0
        )

    async def test_score_ticket_missing_keys_returns_fallback(self):
        service = LLMService(_make_settings())
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            '{"clarity": 4.0}'
        )
        service._client = mock_client

        score = await service.score_ticket("TEST-1", "summary", ["comment"])

        assert score == LLMScore(
            clarity=3.0, completeness=3.0, root_cause=3.0, actionability=3.0
        )


class TestClientLifecycle:
    """Tests for client lazy init and close."""

    def test_get_client_lazy_init(self):
        service = LLMService(_make_settings())
        assert service._client is None

        client1 = service._get_client()
        assert client1 is not None

        client2 = service._get_client()
        assert client2 is client1

    async def test_close_with_client(self):
        service = LLMService(_make_settings())
        mock_client = AsyncMock()
        service._client = mock_client

        await service.close()

        mock_client.aclose.assert_awaited_once()
        assert service._client is None

    async def test_close_without_client(self):
        service = LLMService(_make_settings())
        assert service._client is None

        await service.close()  # Should not raise

        assert service._client is None
