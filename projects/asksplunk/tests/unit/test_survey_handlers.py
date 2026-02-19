"""Unit tests for survey Slack handlers and reminder worker.

Tests survey_open, survey_submit, and _survey_reminder_worker.
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from asksplunk.slack.client import SlackClient


class TestHandleSurveyOpen:
    """Test survey_open action handler."""

    def _make_client_with_captured_handlers(self):
        """Create SlackClient capturing registered action/view handlers."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            action_handlers = {}
            view_handlers = {}

            def capture_action(pattern):
                def decorator(func):
                    action_handlers[
                        str(pattern.pattern) if hasattr(pattern, "pattern") else pattern
                    ] = func
                    return func

                return decorator

            def capture_view(pattern):
                def decorator(func):
                    view_handlers[
                        str(pattern.pattern) if hasattr(pattern, "pattern") else pattern
                    ] = func
                    return func

                return decorator

            def capture_event(event_type):
                def decorator(func):
                    return func

                return decorator

            mock_app.event = capture_event
            mock_app.action = capture_action
            mock_app.view = capture_view

            client = SlackClient(bot_token="xoxb-test", app_token="xapp-test")
            return client, action_handlers, view_handlers

    @pytest.mark.asyncio
    async def test_opens_modal(self) -> None:
        """survey_open should call views_open with modal."""
        client, action_handlers, _ = self._make_client_with_captured_handlers()
        client.access_validator = None
        client.survey_manager = AsyncMock()

        handler_key = r"survey_open_.*"
        handler = action_handlers[handler_key]

        mock_ack = AsyncMock()
        mock_client = AsyncMock()
        body = {
            "user": {"id": "W7MGASQ2K"},
            "trigger_id": "trigger123",
            "actions": [{"action_id": "survey_open_survey_2026_q1"}],
        }

        await handler(mock_ack, body, mock_client)

        mock_ack.assert_awaited_once()
        mock_client.views_open.assert_awaited_once()
        call_args = mock_client.views_open.call_args[1]
        assert call_args["trigger_id"] == "trigger123"
        assert call_args["view"]["callback_id"] == "survey_submit_survey_2026_q1"

    @pytest.mark.asyncio
    async def test_auth_check_blocks_unauthorized(self) -> None:
        """survey_open should not open modal for unauthorized users."""
        client, action_handlers, _ = self._make_client_with_captured_handlers()
        client.access_validator = MagicMock()
        client.access_validator.is_authorized = AsyncMock(return_value=False)

        handler = action_handlers[r"survey_open_.*"]

        mock_ack = AsyncMock()
        mock_client = AsyncMock()
        body = {
            "user": {"id": "UNAUTHORIZED"},
            "trigger_id": "trigger123",
            "actions": [{"action_id": "survey_open_survey_2026_q1"}],
        }

        await handler(mock_ack, body, mock_client)

        mock_ack.assert_awaited_once()
        mock_client.views_open.assert_not_awaited()


