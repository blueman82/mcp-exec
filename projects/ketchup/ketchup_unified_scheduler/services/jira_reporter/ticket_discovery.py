"""
ticket_discovery.py

Service for discovering JIRA tickets linked to CSO channels.
"""

import os
import re
from typing import Any, Dict, Optional

from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger
from packages.integrations.async_mcp_client import AsyncMCPClient

logger = setup_logger(__name__)

# Exigence URL template
EXIGENCE_URL_TEMPLATE = (
    "https://adobe.app.exigence.io/secure/index.html#/events/{event_id}/situationroom"
)


class JiraTicketDiscovery:
    """Service for discovering JIRA tickets linked to CSO channels."""

    def __init__(self, mcp_client: Optional[AsyncMCPClient] = None):
        """
        Initialize the JIRA ticket discovery service.

        Args:
            mcp_client: AsyncMCPClient for direct JIRA API access
        """
        self.mcp_client = mcp_client
        self.valid_projects = os.environ.get(
            "VALID_JIRA_PROJECTS", ",".join(VALID_JIRA_PROJECTS)
        ).split(",")

    def extract_exigence_id(self, channel_name: str) -> Optional[str]:
        """
        Extract Exigence event ID from channel name.

        Args:
            channel_name: The Slack channel name

        Returns:
            The 5-digit Exigence event ID if found, None otherwise
        """
        # Pattern to find 5-digit numbers not part of a date
        # This excludes patterns like YYYYMMDD by ensuring the 5-digit number
        # is not preceded by more digits
        pattern = r"(?<!\d)(\d{5})(?!\d)"

        # Find all 5-digit numbers in the channel name
        matches = re.findall(pattern, channel_name)

        if not matches:
            logger.info(f"No 5-digit ID found in channel name: {channel_name}")
            return None

        # Return the last match (usually at the end of channel name)
        event_id = matches[-1]
        logger.info(f"Extracted Exigence event ID {event_id} from channel: {channel_name}")
        return event_id

    def build_exigence_url(self, event_id: str) -> str:
        """
        Build Exigence URL from event ID.

        Args:
            event_id: The Exigence event ID

        Returns:
            The full Exigence URL
        """
        return EXIGENCE_URL_TEMPLATE.format(event_id=event_id)

    async def search_jira_by_exigence_url(
        self, exigence_url: str, customer_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Search JIRA for tickets containing the Exigence URL.

        Args:
            exigence_url: The Exigence URL to search for
            customer_name: Optional customer name for additional filtering

        Returns:
            JIRA ticket ID if found, None otherwise
        """
        if not self.mcp_client:
            logger.error("MCP client not configured")
            return None

        try:
            # Primary search in CSOPM project descriptions
            jql = f'project = "CSO Problem Management" AND description ~ "{exigence_url}"'

            logger.info(f"Searching JIRA with JQL: {jql}")
            # Use MCP client for direct JIRA access
            results = await self.mcp_client.search_issues(jql, max_results=50)

            # Extract issues from results
            if results and "issues" in results:
                issues = results["issues"]
            else:
                issues = []

            if issues and len(issues) > 0:
                ticket_id = issues[0].get("key")
                logger.info(f"Found JIRA ticket {ticket_id} via CSOPM description search")
                return ticket_id

            # Extended search across all valid projects and comments
            projects_list = ", ".join([f'"{p}"' for p in self.valid_projects])
            jql = (
                f"project IN ({projects_list}) "
                f'AND (description ~ "{exigence_url}" OR comment ~ "{exigence_url}")'
            )

            # Add customer filter if available
            if customer_name and customer_name != "NOT YET AVAILABLE":
                jql += f' AND summary ~ "{customer_name}"'

            logger.info(f"Extended JIRA search with JQL: {jql}")
            results = await self.mcp_client.search_issues(jql, max_results=50)

            # Extract issues from results
            if results and "issues" in results:
                issues = results["issues"]
            else:
                issues = []

            if issues and len(issues) > 0:
                # If multiple results, prefer CSOPM project
                for issue in issues:
                    if issue.get("key", "").startswith("CSOPM-"):
                        ticket_id = issue.get("key")
                        logger.info(
                            f"Found JIRA ticket {ticket_id} via extended search (CSOPM preferred)"
                        )
                        return ticket_id

                # Otherwise return the first result
                ticket_id = issues[0].get("key")
                logger.info(f"Found JIRA ticket {ticket_id} via extended search")
                return ticket_id

            logger.info(f"No JIRA tickets found for Exigence URL: {exigence_url}")
            return None

        except Exception as e:
            logger.error(f"Error searching JIRA: {str(e)}")
            return None

    async def discover_jira_ticket(
        self, channel_name: str, channel_metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Attempt to discover JIRA ticket for a channel.

        Args:
            channel_name: The Slack channel name
            channel_metadata: Channel metadata from DynamoDB

        Returns:
            JIRA ticket ID if discovered, None otherwise
        """
        # First check if channel already has a valid JIRA ticket
        existing_ticket = channel_metadata.get("jira_ticket", "")
        if existing_ticket and existing_ticket != "NOT YET AVAILABLE":
            # Validate it's a proper JIRA ticket format
            if re.match(r"^[A-Z]{2,10}-[0-9]{1,7}(?![0-9])$", existing_ticket):
                logger.info(f"Channel already has valid JIRA ticket: {existing_ticket}")
                return existing_ticket

        # Extract Exigence ID from channel name
        event_id = self.extract_exigence_id(channel_name)
        if not event_id:
            logger.info(f"No Exigence ID found in channel name: {channel_name}")
            return None

        # Build Exigence URL and search JIRA
        exigence_url = self.build_exigence_url(event_id)
        customer_name = channel_metadata.get("customer_name")

        ticket_id = await self.search_jira_by_exigence_url(exigence_url, customer_name)

        if ticket_id:
            logger.info(
                f"Successfully discovered JIRA ticket {ticket_id} for channel {channel_name}"
            )
        else:
            logger.info(f"Could not discover JIRA ticket for channel {channel_name}")

        return ticket_id

    async def discover_csopm_ticket(
        self, channel_name: str, channel_metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Discover CSOPM ticket for dual posting.
        This method specifically looks for CSOPM tickets only,
        regardless of any existing primary ticket.

        Args:
            channel_name: The Slack channel name
            channel_metadata: Channel metadata from DynamoDB

        Returns:
            CSOPM ticket ID if discovered, None otherwise
        """
        # Extract Exigence ID from channel name
        event_id = self.extract_exigence_id(channel_name)
        if not event_id:
            logger.info(f"No Exigence ID found in channel name: {channel_name}")
            return None

        # Build Exigence URL
        exigence_url = self.build_exigence_url(event_id)

        # Search specifically for CSOPM tickets first
        try:
            # Direct CSOPM search - use parentheses to ensure correct operator precedence
            jql = f'project = "CSO Problem Management" AND (description ~ "{exigence_url}" OR comment ~ "{exigence_url}")'
            logger.info(f"Searching for CSOPM ticket with JQL: {jql}")

            if self.mcp_client:
                results = await self.mcp_client.search_issues(jql, max_results=50)

                # Extract issues from results
                if results and "issues" in results:
                    issues = results["issues"]
                else:
                    issues = []

                if issues and len(issues) > 0:
                    ticket_id = issues[0].get("key")
                    if ticket_id and ticket_id.startswith("CSOPM-"):
                        logger.info(f"Found CSOPM ticket {ticket_id} for channel {channel_name}")
                        return ticket_id
                    else:
                        logger.warning(
                            f"Found non-CSOPM ticket {ticket_id} in CSOPM project search"
                        )

            logger.info(
                f"No CSOPM ticket found for channel {channel_name} with exigence URL {exigence_url}"
            )
            return None

        except Exception as e:
            logger.error(f"Error searching for CSOPM ticket: {str(e)}")
            return None
