"""Tests for SkillRouter tool dispatch."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.skills.router import SkillRouter

pytestmark = pytest.mark.unit


class TestSkillRouter:
    """Test SkillRouter dispatches to correct executors."""

    @pytest.mark.asyncio
    async def test_dispatches_to_correct_executor(self) -> None:
        executor_a = AsyncMock()
        executor_a.execute.return_value = "result_a"
        executor_b = AsyncMock()
        executor_b.execute.return_value = "result_b"

        router = SkillRouter({"tool_a": executor_a, "tool_b": executor_b})

        result = await router.execute("tool_a", {"arg": "value"})
        assert result == "result_a"
        executor_a.execute.assert_called_once_with("tool_a", {"arg": "value"})

    @pytest.mark.asyncio
    async def test_dispatches_second_executor(self) -> None:
        executor_a = AsyncMock()
        executor_a.execute.return_value = "result_a"
        executor_b = AsyncMock()
        executor_b.execute.return_value = "result_b"

        router = SkillRouter({"tool_a": executor_a, "tool_b": executor_b})

        result = await router.execute("tool_b", {"key": "val"})
        assert result == "result_b"
        executor_b.execute.assert_called_once_with("tool_b", {"key": "val"})
        executor_a.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_tool(self) -> None:
        router = SkillRouter({"known_tool": AsyncMock()})

        result = await router.execute("unknown_tool", {})
        assert "Error: Unknown tool 'unknown_tool'" in result

    @pytest.mark.asyncio
    async def test_empty_dispatch_table(self) -> None:
        router = SkillRouter({})
        result = await router.execute("any_tool", {})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_passes_arguments_through_unchanged(self) -> None:
        executor = AsyncMock()
        executor.execute.return_value = "ok"
        args = {"query": "test query", "limit": 10, "nested": {"key": "value"}}

        router = SkillRouter({"tool": executor})
        await router.execute("tool", args)

        executor.execute.assert_called_once_with("tool", args)

    @pytest.mark.asyncio
    async def test_passes_empty_arguments(self) -> None:
        executor = AsyncMock()
        executor.execute.return_value = "ok"

        router = SkillRouter({"no_args_tool": executor})
        await router.execute("no_args_tool", {})

        executor.execute.assert_called_once_with("no_args_tool", {})

    @pytest.mark.asyncio
    async def test_returns_executor_result_verbatim(self) -> None:
        executor = AsyncMock()
        executor.execute.return_value = '{"incidents": []}'

        router = SkillRouter({"search": executor})
        result = await router.execute("search", {"query": "test"})

        assert result == '{"incidents": []}'

    @pytest.mark.asyncio
    async def test_error_message_contains_tool_name(self) -> None:
        router = SkillRouter({"existing_tool": AsyncMock()})

        result = await router.execute("missing_tool", {})
        assert "missing_tool" in result
