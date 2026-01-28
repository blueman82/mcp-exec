"""
JIRA Service Protocols

Protocol definitions for JIRA-related services including cache operations,
data extraction, reporting, and core JIRA integration services.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

__all__ = [
    "JIRACacheProtocol",
    "JIRADataExtractorProtocol",
    "SlackReportsProtocol",
]


@runtime_checkable
class JIRACacheProtocol(Protocol):
    """Protocol for JIRA cache operations."""

    async def get(self, key: Any) -> Optional[Any]:
        """Get value from cache if not expired."""
        ...

    async def set(self, key: Any, value: Any) -> None:
        """Set value in cache with current timestamp."""
        ...

    async def invalidate(self, pattern: Optional[str] = None) -> int:
        """Invalidate cache entries matching pattern."""
        ...

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        ...


@runtime_checkable
class JIRADataExtractorProtocol(Protocol):
    """Protocol for JIRA data extractor operations."""

    async def get_jira_context(
        self, channel_id: str, message_texts: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get JIRA context for a channel with caching."""
        ...

    def extract_ticket_ids(self, message_texts: List[str]) -> List[str]:
        """Extract JIRA ticket IDs from message texts."""
        ...

    async def search_related_tickets(self, jql: str) -> Optional[List[Dict[str, Any]]]:
        """Search for tickets using JQL with caching."""
        ...

    async def get_tickets_batch(
        self, ticket_ids: List[str], include_comments: bool = False
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple tickets in a batch for better performance."""
        ...


@runtime_checkable
class SlackReportsProtocol(Protocol):
    """Protocol for Slack reports operations."""

    pass
