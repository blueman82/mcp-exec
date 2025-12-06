"""Unified Async MCP client built on the shared AsyncClient/httpx stack."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import orjson

from packages.core.async_client import AsyncClient
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import BackoffStrategy
from packages.integrations.async_ims_token_manager import AsyncIMSTokenManager

logger = setup_logger(__name__)


@dataclass
class MCPClientConfig:
    """Configuration container for MCP client setup."""

    base_url: str
    token_manager: AsyncIMSTokenManager

    def normalized_base_url(self) -> str:
        """Return the base URL without trailing slash.

        Returns:
            str: Normalized base URL.
        """

        return self.base_url.rstrip("/")


class iPaaSRateLimiter:
    """Rate limiter for MCP/iPaaS API calls."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        """Initialise the limiter.

        Args:
            requests_per_minute: Maximum number of requests per minute.
        """

        self.requests_per_minute = requests_per_minute
        self.request_times: List[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to perform a request respecting the limit."""

        async with self._lock:
            now = time.time()
            self.request_times = [t for t in self.request_times if now - t < 60]

            if len(self.request_times) >= self.requests_per_minute:
                sleep_time = 60 - (now - self.request_times[0])
                logger.info("Rate limit reached, sleeping for %.2fs", sleep_time)
                await asyncio.sleep(sleep_time)
                now = time.time()
                self.request_times = [t for t in self.request_times if now - t < 60]

            self.request_times.append(now)


