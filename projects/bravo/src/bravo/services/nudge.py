"""Nudge orchestration service.

This module orchestrates the nudge flow: evaluating tickets against
gates and LLM scoring, then sending Slack nudges to assignees.
"""

from typing import Any

import structlog

from bravo.config import Settings
from bravo.db import queries
from bravo.protocols import (
    GateServiceProto,
    JiraClientProto,
    LLMServiceProto,
    SlackServiceProto,
)
from bravo.services.blocks import (
    build_nudge_blocks,
    build_nudge_fallback_text,
    format_trigger_reasons,
)

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
        jira: JiraClientProto,
        slack: SlackServiceProto,
        gates: GateServiceProto,
        llm: LLMServiceProto,
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

    async def evaluate_ticket(self, ticket_key: str) -> dict[str, Any]:
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
        failed_gate_codes: list[str] = []

        _gate_labels = {
            "G1": "no comment",
            "G2": "stale",
            "G3": "slow response",
            "G4": "unresolved",
        }

        if gate_result.any_failed:
            should_nudge = True
            for code, passed in [
                ("G1", gate_result.g1_passed),
                ("G2", gate_result.g2_passed),
                ("G3", gate_result.g3_passed),
                ("G4", gate_result.g4_passed),
            ]:
                if not passed:
                    failed_gate_codes.append(code)
            nudge_reason = "Failed gates: " + ", ".join(
                f"{c} ({_gate_labels[c]})" for c in failed_gate_codes
            )
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
            codes = failed_gate_codes if gate_result.any_failed else []
            await self._send_nudge(
                ticket,
                nudge_reason or "Evaluation triggered",
                failed_gate_codes=codes,
            )

        return {
            "ticket_key": ticket_key,
            "gate_result": gate_result,
            "should_nudge": should_nudge,
            "nudge_reason": nudge_reason,
        }

    async def _send_nudge(
        self,
        ticket: dict[str, Any],
        reason: str,
        *,
        failed_gate_codes: list[str] | None = None,
    ) -> None:
        """Send a nudge to the ticket assignee.

        Args:
            ticket: The ticket database record.
            reason: The reason for the nudge.
            failed_gate_codes: List of failed gate codes (e.g. ["G1", "G3"]).
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

        trigger_reason = (
            format_trigger_reasons(failed_gate_codes) if failed_gate_codes else reason
        )
        ticket_url = f"https://jira.corp.adobe.com/browse/{ticket['ticket_key']}"

        blocks = build_nudge_blocks(
            ticket_key=ticket["ticket_key"],
            ticket_url=ticket_url,
            jira_status=ticket["jira_status"] or "Unknown",
            summary=ticket["summary"] or ticket["ticket_key"],
            trigger_reason=trigger_reason,
        )
        fallback = build_nudge_fallback_text(
            ticket_key=ticket["ticket_key"],
            summary=ticket["summary"] or ticket["ticket_key"],
            trigger_reason=trigger_reason,
        )

        ts = await self.slack.send_dm(
            user_id=assignee["slack_user_id"],
            text=fallback,
            blocks=blocks,
        )

        if ts:
            nudge = await queries.create_nudge(
                ticket_key=ticket["ticket_key"],
                assignee_jira_id=ticket["assignee_jira_id"],
                trigger_reason=reason,
                slack_channel=assignee["slack_user_id"],
                message_content=fallback,
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
