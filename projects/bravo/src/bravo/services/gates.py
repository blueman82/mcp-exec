"""Heuristic gate evaluation service.

This module implements the four heuristic gates (G1-G4) that determine
whether a ticket needs attention:
- G1: Assignee has commented
- G2: Comment is not stale
- G3: Response within threshold
- G4: Resolution within threshold
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog

from bravo.config import GateSettings

logger = structlog.get_logger(__name__)


@dataclass
class GateEvaluation:
    """Result of gate evaluation.

    Attributes:
        g1_passed: Whether the assignee has commented.
        g2_passed: Whether the last comment is not stale.
        g3_passed: Whether response was within threshold.
        g4_passed: Whether resolution is within threshold.
    """

    g1_passed: bool
    g2_passed: bool
    g3_passed: bool
    g4_passed: bool

    @property
    def all_passed(self) -> bool:
        """Check if all gates passed.

        Returns:
            True if all four gates passed.
        """
        return self.g1_passed and self.g2_passed and self.g3_passed and self.g4_passed

    @property
    def any_failed(self) -> bool:
        """Check if any gate failed.

        Returns:
            True if any gate failed.
        """
        return not self.all_passed


class GateService:
    """Service for evaluating heuristic gates.

    Evaluates tickets against configurable gate thresholds to determine
    if they need nudging.

    Attributes:
        settings: Gate configuration settings.
    """

    def __init__(self, settings: GateSettings) -> None:
        """Initialize the gate service.

        Args:
            settings: Gate configuration settings.
        """
        self.settings = settings

    def evaluate(
        self,
        has_assignee_comment: bool,
        last_assignee_comment_at: datetime | None,
        first_seen_at: datetime,
        jira_status: str,
    ) -> GateEvaluation:
        """Evaluate all gates for a ticket.

        Args:
            has_assignee_comment: Whether assignee has left any comment.
            last_assignee_comment_at: Timestamp of last assignee comment.
            first_seen_at: When the ticket was first seen by Bravo.
            jira_status: Current Jira status of the ticket.

        Returns:
            GateEvaluation with results for all four gates.
        """
        now = datetime.now(timezone.utc)

        g1 = self._evaluate_g1(has_assignee_comment)
        g2 = self._evaluate_g2(last_assignee_comment_at, now)
        g3 = self._evaluate_g3(first_seen_at, last_assignee_comment_at, now)
        g4 = self._evaluate_g4(first_seen_at, jira_status, now)

        result = GateEvaluation(
            g1_passed=g1,
            g2_passed=g2,
            g3_passed=g3,
            g4_passed=g4,
        )

        logger.debug(
            "gates_evaluated",
            g1=g1,
            g2=g2,
            g3=g3,
            g4=g4,
            all_passed=result.all_passed,
        )

        return result

    def _evaluate_g1(self, has_assignee_comment: bool) -> bool:
        """G1: Assignee has left at least one comment.

        Args:
            has_assignee_comment: Whether assignee has commented.

        Returns:
            True if gate passes (comment exists or gate disabled).
        """
        if not self.settings.g1_enabled:
            return True
        return has_assignee_comment

    def _evaluate_g2(
        self,
        last_comment_at: datetime | None,
        now: datetime,
    ) -> bool:
        """G2: Last comment not stale (within threshold hours).

        Args:
            last_comment_at: Timestamp of last comment.
            now: Current timestamp.

        Returns:
            True if last comment is within stale threshold.
        """
        if last_comment_at is None:
            return False

        threshold = timedelta(hours=self.settings.g2_stale_hours)
        return (now - last_comment_at) <= threshold

    def _evaluate_g3(
        self,
        first_seen_at: datetime,
        last_comment_at: datetime | None,
        now: datetime,
    ) -> bool:
        """G3: Response within threshold hours of first seeing ticket.

        Args:
            first_seen_at: When ticket was first seen.
            last_comment_at: Timestamp of last comment.
            now: Current timestamp.

        Returns:
            True if response was made within threshold or deadline not passed.
        """
        threshold = timedelta(hours=self.settings.g3_response_hours)
        deadline = first_seen_at + threshold

        if last_comment_at is not None:
            return last_comment_at <= deadline

        return now <= deadline

    def _evaluate_g4(
        self,
        first_seen_at: datetime,
        jira_status: str,
        now: datetime,
    ) -> bool:
        """G4: Resolution within threshold hours or status indicates progress.

        Args:
            first_seen_at: When ticket was first seen.
            jira_status: Current Jira status.
            now: Current timestamp.

        Returns:
            True if ticket is resolved or within resolution threshold.
        """
        resolved_statuses = {"Resolved", "Closed", "Done", "Complete"}

        if jira_status in resolved_statuses:
            return True

        threshold = timedelta(hours=self.settings.g4_resolution_hours)
        return (now - first_seen_at) <= threshold
