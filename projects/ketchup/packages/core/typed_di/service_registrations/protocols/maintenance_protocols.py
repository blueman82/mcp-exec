"""
Maintenance Detection Protocol Definitions.

Protocol definitions for maintenance detection services including
SOAP client, maintenance checker, and JIRA prompt handling.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


__all__ = [
    "RavenMaintenanceClientProtocol",
    "MaintenanceCheckerProtocol",
    "JiraPromptHandlerProtocol",
]


@runtime_checkable
class RavenMaintenanceClientProtocol(Protocol):
    """Protocol for Raven SOAP API client operations."""

    async def fetch_maintenance_data(self, date: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch maintenance data for specific date (YYYY-MM-DD format).

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            List of maintenance records or None on error
        """
        ...


@runtime_checkable
class MaintenanceCheckerProtocol(Protocol):
    """Protocol for maintenance checking operations."""

    async def check_maintenance_for_ticket(
        self, jira_ticket: str, channel_id: str
    ) -> Dict[str, Any]:
        """
        Check if JIRA ticket instances are under maintenance.

        Args:
            jira_ticket: JIRA ticket identifier
            channel_id: Slack channel ID

        Returns:
            Dict with maintenance_found, customer_name, etc.
        """
        ...

    def normalize_instance_name(self, url_or_name: str) -> str:
        """
        Normalize instance name for matching.

        Args:
            url_or_name: Instance URL or name

        Returns:
            Normalized instance name
        """
        ...


@runtime_checkable
class JiraPromptHandlerProtocol(Protocol):
    """Protocol for JIRA ticket prompting workflow."""

    async def start_jira_prompt_workflow(
        self, channel_id: str, inviter_id: str
    ) -> None:
        """
        Start JIRA prompt workflow with 3 retry attempts.

        Posts prompt, waits for reply, triggers maintenance check.

        Args:
            channel_id: Slack channel ID
            inviter_id: User ID who invited the bot
        """
        ...
