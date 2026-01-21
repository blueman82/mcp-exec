#!/usr/bin/env python3
"""
CSOPM Slack Notifier Tests.

Unit tests for the CSOPMSlackNotifier service, verifying:
1. Protocol compliance with CSOPMSlackNotifierProtocol
2. Slack user ID resolution from JIRA username
3. Assignment DM sending with Block Kit
4. Reminder DM sending
5. Button action handling (Acknowledge, Create Follow-up, Done, etc.)
6. JIRA comment posting on acknowledgment
7. Error handling for all operations

Edge Cases Covered:
- Empty/invalid JIRA username for resolution
- Email not found in Slack
- DM sending failures
- State tracker unavailable
- JIRA comment posting failures
- Unknown action IDs
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from packages.core.typed_di.protocols import (
    CSOPMSlackNotifierProtocol,
    CSOPMTicket,
    NotificationRecord,
)


class MockSlackPostingHandler:
    """Mock SlackPostingHandler for testing."""

    def __init__(self) -> None:
        self.post_message = AsyncMock()


class MockSlackUserOps:
    """Mock SlackUserOps for testing."""

    def __init__(self) -> None:
        self.get_slack_id_by_email = AsyncMock()


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


class MockMetrics:
    """Mock CSOPMMetricsProtocol for testing."""

    def __init__(self) -> None:
        self.increment_counter = AsyncMock()


def _make_ticket(
    key: str = "CSOPM-1234",
    summary: str = "Test Issue Summary",
    assignee: str = "testuser",
    status: str = "New",
    exigence_id: str = None,
) -> CSOPMTicket:
    """Helper to create a CSOPMTicket."""
    return CSOPMTicket(
        key=key,
        summary=summary,
        assignee_username=assignee,
        created_at=datetime.now(timezone.utc),
        status=status,
        exigence_id=exigence_id,
    )


class TestCSOPMSlackNotifierProtocolCompliance(unittest.TestCase):
    """Test that CSOPMSlackNotifier implements the protocol correctly."""

    def test_implements_protocol(self):
        """Test CSOPMSlackNotifier implements CSOPMSlackNotifierProtocol."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        posting_handler = MockSlackPostingHandler()
        user_ops = MockSlackUserOps()
        mcp_client = MockAsyncMCPClient()

        notifier = CSOPMSlackNotifier(
            posting_handler=posting_handler,
            user_ops=user_ops,
            mcp_client=mcp_client,
        )

        self.assertIsInstance(notifier, CSOPMSlackNotifierProtocol)

    def test_has_send_assignment_dm_method(self):
        """Test CSOPMSlackNotifier has send_assignment_dm method."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.assertTrue(hasattr(CSOPMSlackNotifier, "send_assignment_dm"))

    def test_has_send_reminder_dm_method(self):
        """Test CSOPMSlackNotifier has send_reminder_dm method."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.assertTrue(hasattr(CSOPMSlackNotifier, "send_reminder_dm"))

    def test_has_resolve_slack_user_id_method(self):
        """Test CSOPMSlackNotifier has resolve_slack_user_id method."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.assertTrue(hasattr(CSOPMSlackNotifier, "resolve_slack_user_id"))

    def test_has_handle_button_action_method(self):
        """Test CSOPMSlackNotifier has handle_button_action method."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.assertTrue(hasattr(CSOPMSlackNotifier, "handle_button_action"))


