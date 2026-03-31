"""Protocols for monitoring service integrations."""

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class NewRelicClientProtocol(Protocol):
    """Protocol for New Relic API client."""

    async def execute_nrql(self, nrql: str) -> List[Dict[str, Any]]:
        """Execute a NRQL query."""
        ...

    async def get_active_alerts(self, only_open: bool = True) -> List[Dict[str, Any]]:
        """Get active alert violations."""
        ...

    async def cleanup(self) -> None:
        """Clean up resources."""
        ...
