"""Tests for the Slack service fix-now submission handler."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bravo.config import SlackSettings
from bravo.services.jira import JiraMCPError
from bravo.services.slack import SlackService


def _make_settings() -> SlackSettings:
    """Create SlackSettings with test defaults."""
    return SlackSettings(
        bot_token="xoxb-test",
        app_token="xapp-test",
    )


def _make_service() -> tuple[SlackService, AsyncMock]:
    """Create SlackService with mocked Jira client.

    Returns:
        Tuple of (service, mock_jira).
    """
    mock_jira = AsyncMock()
    service = SlackService(_make_settings(), mock_jira)
    # Stub out the web client so update_message / _fetch_message_blocks work
    mock_web = AsyncMock()
    mock_web.conversations_history.return_value = {
        "messages": [{"blocks": [{"type": "header"}, {"type": "actions"}]}]
    }
    mock_web.chat_update.return_value = {"ok": True}
    service._web_client = mock_web
    return service, mock_jira


def _submission_payload(
    ticket_key: str = "TEST-1",
    *,
    description: str = "A description",
    priority: str | None = None,
    components: str | None = None,
) -> dict:
    """Build a minimal view_submission payload."""
    values: dict = {}
    if description:
        values["fix_description"] = {
            "description_input": {"value": description}
        }
    if priority:
        values["fix_priority"] = {
            "priority_input": {"selected_option": {"value": priority}}
        }
    if components:
        values["fix_components"] = {
            "components_input": {"value": components}
        }
    return {
        "view": {
            "callback_id": "fix_now_modal",
            "private_metadata": json.dumps({
                "ticket_key": ticket_key,
                "channel": "C123",
                "ts": "1234567890.123456",
            }),
            "state": {"values": values},
        },
    }


@pytest.fixture()
def _mock_queries():
    """Patch bravo.db.queries used by slack service."""
    with patch("bravo.services.slack.queries") as mock_q:
        mock_q.get_nudge_by_slack_ts = AsyncMock(
            return_value={"id": "nudge-1"}
        )
        mock_q.update_nudge_status = AsyncMock()
        yield mock_q


class TestFixNowSubmission:
    """Tests for SlackService._handle_fix_now_submission()."""

    @pytest.mark.usefixtures("_mock_queries")
    async def test_fix_now_submission_success(self, _mock_queries) -> None:
        service, mock_jira = _make_service()

        await service._handle_fix_now_submission(
            _submission_payload(description="New desc", priority="Major"),
        )

        mock_jira.update_issue.assert_awaited_once_with(
            "TEST-1",
            {"description": "New desc", "priority": {"name": "Major"}},
        )
        mock_jira.add_comment.assert_awaited_once()
        _mock_queries.update_nudge_status.assert_awaited_once_with(
            "nudge-1", "RESPONDED",
        )
        # Message updated with success text
        web = service._web_client
        web.chat_update.assert_awaited_once()
        call_kwargs = web.chat_update.call_args.kwargs
        assert "Fixed:" in call_kwargs["text"]
        assert "audit comment failed" not in call_kwargs["text"]

    @pytest.mark.usefixtures("_mock_queries")
    async def test_fix_now_submission_update_fails_mcp_error(
        self, _mock_queries,
    ) -> None:
        service, mock_jira = _make_service()
        mock_jira.update_issue.side_effect = JiraMCPError(
            "Field invalid", tool_name="update_jira_issue",
        )

        await service._handle_fix_now_submission(
            _submission_payload(description="New desc"),
        )

        # Error blocks sent, nudge status NOT updated
        _mock_queries.update_nudge_status.assert_not_awaited()
        web = service._web_client
        web.chat_update.assert_awaited_once()
        call_kwargs = web.chat_update.call_args.kwargs
        assert "Could not update TEST-1" in call_kwargs["text"]

    @pytest.mark.usefixtures("_mock_queries")
    async def test_fix_now_submission_update_fails_timeout(
        self, _mock_queries,
    ) -> None:
        service, mock_jira = _make_service()
        mock_jira.update_issue.side_effect = httpx.ReadTimeout(
            "read timed out",
        )

        await service._handle_fix_now_submission(
            _submission_payload(description="New desc"),
        )

        _mock_queries.update_nudge_status.assert_not_awaited()
        web = service._web_client
        call_kwargs = web.chat_update.call_args.kwargs
        assert "timed out" in call_kwargs["text"]

    @pytest.mark.usefixtures("_mock_queries")
    async def test_fix_now_submission_comment_fails_partial(
        self, _mock_queries,
    ) -> None:
        service, mock_jira = _make_service()
        mock_jira.add_comment.side_effect = RuntimeError("MCP down")

        await service._handle_fix_now_submission(
            _submission_payload(description="New desc"),
        )

        # update_issue succeeded, so nudge status should be RESPONDED
        mock_jira.update_issue.assert_awaited_once()
        _mock_queries.update_nudge_status.assert_awaited_once_with(
            "nudge-1", "RESPONDED",
        )
        # Success text with partial failure note
        web = service._web_client
        call_kwargs = web.chat_update.call_args.kwargs
        assert "audit comment failed" in call_kwargs["text"]

    @pytest.mark.usefixtures("_mock_queries")
    async def test_fix_now_submission_no_fields(self, _mock_queries) -> None:
        service, mock_jira = _make_service()
        # Payload with no field values
        payload = {
            "view": {
                "callback_id": "fix_now_modal",
                "private_metadata": json.dumps({
                    "ticket_key": "TEST-1",
                    "channel": "C123",
                    "ts": "1234567890.123456",
                }),
                "state": {"values": {}},
            },
        }

        await service._handle_fix_now_submission(payload)

        mock_jira.update_issue.assert_not_awaited()
        mock_jira.add_comment.assert_not_awaited()
        _mock_queries.update_nudge_status.assert_not_awaited()