class TestHandleSurveySubmit:
    """Test survey_submit view handler."""

    def _make_client_with_captured_handlers(self):
        """Create SlackClient capturing registered action/view handlers."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app

            action_handlers = {}
            view_handlers = {}

            def capture_action(pattern):
                def decorator(func):
                    action_handlers[
                        str(pattern.pattern) if hasattr(pattern, "pattern") else pattern
                    ] = func
                    return func

                return decorator

            def capture_view(pattern):
                def decorator(func):
                    view_handlers[
                        str(pattern.pattern) if hasattr(pattern, "pattern") else pattern
                    ] = func
                    return func

                return decorator

            def capture_event(event_type):
                def decorator(func):
                    return func

                return decorator

            mock_app.event = capture_event
            mock_app.action = capture_action
            mock_app.view = capture_view
            mock_app.client = AsyncMock()
            mock_app.client.conversations_open = AsyncMock(
                return_value={"channel": {"id": "D0123"}}
            )
            mock_app.client.chat_postMessage = AsyncMock()

            client = SlackClient(bot_token="xoxb-test", app_token="xapp-test")
            return client, action_handlers, view_handlers

    @pytest.mark.asyncio
    async def test_stores_response_anonymously(self) -> None:
        """survey_submit should store response without user_id."""
        client, _, view_handlers = self._make_client_with_captured_handlers()
        client.access_validator = None
        client.survey_manager = AsyncMock()

        handler = view_handlers[r"survey_submit_.*"]

        view = {
            "callback_id": "survey_submit_survey_2026_q1",
            "state": {
                "values": {
                    "q1_block": {"question_1": {"selected_option": {"value": "Very useful"}}},
                    "q2_block": {"question_2": {"selected_option": {"value": "Usually correct"}}},
                    "q3_block": {"question_3": {"value": "Multi-turn"}},
                    "q4_block": {"question_4": {"value": "Workflow logs"}},
                }
            },
        }
        body = {"user": {"id": "W7MGASQ2K"}}

        mock_ack = AsyncMock()

        await handler(mock_ack, body, view)

        mock_ack.assert_awaited_once()

        # Verify store_response called with answers (no user_id)
        client.survey_manager.store_response.assert_awaited_once()
        call_args = client.survey_manager.store_response.call_args
        assert call_args[0][0] == "survey_2026_q1"
        answers = call_args[0][1]
        assert answers["question_1"] == "Very useful"
        assert answers["question_2"] == "Usually correct"
        assert answers["question_3"] == "Multi-turn"
        assert answers["question_4"] == "Workflow logs"
        assert "user_id" not in answers

        # Verify mark_completed called with user_id
        client.survey_manager.mark_completed.assert_awaited_once_with("survey_2026_q1", "W7MGASQ2K")


class TestSurveyReminderWorker:
    """Test _survey_reminder_worker background task."""

    def _make_client(self):
        """Create SlackClient with mocked AsyncApp."""
        with patch("asksplunk.slack.client.AsyncApp") as MockApp:
            mock_app = Mock()
            mock_app.client = AsyncMock()
            mock_app.client.chat_postMessage = AsyncMock()
            mock_app.event = lambda _: lambda f: f
            mock_app.action = lambda _: lambda f: f
            mock_app.view = lambda _: lambda f: f
            MockApp.return_value = mock_app

            client = SlackClient(bot_token="xoxb-test", app_token="xapp-test")
            return client

    @pytest.mark.asyncio
    async def test_sends_reminders_to_pending_users(self) -> None:
        """Worker should send reminders to pending users."""
        client = self._make_client()
        client.is_running = True

        client.survey_manager = AsyncMock()
        client.survey_manager.get_active_survey_ids = AsyncMock(return_value=["survey_2026_q1"])
        client.survey_manager.get_pending_users = AsyncMock(
            return_value=[
                {
                    "user_id": "W7MGASQ2K",
                    "reminders_sent": 0,
                    "survey_channel_id": "D0123",
                },
            ]
        )
        client.survey_manager.increment_reminder = AsyncMock(return_value=True)

        with patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            with contextlib.suppress(asyncio.CancelledError):
                await client._survey_reminder_worker()

        client.survey_manager.increment_reminder.assert_awaited_once_with(
            "survey_2026_q1", "W7MGASQ2K"
        )
        client.app.client.chat_postMessage.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_cooldown_active(self) -> None:
        """Worker should skip sending when increment_reminder returns False (cooldown)."""
        client = self._make_client()
        client.is_running = True

        client.survey_manager = AsyncMock()
        client.survey_manager.get_active_survey_ids = AsyncMock(return_value=["survey_2026_q1"])
        client.survey_manager.get_pending_users = AsyncMock(
            return_value=[
                {
                    "user_id": "W7MGASQ2K",
                    "reminders_sent": 1,
                    "survey_channel_id": "D0123",
                },
            ]
        )
        client.survey_manager.increment_reminder = AsyncMock(return_value=False)

        with patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [asyncio.CancelledError()]
            with contextlib.suppress(asyncio.CancelledError):
                await client._survey_reminder_worker()

        client.app.client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_failure_isolated(self) -> None:
        """Worker should continue to next user when send fails for one."""
        client = self._make_client()
        client.is_running = True

        client.survey_manager = AsyncMock()
        client.survey_manager.get_active_survey_ids = AsyncMock(return_value=["survey_2026_q1"])
        client.survey_manager.get_pending_users = AsyncMock(
            return_value=[
                {"user_id": "FAIL_USER", "reminders_sent": 0, "survey_channel_id": "D0123"},
                {"user_id": "OK_USER", "reminders_sent": 0, "survey_channel_id": "D0456"},
            ]
        )
        client.survey_manager.increment_reminder = AsyncMock(return_value=True)
        # First call fails, second succeeds
        client.app.client.chat_postMessage = AsyncMock(
            side_effect=[Exception("channel_not_found"), AsyncMock()]
        )

        with patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            with contextlib.suppress(asyncio.CancelledError):
                await client._survey_reminder_worker()

        # Both users should have had increment_reminder called
        assert client.survey_manager.increment_reminder.await_count == 2

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self) -> None:
        """Worker should continue after errors."""
        client = self._make_client()
        client.is_running = True

        client.survey_manager = AsyncMock()
        client.survey_manager.get_active_survey_ids = AsyncMock(
            side_effect=RuntimeError("DynamoDB error")
        )

        with patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [asyncio.CancelledError()]
            with contextlib.suppress(asyncio.CancelledError):
                await client._survey_reminder_worker()

    @pytest.mark.asyncio
    async def test_no_surveys_when_manager_none(self) -> None:
        """Worker should do nothing if survey_manager is None."""
        client = self._make_client()
        client.is_running = True
        client.survey_manager = None

        with patch("asksplunk.slack.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [asyncio.CancelledError()]
            with contextlib.suppress(asyncio.CancelledError):
                await client._survey_reminder_worker()
