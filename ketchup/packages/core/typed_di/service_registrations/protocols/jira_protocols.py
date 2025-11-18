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
    "JIRAServiceProtocol",
    "JIRATicketServiceProtocol",
    "JIRAWorkflowServiceProtocol",
    "JIRAReportingServiceProtocol",
    "JIRAAnalyticsServiceProtocol",
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


@runtime_checkable
class JIRAServiceProtocol(Protocol):
    """Protocol for core JIRA service operations via MCP."""

    async def post_comment_to_ticket(
        self, jira_ticket_id: str, comment_text: str
    ) -> bool:
        """Post a comment to a JIRA ticket."""
        ...

    async def validate_ticket_exists(self, ticket_id: str) -> bool:
        """Validate that a JIRA ticket exists and is accessible."""
        ...


@runtime_checkable
class JIRATicketServiceProtocol(Protocol):
    """Protocol for JIRA ticket discovery and management."""

    async def discover_jira_ticket(
        self, channel_name: str, channel_metadata: Dict[str, Any]
    ) -> Optional[str]:
        """Discover JIRA ticket for a channel."""
        ...

    async def search_jira_by_exigence_url(
        self, exigence_url: str, customer_name: Optional[str] = None
    ) -> Optional[str]:
        """Search JIRA for tickets containing the Exigence URL."""
        ...

    def extract_exigence_id(self, channel_name: str) -> Optional[str]:
        """Extract Exigence event ID from channel name."""
        ...


@runtime_checkable
class JIRAWorkflowServiceProtocol(Protocol):
    """Protocol for JIRA workflow and status management."""

    async def get_workflow_status(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get current workflow status for a ticket."""
        ...

    async def transition_ticket_status(
        self, ticket_id: str, transition: str
    ) -> bool:
        """Transition ticket to new status."""
        ...

    async def get_available_transitions(
        self, ticket_id: str
    ) -> List[Dict[str, Any]]:
        """Get available transitions for a ticket."""
        ...


@runtime_checkable
class JIRAReportingServiceProtocol(Protocol):
    """Protocol for JIRA reporting and analytics operations."""

    async def generate_channel_report(
        self, channel_id: str, ticket_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive report for a channel's JIRA data."""
        ...

    async def aggregate_ticket_metrics(
        self, ticket_ids: List[str]
    ) -> Dict[str, Any]:
        """Aggregate metrics across multiple tickets."""
        ...

    async def export_report_data(
        self, report_data: Dict[str, Any], format_type: str = "json"
    ) -> str:
        """Export report data in specified format."""
        ...


@runtime_checkable
class JIRAAnalyticsServiceProtocol(Protocol):
    """Protocol for JIRA analytics and performance tracking."""

    async def track_ticket_interaction(
        self, ticket_id: str, interaction_type: str, metadata: Dict[str, Any]
    ) -> None:
        """Track interactions with JIRA tickets for analytics."""
        ...

    async def get_performance_metrics(
        self, time_range: str = "last_7_days"
    ) -> Dict[str, Any]:
        """Get JIRA integration performance metrics."""
        ...

    async def analyze_ticket_patterns(
        self, channel_patterns: List[str]
    ) -> Dict[str, Any]:
        """Analyze patterns in ticket creation and resolution."""
        ...