class AsyncMCPClient(AsyncClient[MCPClientConfig, Dict[str, Any]]):
    """Async MCP client using httpx sessions via AsyncClient."""

    def __init__(
        self,
        base_url: str,
        token_manager: AsyncIMSTokenManager,
        max_concurrent_requests: int = 60,
        request_timeout: int = 30,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ) -> None:
        """Initialise the MCP async client.

        Args:
            base_url: Base URL for the MCP server.
            token_manager: IMS token manager providing access tokens.
            max_concurrent_requests: Maximum concurrent outbound requests.
            request_timeout: Timeout for individual requests in seconds.
            backoff_strategy: Optional custom backoff strategy.
        """
        logger.info(
            "Initializing AsyncMCPClient (NEW ASYNC IMPLEMENTATION) with base_url=%s, "
            "max_concurrent_requests=%d, request_timeout=%d",
            base_url,
            max_concurrent_requests,
            request_timeout,
        )
        super().__init__(
            config=MCPClientConfig(base_url=base_url, token_manager=token_manager),
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout,
            backoff_strategy=backoff_strategy,
        )
        self._request_id_counter = 0
        self._session_id: Optional[str] = None
        self._last_health_check = 0.0
        self._health_check_interval = 60.0
        self._is_healthy = True
        self.rate_limiter = iPaaSRateLimiter()
        logger.info("AsyncMCPClient initialization complete - ready for httpx-based requests")

    @property
    def base_url(self) -> str:
        """Return normalized MCP base URL."""

        return self.config.normalized_base_url()

    @property
    def token_manager(self) -> AsyncIMSTokenManager:
        """Expose the IMS token manager."""

        return self.config.token_manager

    def _get_next_request_id(self) -> int:
        """Generate the next JSON-RPC request identifier."""

        self._request_id_counter += 1
        return self._request_id_counter

    async def ensure_connection(self) -> None:
        """Ensure connection health and reconnect as needed."""

        await self.setup()
        now = time.time()
        if now - self._last_health_check > self._health_check_interval:
            if not await self.health_check():
                logger.warning("MCP server unhealthy, attempting reconnection")
                await self._reconnect()
            self._last_health_check = now

    async def health_check(self) -> bool:
        """Check MCP server health status."""

        try:
            response = await self._make_api_request(
                url=f"{self.base_url}/health",
                method="GET",
            )
            self._is_healthy = response["status"] == 200
        except Exception as exc:
            logger.error("MCP health check failed: %s", exc)
            self._is_healthy = False

        logger.info(
            "MCP health check: %s",
            "healthy" if self._is_healthy else "unhealthy",
        )
        return self._is_healthy

    async def _reconnect(self) -> None:
        """Reconnect by cleaning up and re-establishing session with backoff."""

        try:
            await self.cleanup()

            # Implement backoff: retry health checks until successful
            while not await self.health_check():
                logger.warning("Health check failed, retrying in 1 second...")
                await asyncio.sleep(1)

            await self.setup()
            self._session_id = await self._establish_mcp_session()
            logger.info("Successfully reconnected to MCP server")
        except Exception as exc:  # pragma: no cover - defensive path
            logger.error("Failed to reconnect to MCP server: %s", exc)
            raise

    async def _establish_mcp_session(self) -> str:
        """Establish SSE session and return the session ID."""

        await self.rate_limiter.acquire()
        response = await self._make_api_request(
            url=f"{self.base_url}/sse",
            method="GET",
            headers=await self._build_headers(),
        )

        if response["status"] != 200:
            raise Exception(f"Failed to establish SSE connection: {response['status']}")

        session_id = response["headers"].get("X-Session-ID", str(uuid.uuid4()))
        self._session_id = session_id
        logger.info("MCP session established: %s", session_id)
        return session_id

    async def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers including bearer token."""

        token = await self.token_manager.get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._session_id:
            headers["X-Session-ID"] = self._session_id
        return headers

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool via JSON-RPC."""

        request_id = self._get_next_request_id()
        rpc_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        headers = await self._build_headers()
        await self.rate_limiter.acquire()
        response = await self._make_api_request(
            url=f"{self.base_url}/message",
            method="POST",
            headers=headers,
            json_data=rpc_request,
        )

        if response["status"] != 200:
            error_text = response["body"].decode("utf-8", errors="ignore")
            logger.error(
                "MCP tool call failed: %s - %s",
                response["status"],
                error_text,
            )
            raise Exception(f"MCP tool call failed: {response['status']}")

        result = orjson.loads(response["body"])

        if "error" in result:
            error = result["error"]
            logger.error("MCP tool error: %s", error)
            error_message = error.get("message", "Unknown error")
            if isinstance(error, dict):
                data = error.get("data")
                if isinstance(data, dict):
                    jira_error = data.get("jiraError")
                    if jira_error:
                        error_message = jira_error
            raise Exception(error_message)

        if "result" in result and "content" in result["result"]:
            content = result["result"]["content"]
            if content:
                text_content = content[0].get("text", "{}")
                try:
                    return orjson.loads(text_content)
                except orjson.JSONDecodeError as exc:
                    logger.error("Failed to decode MCP tool content: %s", exc)
                    raise Exception("Invalid MCP tool response format") from exc

        return result

    async def test_jira_auth(self) -> Dict[str, Any]:
        """Test JIRA authentication via MCP."""

        await self.ensure_connection()
        await self.rate_limiter.acquire()
        return await self._call_mcp_tool("test_jira_auth", {})

    async def search_issues(
        self, jql: str, fields: Optional[List[str]] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        """Search JIRA issues via MCP."""

        await self.ensure_connection()
        await self.rate_limiter.acquire()

        if not fields:
            fields = [
                "summary",
                "status",
                "assignee",
                "reporter",
                "created",
                "updated",
                "priority",
                "issuetype",
                "description",
                "customfield_15900",
                "customfield_15901",
                "Priority from Customer Care",
                "Severity from Customer Care",
            ]

        arguments = {"jql": jql, "fields": fields, "maxResults": max_results}

        try:
            result = await self._call_mcp_tool("search_jira_issues", arguments)
            logger.info(
                "JIRA search successful, found %d issues",
                len(result.get("issues", [])),
            )
            return result
        except Exception as exc:
            if "authentication" in str(exc).lower() or "unauthorized" in str(exc).lower():
                logger.error("Authentication failed, refreshing token")
                self.token_manager._token_cache.clear()
            raise

    async def get_issue(
        self, issue_key: str, fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a single JIRA issue."""

        try:
            jql = f'key = "{issue_key}"'
            result = await self.search_issues(jql, fields=fields, max_results=1)
            if result and result.get("issues"):
                return result["issues"][0]
            logger.warning("Issue not found: %s", issue_key)
            return None
        except Exception as exc:
            logger.error("Error getting issue %s: %s", issue_key, exc)
            return None

    async def get_issues_batch(
        self, issue_keys: List[str], fields: Optional[List[str]] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple issues in a single request."""

        if not issue_keys:
            return {}

        escaped_keys = [f'"{key}"' for key in issue_keys]
        jql = f'key IN ({", ".join(escaped_keys)})'

        try:
            result = await self.search_issues(jql, fields=fields, max_results=len(issue_keys))
            issues_map = {key: None for key in issue_keys}
            for issue in result.get("issues", []):
                issue_key = issue.get("key")
                if issue_key in issues_map:
                    issues_map[issue_key] = issue

            missing = [key for key, value in issues_map.items() if value is None]
            if missing:
                logger.warning("Issues not found: %s", missing)
            return issues_map
        except Exception as exc:
            logger.error("Error batch fetching issues: %s", exc)
            return {key: None for key in issue_keys}

    async def get_issue_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """Retrieve comments for a JIRA issue."""

        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            result = await self._call_mcp_tool("get_jira_comments", {"issueIdOrKey": issue_key})
            if isinstance(result, dict) and result.get("success"):
                return result.get("data", {}).get("comments", [])
            if isinstance(result, dict) and "comments" in result:
                return result.get("comments", [])
            logger.warning("Unexpected response format for comments: %s", result)
            return []
        except Exception as exc:
            logger.error("Error getting comments for %s: %s", issue_key, exc)
            return []

    async def create_issue_comment(self, issue_key: str, comment: str) -> bool:
        """Create a JIRA issue comment."""

        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            result = await self._call_mcp_tool(
                "add_jira_comment",
                {"issueIdOrKey": issue_key, "comment": comment},
            )
            success = result.get("success", False)
            if success:
                logger.info("Comment added to %s", issue_key)
            else:
                logger.error("Failed to add comment: %s", result)
            return success
        except Exception as exc:
            logger.error("Error adding comment to %s: %s", issue_key, exc)
            return False

    async def get_fields(self) -> List[Dict[str, Any]]:
        """Retrieve list of JIRA fields."""

        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            result = await self._call_mcp_tool("get_jira_fields", {})
            if isinstance(result, list):
                fields = result
            else:
                fields = result.get("fields", [])
            logger.info("Retrieved %d JIRA field definitions", len(fields))
            return fields
        except Exception as exc:
            logger.error("Error getting JIRA fields: %s", exc)
            return []
