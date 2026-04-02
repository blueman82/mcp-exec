"""RCA Historian skill executor — thin adapter delegating to RCAToolExecutorProtocol."""

from typing import Any

from packages.core.typed_di.service_registrations.protocols.agent_protocols import (
    RCAToolExecutorProtocol,
)


class RCAHistorianExecutor:
    """Bridges BaseSkillExecutor interface to existing RCAToolExecutorProtocol.

    Delegates all tool execution to the RCAToolExecutor registered in TypedDI,
    which contains the dispatch table, truncation logic, and error handling.
    """

    def __init__(self) -> None:
        self._delegate: RCAToolExecutorProtocol | None = None

    async def setup(self, resolver: Any) -> None:
        """Resolve the RCAToolExecutorProtocol from TypedDI."""
        self._delegate = await resolver.aget(RCAToolExecutorProtocol)

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Delegate tool execution to the RCA tool executor."""
        if self._delegate is None:
            return "Error: RCAHistorianExecutor not initialized (call setup first)"
        return await self._delegate.execute(tool_name, arguments)
