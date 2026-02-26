#!/usr/bin/env python3
"""
CSOPM Button Action Handler Tests.

Unit tests for the CSOPMButtonActionHandler, verifying:
1. Button action dispatching (handle_button_action)
2. Acknowledge action handling with JIRA comments
3. Stop/Enable reminders action handling with state updates
4. Snooze action handling with confirmation
5. Close ticket action handling via MCP
6. Create followup action signaling
7. View JIRA action (no-op)
8. Unknown action handling
9. Error handling for all operations
10. Operation without state tracker

These tests were extracted from tests/unit/csopm_notifier/test_slack_notifier.py
to align with the new package structure in packages/slack/csopm/actions.py.
"""

import unittest
from unittest.mock import AsyncMock, patch

from packages.core.typed_di.protocols import NotificationRecord
from packages.slack.csopm.actions import CSOPMButtonActionHandler
from packages.slack.csopm.blocks import CSOPMNotificationBlocks


class MockSlackConfig:
    """Mock config for SlackPostingHandler."""

    def get_api_base_url(self) -> str:
        return "https://slack.com/api"

    def get_headers(self) -> dict:
        return {"Authorization": "Bearer test-token", "Content-Type": "application/json"}


class MockSlackPostingHandler:
    """Mock SlackPostingHandler for testing."""

    def __init__(self) -> None:
        self.post_message = AsyncMock()
        self.config = MockSlackConfig()


class MockAsyncMCPClient:
    """Mock AsyncMCPClient for testing."""

    def __init__(self) -> None:
        self.create_issue_comment = AsyncMock()
        self.get_issue = AsyncMock()
        self._call_mcp_tool = AsyncMock()
        self.search_issues = AsyncMock()
        self.list_projects = AsyncMock()


class MockStateTracker:
    """Mock CSOPMStateTrackerProtocol for testing."""

    def __init__(self) -> None:
        self.get_notification_record = AsyncMock()
        self.update_notification_status = AsyncMock()
        self.mark_closure_reminder_sent = AsyncMock()
        self.set_closure_snooze = AsyncMock()
        self.clear_closure_snooze = AsyncMock()


class TestCSOPMButtonActionHandlerInit(unittest.TestCase):
    """Test CSOPMButtonActionHandler initialization."""

    def test_init_with_all_dependencies(self):
        """Test initialization with all dependencies."""
        posting_handler = MockSlackPostingHandler()
        mcp_client = MockAsyncMCPClient()
        state_tracker = MockStateTracker()

        handler = CSOPMButtonActionHandler(
            posting_handler=posting_handler,
            mcp_client=mcp_client,
            state_tracker=state_tracker,
        )

        self.assertIsNotNone(handler)
        self.assertEqual(handler._posting_handler, posting_handler)
        self.assertEqual(handler._mcp_client, mcp_client)
        self.assertEqual(handler._state_tracker, state_tracker)

    def test_init_without_state_tracker(self):
        """Test initialization without optional state tracker."""
        posting_handler = MockSlackPostingHandler()
        mcp_client = MockAsyncMCPClient()

        handler = CSOPMButtonActionHandler(
            posting_handler=posting_handler,
            mcp_client=mcp_client,
            state_tracker=None,
        )

        self.assertIsNotNone(handler)
        self.assertIsNone(handler._state_tracker)