class TestCSOPMSlackNotifierResolveSlackUserId(unittest.IsolatedAsyncioTestCase):
    """Test resolve_slack_user_id method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.posting_handler = MockSlackPostingHandler()
        self.user_ops = MockSlackUserOps()
        self.mcp_client = MockAsyncMCPClient()
        self.metrics = MockMetrics()

        self.notifier = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            metrics=self.metrics,
        )

    async def test_resolve_slack_user_id_success(self):
        """Test successful Slack ID resolution."""
        self.user_ops.get_slack_id_by_email.return_value = "U12345678"

        result = await self.notifier.resolve_slack_user_id("testuser")

        self.assertEqual(result, "U12345678")
        self.user_ops.get_slack_id_by_email.assert_awaited_once_with("testuser@adobe.com")
        self.metrics.increment_counter.assert_awaited_once_with("csopm.user.resolution.success")

    async def test_resolve_slack_user_id_not_found(self):
        """Test when Slack ID is not found."""
        self.user_ops.get_slack_id_by_email.return_value = None

        result = await self.notifier.resolve_slack_user_id("unknownuser")

        self.assertIsNone(result)
        self.metrics.increment_counter.assert_awaited_once_with("csopm.user.resolution.failed")

    async def test_resolve_slack_user_id_empty_username(self):
        """Test with empty username."""
        result = await self.notifier.resolve_slack_user_id("")

        self.assertIsNone(result)
        self.user_ops.get_slack_id_by_email.assert_not_awaited()

    async def test_resolve_slack_user_id_none_username(self):
        """Test with None username."""
        result = await self.notifier.resolve_slack_user_id(None)

        self.assertIsNone(result)
        self.user_ops.get_slack_id_by_email.assert_not_awaited()

    async def test_resolve_slack_user_id_builds_correct_email(self):
        """Test that email is built correctly with lowercase."""
        self.user_ops.get_slack_id_by_email.return_value = "U12345678"

        await self.notifier.resolve_slack_user_id("UPPERCASE")

        self.user_ops.get_slack_id_by_email.assert_awaited_once_with("uppercase@adobe.com")

    async def test_resolve_slack_user_id_on_error(self):
        """Test error handling during resolution."""
        self.user_ops.get_slack_id_by_email.side_effect = Exception("API error")

        result = await self.notifier.resolve_slack_user_id("testuser")

        self.assertIsNone(result)
        self.metrics.increment_counter.assert_awaited_once_with("csopm.user.resolution.failed")


class TestCSOPMSlackNotifierSendAssignmentDM(unittest.IsolatedAsyncioTestCase):
    """Test send_assignment_dm method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.posting_handler = MockSlackPostingHandler()
        self.user_ops = MockSlackUserOps()
        self.mcp_client = MockAsyncMCPClient()
        self.metrics = MockMetrics()

        self.notifier = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            metrics=self.metrics,
        )

    async def test_send_assignment_dm_success(self):
        """Test successful assignment DM sending."""
        self.posting_handler.post_message.return_value = {"ok": True}
        ticket = _make_ticket()

        result = await self.notifier.send_assignment_dm(ticket, "U12345678")

        self.assertTrue(result)
        self.posting_handler.post_message.assert_awaited_once()

        # Verify channel_id is the user ID for DM
        call_kwargs = self.posting_handler.post_message.call_args.kwargs
        self.assertEqual(call_kwargs["channel_id"], "U12345678")

        # Verify blocks were included
        self.assertIn("blocks", call_kwargs)
        self.assertIsInstance(call_kwargs["blocks"], list)
        self.assertTrue(len(call_kwargs["blocks"]) > 0)

        # Verify metric was incremented
        self.metrics.increment_counter.assert_awaited_once_with("csopm.notifications.sent")

    async def test_send_assignment_dm_failure(self):
        """Test handling of DM send failure."""
        self.posting_handler.post_message.return_value = {
            "ok": False,
            "error": "channel_not_found",
        }
        ticket = _make_ticket()

        result = await self.notifier.send_assignment_dm(ticket, "U12345678")

        self.assertFalse(result)
        self.metrics.increment_counter.assert_awaited_once_with("csopm.notifications.failed")

    async def test_send_assignment_dm_exception(self):
        """Test handling of exceptions during DM send."""
        self.posting_handler.post_message.side_effect = Exception("Network error")
        ticket = _make_ticket()

        result = await self.notifier.send_assignment_dm(ticket, "U12345678")

        self.assertFalse(result)
        self.metrics.increment_counter.assert_awaited_once_with("csopm.notifications.failed")

    async def test_send_assignment_dm_includes_exigence_id(self):
        """Test that Exigence ID is included in blocks when present."""
        self.posting_handler.post_message.return_value = {"ok": True}
        ticket = _make_ticket(exigence_id="EX-12345")

        await self.notifier.send_assignment_dm(ticket, "U12345678")

        call_kwargs = self.posting_handler.post_message.call_args.kwargs
        blocks = call_kwargs["blocks"]

        # Find the section block with ticket details
        section_blocks = [b for b in blocks if b.get("type") == "section"]
        self.assertTrue(len(section_blocks) > 0)

        # Check that Exigence ID is in one of the section blocks
        found_exigence = False
        for block in section_blocks:
            text = block.get("text", {}).get("text", "")
            if "EX-12345" in text:
                found_exigence = True
                break

        self.assertTrue(found_exigence, "Exigence ID not found in blocks")


