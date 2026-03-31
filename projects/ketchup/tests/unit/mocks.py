"""Shared mock classes for unit tests.

Each mock implements the corresponding protocol and tracks call metadata
for assertion in test cases.
"""

from typing import Any, Dict, List, Optional


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


class MockVectorStore:
    """Mock ChromaDB vector store for testing."""

    def __init__(self) -> None:
        self.query_count = 0
        self.last_channel_id: Optional[str] = None

    async def query(
        self,
        query_embedding: List[float],
        channel_id: Optional[str] = None,
        top_k: int = 15,
    ) -> List[Dict[str, Any]]:
        self.query_count += 1
        self.last_channel_id = channel_id
        return []

    async def add_documents(
        self, documents: List[Dict[str, Any]], embeddings: List[List[float]]
    ) -> None:
        pass

    async def delete_by_channel(self, channel_id: str) -> None:
        pass

    async def get_document_count(self, channel_id: Optional[str] = None) -> int:
        return 0

    async def get_by_time_range(
        self, channel_id: str, since_ts: str, until_ts: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return []

    async def cleanup(self) -> None:
        pass


class MockRetriever:
    """Mock retriever for testing."""

    def __init__(self) -> None:
        self.retrieve_count = 0
        self.last_channel_id: Optional[str] = None

    async def retrieve(
        self,
        query: str,
        channel_id: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        self.retrieve_count += 1
        self.last_channel_id = channel_id
        return []


class MockRCAToolExecutor:
    """Mock RCA tool executor for testing."""

    def __init__(self) -> None:
        self.call_count = 0
        self.last_tool_name: Optional[str] = None
        self.last_arguments: Optional[Dict[str, Any]] = None

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        self.call_count += 1
        self.last_tool_name = tool_name
        self.last_arguments = arguments
        return '{"result": "mock"}'
