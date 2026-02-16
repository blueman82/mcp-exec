"""Tests for PAT collection flow in SlackService."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from bravo.config import SlackSettings
from bravo.services.slack import SlackService


def _make_settings() -> SlackSettings:
    """Create SlackSettings with test defaults."""
    return SlackSettings(
        bot_token="xoxb-test",
        app_token="xapp-test",
    )


def _make_service(
    *, pat_service: AsyncMock | None = None,
) -> tuple[SlackService, AsyncMock]:
    """Create SlackService with mocked Jira client and optional pat_service.

    Returns:
        Tuple of (service, mock_jira).
    """
    mock_jira = AsyncMock()
    mock_jira.test_auth = AsyncMock(return_value=True)
    service = SlackService(_make_settings(), mock_jira, pat_service)
    # Stub out the web client so open_modal works
    mock_web = AsyncMock()
    mock_web.views_open.return_value = {"ok": True}
    service._web_client = mock_web
    return service, mock_jira


def _fix_now_payload(ticket_key: str = "TEST-1") -> tuple[dict, dict]:
    """Build a minimal block_actions payload for nudge_fix_now.

    Returns:
        Tuple of (payload, action).
    """
    payload = {
        "trigger_id": "T123",
        "user": {"id": "U456"},
        "channel": {"id": "C789"},
        "message": {
            "ts": "1234567890.123456",
            "blocks": [{"type": "header"}, {"type": "actions"}],
        },
    }
    action = {"action_id": "nudge_fix_now", "value": ticket_key}
    return payload, action


def _yes_updates_payload(ticket_key: str = "TEST-1") -> tuple[dict, dict]:
    """Build a minimal block_actions payload for nudge_yes_updates.

    Returns:
        Tuple of (payload, action).
    """
    payload = {
        "trigger_id": "T123",
        "user": {"id": "U456"},
        "channel": {"id": "C789"},
        "message": {
            "ts": "1234567890.123456",
            "blocks": [{"type": "header"}, {"type": "actions"}],
        },
    }
    action = {"action_id": "nudge_yes_updates", "value": ticket_key}
    return payload, action


CURRENT_FIELDS = {
    "summary": "Test ticket",
    "description": "",
    "priority": "",
    "components": [],
}


class TestPATGateInFixNow:
    """Tests for PAT check gating in _handle_nudge_fix_now."""

    async def test_fix_now_opens_pat_modal_when_no_pat(self) -> None:
        mock_pat = AsyncMock()
        mock_pat.has_pat.return_value = False
        service, mock_jira = _make_service(pat_service=mock_pat)
        mock_jira.get_ticket_fields.return_value = CURRENT_FIELDS
        payload, action = _fix_now_payload()

        await service._handle_nudge_fix_now(payload, action)

        mock_pat.has_pat.assert_awaited_once_with("U456")
        web = service._web_client
        web.views_open.assert_awaited_once()
        view = web.views_open.call_args.kwargs["view"]
        assert view["callback_id"] == "collect_pat_modal"

    async def test_fix_now_opens_fix_modal_when_pat_exists(self) -> None:
        mock_pat = AsyncMock()
        mock_pat.has_pat.return_value = True
        service, mock_jira = _make_service(pat_service=mock_pat)
        mock_jira.get_ticket_fields.return_value = CURRENT_FIELDS
        payload, action = _fix_now_payload()

        await service._handle_nudge_fix_now(payload, action)

        web = service._web_client
        web.views_open.assert_awaited_once()
        view = web.views_open.call_args.kwargs["view"]
        assert view["callback_id"] == "fix_now_modal"

    async def test_fix_now_skips_pat_check_when_no_pat_service(self) -> None:
        service, mock_jira = _make_service(pat_service=None)
        mock_jira.get_ticket_fields.return_value = CURRENT_FIELDS
        payload, action = _fix_now_payload()

        await service._handle_nudge_fix_now(payload, action)

        web = service._web_client
        web.views_open.assert_awaited_once()
        view = web.views_open.call_args.kwargs["view"]
        assert view["callback_id"] == "fix_now_modal"

    async def test_collect_pat_metadata_carries_context(self) -> None:
        mock_pat = AsyncMock()
        mock_pat.has_pat.return_value = False
        service, mock_jira = _make_service(pat_service=mock_pat)
        mock_jira.get_ticket_fields.return_value = CURRENT_FIELDS
        payload, action = _fix_now_payload("CPGNCX-999")

        await service._handle_nudge_fix_now(payload, action)

        web = service._web_client
        view = web.views_open.call_args.kwargs["view"]
        metadata = json.loads(view["private_metadata"])
        assert metadata["ticket_key"] == "CPGNCX-999"
        assert metadata["channel"] == "C789"
        assert metadata["ts"] == "1234567890.123456"
        assert metadata["current_fields"] == CURRENT_FIELDS
        assert metadata["original_action"] == "fix_now"


class TestPATGateInYesUpdates:
    """Tests for PAT check gating in _handle_nudge_yes_updates."""

    async def test_yes_updates_opens_pat_modal_when_no_pat(self) -> None:
        mock_pat = AsyncMock()
        mock_pat.has_pat.return_value = False
        service, mock_jira = _make_service(pat_service=mock_pat)
        payload, action = _yes_updates_payload()

        await service._handle_nudge_yes_updates(payload, action)

        mock_pat.has_pat.assert_awaited_once_with("U456")
        web = service._web_client
        web.views_open.assert_awaited_once()
        view = web.views_open.call_args.kwargs["view"]
        assert view["callback_id"] == "collect_pat_modal"
        metadata = json.loads(view["private_metadata"])
        assert metadata["original_action"] == "yes_updates"
        assert metadata["ticket_key"] == "TEST-1"

    async def test_yes_updates_proceeds_when_pat_exists(self) -> None:
        mock_pat = AsyncMock()
        mock_pat.has_pat.return_value = True
        service, mock_jira = _make_service(pat_service=mock_pat)
        payload, action = _yes_updates_payload()

        await service._handle_nudge_yes_updates(payload, action)

        # Should open comment modal when PAT exists
        web = service._web_client
        web.views_open.assert_awaited_once()
        view = web.views_open.call_args.kwargs["view"]
        assert view["callback_id"] == "comment_modal"

    async def test_yes_updates_skips_pat_check_when_no_pat_service(self) -> None:
        service, mock_jira = _make_service(pat_service=None)
        service._complete_yes_updates = AsyncMock()
        payload, action = _yes_updates_payload()

        await service._handle_nudge_yes_updates(payload, action)

        web = service._web_client
        web.views_open.assert_not_awaited()
        service._complete_yes_updates.assert_awaited_once()


class TestCollectPATSubmission:
    """Tests for _handle_collect_pat_submission handler."""

    def _submission_payload(
        self,
        pat_value: str = "ATATT3x_test_token",
        ticket_key: str = "TEST-1",
    ) -> dict:
        """Build a minimal collect_pat_modal view_submission payload."""
        return {
            "user": {"id": "U456"},
            "view": {
                "callback_id": "collect_pat_modal",
                "private_metadata": json.dumps({
                    "original_action": "fix_now",
                    "ticket_key": ticket_key,
                    "channel": "C789",
                    "ts": "1234567890.123456",
                    "current_fields": CURRENT_FIELDS,
                }),
                "state": {
                    "values": {
                        "pat_input_block": {
                            "pat_value": {"value": pat_value},
                        },
                    },
                },
            },
        }

    async def test_collect_pat_submission_stores_and_transitions(self) -> None:
        mock_pat = AsyncMock()
        service, mock_jira = _make_service(pat_service=mock_pat)
        mock_client = AsyncMock()
        mock_req = AsyncMock()
        mock_req.envelope_id = "env-123"

        payload = self._submission_payload()
        await service._handle_collect_pat_submission(
            payload, mock_client, mock_req,
        )

        mock_jira.test_auth.assert_awaited_once_with(user_pat="ATATT3x_test_token")
        mock_pat.store_pat.assert_awaited_once_with("U456", "ATATT3x_test_token")
        # Should send response_action: update with fix_now_modal
        mock_client.send_socket_mode_response.assert_awaited_once()
        response = mock_client.send_socket_mode_response.call_args[0][0]
        assert response.payload["response_action"] == "update"
        assert response.payload["view"]["callback_id"] == "fix_now_modal"

    async def test_collect_pat_yes_updates_closes_and_completes(self) -> None:
        mock_pat = AsyncMock()
        service, mock_jira = _make_service(pat_service=mock_pat)
        mock_jira.test_auth = AsyncMock(return_value=True)
        mock_client = AsyncMock()
        mock_req = AsyncMock()
        mock_req.envelope_id = "env-123"

        payload = {
            "user": {"id": "U456"},
            "view": {
                "callback_id": "collect_pat_modal",
                "private_metadata": json.dumps({
                    "original_action": "yes_updates",
                    "ticket_key": "TEST-1",
                    "channel": "C789",
                    "ts": "1234567890.123456",
                }),
                "state": {
                    "values": {
                        "pat_input_block": {
                            "pat_value": {"value": "ATATT3x_test_token"},
                        },
                    },
                },
            },
        }
        await service._handle_collect_pat_submission(
            payload, mock_client, mock_req,
        )

        mock_jira.test_auth.assert_awaited_once_with(user_pat="ATATT3x_test_token")
        mock_pat.store_pat.assert_awaited_once_with("U456", "ATATT3x_test_token")
        # Should transition to comment_modal
        mock_client.send_socket_mode_response.assert_awaited_once()
        response = mock_client.send_socket_mode_response.call_args[0][0]
        assert response.payload["response_action"] == "update"
        assert response.payload["view"]["callback_id"] == "comment_modal"

    async def test_collect_pat_submission_empty_returns_error(self) -> None:
        mock_pat = AsyncMock()
        service, _ = _make_service(pat_service=mock_pat)
        mock_client = AsyncMock()
        mock_req = AsyncMock()
        mock_req.envelope_id = "env-123"

        payload = self._submission_payload(pat_value="")
        await service._handle_collect_pat_submission(
            payload, mock_client, mock_req,
        )

        mock_pat.store_pat.assert_not_awaited()
        response = mock_client.send_socket_mode_response.call_args[0][0]
        assert response.payload["response_action"] == "errors"
        assert "pat_input_block" in response.payload["errors"]

    async def test_collect_pat_invalid_shows_error_modal(self) -> None:
        mock_pat = AsyncMock()
        service, mock_jira = _make_service(pat_service=mock_pat)
        mock_jira.test_auth = AsyncMock(return_value=False)
        mock_client = AsyncMock()
        mock_req = AsyncMock()
        mock_req.envelope_id = "env-123"

        payload = self._submission_payload()
        await service._handle_collect_pat_submission(
            payload, mock_client, mock_req,
        )

        mock_pat.store_pat.assert_not_awaited()
        mock_jira.test_auth.assert_awaited_once()
        response = mock_client.send_socket_mode_response.call_args[0][0]
        assert response.payload["response_action"] == "update"
        assert response.payload["view"]["callback_id"] == "collect_pat_modal"

    async def test_collect_pat_strips_whitespace(self) -> None:
        mock_pat = AsyncMock()
        service, mock_jira = _make_service(pat_service=mock_pat)
        mock_jira.test_auth = AsyncMock(return_value=True)
        mock_client = AsyncMock()
        mock_req = AsyncMock()
        mock_req.envelope_id = "env-123"

        payload = self._submission_payload(pat_value="  ATATT3x_test_token  ")
        await service._handle_collect_pat_submission(
            payload, mock_client, mock_req,
        )

        mock_jira.test_auth.assert_awaited_once_with(user_pat="ATATT3x_test_token")
        mock_pat.store_pat.assert_awaited_once_with("U456", "ATATT3x_test_token")

    async def test_collect_pat_store_after_validate(self) -> None:
        """PAT is stored only after successful validation."""
        mock_pat = AsyncMock()
        service, mock_jira = _make_service(pat_service=mock_pat)

        call_order = []
        async def track_test_auth(**kwargs):
            call_order.append("test_auth")
            return True
        async def track_store_pat(uid, pat):
            call_order.append("store_pat")

        mock_jira.test_auth = AsyncMock(side_effect=track_test_auth)
        mock_pat.store_pat = AsyncMock(side_effect=track_store_pat)
        mock_client = AsyncMock()
        mock_req = AsyncMock()
        mock_req.envelope_id = "env-123"

        payload = self._submission_payload()
        await service._handle_collect_pat_submission(
            payload, mock_client, mock_req,
        )

        assert call_order == ["test_auth", "store_pat"]
