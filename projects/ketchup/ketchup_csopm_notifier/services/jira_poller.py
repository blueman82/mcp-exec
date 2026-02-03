"""
CSOPM JIRA Poller Service.

This module implements the CSOPMJIRAPoller service for polling JIRA
to discover new CSOPM ticket assignments that require notifications.

Follows the pattern established in:
ketchup_unified_scheduler/services/jira_reporter/ticket_discovery.py
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import CSOPMJIRAPollerProtocol, CSOPMTicket
from packages.integrations.async_mcp_client import AsyncMCPClient

logger = setup_logger(__name__)

# Exigence URL pattern for extracting event IDs from ticket descriptions
# Matches 5-6 digit IDs in Exigence URLs like: /events/12345/ or /events/123456/
from packages.core.config.csopm_config import CSOPM_JIRA_PROJECT

EXIGENCE_ID_PATTERN = re.compile(r"/events/(\d{5,6})/")


class CSOPMJIRAPoller(CSOPMJIRAPollerProtocol):
    """Service for polling JIRA for new CSOPM ticket assignments.

    This service queries JIRA for newly assigned tickets in the CSOPM project
    that need notifications. It transforms JIRA response data into CSOPMTicket
    instances for consumption by the notification pipeline.

    Architectural Note:
    This is the first JIRA polling service for CSOPM and establishes the pattern
    for how CSOPM tickets are queried and parsed. The CSOPMTicket parsing logic
    should be reused by other CSOPM services.
    """

    # JQL query for discovering new CSOPM assignments
    # Note: We don't filter by 'assignee IS NOT EMPTY' in JQL because CSOPM project
    # restricts that field. Instead, we filter out unassigned tickets in Python code.
    # Filter by TechOps Product (customfield_20800) for Adobe Campaign/AJO only.
    NEW_ASSIGNMENTS_JQL = (
        f"project = {CSOPM_JIRA_PROJECT} AND "
        "status = 'New' AND "
        "cf[20800] IN ('Adobe Campaign', 'Adobe Journey Optimizer') "
        "ORDER BY created DESC"
    )

    # Default fields to retrieve from JIRA
    DEFAULT_FIELDS = [
        "summary",
        "status",
        "assignee",
        "created",
        "description",
    ]

    def __init__(self, mcp_client: AsyncMCPClient) -> None:
        """Initialize the CSOPM JIRA poller.

        Args:
            mcp_client: AsyncMCPClient for JIRA API access via MCP.
        """
        self._mcp_client = mcp_client
        logger.info("CSOPMJIRAPoller initialized")

    def _extract_exigence_id(self, description: Optional[str]) -> Optional[str]:
        """Extract Exigence event ID from ticket description.

        Searches for Exigence URLs in the description and extracts
        the 5-6 digit event ID.

        Args:
            description: The JIRA ticket description text.

        Returns:
            The Exigence event ID if found, None otherwise.
        """
        if not description:
            return None

        match = EXIGENCE_ID_PATTERN.search(description)
        if match:
            event_id = match.group(1)
            logger.debug("Extracted Exigence ID %s from description", event_id)
            return event_id

        return None

    def _parse_jira_issue(self, issue: Dict[str, Any]) -> Optional[CSOPMTicket]:
        """Parse a JIRA issue into a CSOPMTicket instance.

        Args:
            issue: Raw JIRA issue data from MCP response.

        Returns:
            CSOPMTicket instance if parsing succeeds, None on error.
        """
        try:
            key = issue.get("key")
            if not key:
                logger.warning("Issue missing key field")
                return None

            fields = issue.get("fields", {})

            # Extract summary
            summary = fields.get("summary", "")

            # Extract status name
            status_obj = fields.get("status", {})
            status = status_obj.get("name", "Unknown") if isinstance(status_obj, dict) else "Unknown"

            # Extract assignee username
            assignee_obj = fields.get("assignee", {})
            if not assignee_obj:
                logger.warning("Issue %s has no assignee", key)
                return None
            assignee_username = (
                assignee_obj.get("name") or assignee_obj.get("displayName", "")
                if isinstance(assignee_obj, dict)
                else ""
            )
            if not assignee_username:
                logger.warning("Issue %s has empty assignee username", key)
                return None

            # Parse created date
            created_str = fields.get("created", "")
            try:
                # JIRA datetime format: 2024-01-15T10:30:00.000+0000
                created_at = datetime.fromisoformat(created_str.replace("+0000", "+00:00"))
            except (ValueError, AttributeError):
                logger.warning("Issue %s has invalid created date: %s", key, created_str)
                created_at = datetime.now()

            # Extract Exigence ID from description
            description = fields.get("description", "")
            exigence_id = self._extract_exigence_id(description)

            ticket = CSOPMTicket(
                key=key,
                summary=summary,
                assignee_username=assignee_username,
                created_at=created_at,
                status=status,
                exigence_id=exigence_id,
            )

            logger.debug(
                "Parsed CSOPM ticket: %s (assignee=%s, status=%s)",
                key,
                assignee_username,
                status,
            )
            return ticket

        except Exception as e:
            logger.error("Error parsing JIRA issue: %s", e)
            return None

    async def poll_for_new_assignments(self) -> List[CSOPMTicket]:
        """Poll JIRA for newly assigned tickets requiring notification.

        Queries JIRA using the NEW_ASSIGNMENTS_JQL to find tickets that:
        - Are in the CSOPM project
        - Have an assignee
        - Are in 'New' status
        - Were created within the last day

        Returns:
            List of CSOPMTicket instances representing new assignments.
            Empty list if no new assignments found or on error.
        """
        try:
            logger.info("Polling JIRA for new CSOPM assignments")

            result = await self._mcp_client.search_issues(
                jql=self.NEW_ASSIGNMENTS_JQL,
                fields=self.DEFAULT_FIELDS,
                max_results=50,
            )

            # Extract issues from response
            issues = result.get("issues", []) if result else []

            if not issues:
                logger.info("No new CSOPM assignments found")
                return []

            # Parse issues into CSOPMTicket instances
            tickets: List[CSOPMTicket] = []
            for issue in issues:
                ticket = self._parse_jira_issue(issue)
                if ticket:
                    tickets.append(ticket)

            logger.info(
                "Found %d new CSOPM assignments (parsed %d/%d issues)",
                len(tickets),
                len(tickets),
                len(issues),
            )

            return tickets

        except Exception as e:
            logger.error("Error polling for new CSOPM assignments: %s", e)
            return []

    async def get_ticket_details(self, ticket_key: str) -> Optional[CSOPMTicket]:
        """Get detailed information for a specific ticket.

        Args:
            ticket_key: The JIRA ticket key (e.g., "CSOPM-1234")

        Returns:
            CSOPMTicket instance if found, None otherwise.
        """
        try:
            logger.info("Getting details for ticket: %s", ticket_key)

            issue = await self._mcp_client.get_issue(
                issue_key=ticket_key,
                fields=self.DEFAULT_FIELDS,
            )

            if not issue:
                logger.warning("Ticket not found: %s", ticket_key)
                return None

            return self._parse_jira_issue(issue)

        except Exception as e:
            logger.error("Error getting ticket details for %s: %s", ticket_key, e)
            return None

    async def get_tickets_by_assignee(self, assignee_username: str) -> List[CSOPMTicket]:
        """Get all active tickets assigned to a specific user.

        Args:
            assignee_username: The JIRA username of the assignee

        Returns:
            List of CSOPMTicket instances assigned to the user.
        """
        try:
            logger.info("Getting CSOPM tickets for assignee: %s", assignee_username)

            # Query for all active tickets assigned to the user
            jql = (
                f"project = {CSOPM_JIRA_PROJECT} AND "
                f'assignee = "{assignee_username}" AND '
                f"status NOT IN (Closed, Resolved, Done) "
                f"ORDER BY created DESC"
            )

            result = await self._mcp_client.search_issues(
                jql=jql,
                fields=self.DEFAULT_FIELDS,
                max_results=100,
            )

            issues = result.get("issues", []) if result else []

            if not issues:
                logger.info("No active tickets found for assignee: %s", assignee_username)
                return []

            # Parse issues into CSOPMTicket instances
            tickets: List[CSOPMTicket] = []
            for issue in issues:
                ticket = self._parse_jira_issue(issue)
                if ticket:
                    tickets.append(ticket)

            logger.info(
                "Found %d active tickets for assignee %s",
                len(tickets),
                assignee_username,
            )

            return tickets

        except Exception as e:
            logger.error(
                "Error getting tickets for assignee %s: %s",
                assignee_username,
                e,
            )
            return []
