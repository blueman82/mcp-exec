"""
mcp_client.py

MCP (Model Context Protocol) client with health monitoring, rate limiting,
and connection resilience for JIRA integration.
"""

import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import aiohttp

from packages.core.logging import setup_logger
from packages.integrations.ims_token_manager import IMSTokenManager

logger = setup_logger(__name__)


class iPaaSRateLimiter:
    """Rate limiter for iPaaS API calls."""

    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.request_times: List[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        Blocks if rate limit would be exceeded.
        """
        async with self._lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.request_times = [t for t in self.request_times if now - t < 60]

            if len(self.request_times) >= self.requests_per_minute:
                # Calculate sleep time until oldest request expires
                sleep_time = 60 - (now - self.request_times[0])
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                # Clean up again after sleep
                now = time.time()
                self.request_times = [t for t in self.request_times if now - t < 60]

            self.request_times.append(now)


class MCPClient:
    """MCP client with health monitoring and rate limiting."""

    def __init__(self, token_manager: IMSTokenManager):
        """
        Initialize MCP client.

        Args:
            token_manager: IMS token manager for authentication
        """
        self.token_manager = token_manager
        # Use localhost for local testing, mcp-jira for container networking
        self.base_url = os.getenv("MCP_BASE_URL", "http://localhost:8081")
        self.rate_limiter = iPaaSRateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_id: Optional[str] = None
        self._last_health_check = 0
        self._health_check_interval = 60  # seconds
        self._is_healthy = True
        self._request_id_counter = 0

    async def ensure_connection(self) -> None:
        """Ensure MCP connection is healthy, reconnect if needed."""
        now = time.time()
        if now - self._last_health_check > self._health_check_interval:
            if not await self.health_check():
                logger.warning("MCP server unhealthy, attempting reconnection")
                await self._reconnect()
            self._last_health_check = now

    async def health_check(self) -> bool:
        """
        Check if MCP server is responsive.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    self._is_healthy = response.status == 200
                    if self._is_healthy:
                        logger.info("MCP server health check passed")
                    else:
                        logger.warning(
                            f"MCP server health check failed: {response.status}"
                        )
                    return self._is_healthy
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._is_healthy = False
            return False

    async def _reconnect(self) -> None:
        """Reconnect to MCP server with exponential backoff."""
        backoff = 1
        max_backoff = 60
        attempt = 0

        while True:
            attempt += 1
            logger.info(f"Reconnection attempt {attempt}")

            if await self.health_check():
                logger.info("Successfully reconnected to MCP server")
                break

            logger.warning(f"Reconnection failed, retrying in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    async def _get_headers(self) -> Dict[str, str]:
        """
        Get headers for MCP requests including IMS token.

        Returns:
            Headers dictionary
        """
        token = await self.token_manager.get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._session_id:
            headers["X-Session-ID"] = self._session_id
        return headers

    def _get_next_request_id(self) -> int:
        """Get the next request ID for JSON-RPC."""
        self._request_id_counter += 1
        return self._request_id_counter

    async def _establish_mcp_session(self) -> str:
        """
        Establish an MCP session by connecting to the SSE endpoint.

        Returns:
            Session ID for subsequent requests
        """
        try:
            headers = await self._get_headers()

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/sse",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Failed to establish SSE connection: {response.status}"
                        )

                    # Extract session ID from response headers or generate one
                    session_id = response.headers.get("X-Session-ID", str(uuid.uuid4()))
                    self._session_id = session_id
                    logger.info(f"MCP session established: {session_id}")
                    return session_id

        except Exception as e:
            logger.error(f"Failed to establish MCP session: {e}")
            raise

    async def _call_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool using JSON-RPC protocol.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool response
        """
        request_id = self._get_next_request_id()

        # Create JSON-RPC request
        rpc_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        headers = await self._get_headers()

        try:
            async with aiohttp.ClientSession() as session:
                # Use direct tool call endpoint without session management
                async with session.post(
                    f"{self.base_url}/message",
                    json=rpc_request,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"MCP tool call failed: {response.status} - {error_text}"
                        )
                        raise Exception(f"MCP tool call failed: {response.status}")

                    result = await response.json()

                    # Handle JSON-RPC error response
                    if "error" in result:
                        error = result["error"]
                        logger.error(f"MCP tool error: {error}")
                        # Preserve the full error message for better error handling
                        error_message = error.get("message", "Unknown error")
                        # Check if this is a JIRA-specific error with details
                        if isinstance(error, dict) and "data" in error:
                            error_data = error.get("data", {})
                            if "jiraError" in error_data:
                                # Use the JIRA error message if available
                                error_message = error_data.get(
                                    "jiraError", error_message
                                )
                        raise Exception(f"{error_message}")

                    # Return the result content
                    if "result" in result and "content" in result["result"]:
                        content = result["result"]["content"]
                        if content and len(content) > 0:
                            # Parse the text content which should be JSON
                            text_content = content[0].get("text", "{}")
                            return json.loads(text_content)

                    return result

        except aiohttp.ClientError as e:
            logger.error(f"Network error during MCP tool call: {e}")
            raise Exception(f"Failed to call MCP tool: {e}")

    async def test_jira_auth(self) -> Dict[str, Any]:
        """
        Test JIRA authentication via MCP.

        Returns:
            Authentication test result
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        return await self._call_mcp_tool("test_jira_auth", {})

    async def search_issues(
        self, jql: str, fields: Optional[List[str]] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        """
        Search JIRA issues via MCP with rate limiting.

        Args:
            jql: JIRA Query Language string
            fields: Optional list of fields to return
            max_results: Maximum number of results to return

        Returns:
            JIRA search results

        Raises:
            Exception: If search fails
        """
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
                "Priority from Customer Care",
                "Severity from Customer Care",
            ]

        arguments = {"jql": jql, "fields": fields, "maxResults": max_results}

        try:
            result = await self._call_mcp_tool("search_jira_issues", arguments)
            logger.info(
                f"JIRA search successful, found {len(result.get('issues', []))} issues"
            )
            return result
        except Exception as e:
            # Handle authentication errors
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                logger.error("Authentication failed, refreshing token")
                # Force token refresh on next call
                self.token_manager._token_cache.clear()
            raise

    async def get_issue_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get comments for a JIRA issue via MCP.

        Args:
            issue_key: JIRA issue key

        Returns:
            List of comments
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            result = await self._call_mcp_tool(
                "get_jira_comments", {"issueIdOrKey": issue_key}
            )
            # Handle the response format from MCP tool
            if isinstance(result, dict) and result.get("success"):
                data = result.get("data", {})
                return data.get("comments", [])
            elif isinstance(result, dict) and "comments" in result:
                return result.get("comments", [])
            else:
                logger.warning(f"Unexpected response format for comments: {result}")
                return []
        except Exception as e:
            logger.error(f"Error getting comments for {issue_key}: {e}")
            return []

    async def get_issue(
        self, issue_key: str, fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single JIRA issue by key.

        Args:
            issue_key: JIRA issue key (e.g., "NEO-88802")
            fields: List of fields to return (default: all)

        Returns:
            Issue data dict or None if not found
        """
        try:
            # Use JQL to search for the specific issue
            jql = f'key = "{issue_key}"'
            result = await self.search_issues(jql, fields=fields, max_results=1)

            if result and result.get("issues"):
                return result["issues"][0]

            logger.warning(f"Issue not found: {issue_key}")
            return None

        except Exception as e:
            logger.error(f"Error getting issue {issue_key}: {e}")
            return None

    async def get_issues_batch(
        self, issue_keys: List[str], fields: Optional[List[str]] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get multiple JIRA issues in a single batch request.

        Args:
            issue_keys: List of JIRA issue keys (e.g., ["NEO-88802", "CPGNREQ-179715"])
            fields: List of fields to return (default: all)

        Returns:
            Dict mapping issue key to issue data (or None if not found)
        """
        if not issue_keys:
            return {}

        try:
            # Build JQL for batch search - escape special characters in keys
            escaped_keys = [f'"{key}"' for key in issue_keys]
            jql = f'key IN ({", ".join(escaped_keys)})'

            logger.info(f"Batch fetching {len(issue_keys)} issues")
            result = await self.search_issues(
                jql, fields=fields, max_results=len(issue_keys)
            )

            # Build result map
            issues_map = {}
            for key in issue_keys:
                issues_map[key] = None  # Initialize all as not found

            if result and result.get("issues"):
                for issue in result["issues"]:
                    issue_key = issue.get("key")
                    if issue_key:
                        issues_map[issue_key] = issue

            # Log any missing issues
            missing = [k for k, v in issues_map.items() if v is None]
            if missing:
                logger.warning(f"Issues not found: {missing}")

            return issues_map

        except Exception as e:
            logger.error(f"Error batch fetching issues: {e}")
            # Return empty results for all requested keys
            return {key: None for key in issue_keys}

    async def create_issue_comment(self, issue_key: str, comment: str) -> bool:
        """
        Add a comment to a JIRA issue via MCP.

        Args:
            issue_key: JIRA issue key
            comment: Comment text

        Returns:
            True if successful, False otherwise
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            result = await self._call_mcp_tool(
                "add_jira_comment", {"issueIdOrKey": issue_key, "comment": comment}
            )
            success = result.get("success", False)
            if success:
                logger.info(f"Comment added to {issue_key}")
            else:
                logger.error(f"Failed to add comment: {result}")
            return success
        except Exception as e:
            logger.error(f"Error adding comment to {issue_key}: {e}")
            return False

    async def close(self) -> None:
        """Close any open connections."""
        if self._session:
            await self._session.close()
            self._session = None