class TestCSOPMSlackNotifierSendReminderDM(unittest.IsolatedAsyncioTestCase):
    """Test send_reminder_dm method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.posting_handler = MockSlackPostingHandler()
        self.user_ops = MockSlackUserOps()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()
        self.metrics = MockMetrics()

        self.notifier = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
            metrics=self.metrics,
        )

    async def test_send_rca_reminder_dm_success(self):
        """Test successful RCA reminder DM."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.state_tracker.get_notification_record.return_value = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=1, closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )
        ticket = _make_ticket()

        result = await self.notifier.send_reminder_dm(ticket, "U12345678", "rca")

        self.assertTrue(result)
        self.posting_handler.post_message.assert_awaited_once()
        self.metrics.increment_counter.assert_awaited_once_with("csopm.reminders.rca.sent")

    async def test_send_closure_reminder_dm_success(self):
        """Test successful closure reminder DM."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.state_tracker.get_notification_record.return_value = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0, closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=True,
            closure_reminder_sent=False,
        )
        ticket = _make_ticket()

        result = await self.notifier.send_reminder_dm(ticket, "U12345678", "closure")

        self.assertTrue(result)
        self.metrics.increment_counter.assert_awaited_once_with("csopm.reminders.closure.sent")

    async def test_send_reminder_dm_unknown_type(self):
        """Test with unknown reminder type."""
        ticket = _make_ticket()

        result = await self.notifier.send_reminder_dm(ticket, "U12345678", "unknown_type")

        self.assertFalse(result)
        self.posting_handler.post_message.assert_not_awaited()


class TestCSOPMSlackNotifierHandleButtonAction(unittest.IsolatedAsyncioTestCase):
    """Test handle_button_action method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.posting_handler = MockSlackPostingHandler()
        self.user_ops = MockSlackUserOps()
        self.mcp_client = MockAsyncMCPClient()
        self.state_tracker = MockStateTracker()

        self.notifier = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
        )

    async def test_handle_acknowledge_action(self):
        """Test handling acknowledge button action."""
        self.mcp_client.create_issue_comment.return_value = True
        self.state_tracker.update_notification_status.return_value = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=1, closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        result = await self.notifier.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},  # No trigger_id, modal won't open but action succeeds
        )

        self.assertTrue(result)
        self.state_tracker.update_notification_status.assert_awaited_once_with("CSOPM-1234", "ack")
        self.mcp_client.create_issue_comment.assert_awaited_once()

    async def test_handle_acknowledge_posts_jira_comment(self):
        """Test that acknowledge action posts JIRA comment."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        await self.notifier.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.mcp_client.create_issue_comment.assert_awaited_once()
        call_args = self.mcp_client.create_issue_comment.call_args.kwargs
        self.assertEqual(call_args["issue_key"], "CSOPM-1234")
        self.assertIn("acknowledged", call_args["comment"].lower())

    async def test_handle_acknowledge_increments_metric(self):
        """Test that acknowledge action increments metric on success."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        metrics = MockMetrics()
        notifier_with_metrics = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            state_tracker=self.state_tracker,
            metrics=metrics,
        )

        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        await notifier_with_metrics.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        # Verify metric was incremented
        metrics.increment_counter.assert_awaited_once_with("csopm.notifications.acknowledged")

    async def test_handle_stop_reminders_action(self):
        """Test handling stop reminders button action."""
        self.posting_handler.post_message.return_value = {"ok": True}

        result = await self.notifier.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        self.state_tracker.update_notification_status.assert_awaited_once_with(
            "CSOPM-1234", "reminders_stopped"
        )

    async def test_handle_stop_reminders_updates_state(self):
        """Test stop reminders action updates notification state."""
        result = await self.notifier.handle_button_action(
            action_id="csopm_stop_reminders",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},  # No trigger_id, modal won't open but action succeeds
        )

        self.assertTrue(result)
        self.state_tracker.update_notification_status.assert_awaited_once_with(
            "CSOPM-1234", "reminders_stopped"
        )

    async def test_handle_snooze_action(self):
        """Test handling snooze button action."""
        result = await self.notifier.handle_button_action(
            action_id="csopm_snooze",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},  # No trigger_id, modal won't open but action succeeds
        )

        self.assertTrue(result)

    async def test_handle_close_ticket_action_success(self):
        """Test handling close ticket button action.
        
        Note: Close ticket now signals modal opening (returns True)
        without calling MCP directly. The actual transition happens
        via modal submission in csopm_handler.py.
        """
        result = await self.notifier.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        # Returns True to signal modal should be opened
        self.assertTrue(result)
        # MCP is NOT called directly - transition happens via modal
        self.mcp_client._call_mcp_tool.assert_not_awaited()

    async def test_handle_close_ticket_action_does_not_post_message(self):
        """Test close ticket does not post messages directly.
        
        Confirmation messages are sent after modal submission,
        not when the button is clicked.
        """
        result = await self.notifier.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        # No messages posted - confirmation happens after modal submission
        self.posting_handler.post_message.assert_not_awaited()

    async def test_handle_view_jira_action(self):
        """Test handling view in JIRA button action (no-op)."""
        result = await self.notifier.handle_button_action(
            action_id="csopm_view_jira",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        # No state changes or API calls expected for URL button
        self.state_tracker.update_notification_status.assert_not_awaited()
        self.mcp_client.create_issue_comment.assert_not_awaited()

    async def test_handle_unknown_action(self):
        """Test handling unknown action ID."""
        result = await self.notifier.handle_button_action(
            action_id="unknown_action",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)

    async def test_handle_create_followup_action(self):
        """Test handling create followup button action.

        Note: The shared CSOPMButtonActionHandler returns True to signal that
        a modal should be opened. The actual modal opening (which requires
        trigger_id and views.open) is handled by CSOPMHandler at the ketchup-app
        level. The handler doesn't fetch issue details - that's done by the
        caller when building the modal.
        """
        result = await self.notifier.handle_button_action(
            action_id="csopm_create_followup",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "12345.67890"},
        )

        # Handler returns True to signal modal should be opened by caller
        self.assertTrue(result)

    async def test_handle_create_followup_returns_true_for_modal_signal(self):
        """Test that create followup action returns True to signal modal opening.

        Note: The shared CSOPMButtonActionHandler doesn't fetch projects directly.
        It returns True to signal that a follow-up modal should be opened.
        The actual project fetching and modal building is handled by CSOPMHandler
        at the ketchup-app level, which has access to the Slack views.open API.
        """
        result = await self.notifier.handle_button_action(
            action_id="csopm_create_followup",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "12345.67890"},
        )

        # Returns True to indicate the caller should proceed with modal
        self.assertTrue(result)
        # No JIRA API calls are made by the handler - that's the caller's job
        self.mcp_client.list_projects.assert_not_awaited()
        self.mcp_client.get_issue.assert_not_awaited()

    async def test_handle_action_without_state_tracker(self):
        """Test handling action when state tracker is not available."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        notifier_no_state = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            state_tracker=None,  # No state tracker
        )

        self.mcp_client.create_issue_comment.return_value = True

        # Should still work, just won't update state
        result = await notifier_no_state.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},  # No trigger_id, modal won't open but action succeeds
        )

        self.assertTrue(result)
        # JIRA comment should still be posted
        self.mcp_client.create_issue_comment.assert_awaited()


class TestCSOPMSlackNotifierWithoutMetrics(unittest.IsolatedAsyncioTestCase):
    """Test CSOPMSlackNotifier without metrics injection."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        self.posting_handler = MockSlackPostingHandler()
        self.user_ops = MockSlackUserOps()
        self.mcp_client = MockAsyncMCPClient()

        # Create notifier without metrics
        self.notifier = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            metrics=None,  # No metrics
        )

    async def test_resolve_slack_user_id_without_metrics(self):
        """Test resolution works without metrics."""
        self.user_ops.get_slack_id_by_email.return_value = "U12345678"

        result = await self.notifier.resolve_slack_user_id("testuser")

        self.assertEqual(result, "U12345678")

    async def test_send_assignment_dm_without_metrics(self):
        """Test DM sending works without metrics."""
        self.posting_handler.post_message.return_value = {"ok": True}
        ticket = _make_ticket()

        result = await self.notifier.send_assignment_dm(ticket, "U12345678")

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
