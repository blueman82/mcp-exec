"""Tests for the poller service nudge wiring."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from bravo.config import Settings
from bravo.services.poller import PollerService


def _make_ticket(key: str = "TEST-1") -> SimpleNamespace:
    """Create a mock Jira ticket."""
    return SimpleNamespace(
        key=key,
        id="12345",
        project="TEST",
        summary="Test ticket",
        assignee_id="user1",
        assignee_name="Test User",
        status="Open",
    )


def _make_poller(
    *,
    nudge_results: dict | None = None,
    nudge_side_effect: Exception | None = None,
) -> tuple[PollerService, AsyncMock, AsyncMock]:
    """Create a PollerService with mocked dependencies.

    Returns:
        Tuple of (poller, mock_jira, mock_nudge).
    """
    settings = Settings()
    mock_jira = AsyncMock()
    mock_nudge = AsyncMock()

    if nudge_side_effect:
        mock_nudge.evaluate_ticket.side_effect = nudge_side_effect
    elif nudge_results:
        mock_nudge.evaluate_ticket.return_value = nudge_results
    else:
        mock_nudge.evaluate_ticket.return_value = {"should_nudge": False}

    return PollerService(settings, mock_jira, mock_nudge), mock_jira, mock_nudge


@pytest.fixture()
def _mock_queries():
    """Patch bravo.db.queries used by poller."""
    poll_id = uuid4()
    with patch("bravo.services.poller.queries") as mock_q:
        mock_q.create_poll_history = AsyncMock(return_value={"id": poll_id})
        mock_q.get_poll_state = AsyncMock(return_value=None)
        mock_q.get_ticket = AsyncMock(return_value=None)
        mock_q.upsert_ticket = AsyncMock(return_value={"ticket_key": "TEST-1"})
        mock_q.update_poll_state = AsyncMock()
        mock_q.complete_poll_history = AsyncMock()
        yield mock_q


class TestPollerNudgeWiring:
    """Tests for poller → nudge evaluation wiring."""

    @pytest.mark.usefixtures("_mock_queries")
    async def test_evaluate_called_for_each_ticket(self, _mock_queries):
        tickets = [_make_ticket("TEST-1"), _make_ticket("TEST-2"), _make_ticket("TEST-3")]
        poller, mock_jira, mock_nudge = _make_poller()
        mock_jira.search_tickets.return_value = tickets

        await poller.run_poll()

        assert mock_nudge.evaluate_ticket.call_count == 3
        mock_nudge.evaluate_ticket.assert_any_call("TEST-1")
        mock_nudge.evaluate_ticket.assert_any_call("TEST-2")
        mock_nudge.evaluate_ticket.assert_any_call("TEST-3")

    @pytest.mark.usefixtures("_mock_queries")
    async def test_nudge_triggered_count(self, _mock_queries):
        tickets = [_make_ticket("TEST-1"), _make_ticket("TEST-2")]
        poller, mock_jira, mock_nudge = _make_poller()
        mock_jira.search_tickets.return_value = tickets
        mock_nudge.evaluate_ticket.side_effect = [
            {"should_nudge": True},
            {"should_nudge": False},
        ]

        result = await poller.run_poll()

        assert result["nudges_triggered"] == 1

    @pytest.mark.usefixtures("_mock_queries")
    async def test_evaluation_failure_doesnt_abort_poll(self, _mock_queries):
        tickets = [_make_ticket("TEST-1"), _make_ticket("TEST-2")]
        poller, mock_jira, mock_nudge = _make_poller()
        mock_jira.search_tickets.return_value = tickets
        mock_nudge.evaluate_ticket.side_effect = [
            RuntimeError("eval failed"),
            {"should_nudge": True},
        ]

        result = await poller.run_poll()

        assert result["nudges_triggered"] == 1
        assert mock_nudge.evaluate_ticket.call_count == 2

    @pytest.mark.usefixtures("_mock_queries")
    async def test_no_tickets_no_evaluations(self, _mock_queries):
        poller, mock_jira, mock_nudge = _make_poller()
        mock_jira.search_tickets.return_value = []

        result = await poller.run_poll()

        mock_nudge.evaluate_ticket.assert_not_called()
        assert result["tickets_fetched"] == 0

    @pytest.mark.usefixtures("_mock_queries")
    async def test_nudges_triggered_in_poll_history(self, _mock_queries):
        tickets = [_make_ticket("TEST-1")]
        poller, mock_jira, mock_nudge = _make_poller(
            nudge_results={"should_nudge": True},
        )
        mock_jira.search_tickets.return_value = tickets

        await poller.run_poll()

        complete_call = _mock_queries.complete_poll_history.call_args
        assert complete_call.kwargs["nudges_triggered"] == 1
        assert complete_call.kwargs["status"] == "completed"
