"""
JIRA Core Service Implementations

Core JIRA service implementations for ticket discovery and basic operations.
Separated from registration module to maintain size limits.
"""

from typing import Any, Dict, Optional

from packages.core.logging import setup_logger

try:
    from jira_reporter.jira_ticket_discovery import JiraTicketDiscovery
except ImportError as e:
    logger = setup_logger(__name__)
    logger.warning(f"JIRA core import failed: {e}")

logger = setup_logger(__name__)


class JIRATicketService:
    """JIRA ticket discovery and management service."""

    def __init__(self, discovery: JiraTicketDiscovery):
        """Initialize with ticket discovery service."""
        self.discovery = discovery

    async def discover_jira_ticket(
        self, channel_name: str, channel_metadata: Dict[str, Any]
    ) -> Optional[str]:
        """Discover JIRA ticket for a channel."""
        return await self.discovery.discover_jira_ticket(channel_name, channel_metadata)

    async def search_jira_by_exigence_url(
        self, exigence_url: str, customer_name: Optional[str] = None
    ) -> Optional[str]:
        """Search JIRA for tickets containing the Exigence URL."""
        return await self.discovery.search_jira_by_exigence_url(exigence_url, customer_name)

    def extract_exigence_id(self, channel_name: str) -> Optional[str]:
        """Extract Exigence event ID from channel name."""
        return self.discovery.extract_exigence_id(channel_name)
