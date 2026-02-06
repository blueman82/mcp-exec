"""Nudge orchestration service.

This module orchestrates the nudge flow: evaluating tickets against
gates and LLM scoring, then sending Slack nudges to assignees.
"""

import structlog

from bravo.config import Settings
from bravo.db import queries
from bravo.services.gates import GateService
from bravo.services.jira import JiraClient
from bravo.services.llm import LLMService
from bravo.services.slack import SlackService

logger = structlog.get_logger(__name__)


class NudgeService:
    """Service for orchestrating nudge flow.

    Coordinates gate evaluation, LLM scoring, and Slack message sending
    to nudge engineers about tickets needing attention.

    Attributes:
        settings: Application configuration.
        jira: Jira API client.
        slack: Slack service for sending messages.
        gates: Gate evaluation service.
        llm: LLM scoring service.
    """

    def __init__(
        self,
        settings: Settings,
        jira: JiraClient,
        slack: SlackService,
        gates: GateService,
        llm: LLMService,
    ) -> None:
        """Initialize the nudge service.

        Args:
            settings: Application configuration.
            jira: Jira API client.
            slack: Slack service for sending messages.
            gates: Gate evaluation service.
            llm: LLM scoring service.
        """
        self.settings = settings
        self.jira = jira
        self.slack = slack
        self.gates = gates
        self.llm = llm

    async def evaluate_ticket(self, ticket_key: str) -> dict:
        """Evaluate a ticket and potentially trigger a nudge.

        Args:
            ticket_key: The Jira ticket key to evaluate.

        Returns:
            Dict with ticket_key, gate_result, should_nudge, nudge_reason.

        Raises:
            ValueError: If the ticket is not found.
        """
        ticket = await queries.get_ticket(ticket_key)
        if not ticket:
            raise ValueError(f"Ticket not found: {ticket_key}")

        gate_result = self.gates.evaluate(
            has_assignee_comment=ticket["last_assignee_comment_at"] is not None,
            last_assignee_comment_at=ticket["last_assignee_comment_at"],
            first_seen_at=ticket["first_seen_at"],
            jira_status=ticket["jira_status"] or "",
        )

        await queries.update_ticket_gates(
            ticket_key=ticket_key,
            g1=gate_result.g1_passed,
            g2=gate_result.g2_passed,
            g3=gate_result.g3_passed,
            g4=gate_result.g4_passed,
        )

        should_nudge = False
        nudge_reason = None

        if gate_result.any_failed:
            should_nudge = True
            failed_gates = []
            if not gate_result.g1_passed:
                failed_gates.append("G1 (no comment)")
            if not gate_result.g2_passed:
                failed_gates.append("G2 (stale)")
            if not gate_result.g3_passed:
                failed_gates.append("G3 (slow response)")
            if not gate_result.g4_passed:
                failed_gates.append("G4 (unresolved)")
            nudge_reason = f"Failed gates: {', '.join(failed_gates)}"
        else:
            llm_score = await self.llm.score_ticket(
                ticket_key=ticket_key,
                summary=ticket["summary"] or "",
                comments=[],
            )

            await queries.update_ticket_llm_scores(
                ticket_key=ticket_key,
                clarity=llm_score.clarity,
                completeness=llm_score.completeness,
                root_cause=llm_score.root_cause,
                actionability=llm_score.actionability,
            )

            if llm_score.below_threshold(self.settings.llm.threshold):
                should_nudge = True
                nudge_reason = f"LLM score below threshold ({llm_score.average:.1f} < {self.settings.llm.threshold})"

        if should_nudge:
            await self._send_nudge(ticket, nudge_reason or "Evaluation triggered")

        return {
            "ticket_key": ticket_key,
            "gate_result": gate_result,
            "should_nudge": should_nudge,
            "nudge_reason": nudge_reason,
        }

    async def _send_nudge(self, ticket: dict, reason: str) -> None:
        """Send a nudge to the ticket assignee.

        Args:
            ticket: The ticket database record.
            reason: The reason for the nudge.
        """
        if not ticket["assignee_jira_id"]:
            logger.warning("cannot_nudge_no_assignee", ticket_key=ticket["ticket_key"])
            return

        assignee = await queries.get_assignee(ticket["assignee_jira_id"])
        if not assignee or not assignee["slack_user_id"]:
            logger.warning(
                "cannot_nudge_no_slack",
                ticket_key=ticket["ticket_key"],
                assignee_id=ticket["assignee_jira_id"],
            )
            return

        message = self._build_nudge_message(ticket, reason)

        ts = await self.slack.send_dm(
            user_id=assignee["slack_user_id"],
            text=message,
        )

        if ts:
            nudge = await queries.create_nudge(
                ticket_key=ticket["ticket_key"],
                assignee_jira_id=ticket["assignee_jira_id"],
                trigger_reason=reason,
                slack_channel=assignee["slack_user_id"],
                message_content=message,
            )

            await queries.update_nudge_status(
                nudge_id=nudge["id"],
                status="SENT",
                slack_ts=ts,
            )

            await queries.increment_assignee_nudge_count(ticket["assignee_jira_id"])

            logger.info(
                "nudge_sent",
                ticket_key=ticket["ticket_key"],
                nudge_id=str(nudge["id"]),
            )

    def _build_nudge_message(self, ticket: dict, reason: str) -> str:
        """Build the nudge message text.

        Args:
            ticket: The ticket database record.
            reason: The reason for the nudge.

        Returns:
            The formatted Slack message text.
        """
        return f"""Hi! I noticed your ticket *{ticket['ticket_key']}* could use some attention.

*{ticket['summary']}*

{reason}

Could you add an update to the ticket? Even a brief status helps the team track progress.

_Reply here with your update and I'll add it to Jira for you._"""
