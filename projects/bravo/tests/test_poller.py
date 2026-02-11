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
) -> tuple[PollerService, AsyncMock, AsyncMock, AsyncMock]:
    """Create a PollerService with mocked dependencies.

    Returns:
        Tuple of (poller, mock_jira, mock_nudge, mock_slack).
    """
    settings = Settings()
    mock_jira = AsyncMock()
    mock_nudge = AsyncMock()
    mock_slack = AsyncMock()

    if nudge_side_effect:
        mock_nudge.evaluate_ticket.side_effect = nudge_side_effect
    elif nudge_results:
        mock_nudge.evaluate_ticket.return_value = nudge_results
    else:
        mock_nudge.evaluate_ticket.return_value = {"should_nudge": False}

    return (
        PollerService(settings, mock_jira, mock_nudge, mock_slack),
        mock_jira,
        mock_nudge,
        mock_slack,
    )


@pytest.fixture()
def _mock_queries():
    """Patch bravo.db.queries used by poller."""
    poll_id = uuid4()
    with patch("bravo.services.poller.queries") as mock_q:
        mock_q.create_poll_history = AsyncMock(return_value={"id": poll_id})
        mock_q.get_poll_state = AsyncMock(return_value=None)
        mock_q.get_ticket = AsyncMock(return_value=None)
        mock_q.upsert_ticket = AsyncMock(return_value={"ticket_key": "TEST-1"})
        mock_q.upsert_assignee = AsyncMock(
            return_value={"jira_id": "user1", "slack_user_id": None}
        )
        mock_q.update_poll_state = AsyncMock()
        mock_q.complete_poll_history = AsyncMock()
        yield mock_q


class TestPollerNudgeWiring:
    """Tests for poller → nudge evaluation wiring."""

    @pytest.mark.usefixtures("_mock_queries")
    async def test_evaluate_called_for_each_ticket(self, _mock_queries):
        tickets = [_make_ticket("TEST-1"), _make_ticket("TEST-2"), _make_ticket("TEST-3")]
        poller, mock_jira, mock_nudge, _ = _make_poller()
        mock_jira.search_tickets.return_value = tickets

        await poller.run_poll()

        assert mock_nudge.evaluate_ticket.call_count == 3
        mock_nudge.evaluate_ticket.assert_any_call("TEST-1")
        mock_nudge.evaluate_ticket.assert_any_call("TEST-2")
        mock_nudge.evaluate_ticket.assert_any_call("TEST-3")

    @pytest.mark.usefixtures("_mock_queries")
    async def test_nudge_triggered_count(self, _mock_queries):
        tickets = [_make_ticket("TEST-1"), _make_ticket("TEST-2")]
        poller, mock_jira, mock_nudge, _ = _make_poller()
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
        poller, mock_jira, mock_nudge, _ = _make_poller()
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
        poller, mock_jira, mock_nudge, _ = _make_poller()
        mock_jira.search_tickets.return_value = []

        result = await poller.run_poll()

        mock_nudge.evaluate_ticket.assert_not_called()
        assert result["tickets_fetched"] == 0

    @pytest.mark.usefixtures("_mock_queries")
    async def test_nudges_triggered_in_poll_history(self, _mock_queries):
        tickets = [_make_ticket("TEST-1")]
        poller, mock_jira, mock_nudge, _ = _make_poller(
            nudge_results={"should_nudge": True},
        )
        mock_jira.search_tickets.return_value = tickets

        await poller.run_poll()

        complete_call = _mock_queries.complete_poll_history.call_args
        assert complete_call.kwargs["nudges_triggered"] == 1
        assert complete_call.kwargs["status"] == "completed"


class TestAssigneeAutoRegistration:
    """Tests for automatic assignee registration during polling."""

    @pytest.mark.usefixtures("_mock_queries")
    async def test_assignee_registered_on_poll(self, _mock_queries):
        tickets = [_make_ticket("TEST-1")]
        poller, mock_jira, _, _ = _make_poller()
        mock_jira.search_tickets.return_value = tickets

        await poller.run_poll()

        _mock_queries.upsert_assignee.assert_awaited()
        call_kwargs = _mock_queries.upsert_assignee.call_args_list[0].kwargs
        assert call_kwargs["jira_id"] == "user1"
        assert call_kwargs["display_name"] == "Test User"
        assert call_kwargs["email"] == "user1@adobe.com"

    @pytest.mark.usefixtures("_mock_queries")
    async def test_assignee_slack_lookup_when_missing(self, _mock_queries):
        tickets = [_make_ticket("TEST-1")]
        poller, mock_jira, _, mock_slack = _make_poller()
        mock_jira.search_tickets.return_value = tickets
        _mock_queries.upsert_assignee.return_value = {
            "jira_id": "user1",
            "slack_user_id": None,
        }
        mock_slack.lookup_user_by_email.return_value = SimpleNamespace(
            user_id="U12345",
            email="user1@adobe.com",
            display_name="Test User",
        )

        await poller.run_poll()

        mock_slack.lookup_user_by_email.assert_awaited_once_with("user1@adobe.com")
        assert _mock_queries.upsert_assignee.await_count == 2
        second_call = _mock_queries.upsert_assignee.call_args_list[1].kwargs
        assert second_call["slack_user_id"] == "U12345"

    @pytest.mark.usefixtures("_mock_queries")
    async def test_assignee_slack_lookup_skipped_when_present(self, _mock_queries):
        tickets = [_make_ticket("TEST-1")]
        poller, mock_jira, _, mock_slack = _make_poller()
        mock_jira.search_tickets.return_value = tickets
        _mock_queries.upsert_assignee.return_value = {
            "jira_id": "user1",
            "slack_user_id": "U99999",
        }

        await poller.run_poll()

        mock_slack.lookup_user_by_email.assert_not_awaited()
        assert _mock_queries.upsert_assignee.await_count == 1

    @pytest.mark.usefixtures("_mock_queries")
    async def test_assignee_registration_failure_doesnt_block_poll(self, _mock_queries):
        tickets = [_make_ticket("TEST-1")]
        poller, mock_jira, mock_nudge, _ = _make_poller()
        mock_jira.search_tickets.return_value = tickets
        _mock_queries.upsert_assignee.side_effect = RuntimeError("DB down")

        result = await poller.run_poll()

        mock_nudge.evaluate_ticket.assert_awaited_once_with("TEST-1")
        assert result["tickets_fetched"] == 1

    @pytest.mark.usefixtures("_mock_queries")
    async def test_no_assignee_skips_registration(self, _mock_queries):
        ticket = SimpleNamespace(
            key="TEST-1",
            id="12345",
            project="TEST",
            summary="Unassigned ticket",
            assignee_id=None,
            assignee_name=None,
            status="Open",
        )
        poller, mock_jira, _, mock_slack = _make_poller()
        mock_jira.search_tickets.return_value = [ticket]

        await poller.run_poll()

        _mock_queries.upsert_assignee.assert_not_awaited()
        mock_slack.lookup_user_by_email.assert_not_awaited()
