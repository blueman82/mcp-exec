"""
MCP Service Protocols

Protocol definitions for MCP (Model Context Protocol) related services including
client operations, configuration, and rate limiting.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

__all__ = [
    "MCPClientProtocol",
    "MCPAsyncClientProtocol",
    "MCPConfigProtocol",
]


@runtime_checkable
class MCPClientProtocol(Protocol):
    """Protocol for MCP client operations."""

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


@runtime_checkable
class MCPAsyncClientProtocol(Protocol):
    """Protocol for MCP async client operations."""

    async def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Get a single JIRA issue by key."""
        ...

    async def get_issue_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get comments for a JIRA issue."""
        ...

    async def search_issues(self, jql: str) -> Dict[str, Any]:
        """Search JIRA issues using JQL."""
        ...

    async def get_issues_batch(self, issue_keys: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple JIRA issues in a batch."""
        ...


@runtime_checkable
class MCPConfigProtocol(Protocol):
    """Protocol for MCP configuration operations."""

    pass
