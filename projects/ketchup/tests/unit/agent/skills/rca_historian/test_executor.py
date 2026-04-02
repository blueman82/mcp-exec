"""Tests for RCAHistorianExecutor adapter."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.skills.rca_historian.executor import RCAHistorianExecutor
from packages.core.typed_di.service_registrations.protocols.agent_protocols import (
    RCAToolExecutorProtocol,
)

pytestmark = pytest.mark.unit


class TestRCAHistorianExecutor:
    """Test the thin adapter that delegates to RCAToolExecutorProtocol."""

    @pytest.mark.asyncio
    async def test_setup_resolves_protocol(self) -> None:
        mock_delegate = AsyncMock()
        mock_resolver = AsyncMock()
        mock_resolver.aget.return_value = mock_delegate

        executor = RCAHistorianExecutor()
        await executor.setup(mock_resolver)

        assert executor._delegate is mock_delegate

    @pytest.mark.asyncio
    async def test_setup_calls_aget_with_rca_protocol(self) -> None:

        mock_delegate = AsyncMock()
        mock_resolver = AsyncMock()
        mock_resolver.aget.return_value = mock_delegate

        executor = RCAHistorianExecutor()
        await executor.setup(mock_resolver)

        mock_resolver.aget.assert_called_once_with(RCAToolExecutorProtocol)

    @pytest.mark.asyncio
    async def test_execute_delegates_to_rca_executor(self) -> None:
        mock_delegate = AsyncMock()
        mock_delegate.execute.return_value = "rca result"
        mock_resolver = AsyncMock()
        mock_resolver.aget.return_value = mock_delegate

        executor = RCAHistorianExecutor()
        await executor.setup(mock_resolver)

        result = await executor.execute("search_similar_incidents", {"query": "test"})
        assert result == "rca result"
        mock_delegate.execute.assert_called_once_with("search_similar_incidents", {"query": "test"})

    @pytest.mark.asyncio
    async def test_execute_passes_tool_name_through(self) -> None:
        mock_delegate = AsyncMock()
        mock_delegate.execute.return_value = "result"
        mock_resolver = AsyncMock()
        mock_resolver.aget.return_value = mock_delegate

        executor = RCAHistorianExecutor()
        await executor.setup(mock_resolver)

        await executor.execute("get_active_alerts", {})
        mock_delegate.execute.assert_called_once_with("get_active_alerts", {})

    @pytest.mark.asyncio
    async def test_execute_without_setup_returns_error(self) -> None:
        executor = RCAHistorianExecutor()
        result = await executor.execute("any_tool", {})
        assert "not initialized" in result

    @pytest.mark.asyncio
    async def test_delegate_is_none_before_setup(self) -> None:
        executor = RCAHistorianExecutor()
        assert executor._delegate is None

    @pytest.mark.asyncio
    async def test_execute_returns_delegate_result_verbatim(self) -> None:
        json_result = '{"incidents": [{"id": "1", "score": 0.95}]}'
        mock_delegate = AsyncMock()
        mock_delegate.execute.return_value = json_result
        mock_resolver = AsyncMock()
        mock_resolver.aget.return_value = mock_delegate

        executor = RCAHistorianExecutor()
        await executor.setup(mock_resolver)

        result = await executor.execute("search_similar_incidents", {"query": "ORA-01555"})
        assert result == json_result

    @pytest.mark.asyncio
    async def test_execute_can_be_called_multiple_times(self) -> None:
        mock_delegate = AsyncMock()
        mock_delegate.execute.side_effect = ["first", "second", "third"]
        mock_resolver = AsyncMock()
        mock_resolver.aget.return_value = mock_delegate

        executor = RCAHistorianExecutor()
        await executor.setup(mock_resolver)

        assert await executor.execute("tool_a", {}) == "first"
        assert await executor.execute("tool_b", {}) == "second"
        assert await executor.execute("tool_c", {}) == "third"
        assert mock_delegate.execute.call_count == 3
