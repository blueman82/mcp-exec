"""Jira API client service.

This module provides an async client for interacting with the Jira REST API,
including ticket search and comment operations.
"""

from dataclasses import dataclass
from datetime import datetime

import aiohttp
import structlog

from bravo.config import JiraSettings

logger = structlog.get_logger(__name__)


@dataclass
class JiraTicket:
    """Jira ticket data.

    Attributes:
        key: The ticket key (e.g., CPGNCX-12345).
        id: The internal Jira ticket ID.
        project: The project key extracted from the ticket key.
        summary: The ticket summary/title.
        assignee_id: The Jira account ID of the assignee.
        assignee_name: The display name of the assignee.
        status: The current ticket status.
        updated: When the ticket was last updated.
        last_comment_at: When the last comment was made.
    """

    key: str
    id: str
    project: str
    summary: str
    assignee_id: str | None
    assignee_name: str | None
    status: str
    updated: datetime
    last_comment_at: datetime | None = None


class JiraClient:
    """Async Jira API client.

    Provides methods for searching tickets and adding comments via the Jira
    REST API using aiohttp for async HTTP operations.

    Attributes:
        settings: Jira configuration settings.
    """

    def __init__(self, settings: JiraSettings) -> None:
        """Initialize the Jira client.

        Args:
            settings: Jira API configuration.
        """
        self.settings = settings
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session.

        Returns:
            The aiohttp client session.
        """
        if self._session is None or self._session.closed:
            auth = aiohttp.BasicAuth(
                self.settings.username,
                self.settings.api_token,
            )
            self._session = aiohttp.ClientSession(
                base_url=self.settings.base_url,
                auth=auth,
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session.

        Closes the aiohttp session if it exists and is open.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def search_tickets(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 100,
    ) -> list[JiraTicket]:
        """Search for tickets using JQL.

        Args:
            jql: The JQL query string.
            start_at: The index to start results from (pagination).
            max_results: Maximum number of results to return.

        Returns:
            List of matching JiraTicket objects.
        """
        session = await self._get_session()

        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": "summary,assignee,status,updated,comment",
        }

        logger.debug("jira_search", jql=jql, start_at=start_at)

        async with session.get("/rest/api/2/search", params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

        tickets = []
        for issue in data.get("issues", []):
            fields = issue["fields"]
            assignee = fields.get("assignee")

            last_comment_at = None
            comments = fields.get("comment", {}).get("comments", [])
            if comments:
                last_comment_at = datetime.fromisoformat(
                    comments[-1]["updated"].replace("Z", "+00:00")
                )

            tickets.append(JiraTicket(
                key=issue["key"],
                id=issue["id"],
                project=issue["key"].split("-")[0],
                summary=fields.get("summary", ""),
                assignee_id=assignee.get("accountId") if assignee else None,
                assignee_name=assignee.get("displayName") if assignee else None,
                status=fields["status"]["name"],
                updated=datetime.fromisoformat(
                    fields["updated"].replace("Z", "+00:00")
                ),
                last_comment_at=last_comment_at,
            ))

        logger.info("jira_search_complete", count=len(tickets))
        return tickets

    async def add_comment(self, ticket_key: str, body: str) -> None:
        """Add a comment to a ticket.

        Args:
            ticket_key: The ticket key (e.g., CPGNCX-12345).
            body: The comment body text.
        """
        session = await self._get_session()

        logger.info("adding_jira_comment", ticket_key=ticket_key)

        async with session.post(
            f"/rest/api/2/issue/{ticket_key}/comment",
            json={"body": body},
        ) as resp:
            resp.raise_for_status()

        logger.info("jira_comment_added", ticket_key=ticket_key)