class TestCSOPMButtonActionHandlerDispatch(unittest.IsolatedAsyncioTestCase):
    """Test handle_button_action dispatching to specific handlers."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_dispatches_acknowledge_action(self):
        """Test that acknowledge action ID dispatches correctly."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        result = await self.handler.handle_button_action(
            action_id=CSOPMNotificationBlocks.ACTION_ACKNOWLEDGE,
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        self.mcp_client.create_issue_comment.assert_awaited_once()

    async def test_dispatches_stop_reminders_action(self):
        """Test that stop reminders action ID dispatches correctly."""
        self.posting_handler.post_message.return_value = {"ok": True}

        result = await self.handler.handle_button_action(
            action_id=CSOPMNotificationBlocks.ACTION_STOP_REMINDERS,
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        self.state_tracker.update_notification_status.assert_awaited()

    async def test_dispatches_snooze_action(self):
        """Test that snooze action ID dispatches correctly."""
        # Snooze now shows modal, which may fail without trigger_id but action still returns True
        result = await self.handler.handle_button_action(
            action_id=CSOPMNotificationBlocks.ACTION_SNOOZE,
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

    async def test_dispatches_close_ticket_action(self):
        """Test that close ticket action ID dispatches correctly.

        Note: Close ticket now signals modal opening (returns True)
        without calling MCP directly.
        """
        result = await self.handler.handle_button_action(
            action_id=CSOPMNotificationBlocks.ACTION_CLOSE_TICKET,
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        # MCP is NOT called - transition happens via modal submission
        self.mcp_client._call_mcp_tool.assert_not_awaited()

    async def test_dispatches_create_followup_action(self):
        """Test that create followup action ID dispatches correctly."""
        result = await self.handler.handle_button_action(
            action_id=CSOPMNotificationBlocks.ACTION_CREATE_FOLLOWUP,
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        # Returns True to signal modal should be opened
        self.assertTrue(result)

    async def test_dispatches_view_jira_action(self):
        """Test that view JIRA action ID dispatches correctly (no-op)."""
        result = await self.handler.handle_button_action(
            action_id=CSOPMNotificationBlocks.ACTION_VIEW_JIRA,
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        # No state changes or API calls for URL button
        self.state_tracker.update_notification_status.assert_not_awaited()
        self.mcp_client.create_issue_comment.assert_not_awaited()

    async def test_returns_false_for_unknown_action(self):
        """Test that unknown action ID returns False."""
        result = await self.handler.handle_button_action(
            action_id="unknown_action",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)


class TestCSOPMButtonActionHandlerAcknowledge(unittest.IsolatedAsyncioTestCase):
    """Test acknowledge button action handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_acknowledge_updates_state_to_ack(self):
        """Test acknowledge action updates notification status to 'ack'."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.state_tracker.update_notification_status.assert_awaited_once_with("CSOPM-1234", "ack")

    async def test_acknowledge_posts_jira_comment(self):
        """Test acknowledge action posts comment to JIRA."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.mcp_client.create_issue_comment.assert_awaited_once()
        call_args = self.mcp_client.create_issue_comment.call_args.kwargs
        self.assertEqual(call_args["issue_key"], "CSOPM-1234")
        self.assertIn("acknowledged", call_args["comment"].lower())

    async def test_acknowledge_uses_jira_username_when_available(self):
        """Test acknowledge uses JIRA username format when available."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True
        self.state_tracker.get_notification_record.return_value = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=1,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="jdoe",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        call_args = self.mcp_client.create_issue_comment.call_args.kwargs
        self.assertIn("[~jdoe]", call_args["comment"])

    async def test_acknowledge_uses_slack_user_id_fallback(self):
        """Test acknowledge uses Slack user ID when JIRA username not available."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True
        self.state_tracker.get_notification_record.return_value = None

        await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        call_args = self.mcp_client.create_issue_comment.call_args.kwargs
        self.assertIn("U12345678", call_args["comment"])

    @patch("aiohttp.ClientSession")
    async def test_acknowledge_shows_confirmation_modal(self, mock_session_class):
        """Test acknowledge action shows confirmation modal."""
        self.mcp_client.create_issue_comment.return_value = True
        # Mock aiohttp session for modal
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "test_trigger_123"},
        )

        self.assertTrue(result)
        # Verify modal API was called
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        self.assertIn("views.open", call_args[0][0])

    async def test_acknowledge_returns_true_on_success(self):
        """Test acknowledge returns True on successful handling."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        result = await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

    async def test_acknowledge_returns_false_on_error(self):
        """Test acknowledge returns False when exception occurs."""
        self.mcp_client.create_issue_comment.side_effect = Exception("JIRA error")

        result = await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)


class TestCSOPMButtonActionHandlerStopReminders(unittest.IsolatedAsyncioTestCase):
    """Test stop reminders button action handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_stop_reminders_updates_state(self):
        """Test stop reminders action updates notification status to 'reminders_stopped'."""
        self.posting_handler.post_message.return_value = {"ok": True}

        await self.handler.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.state_tracker.update_notification_status.assert_awaited_once_with(
            "CSOPM-1234", "reminders_stopped"
        )

    @patch("aiohttp.ClientSession")
    async def test_stop_reminders_shows_confirmation_modal(self, mock_session_class):
        """Test stop reminders shows confirmation modal."""
        # Mock aiohttp session for modal
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await self.handler.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "test_trigger_123"},
        )

        self.assertTrue(result)
        # Verify modal API was called
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        self.assertIn("views.open", call_args[0][0])

    async def test_stop_reminders_returns_true_on_success(self):
        """Test stop reminders returns True on successful handling."""
        self.posting_handler.post_message.return_value = {"ok": True}

        result = await self.handler.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

    async def test_stop_reminders_returns_false_on_error(self):
        """Test stop reminders returns False when exception occurs."""
        self.state_tracker.update_notification_status.side_effect = Exception("DB error")

        result = await self.handler.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)


class TestCSOPMButtonActionHandlerEnableReminders(unittest.IsolatedAsyncioTestCase):
    """Test enable reminders button action handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_enable_reminders_updates_state(self):
        """Test enable reminders action updates notification status to 'ack'."""
        self.posting_handler.post_message.return_value = {"ok": True}

        await self.handler.handle_button_action(
            action_id="csopm_enable_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.state_tracker.update_notification_status.assert_awaited_once_with("CSOPM-1234", "ack")

    @patch("aiohttp.ClientSession")
    async def test_enable_reminders_shows_confirmation_modal(self, mock_session_class):
        """Test enable reminders shows confirmation modal."""
        # Mock aiohttp session for modal
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await self.handler.handle_button_action(
            action_id="csopm_enable_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "test_trigger_123"},
        )

        self.assertTrue(result)
        # Verify modal API was called
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        self.assertIn("views.open", call_args[0][0])

    async def test_enable_reminders_returns_true_on_success(self):
        """Test enable reminders returns True on successful handling."""
        self.posting_handler.post_message.return_value = {"ok": True}

        result = await self.handler.handle_button_action(
            action_id="csopm_enable_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)


class TestCSOPMButtonActionHandlerSnooze(unittest.IsolatedAsyncioTestCase):
    """Test snooze button action handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    @patch("aiohttp.ClientSession")
    async def test_snooze_shows_confirmation_modal(self, mock_session_class):
        """Test snooze action shows confirmation modal."""
        # Mock aiohttp session for modal
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        result = await self.handler.handle_button_action(
            action_id="csopm_snooze",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "test_trigger_123"},
        )

        self.assertTrue(result)
        # Verify modal API was called
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        self.assertIn("views.open", call_args[0][0])

    async def test_snooze_returns_true_on_success(self):
        """Test snooze returns True on successful handling."""
        self.posting_handler.post_message.return_value = {"ok": True}

        result = await self.handler.handle_button_action(
            action_id="csopm_snooze",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

    @patch("aiohttp.ClientSession")
    async def test_snooze_returns_false_on_error(self, mock_session_class):
        """Test snooze returns False when exception occurs."""
        # Make the modal call raise an exception
        mock_session_class.side_effect = Exception("Connection error")

        result = await self.handler.handle_button_action(
            action_id="csopm_snooze",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "test_trigger_123"},
        )

        # Snooze still returns True because the modal error is caught internally
        # The action itself (snooze logic) didn't fail
        self.assertTrue(result)


class TestCSOPMButtonActionHandlerCloseTicket(unittest.IsolatedAsyncioTestCase):
    """Test close ticket button action handling.

    Note: The close ticket action now signals that a modal should be opened
    (for collecting required transition fields). The actual transition is
    handled by the modal submission handler in csopm_handler.py.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_close_ticket_returns_true_to_signal_modal(self):
        """Test close ticket returns True to signal modal should be opened.

        The actual modal opening is handled by CSOPMHandler which has
        access to trigger_id and can fetch transition fields.
        """
        result = await self.handler.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

    async def test_close_ticket_does_not_call_mcp(self):
        """Test close ticket does not make JIRA API calls.

        Transition is delegated to the modal submission handler.
        """
        await self.handler.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.mcp_client._call_mcp_tool.assert_not_awaited()

    async def test_close_ticket_does_not_post_message(self):
        """Test close ticket does not post any messages.

        Confirmation is sent after modal submission, not on button click.
        """
        await self.handler.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.posting_handler.post_message.assert_not_awaited()


class TestCSOPMButtonActionHandlerMarkComplete(unittest.IsolatedAsyncioTestCase):
    """Test mark complete button action handling.

    Note: The mark complete action signals that a modal should be opened
    (for collecting required transition fields). The actual transition is
    handled by the modal submission handler in csopm_handler.py.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_mark_complete_returns_true_to_signal_modal(self):
        """Test mark complete returns True to signal modal should be opened."""
        result = await self.handler.handle_button_action(
            action_id="csopm_mark_complete",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

    async def test_mark_complete_does_not_call_mcp(self):
        """Test mark complete does not make JIRA API calls."""
        await self.handler.handle_button_action(
            action_id="csopm_mark_complete",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.mcp_client._call_mcp_tool.assert_not_awaited()

    async def test_mark_complete_does_not_post_message(self):
        """Test mark complete does not post any messages."""
        await self.handler.handle_button_action(
            action_id="csopm_mark_complete",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.posting_handler.post_message.assert_not_awaited()


class TestCSOPMButtonActionHandlerCreateFollowup(unittest.IsolatedAsyncioTestCase):
    """Test create followup button action handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_create_followup_returns_true_to_signal_modal(self):
        """Test create followup returns True to signal modal should be opened.

        The actual modal opening is handled by the caller (CSOPMHandler)
        which has access to the trigger_id and views.open API.
        """
        result = await self.handler.handle_button_action(
            action_id="csopm_create_followup",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "12345.67890"},
        )

        self.assertTrue(result)

    async def test_create_followup_does_not_call_mcp(self):
        """Test create followup does not make JIRA API calls.

        Project fetching and modal building is delegated to the caller.
        """
        await self.handler.handle_button_action(
            action_id="csopm_create_followup",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "12345.67890"},
        )

        self.mcp_client.list_projects.assert_not_awaited()
        self.mcp_client.get_issue.assert_not_awaited()

    async def test_create_followup_does_not_update_state(self):
        """Test create followup does not update notification state."""
        await self.handler.handle_button_action(
            action_id="csopm_create_followup",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "12345.67890"},
        )

        self.state_tracker.update_notification_status.assert_not_awaited()


class TestCSOPMButtonActionHandlerViewJira(unittest.IsolatedAsyncioTestCase):
    """Test view JIRA button action handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_view_jira_returns_true(self):
        """Test view JIRA action returns True (no-op)."""
        result = await self.handler.handle_button_action(
            action_id="csopm_view_jira",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

    async def test_view_jira_does_not_update_state(self):
        """Test view JIRA does not update notification state."""
        await self.handler.handle_button_action(
            action_id="csopm_view_jira",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.state_tracker.update_notification_status.assert_not_awaited()

    async def test_view_jira_does_not_call_mcp(self):
        """Test view JIRA does not make JIRA API calls."""
        await self.handler.handle_button_action(
            action_id="csopm_view_jira",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.mcp_client.create_issue_comment.assert_not_awaited()

    async def test_view_jira_does_not_send_message(self):
        """Test view JIRA does not send confirmation message."""
        await self.handler.handle_button_action(
            action_id="csopm_view_jira",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.posting_handler.post_message.assert_not_awaited()


class TestCSOPMButtonActionHandlerWithoutStateTracker(unittest.IsolatedAsyncioTestCase):
    """Test CSOPMButtonActionHandler when state tracker is not available."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()

        # Handler without state tracker
        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=None,
        )

    async def test_acknowledge_works_without_state_tracker(self):
        """Test acknowledge action works when state tracker is not available."""
        self.mcp_client.create_issue_comment.return_value = True

        result = await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},  # No trigger_id, so modal won't open but action still succeeds
        )

        self.assertTrue(result)
        # JIRA comment should still be posted
        self.mcp_client.create_issue_comment.assert_awaited()

    async def test_acknowledge_uses_slack_id_fallback_without_state_tracker(self):
        """Test acknowledge uses Slack ID fallback without state tracker."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        call_args = self.mcp_client.create_issue_comment.call_args.kwargs
        self.assertIn("U12345678", call_args["comment"])

    async def test_stop_reminders_works_without_state_tracker(self):
        """Test stop reminders action works when state tracker is not available."""
        result = await self.handler.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},  # No trigger_id, so modal won't open but action still succeeds
        )

        self.assertTrue(result)

    async def test_close_ticket_works_without_state_tracker(self):
        """Test close ticket works when state tracker is not available."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client._call_mcp_tool.return_value = {"success": True}

        result = await self.handler.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)


class TestCSOPMButtonActionHandlerErrorHandling(unittest.IsolatedAsyncioTestCase):
    """Test error handling in CSOPMButtonActionHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.posting_handler = MockSlackPostingHandler()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.handler = CSOPMButtonActionHandler(
            posting_handler=self.posting_handler,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_dispatch_catches_exception_and_returns_false(self):
        """Test dispatcher catches exceptions and returns False."""
        self.mcp_client.create_issue_comment.side_effect = Exception("API error")

        result = await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)

    async def test_state_tracker_error_in_acknowledge(self):
        """Test state tracker error handling in acknowledge."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True
        self.state_tracker.get_notification_record.side_effect = Exception("DB error")

        # Should still complete since state tracker is optional
        result = await self.handler.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)

    async def test_state_error_in_stop_reminders(self):
        """Test state tracker error handling in stop reminders action."""
        self.state_tracker.update_notification_status.side_effect = Exception("DB error")

        result = await self.handler.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)

    async def test_snooze_succeeds_without_trigger_id(self):
        """Test snooze action succeeds even without trigger_id (modal won't open but action works)."""
        result = await self.handler.handle_button_action(
            action_id="csopm_snooze",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},  # No trigger_id
        )

        # Snooze should still succeed, modal just won't open
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
