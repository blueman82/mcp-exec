"""Jira MCP client service.

Thin async client that talks to the corp_jira_mcp server via JSON-RPC 2.0
over HTTP. All Jira operations go through the iPaaS gateway — no direct
Jira REST calls.
"""

from dataclasses import dataclass
from datetime import datetime

import json

import httpx
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
        assignee_id: The Jira username of the assignee.
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


class JiraMCPClient:
    """Async Jira client via corp_jira_mcp JSON-RPC.

    Sends JSON-RPC 2.0 requests to the corp_jira_mcp server's /message
    endpoint. The MCP server handles iPaaS auth, IMS tokens, and PAT
    rotation transparently.
    """

    def __init__(self, settings: JiraSettings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.settings.mcp_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool via JSON-RPC 2.0 POST to /message."""
        client = await self._get_client()

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        logger.debug("mcp_call", tool=tool_name, arguments=arguments)
        resp = await client.post("/message", json=payload)
        resp.raise_for_status()

        result = resp.json()

        if "error" in result:
            error = result["error"]
            msg = error.get("message", "Unknown MCP error") if isinstance(error, dict) else str(error)
            logger.error("mcp_tool_error", tool=tool_name, error=msg)
            raise RuntimeError(f"MCP tool {tool_name} failed: {msg}")

        content = result.get("result", {}).get("content", [])
        if content:
            text = content[0].get("text", "{}")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                logger.error("mcp_response_parse_error", tool=tool_name, error=str(exc))
                raise RuntimeError(f"Invalid MCP response from {tool_name}") from exc

        return result

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def search_tickets(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 100,
    ) -> list[JiraTicket]:
        """Search for tickets using JQL via MCP.

        Args:
            jql: The JQL query string.
            start_at: Pagination offset.
            max_results: Maximum results to return.

        Returns:
            List of matching JiraTicket objects.
        """
        logger.debug("jira_search", jql=jql, start_at=start_at)

        data = await self._call_tool("search_jira_issues", {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": ["summary", "assignee", "status", "updated", "comment"],
            "minimizeOutput": True,
        })

        tickets: list[JiraTicket] = []
        for issue in data.get("data", {}).get("issues", []):
            fields = issue.get("fields", {})
            assignee = fields.get("assignee")

            last_comment_at = None
            comments = fields.get("comment", {}).get("comments", [])
            if comments:
                last_comment_at = datetime.fromisoformat(
                    comments[-1]["updated"].replace("Z", "+00:00")
                )

            # With minimizeOutput, assignee may be a string (displayName)
            if isinstance(assignee, str):
                assignee_id = None
                assignee_name = assignee
            elif isinstance(assignee, dict):
                assignee_id = assignee.get("name")
                assignee_name = assignee.get("displayName")
            else:
                assignee_id = None
                assignee_name = None

            status = fields.get("status", {})
            status_name = status.get("name", "") if isinstance(status, dict) else str(status)

            updated_raw = fields.get("updated", "")
            updated = datetime.fromisoformat(
                updated_raw.replace("Z", "+00:00")
            ) if updated_raw else datetime.now()

            tickets.append(JiraTicket(
                key=issue["key"],
                id=issue.get("id", ""),
                project=issue["key"].split("-")[0],
                summary=fields.get("summary", ""),
                assignee_id=assignee_id,
                assignee_name=assignee_name,
                status=status_name,
                updated=updated,
                last_comment_at=last_comment_at,
            ))

        logger.info("jira_search_complete", count=len(tickets))
        return tickets

    async def add_comment(self, ticket_key: str, body: str) -> None:
        """Add a comment to a ticket via MCP.

        Args:
            ticket_key: The ticket key (e.g., CPGNCX-12345).
            body: The comment body text.
        """
        logger.info("adding_jira_comment", ticket_key=ticket_key)

        await self._call_tool("add_jira_comment", {
            "issueIdOrKey": ticket_key,
            "comment": {"body": body},
        })

        logger.info("jira_comment_added", ticket_key=ticket_key)

    async def transition_status(
        self,
        ticket_key: str,
        transition_id: str,
        resolution: dict | None = None,
    ) -> None:
        """Transition a ticket's status via MCP.

        Args:
            ticket_key: The ticket key.
            transition_id: The transition ID (from get_transitions).
            resolution: Optional resolution dict, e.g. {"name": "Done"}.
        """
        logger.info("transitioning_ticket", ticket_key=ticket_key, transition_id=transition_id)

        args: dict = {
            "issueIdOrKey": ticket_key,
            "transitionId": transition_id,
        }
        if resolution:
            args["resolution"] = resolution

        await self._call_tool("transition_jira_status", args)
        logger.info("ticket_transitioned", ticket_key=ticket_key)

    async def get_transitions(self, ticket_key: str) -> list[dict]:
        """Get available transitions for a ticket.

        Args:
            ticket_key: The ticket key.

        Returns:
            List of transition dicts with id, name, and to fields.
        """
        data = await self._call_tool("get_jira_transitions", {
            "issueIdOrKey": ticket_key,
        })
        return data.get("data", {}).get("transitions", [])

    async def create_issue(self, fields: dict) -> dict:
        """Create a new Jira issue via MCP.

        Args:
            fields: Issue fields dict (project, issuetype, summary, etc.).

        Returns:
            Created issue data with key, id, etc.
        """
        logger.info("creating_jira_issue", project=fields.get("project", {}).get("key"))

        return await self._call_tool("create_jira_issue", {"fields": fields})

    async def update_issue(self, ticket_key: str, fields: dict) -> None:
        """Update an existing Jira issue via MCP.

        Args:
            ticket_key: The ticket key.
            fields: Fields to update.
        """
        logger.info("updating_jira_issue", ticket_key=ticket_key)

        await self._call_tool("update_jira_issue", {
            "issueIdOrKey": ticket_key,
            "fields": fields,
        })

    async def download_attachment(
        self,
        ticket_key: str,
        attachment_id: str,
        destination_path: str,
    ) -> dict:
        """Download an attachment from a Jira issue via MCP.

        Args:
            ticket_key: The ticket key.
            attachment_id: The attachment ID.
            destination_path: Absolute path to save the file.

        Returns:
            Download result data.
        """
        logger.info(
            "downloading_attachment",
            ticket_key=ticket_key,
            attachment_id=attachment_id,
        )

        return await self._call_tool("download_attachment", {
            "issueIdOrKey": ticket_key,
            "attachmentId": attachment_id,
            "destinationPath": destination_path,
        })
