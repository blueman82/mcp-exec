"""RCA Historian tool executor — routes tool_calls to service clients."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from packages.core.logging import setup_logger

logger = setup_logger(__name__)

RCA_TOOL_RESULT_MAX_CHARS = 2_000


class RCAToolExecutor:
    """Executes RCA tool calls by routing to the appropriate service client."""

    def __init__(self, retriever: Any, mcp_client: Any, newrelic_client: Any) -> None:
        """
        Args:
            retriever: AgentRetriever for cross-channel ChromaDB search.
            mcp_client: AsyncMCPClient for JIRA queries.
            newrelic_client: AsyncNewRelicClient for health metrics.
        """
        self._retriever = retriever
        self._mcp_client = mcp_client
        self._newrelic_client = newrelic_client
        self._dispatch_table: dict[str, Callable[..., Any]] = {
            "search_similar_incidents": self._search_similar_incidents,
            "search_jira_history": self._search_jira_history,
            "query_instance_health": self._query_instance_health,
            "get_active_alerts": self._get_active_alerts,
        }

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool call and return the result as a string.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments dict from the model's tool_call.

        Returns:
            JSON string of the result, truncated to RCA_TOOL_RESULT_MAX_CHARS.
        """
        try:
            result = await self._dispatch(tool_name, arguments)
            result_str = json.dumps(result, default=str)
        except Exception as e:
            logger.error("RCA tool %s failed: %s", tool_name, e)
            result_str = json.dumps({"error": str(e)})

        # Truncate to stay within token budget
        if len(result_str) > RCA_TOOL_RESULT_MAX_CHARS:
            result_str = result_str[:RCA_TOOL_RESULT_MAX_CHARS] + "...[truncated]"

        return result_str

    async def _dispatch(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Route a tool call to the correct client."""
        handler = self._dispatch_table.get(tool_name)
        if not handler:
            raise ValueError(f"Unknown RCA tool: {tool_name}")
        return await handler(arguments)

    async def _search_similar_incidents(self, arguments: dict[str, Any]) -> Any:
        # Cross-channel search: channel_id=None omits the where filter
        return await self._retriever.retrieve(query=arguments["query"], channel_id=None)

    async def _search_jira_history(self, arguments: dict[str, Any]) -> Any:
        return await self._mcp_client.search_issues(jql=arguments["jql"])

    async def _query_instance_health(self, arguments: dict[str, Any]) -> Any:
        return await self._newrelic_client.execute_nrql(nrql=arguments["nrql"])

    async def _get_active_alerts(self, arguments: dict[str, Any]) -> Any:
        return await self._newrelic_client.get_active_alerts()
