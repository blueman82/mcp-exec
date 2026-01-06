"""
MCP Service Protocols

Protocol definitions for MCP (Model Context Protocol) related services.
Only MCPAsyncClientProtocol remains after consolidation - all legacy protocols removed.
AsyncMCPClient is the single MCP client implementation.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

__all__ = [
    "MCPAsyncClientProtocol",
    "MCPConfigProtocol",
]


@runtime_checkable
class MCPAsyncClientProtocol(Protocol):
    """Protocol for the unified async MCP client operations.

    This is THE single MCP client protocol. AsyncMCPClient is the only implementation.
    Legacy MCPClient and MCPAsyncClient (aiohttp) have been deleted.
    """

    async def ensure_connection(self) -> None:
        """Ensure MCP connection is healthy, reconnect if needed."""
        ...

    async def health_check(self) -> bool:
        """Check if MCP server is responsive."""
        ...

    async def test_jira_auth(self) -> Dict[str, Any]:
        """Test JIRA authentication via MCP."""
        ...

    async def search_issues(
        self, jql: str, fields: Optional[List[str]] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        """Search JIRA issues via MCP with rate limiting."""
        ...

    async def get_issue_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get comments for a JIRA issue via MCP."""
        ...

    async def get_issue(
        self, issue_key: str, fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a single JIRA issue by key."""
        ...

    async def get_issues_batch(
        self, issue_keys: List[str], fields: Optional[List[str]] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple JIRA issues in a single batch request."""
        ...

    async def create_issue_comment(self, issue_key: str, comment: str) -> bool:
        """Add a comment to a JIRA issue via MCP."""
        ...

    async def get_fields(self) -> List[Dict[str, Any]]:
        """Get all available JIRA fields including custom fields."""
        ...

    async def list_projects(self, expand: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all JIRA projects accessible to the authenticated user."""
        ...

    async def create_pat(
        self, token_name: str = "ketchup-pat-rotator", expiry_days: int = 90
    ) -> Dict[str, Any]:
        """Create new JIRA PAT via MCP service."""
        ...

    async def validate_pat(self, token: str) -> Dict[str, Any]:
        """Validate PAT token via MCP service."""
        ...

    async def revoke_pat(self, token_id: str) -> Dict[str, Any]:
        """Revoke PAT token via MCP service."""
        ...


@runtime_checkable
class MCPConfigProtocol(Protocol):
    """Protocol for MCP configuration operations."""

    pass
