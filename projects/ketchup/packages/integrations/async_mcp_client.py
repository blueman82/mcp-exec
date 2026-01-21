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

    async def create_issue_comment(
        self, issue_key: str, comment: str, user_pat: Optional[str] = None
    ) -> bool:
        """Create a JIRA issue comment.

        Args:
            issue_key: The JIRA issue key (e.g., "CPGNCX-12345")
            comment: Plain text comment to add
            user_pat: Optional user-provided PAT for authentication

        Returns:
            True if comment was added successfully, False otherwise.
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        # MCP JIRA server expects comment object with body as string
        # The MCP server handles ADF conversion internally
        comment_payload = {"body": comment}

        arguments: Dict[str, Any] = {
            "issueIdOrKey": issue_key,
            "comment": comment_payload,
        }
        if user_pat:
            arguments["userPat"] = user_pat

        try:
            result = await self._call_mcp_tool(
                "add_jira_comment",
                arguments,
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

    async def create_issue(
        self, fields: Dict[str, Any], user_pat: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a JIRA issue.

        Args:
            fields: The JIRA issue fields (project, issuetype, summary, etc.)
            user_pat: Optional user-provided PAT for authentication

        Returns:
            Dictionary with success status and created issue key.
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        arguments: Dict[str, Any] = {"fields": fields}
        if user_pat:
            arguments["userPat"] = user_pat

        try:
            result = await self._call_mcp_tool("create_jira_issue", arguments)
            return result
        except Exception as exc:
            logger.error("Error creating issue: %s", exc)
            return {"success": False, "message": str(exc)}

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

    async def list_projects(self, expand: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all JIRA projects accessible to the authenticated user via MCP.

        Args:
            expand: Comma-separated fields to expand (description, lead, url, projectKeys, issueTypes)

        Returns:
            List of projects
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        arguments: Dict[str, Any] = {}
        if expand:
            arguments["expand"] = expand

        try:
            result = await self._call_mcp_tool("list_jira_projects", arguments)
            # Handle the response format from MCP tool
            # MCP returns: {success: bool, message: str, data: projects[]}
            if isinstance(result, dict) and result.get("success"):
                return result.get("data", [])
            elif isinstance(result, list):
                return result
            else:
                logger.warning("Unexpected response format for projects: %s", result)
                return []
        except Exception as exc:
            logger.error("Error listing projects: %s", exc)
            return []

    async def get_project_issue_types(self, project_key: str) -> List[Dict[str, Any]]:
        """Get all issue types available for a specific JIRA project.

        Args:
            project_key: The project key (e.g., "CPGNCX", "CSOPM")

        Returns:
            List of issue types, each containing:
                - id: str - the issue type ID
                - name: str - the issue type name (e.g., "Task", "Bug")
                - subtask: bool - whether this is a subtask type
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            result = await self._call_mcp_tool(
                "get_project_issue_types", {"projectKey": project_key}
            )
            # MCP returns: {success: bool, message: str, data: {issueTypes: [...]}}
            if isinstance(result, dict) and result.get("success"):
                return result.get("data", {}).get("issueTypes", [])
            else:
                logger.warning(
                    "Failed to get issue types for %s: %s",
                    project_key,
                    result.get("message", "Unknown error"),
                )
                return []
        except Exception as exc:
            logger.error("Error getting issue types for %s: %s", project_key, exc)
            return []

    async def get_issuetype_metadata(
        self, project_key: str, issue_type_id: str, user_pat: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get field metadata for a specific issue type in a JIRA project.

        This returns detailed field information including which fields are required
        and their allowed values.

        Args:
            project_key: The project key (e.g., "CPGNCX", "CSOPM")
            issue_type_id: The issue type ID (e.g., "10200")
            user_pat: Optional user-provided PAT for authentication

        Returns:
            Dictionary containing field metadata with structure:
                {
                    "values": [
                        {"fieldId": "summary", "name": "Summary", "required": true, ...},
                        {"fieldId": "description", "name": "Description", "required": false, ...},
                        ...
                    ]
                }
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            arguments: Dict[str, Any] = {
                "projectKey": project_key,
                "issueTypeId": issue_type_id,
            }
            if user_pat:
                arguments["userPat"] = user_pat

            result = await self._call_mcp_tool(
                "get_issuetype_metadata",
                arguments,
            )
            # MCP returns: {success: bool, message: str, data: {...}}
            if isinstance(result, dict) and result.get("success"):
                return result.get("data", {})
            else:
                logger.warning(
                    "Failed to get metadata for %s/%s: %s",
                    project_key,
                    issue_type_id,
                    result.get("message", "Unknown error"),
                )
                return {}
        except Exception as exc:
            logger.error(
                "Error getting metadata for %s/%s: %s", project_key, issue_type_id, exc
            )
            return {}

    async def get_transition_fields(
        self, ticket_key: str, target_status: str, user_pat: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get required fields for a specific status transition.

        Fetches available transitions for a ticket and returns the fields
        required for the specified target status transition.

        Args:
            ticket_key: The JIRA ticket key (e.g., "CSOPM-12345")
            target_status: The target status name (e.g., "Complete", "Closed")
            user_pat: Optional user-provided PAT for authentication

        Returns:
            List of field metadata dictionaries for the transition, e.g.:
                [
                    {"fieldId": "resolution", "name": "Resolution", "required": true, ...},
                    ...
                ]
            Returns empty list if transition not found or on error.
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        try:
            arguments: Dict[str, Any] = {"issueIdOrKey": ticket_key}
            if user_pat:
                arguments["userPat"] = user_pat

            result = await self._call_mcp_tool("get_jira_transitions", arguments)

            if not isinstance(result, dict) or not result.get("success"):
                logger.warning(
                    "Failed to get transitions for %s: %s",
                    ticket_key,
                    result.get("message", "Unknown error") if result else "No response",
                )
                return []

            data = result.get("data", {})
            transitions = data.get("transitions", [])

            # Find the transition matching target status
            for transition in transitions:
                to_status = transition.get("to", {}).get("name", "")
                if to_status.lower() == target_status.lower():
                    # Return the fields for this transition
                    fields = transition.get("fields", {})
                    # Convert fields dict to list format matching get_issuetype_metadata
                    field_list = []
                    for field_id, field_data in fields.items():
                        field_list.append({
                            "fieldId": field_id,
                            "name": field_data.get("name", field_id),
                            "required": field_data.get("required", False),
                            "allowedValues": field_data.get("allowedValues", []),
                            "schema": field_data.get("schema", {}),
                        })
                    logger.info(
                        "Found %d fields for transition to '%s' on %s",
                        len(field_list),
                        target_status,
                        ticket_key,
                    )
                    return field_list

            logger.warning(
                "Transition to '%s' not found for %s. Available: %s",
                target_status,
                ticket_key,
                [t.get("to", {}).get("name") for t in transitions],
            )
            return []

        except Exception as exc:
            logger.error(
                "Error getting transition fields for %s to %s: %s",
                ticket_key,
                target_status,
                exc,
            )
            return []

    async def create_pat(
        self, token_name: str = "ketchup-pat-rotator", expiry_days: int = 90
    ) -> Dict[str, Any]:
        """Create new JIRA PAT via MCP service.

        Args:
            token_name: Name for the new PAT token.
            expiry_days: Number of days until expiration (max 90).

        Returns:
            Dictionary containing PAT token details with keys:
                - pat: str - the PAT token value
                - id: str - the PAT token ID
                - expiryDate: str - ISO 8601 expiry date

        Raises:
            Exception: If PAT creation fails.
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        arguments = {"tokenName": token_name, "expiryDays": expiry_days}

        try:
            result = await self._call_mcp_tool("create_jira_pat", arguments)

            # Extract data from MCP response
            # MCP returns: {success: bool, message: str, data: {pat, id, expiryDate}}
            # We return just the data portion for compatibility with rotator.py
            if result.get("success") and "data" in result:
                data = result["data"]
                logger.info("PAT created successfully: %s", data.get("id", "unknown"))
                return data
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error("Failed to create PAT: %s", error_msg)
                raise Exception(f"PAT creation failed: {error_msg}")

        except Exception as exc:
            logger.error("Error creating PAT: %s", exc)
            raise

    async def validate_pat(self, token: str) -> Dict[str, Any]:
        """Validate PAT token via MCP service.

        Args:
            token: PAT token to validate.

        Returns:
            Dictionary containing validation result with keys:
                - success: bool - whether validation request succeeded
                - valid: bool - whether the token is valid
                - message: str - status message
                - error: str (optional) - error details if validation failed

        Raises:
            Exception: If validation request fails.
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        arguments = {"token": token}

        try:
            result = await self._call_mcp_tool("validate_jira_pat", arguments)

            if result.get("valid"):
                logger.info("PAT validation successful")
            else:
                logger.warning("PAT validation failed: %s", result.get("message", "Unknown error"))

            return result
        except Exception as exc:
            logger.error("Error validating PAT: %s", exc)
            raise

    async def revoke_pat(self, token_id: str) -> Dict[str, Any]:
        """Revoke PAT token via MCP service.

        Args:
            token_id: ID of the PAT token to revoke.

        Returns:
            Dictionary containing revocation result with keys:
                - success: bool - whether revocation succeeded
                - message: str - status message
                - error: str (optional) - error details if revocation failed

        Raises:
            Exception: If revocation request fails.
        """
        await self.ensure_connection()
        await self.rate_limiter.acquire()

        arguments = {"tokenId": token_id}

        try:
            result = await self._call_mcp_tool("revoke_jira_pat", arguments)

            if result.get("success"):
                logger.info("PAT revoked successfully: %s", token_id)
            else:
                logger.warning(
                    "Failed to revoke PAT %s: %s", token_id, result.get("message", "Unknown error")
                )

            return result
        except Exception as exc:
            logger.error("Error revoking PAT %s: %s", token_id, exc)
            raise
