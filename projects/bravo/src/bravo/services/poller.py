"""Jira polling service.

This module provides the polling service that periodically fetches
tickets from Jira based on configured projects and org groups.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from bravo.config import Settings
from bravo.db import queries
from bravo.protocols import JiraClientProto, NudgeServiceProto, SlackServiceProto
from bravo.services.jira import JiraTicket

logger = structlog.get_logger(__name__)


class PollerService:
    """Service for polling Jira tickets.

    Periodically queries Jira for tickets matching configured criteria
    and upserts them into the local database for tracking.

    Attributes:
        settings: Application configuration.
        jira: Jira API client.
    """

    def __init__(
        self,
        settings: Settings,
        jira_client: JiraClientProto,
        nudge: NudgeServiceProto,
        slack: SlackServiceProto,
    ) -> None:
        """Initialize the poller service.

        Args:
            settings: Application configuration.
            jira_client: Jira API client instance.
            nudge: Nudge orchestration service.
            slack: Slack service for user lookups.
        """
        self.settings = settings
        self.jira = jira_client
        self.nudge = nudge
        self.slack = slack

    async def _ensure_assignee(self, ticket: JiraTicket) -> None:
        """Auto-register an assignee from Jira ticket data.

        Upserts the assignee record and looks up their Slack user ID
        via email if not already mapped.

        Args:
            ticket: The Jira ticket with assignee info.
        """
        if not ticket.assignee_id:
            return

        email = f"{ticket.assignee_id}@{self.settings.jira.email_domain}"
        assignee = await queries.upsert_assignee(
            jira_id=ticket.assignee_id,
            display_name=ticket.assignee_name,
            slack_user_id=None,
            email=email,
        )

        if not assignee["slack_user_id"]:
            slack_user = await self.slack.lookup_user_by_email(email)
            if slack_user:
                await queries.upsert_assignee(
                    jira_id=ticket.assignee_id,
                    display_name=ticket.assignee_name,
                    slack_user_id=slack_user.user_id,
                    email=email,
                )

    def _build_jql(self, since: datetime | None = None) -> str:
        """Build JQL query for polling.

        Args:
            since: Only fetch tickets updated since this time.

        Returns:
            The JQL query string.
        """
        projects = ", ".join(self.settings.jira.projects)
        groups = " OR ".join(
            f'assignee in membersOf("{g}")' for g in self.settings.jira.org_groups
        )

        jql = f"project IN ({projects}) AND ({groups}) AND status != Closed"

        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M")
            jql += f' AND updated >= "{since_str}"'

        jql += " ORDER BY updated DESC"
        return jql

    async def run_poll(self) -> dict[str, Any]:
        """Execute a poll cycle.

        Fetches tickets from Jira, upserts them to the database,
        and records the poll in history.

        Returns:
            Dict with poll_id, tickets_fetched, tickets_new, tickets_updated.

        Raises:
            Exception: If the poll fails, after recording the failure.
        """
        poll_record = await queries.create_poll_history()
        poll_id = poll_record["id"]

        logger.info("poll_cycle_started", poll_id=str(poll_id))

        state = await queries.get_poll_state()
        last_cursor = state["last_cursor"] if state else None

        jql = self._build_jql(since=last_cursor)
        tickets_new = 0
        tickets_updated = 0
        tickets_fetched = 0

        nudges_triggered = 0

        try:
            tickets = await self.jira.search_tickets(jql)
            tickets_fetched = len(tickets)

            for ticket in tickets:
                existing = await queries.get_ticket(ticket.key)

                await queries.upsert_ticket(
                    ticket_key=ticket.key,
                    jira_id=ticket.id,
                    project=ticket.project,
                    summary=ticket.summary,
                    assignee_jira_id=ticket.assignee_id,
                    assignee_name=ticket.assignee_name,
                    jira_status=ticket.status,
                )

                try:
                    await self._ensure_assignee(ticket)
                except Exception:
                    logger.warning(
                        "assignee_registration_failed",
                        ticket_key=ticket.key,
                        assignee_id=ticket.assignee_id,
                        exc_info=True,
                    )

                if ticket.assignee_id:
                    try:
                        comment_ts = await self.jira.get_assignee_comment_ts(
                            ticket.key, ticket.assignee_id
                        )
                        await queries.update_ticket_comment_ts(
                            ticket.key, ticket.assignee_id, comment_ts
                        )
                    except Exception:
                        logger.warning(
                            "comment_ts_fetch_failed",
                            ticket_key=ticket.key,
                            exc_info=True,
                        )

                if existing:
                    tickets_updated += 1
                else:
                    tickets_new += 1

            for ticket in tickets:
                try:
                    result = await self.nudge.evaluate_ticket(ticket.key)
                    if result.get("should_nudge"):
                        nudges_triggered += 1
                except Exception as eval_err:
                    logger.warning(
                        "ticket_evaluation_failed",
                        ticket_key=ticket.key,
                        error=str(eval_err),
                    )

            next_poll = datetime.now(UTC) + timedelta(
                minutes=self.settings.poll_interval_minutes
            )

            await queries.update_poll_state(
                last_cursor=datetime.now(UTC),
                tickets_fetched=tickets_fetched,
                next_poll_at=next_poll,
            )

            await queries.complete_poll_history(
                poll_id=poll_id,
                tickets_fetched=tickets_fetched,
                tickets_new=tickets_new,
                tickets_updated=tickets_updated,
                nudges_triggered=nudges_triggered,
                status="completed",
            )

            logger.info(
                "poll_cycle_complete",
                poll_id=str(poll_id),
                fetched=tickets_fetched,
                new=tickets_new,
                updated=tickets_updated,
                nudges=nudges_triggered,
            )

        except Exception as e:
            logger.error("poll_cycle_failed", poll_id=str(poll_id), error=str(e))
            await queries.complete_poll_history(
                poll_id=poll_id,
                tickets_fetched=tickets_fetched,
                tickets_new=tickets_new,
                tickets_updated=tickets_updated,
                nudges_triggered=nudges_triggered,
                status="failed",
                error_message=str(e),
            )
            raise

        return {
            "poll_id": poll_id,
            "tickets_fetched": tickets_fetched,
            "tickets_new": tickets_new,
            "tickets_updated": tickets_updated,
            "nudges_triggered": nudges_triggered,
        }
