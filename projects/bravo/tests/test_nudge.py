"""Tests for the nudge orchestration service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from bravo.config import Settings
from bravo.services.gates import GateEvaluation
from bravo.services.llm import LLMScore
from bravo.services.nudge import NudgeService


def _make_settings(**overrides) -> Settings:
    """Create Settings with test defaults."""
    return Settings(**overrides)


def _make_ticket_record(
    ticket_key: str = "TEST-1",
    *,
    assignee_jira_id: str | None = "user1",
    last_assignee_comment_at: datetime | None = None,
    jira_status: str = "Open",
) -> dict:
    """Create a mock ticket database record."""
    return {
        "ticket_key": ticket_key,
        "jira_id": "12345",
        "project": "TEST",
        "summary": "Test ticket summary",
        "assignee_jira_id": assignee_jira_id,
        "assignee_name": "Test User",
        "jira_status": jira_status,
        "first_seen_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_assignee_comment_at": last_assignee_comment_at,
    }


def _make_nudge_service() -> tuple[NudgeService, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    """Create NudgeService with mocked dependencies.

    Returns:
        Tuple of (service, mock_jira, mock_slack, mock_gates, mock_llm).
    """
    settings = _make_settings()
    mock_jira = AsyncMock()
    mock_jira.get_ticket_comments.return_value = []
    mock_slack = AsyncMock()
    mock_gates = MagicMock()
    mock_llm = AsyncMock()
    service = NudgeService(settings, mock_jira, mock_slack, mock_gates, mock_llm)
    return service, mock_jira, mock_slack, mock_gates, mock_llm


@pytest.fixture()
def _mock_queries():
    """Patch bravo.db.queries used by nudge service."""
    with patch("bravo.services.nudge.queries") as mock_q:
        mock_q.has_pending_reeval = AsyncMock(return_value=False)
        mock_q.get_active_snooze_for_ticket = AsyncMock(return_value=None)
        mock_q.get_latest_nudge_for_ticket = AsyncMock(return_value=None)
        mock_q.get_ticket = AsyncMock(return_value=_make_ticket_record())
        mock_q.update_ticket_gates = AsyncMock()
        mock_q.update_ticket_llm_scores = AsyncMock()
        mock_q.get_assignee = AsyncMock(
            return_value={"slack_user_id": "U12345", "jira_id": "user1"}
        )
        mock_q.create_nudge = AsyncMock(return_value={"id": uuid4()})
        mock_q.update_nudge_status = AsyncMock()
        mock_q.increment_assignee_nudge_count = AsyncMock()
        yield mock_q


class TestEvaluateTicket:
    """Tests for NudgeService.evaluate_ticket()."""

    @pytest.mark.usefixtures("_mock_queries")
    async def test_gate_failure_triggers_nudge(self, _mock_queries):
        service, _, mock_slack, mock_gates, _ = _make_nudge_service()
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=False, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_slack.send_dm.return_value = "1234567890.123456"

        result = await service.evaluate_ticket("TEST-1")

        assert result["should_nudge"] is True
        assert "G1" in result["nudge_reason"]
        mock_slack.send_dm.assert_called_once()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_gates_pass_llm_below_threshold_triggers_nudge(self, _mock_queries):
        service, _, mock_slack, mock_gates, mock_llm = _make_nudge_service()
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=1.0, completeness=1.0, root_cause=1.0, actionability=1.0,
        )
        mock_slack.send_dm.return_value = "1234567890.123456"

        result = await service.evaluate_ticket("TEST-1")

        assert result["should_nudge"] is True
        assert "LLM score below threshold" in result["nudge_reason"]

    @pytest.mark.usefixtures("_mock_queries")
    async def test_gates_pass_llm_above_threshold_no_nudge(self, _mock_queries):
        service, _, mock_slack, mock_gates, mock_llm = _make_nudge_service()
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=5.0, completeness=5.0, root_cause=5.0, actionability=5.0,
        )

        result = await service.evaluate_ticket("TEST-1")

        assert result["should_nudge"] is False
        mock_slack.send_dm.assert_not_called()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_cooldown_skips_evaluation(self, _mock_queries):
        service, _, mock_slack, mock_gates, _ = _make_nudge_service()
        _mock_queries.get_latest_nudge_for_ticket.return_value = {
            "created_at": datetime.now(UTC) - timedelta(hours=1),
            "status": "SENT",
        }

        result = await service.evaluate_ticket("TEST-1")

        assert result["should_nudge"] is False
        assert result["nudge_reason"] == "cooldown"
        mock_gates.evaluate.assert_not_called()
        mock_slack.send_dm.assert_not_called()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_cooldown_expired_allows_evaluation(self, _mock_queries):
        service, _, mock_slack, mock_gates, mock_llm = _make_nudge_service()
        _mock_queries.get_latest_nudge_for_ticket.return_value = {
            "created_at": datetime.now(UTC) - timedelta(hours=25),
            "status": "SENT",
        }
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=5.0, completeness=5.0, root_cause=5.0, actionability=5.0,
        )

        result = await service.evaluate_ticket("TEST-1")

        mock_gates.evaluate.assert_called_once()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_active_snooze_skips_evaluation(self, _mock_queries):
        service, _, mock_slack, mock_gates, _ = _make_nudge_service()
        _mock_queries.get_active_snooze_for_ticket.return_value = {
            "snoozed_until": datetime(2099, 1, 1, tzinfo=UTC),
            "status": "SNOOZED",
        }

        result = await service.evaluate_ticket("TEST-1")

        assert result["should_nudge"] is False
        assert result["nudge_reason"] == "snoozed"
        mock_gates.evaluate.assert_not_called()
        mock_slack.send_dm.assert_not_called()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_expired_snooze_allows_evaluation(self, _mock_queries):
        service, _, mock_slack, mock_gates, mock_llm = _make_nudge_service()
        _mock_queries.get_active_snooze_for_ticket.return_value = None
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=5.0, completeness=5.0, root_cause=5.0, actionability=5.0,
        )

        result = await service.evaluate_ticket("TEST-1")

        mock_gates.evaluate.assert_called_once()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_ticket_not_found_raises(self, _mock_queries):
        service, _, _, _, _ = _make_nudge_service()
        _mock_queries.get_ticket.return_value = None

        with pytest.raises(ValueError, match="Ticket not found"):
            await service.evaluate_ticket("MISSING-1")

    @pytest.mark.usefixtures("_mock_queries")
    async def test_comments_fetched_and_passed_to_llm(self, _mock_queries):
        service, mock_jira, _, mock_gates, mock_llm = _make_nudge_service()
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_jira.get_ticket_comments.return_value = ["Fix applied", "Verified"]
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=5.0, completeness=5.0, root_cause=5.0, actionability=5.0,
        )

        await service.evaluate_ticket("TEST-1")

        mock_jira.get_ticket_comments.assert_awaited_once_with("TEST-1")
        mock_llm.score_ticket.assert_awaited_once_with(
            ticket_key="TEST-1",
            summary="Test ticket summary",
            comments=["Fix applied", "Verified"],
        )

    @pytest.mark.usefixtures("_mock_queries")
    async def test_comment_fetch_failure_falls_back_to_empty(self, _mock_queries):
        service, mock_jira, _, mock_gates, mock_llm = _make_nudge_service()
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_jira.get_ticket_comments.side_effect = RuntimeError("MCP down")
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=5.0, completeness=5.0, root_cause=5.0, actionability=5.0,
        )

        result = await service.evaluate_ticket("TEST-1")

        mock_llm.score_ticket.assert_awaited_once_with(
            ticket_key="TEST-1",
            summary="Test ticket summary",
            comments=[],
        )
        assert result["should_nudge"] is False

    @pytest.mark.usefixtures("_mock_queries")
    async def test_force_bypasses_cooldown(self, _mock_queries):
        service, _, mock_slack, mock_gates, mock_llm = _make_nudge_service()
        _mock_queries.get_latest_nudge_for_ticket.return_value = {
            "created_at": datetime.now(UTC) - timedelta(hours=1),
            "status": "SENT",
        }
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=5.0, completeness=5.0, root_cause=5.0, actionability=5.0,
        )

        result = await service.evaluate_ticket("TEST-1", force=True)

        # Should NOT return cooldown — force bypasses it
        assert result["nudge_reason"] != "cooldown"
        mock_gates.evaluate.assert_called_once()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_force_bypasses_snooze(self, _mock_queries):
        service, _, mock_slack, mock_gates, mock_llm = _make_nudge_service()
        _mock_queries.get_active_snooze_for_ticket.return_value = {
            "snoozed_until": datetime(2099, 1, 1, tzinfo=UTC),
            "status": "SNOOZED",
        }
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=True, g2_passed=True, g3_passed=True, g4_passed=True,
        )
        mock_llm.score_ticket.return_value = LLMScore(
            clarity=5.0, completeness=5.0, root_cause=5.0, actionability=5.0,
        )

        result = await service.evaluate_ticket("TEST-1", force=True)

        # Should NOT return snoozed — force bypasses it
        assert result["nudge_reason"] != "snoozed"
        mock_gates.evaluate.assert_called_once()


class TestSendNudge:
    """Tests for NudgeService._send_nudge() edge cases."""

    @pytest.mark.usefixtures("_mock_queries")
    async def test_no_assignee_skips_nudge(self, _mock_queries):
        service, _, mock_slack, mock_gates, _ = _make_nudge_service()
        _mock_queries.get_ticket.return_value = _make_ticket_record(
            assignee_jira_id=None,
        )
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=False, g2_passed=True, g3_passed=True, g4_passed=True,
        )

        result = await service.evaluate_ticket("TEST-1")

        assert result["should_nudge"] is True
        mock_slack.send_dm.assert_not_called()

    @pytest.mark.usefixtures("_mock_queries")
    async def test_no_slack_user_skips_dm(self, _mock_queries):
        service, _, mock_slack, mock_gates, _ = _make_nudge_service()
        _mock_queries.get_assignee.return_value = {
            "slack_user_id": None, "jira_id": "user1",
        }
        mock_gates.evaluate.return_value = GateEvaluation(
            g1_passed=False, g2_passed=True, g3_passed=True, g4_passed=True,
        )

        result = await service.evaluate_ticket("TEST-1")

        assert result["should_nudge"] is True
        mock_slack.send_dm.assert_not_called()
