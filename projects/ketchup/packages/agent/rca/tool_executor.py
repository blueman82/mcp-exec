"""RCA Historian tool executor — routes tool_calls to service clients."""

import json
from typing import Any, Dict

from packages.core.logging import setup_logger

logger = setup_logger(__name__)

RCA_TOOL_RESULT_MAX_CHARS = 2_000


class RCAToolExecutor:
    """Executes RCA tool calls by routing to the appropriate service client."""

    def __init__(self, retriever, mcp_client, newrelic_client):
        """
        Args:
            retriever: AgentRetriever for cross-channel ChromaDB search.
            mcp_client: AsyncMCPClient for JIRA queries.
            newrelic_client: AsyncNewRelicClient for health metrics.
        """
        self._retriever = retriever
        self._mcp_client = mcp_client
        self._newrelic_client = newrelic_client

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
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

    async def _dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Route a tool call to the correct client."""
        if tool_name == "search_similar_incidents":
            query = arguments["query"]
            # Cross-channel search: channel_id=None omits the where filter
            return await self._retriever.retrieve(query=query, channel_id=None)

        elif tool_name == "search_jira_history":
            jql = arguments["jql"]
            return await self._mcp_client.search_issues(jql=jql)

        elif tool_name == "query_instance_health":
            nrql = arguments["nrql"]
            return await self._newrelic_client.execute_nrql(nrql=nrql)

        elif tool_name == "get_active_alerts":
            return await self._newrelic_client.get_active_alerts()

        else:
            raise ValueError(f"Unknown RCA tool: {tool_name}")
