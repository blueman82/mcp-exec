"""
MCP Async Client

This module provides a specialized client for asynchronous interaction with MCP server,
with improved connection management, concurrency control, and retry logic.
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

import aiohttp
import orjson

from packages.core.async_client import AsyncClient
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import BackoffStrategy
from packages.integrations.ims_token_manager import IMSTokenManager

logger = setup_logger(__name__)


class MCPConfig:
    """Configuration for MCP server access."""

    def __init__(self, base_url: str, token_manager: IMSTokenManager):
        """
        Initialize MCP configuration.

        Args:
            base_url: Base URL for MCP server
            token_manager: IMS token manager for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.token_manager = token_manager

    async def get_headers(self) -> Dict[str, str]:
        """Get headers for MCP requests with authentication."""
        token = await self.token_manager.get_valid_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_api_base_url(self) -> str:
        """Get base URL for MCP requests."""
        return self.base_url


class MCPAsyncClient(AsyncClient[MCPConfig, aiohttp.ClientResponse]):
    """Specialized client for asynchronous interactions with MCP server."""

    def __init__(
        self,
        mcp_config: MCPConfig,
        max_concurrent_requests: int = 60,
        request_timeout: int = 30,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ) -> None:
        """
        Initialize the MCP async client.

        Args:
            mcp_config: MCP configuration object
            max_concurrent_requests: Max concurrent requests allowed
            request_timeout: Request timeout in seconds
            backoff_strategy: Custom backoff strategy (optional)
        """
        super().__init__(
            config=mcp_config,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout,
            backoff_strategy=backoff_strategy,
        )
        self.mcp_config = mcp_config
        self._request_id_counter = 0
        self._session_id: Optional[str] = None
        self._last_health_check = 0
        self._health_check_interval = 60  # seconds
        self._is_healthy = True

    def _get_next_request_id(self) -> int:
        """Get the next request ID for JSON-RPC."""
        self._request_id_counter += 1
        return self._request_id_counter

    async def ensure_connection(self) -> None:
        """Ensure MCP connection is healthy, reconnect if needed."""
        await self.setup()  # Ensure session exists

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
            url = f"{self.mcp_config.get_api_base_url()}/health"
            response = await self._make_api_request(url, method="GET")
            # Response is now a SafeResponse dict
            self._is_healthy = response["status"] == 200
            logger.info(
                f"MCP health check: {'healthy' if self._is_healthy else 'unhealthy'}"
            )
            return self._is_healthy
        except Exception as e:
            logger.error(f"MCP health check failed: {e}")
            self._is_healthy = False
            return False

    async def _reconnect(self) -> None:
        """Attempt to reconnect to MCP server."""
        try:
            # Close existing session
            await self.cleanup()

            # Wait a bit before reconnecting
            await asyncio.sleep(1)

            # Re-setup connection
            await self.setup()

            # Establish new MCP session
            self._session_id = await self._establish_mcp_session()
            logger.info("Successfully reconnected to MCP server")
        except Exception as e:
            logger.error(f"Failed to reconnect to MCP server: {e}")
            raise

    async def _establish_mcp_session(self) -> str:
        """
        Establish an MCP session by connecting to the SSE endpoint.

        Returns:
            Session ID for subsequent requests
        """
        try:
            headers = await self.mcp_config.get_headers()
            url = f"{self.mcp_config.get_api_base_url()}/sse"

            response = await self._make_api_request(url, method="GET", headers=headers)

            # Response is now a SafeResponse dict
            if response["status"] != 200:
                raise Exception(
                    f"Failed to establish SSE connection: {response['status']}"
                )

            # Extract session ID from response headers or generate one
            session_id = response["headers"].get("X-Session-ID", str(uuid.uuid4()))
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

        headers = await self.mcp_config.get_headers()
        url = f"{self.mcp_config.get_api_base_url()}/message"

        try:
            response = await self._make_api_request(
                url, method="POST", headers=headers, json_data=rpc_request
            )

            # Response is now a SafeResponse dict
            if response["status"] != 200:
                error_text = response["body"].decode("utf-8")
                logger.error(
                    f"MCP tool call failed: {response['status']} - {error_text}"
                )
                raise Exception(f"MCP tool call failed: {response['status']}")

            result = orjson.loads(response["body"])

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
                        error_message = error_data.get("jiraError", error_message)
                raise Exception(f"{error_message}")

            # Return the result content
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"]
                if content and len(content) > 0:
                    # Parse the text content which should be JSON
                    text_content = content[0].get("text", "{}")
                    return json.loads(text_content)

            return result

        except Exception:
            # Re-raise as-is, the backoff strategy will handle retries
            raise

    # JIRA-specific methods

    async def test_jira_auth(self) -> Dict[str, Any]:
        """
        Test JIRA authentication via MCP.

        Returns:
            Authentication test result
        """
        await self.ensure_connection()
        return await self._call_mcp_tool("test_jira_auth", {})

    async def search_issues(
        self, jql: str, fields: Optional[List[str]] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        """
        Search JIRA issues via MCP.

        Args:
            jql: JIRA Query Language string
            fields: Optional list of fields to return
            max_results: Maximum number of results to return

        Returns:
            JIRA search results
        """
        await self.ensure_connection()

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
                "customfield_15901",  # Priority/Severity from Customer Care by ID
                "Priority from Customer Care",
                "Severity from Customer Care",
            ]  # Also by name for compatibility

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
                self.mcp_config.token_manager._token_cache.clear()
            raise

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
            issue_keys: List of JIRA issue keys
            fields: List of fields to return (default: all)

        Returns:
            Dict mapping issue key to issue data (or None if not found)
        """
        if not issue_keys:
            return {}

        # Build JQL for batch search
        escaped_keys = [f'"{key}"' for key in issue_keys]
        jql = f'key IN ({", ".join(escaped_keys)})'

        logger.info(f"Batch fetching {len(issue_keys)} issues via MCP")

        try:
            result = await self.search_issues(
                jql, fields=fields, max_results=len(issue_keys)
            )

            # Build result map
            issues_map = {key: None for key in issue_keys}

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
            return {key: None for key in issue_keys}

    async def get_issue_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get comments for a JIRA issue via MCP.

        Args:
            issue_key: JIRA issue key

        Returns:
            List of comments
        """
        await self.ensure_connection()

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

    async def get_fields(self) -> List[Dict[str, Any]]:
        """
        Get all available JIRA fields including custom fields via MCP.

        Returns:
            List of field definitions with id, name, custom flag, etc.
        """
        await self.ensure_connection()

        try:
            result = await self._call_mcp_tool("get_jira_fields", {})
            # The MCP server returns the fields array directly
            if isinstance(result, list):
                fields = result
            else:
                # Fallback for dict response format
                fields = result.get("fields", [])
            logger.info(f"Retrieved {len(fields)} JIRA field definitions")
            return fields
        except Exception as e:
            logger.error(f"Error getting JIRA fields: {e}")
            # Return empty list on error to allow graceful degradation
            return []
