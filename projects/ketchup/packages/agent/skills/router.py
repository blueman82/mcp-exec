"""Skill router — dispatches tool calls to the correct skill executor."""

from typing import Any

from packages.agent.skills.base import BaseSkillExecutor
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class SkillRouter:
    """Routes tool calls to the appropriate skill executor.

    Same execute() signature as RCAToolExecutorProtocol — AgentEngine works unchanged.
    """

    def __init__(self, dispatch_table: dict[str, BaseSkillExecutor]) -> None:
        self._dispatch_table = dispatch_table

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool call by dispatching to the registered executor."""
        executor = self._dispatch_table.get(tool_name)
        if executor is None:
            logger.error(
                "Unknown tool: %s (registered: %s)", tool_name, list(self._dispatch_table.keys())
            )
            return f"Error: Unknown tool '{tool_name}'"
        return await executor.execute(tool_name, arguments)
