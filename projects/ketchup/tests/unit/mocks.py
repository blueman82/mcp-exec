"""Shared mock classes for unit tests.

Each mock implements the corresponding protocol and tracks call metadata
for assertion in test cases.
"""

from typing import Any, Dict, List


class MockNewRelicClient:
    """Mock New Relic client for testing."""

    def __init__(self) -> None:
        self.call_count = 0
        self.last_nrql: str | None = None

    async def execute_nrql(self, nrql: str) -> List[Dict[str, Any]]:
        self.call_count += 1
        self.last_nrql = nrql
        return [{"count": 42}]

    async def get_active_alerts(self, only_open: bool = True) -> List[Dict[str, Any]]:
        return []

    async def cleanup(self) -> None:
        pass
