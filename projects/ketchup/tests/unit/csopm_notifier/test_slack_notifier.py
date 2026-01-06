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
from unittest.mock import AsyncMock, MagicMock, patch

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
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.user.resolution.success"
        )

    async def test_resolve_slack_user_id_not_found(self):
        """Test when Slack ID is not found."""
        self.user_ops.get_slack_id_by_email.return_value = None

        result = await self.notifier.resolve_slack_user_id("unknownuser")

        self.assertIsNone(result)
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.user.resolution.failed"
        )

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

        self.user_ops.get_slack_id_by_email.assert_awaited_once_with(
            "uppercase@adobe.com"
        )

    async def test_resolve_slack_user_id_on_error(self):
        """Test error handling during resolution."""
        self.user_ops.get_slack_id_by_email.side_effect = Exception("API error")

        result = await self.notifier.resolve_slack_user_id("testuser")

        self.assertIsNone(result)
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.user.resolution.failed"
        )


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
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.notifications.sent"
        )

    async def test_send_assignment_dm_failure(self):
        """Test handling of DM send failure."""
        self.posting_handler.post_message.return_value = {
            "ok": False,
            "error": "channel_not_found",
        }
        ticket = _make_ticket()

        result = await self.notifier.send_assignment_dm(ticket, "U12345678")

        self.assertFalse(result)
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.notifications.failed"
        )

    async def test_send_assignment_dm_exception(self):
        """Test handling of exceptions during DM send."""
        self.posting_handler.post_message.side_effect = Exception("Network error")
        ticket = _make_ticket()

        result = await self.notifier.send_assignment_dm(ticket, "U12345678")

        self.assertFalse(result)
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.notifications.failed"
        )

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
            ping_count=1,
            assignee_slack_id="U12345678",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )
        ticket = _make_ticket()

        result = await self.notifier.send_reminder_dm(ticket, "U12345678", "rca")

        self.assertTrue(result)
        self.posting_handler.post_message.assert_awaited_once()
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.reminders.rca.sent"
        )

    async def test_send_closure_reminder_dm_success(self):
        """Test successful closure reminder DM."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.state_tracker.get_notification_record.return_value = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            ping_count=0,
            assignee_slack_id="U12345678",
            rca_reminder_sent=True,
            closure_reminder_sent=False,
        )
        ticket = _make_ticket()

        result = await self.notifier.send_reminder_dm(ticket, "U12345678", "closure")

        self.assertTrue(result)
        self.metrics.increment_counter.assert_awaited_once_with(
            "csopm.reminders.closure.sent"
        )

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
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True
        self.state_tracker.update_notification_status.return_value = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            ping_count=1,
            assignee_slack_id="U12345678",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        result = await self.notifier.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        self.state_tracker.update_notification_status.assert_awaited_once_with(
            "CSOPM-1234", "ack"
        )
        self.mcp_client.create_issue_comment.assert_awaited_once()

        # Verify confirmation message was sent
        self.posting_handler.post_message.assert_awaited()

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
        metrics.increment_counter.assert_awaited_once_with(
            "csopm.notifications.acknowledged"
        )

    async def test_handle_done_action(self):
        """Test handling done button action."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True
        self.mcp_client.search_issues.return_value = {"issues": []}

        result = await self.notifier.handle_button_action(
            action_id="csopm_done",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        self.state_tracker.update_notification_status.assert_awaited_once_with(
            "CSOPM-1234", "done"
        )

    async def test_handle_done_action_includes_followup_batch_info(self):
        """Test that done action includes follow-up ticket info in JIRA comment."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True
        # Mock linked follow-up tickets
        self.mcp_client.search_issues.return_value = {
            "issues": [
                {
                    "key": "CSOPM-5001",
                    "fields": {
                        "summary": "Follow-up task 1",
                        "status": {"name": "Open"},
                    },
                },
                {
                    "key": "CSOPM-5002",
                    "fields": {
                        "summary": "Follow-up task 2",
                        "status": {"name": "Closed"},
                    },
                },
            ]
        }

        await self.notifier.handle_button_action(
            action_id="csopm_done",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        # Verify search was performed for linked follow-ups
        self.mcp_client.search_issues.assert_awaited_once()

        # Verify comment includes follow-up info
        call_args = self.mcp_client.create_issue_comment.call_args.kwargs
        comment = call_args["comment"]
        self.assertIn("CSOPM-5001", comment)
        self.assertIn("CSOPM-5002", comment)
        self.assertIn("2 total", comment)
        self.assertIn("1 open", comment)
        self.assertIn("1 closed", comment)

    async def test_handle_done_action_no_followups(self):
        """Test done action when no follow-up tickets exist."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True
        self.mcp_client.search_issues.return_value = {"issues": []}

        await self.notifier.handle_button_action(
            action_id="csopm_done",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        # Verify simple comment without follow-up info
        call_args = self.mcp_client.create_issue_comment.call_args.kwargs
        comment = call_args["comment"]
        self.assertIn("marked as done", comment)
        self.assertNotIn("Follow-up Tickets", comment)

    async def test_handle_snooze_action(self):
        """Test handling snooze button action."""
        self.posting_handler.post_message.return_value = {"ok": True}

        result = await self.notifier.handle_button_action(
            action_id="csopm_snooze",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)

        # Verify confirmation message includes "snoozed"
        call_kwargs = self.posting_handler.post_message.call_args.kwargs
        self.assertIn("snoozed", call_kwargs["message"].lower())

    async def test_handle_close_ticket_action_success(self):
        """Test handling close ticket button action successfully."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client._call_mcp_tool.return_value = {"success": True}

        result = await self.notifier.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        self.mcp_client._call_mcp_tool.assert_awaited_once()

        # Verify correct MCP tool was called
        call_args = self.mcp_client._call_mcp_tool.call_args
        self.assertEqual(call_args[0][0], "transition_jira_status_by_name")
        self.assertEqual(call_args[0][1]["issueIdOrKey"], "CSOPM-1234")
        self.assertEqual(call_args[0][1]["statusName"], "Closed")

    async def test_handle_close_ticket_action_failure(self):
        """Test handling close ticket button action with failure."""
        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client._call_mcp_tool.return_value = {
            "success": False,
            "message": "Transition not allowed",
        }

        result = await self.notifier.handle_button_action(
            action_id="csopm_close_ticket",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertFalse(result)

        # Verify error message was sent
        call_kwargs = self.posting_handler.post_message.call_args.kwargs
        self.assertIn("Failed", call_kwargs["message"])

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
        """Test handling create followup button action."""
        self.mcp_client.get_issue.return_value = {
            "key": "CSOPM-1234",
            "fields": {
                "summary": "Test Summary",
                "status": {"name": "Open"},
                "assignee": {"name": "testuser"},
            },
        }
        self.mcp_client.list_projects.return_value = []

        result = await self.notifier.handle_button_action(
            action_id="csopm_create_followup",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "12345.67890"},
        )

        self.assertTrue(result)
        self.mcp_client.get_issue.assert_awaited_once_with(
            issue_key="CSOPM-1234",
            fields=["summary", "status", "assignee", "description"],
        )

    async def test_handle_create_followup_fetches_projects(self):
        """Test that create followup action fetches JIRA projects."""
        self.mcp_client.get_issue.return_value = {
            "key": "CSOPM-1234",
            "fields": {
                "summary": "Test Summary",
                "status": {"name": "Open"},
                "assignee": {"name": "testuser"},
            },
        }
        self.mcp_client.list_projects.return_value = [
            {
                "key": "CSOPM",
                "name": "CSO Project Management",
                "issueTypes": [
                    {"id": "1", "name": "Task"},
                    {"id": "2", "name": "Bug"},
                ],
            },
            {
                "key": "OTHER",
                "name": "Other Project",
                "issueTypes": [
                    {"id": "3", "name": "Story"},
                ],
            },
        ]

        result = await self.notifier.handle_button_action(
            action_id="csopm_create_followup",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={"trigger_id": "12345.67890"},
        )

        self.assertTrue(result)
        # Verify list_projects was called with expand=issueTypes
        self.mcp_client.list_projects.assert_awaited_once_with(expand="issueTypes")

    async def test_handle_action_without_state_tracker(self):
        """Test handling action when state tracker is not available."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        notifier_no_state = CSOPMSlackNotifier(
            posting_handler=self.posting_handler,
            user_ops=self.user_ops,
            mcp_client=self.mcp_client,
            state_tracker=None,  # No state tracker
        )

        self.posting_handler.post_message.return_value = {"ok": True}
        self.mcp_client.create_issue_comment.return_value = True

        # Should still work, just won't update state
        result = await notifier_no_state.handle_button_action(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload={},
        )

        self.assertTrue(result)
        # Confirmation message should still be sent
        self.posting_handler.post_message.assert_awaited()


class TestCSOPMNotificationBlocks(unittest.TestCase):
    """Test Block Kit block builders."""

    def test_build_assignment_notification_structure(self):
        """Test assignment notification has correct structure."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        # Verify block types
        block_types = [b["type"] for b in blocks]
        self.assertIn("header", block_types)
        self.assertIn("section", block_types)
        self.assertIn("actions", block_types)
        self.assertIn("divider", block_types)
        self.assertIn("context", block_types)

    def test_build_assignment_notification_has_four_buttons(self):
        """Test assignment notification has 4 action buttons."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        # Find actions block
        actions_block = next(b for b in blocks if b["type"] == "actions")
        elements = actions_block["elements"]

        self.assertEqual(len(elements), 4)

        # Verify button action IDs
        action_ids = [e["action_id"] for e in elements]
        self.assertIn("csopm_acknowledge", action_ids)
        self.assertIn("csopm_create_followup", action_ids)
        self.assertIn("csopm_done", action_ids)
        self.assertIn("csopm_view_jira", action_ids)

    def test_build_assignment_notification_includes_ticket_key_as_value(self):
        """Test that ticket key is passed as button value."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket(key="CSOPM-9999")
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        actions_block = next(b for b in blocks if b["type"] == "actions")
        for element in actions_block["elements"]:
            self.assertEqual(element["value"], "CSOPM-9999")

    def test_build_assignment_notification_jira_url(self):
        """Test that JIRA URL is included in View in JIRA button."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket(key="CSOPM-1234")
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        actions_block = next(b for b in blocks if b["type"] == "actions")
        view_jira_button = next(
            e for e in actions_block["elements"] if e["action_id"] == "csopm_view_jira"
        )

        self.assertIn("url", view_jira_button)
        self.assertIn("CSOPM-1234", view_jira_button["url"])

    def test_build_rca_reminder_structure(self):
        """Test RCA reminder has correct structure."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_rca_reminder(
            ticket=ticket,
            days_old=10,
            ping_count=1,
        )

        block_types = [b["type"] for b in blocks]
        self.assertIn("header", block_types)
        self.assertIn("section", block_types)
        self.assertIn("actions", block_types)

    def test_build_rca_reminder_shows_warning_at_high_ping_count(self):
        """Test RCA reminder shows warning at ping count >= 2."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_rca_reminder(
            ticket=ticket,
            days_old=10,
            ping_count=2,
        )

        # Find context block with warning
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        context_texts = [
            e.get("text", "")
            for b in context_blocks
            for e in b.get("elements", [])
        ]

        has_warning = any("escalated" in text.lower() for text in context_texts)
        self.assertTrue(has_warning, "Warning about escalation not found")

    def test_build_closure_reminder_structure(self):
        """Test closure reminder has correct structure."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_closure_reminder(
            ticket=ticket,
            days_old=50,
            ping_count=1,
            has_open_linked=False,
        )

        block_types = [b["type"] for b in blocks]
        self.assertIn("header", block_types)
        self.assertIn("actions", block_types)

        # Find actions block
        actions_block = next(b for b in blocks if b["type"] == "actions")
        action_ids = [e["action_id"] for e in actions_block["elements"]]

        self.assertIn("csopm_close_ticket", action_ids)
        self.assertIn("csopm_snooze", action_ids)

    def test_build_closure_reminder_shows_linked_tickets_warning(self):
        """Test closure reminder shows warning about linked tickets."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_closure_reminder(
            ticket=ticket,
            days_old=50,
            ping_count=1,
            has_open_linked=True,
        )

        context_blocks = [b for b in blocks if b.get("type") == "context"]
        context_texts = [
            e.get("text", "")
            for b in context_blocks
            for e in b.get("elements", [])
        ]

        has_linked_warning = any("linked" in text.lower() for text in context_texts)
        self.assertTrue(has_linked_warning, "Linked tickets warning not found")

    def test_build_acknowledgment_confirmation(self):
        """Test acknowledgment confirmation message."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
            ticket_key="CSOPM-1234",
            action_type="acknowledged",
        )

        self.assertTrue(len(blocks) > 0)

        # Find section with confirmation text
        section = next(b for b in blocks if b["type"] == "section")
        text = section["text"]["text"]

        self.assertIn("CSOPM-1234", text)
        self.assertIn("acknowledged", text)

    def test_build_create_followup_modal(self):
        """Test create followup modal structure."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        modal = CSOPMNotificationBlocks.build_create_followup_modal(ticket)

        self.assertEqual(modal["type"], "modal")
        self.assertEqual(modal["callback_id"], "csopm_create_followup_modal")
        self.assertEqual(modal["private_metadata"], ticket.key)
        self.assertIn("blocks", modal)

        # Verify input blocks are present
        block_types = [b["type"] for b in modal["blocks"]]
        self.assertIn("input", block_types)

        # Verify project and issue type blocks exist (fallback text inputs)
        block_ids = [b.get("block_id", "") for b in modal["blocks"]]
        self.assertIn("project_block", block_ids)
        self.assertIn("issue_type_block", block_ids)
        self.assertIn("summary_block", block_ids)
        self.assertIn("description_block", block_ids)

    def test_build_create_followup_modal_with_dynamic_projects(self):
        """Test create followup modal with dynamic project dropdown."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        projects = [
            {"key": "CSOPM", "name": "CSO Project Management"},
            {"key": "OTHER", "name": "Other Project"},
        ]
        modal = CSOPMNotificationBlocks.build_create_followup_modal(
            ticket, projects=projects
        )

        # Find project block
        project_block = next(
            b for b in modal["blocks"]
            if b.get("block_id") == "project_block"
        )

        # Verify it's a static_select with options
        element = project_block["element"]
        self.assertEqual(element["type"], "static_select")
        self.assertEqual(len(element["options"]), 2)
        self.assertEqual(element["options"][0]["value"], "CSOPM")
        self.assertEqual(element["options"][1]["value"], "OTHER")

    def test_build_create_followup_modal_with_dynamic_issue_types(self):
        """Test create followup modal with dynamic issue type dropdown."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        ticket = _make_ticket()
        issue_types = [
            {"id": "1", "name": "Task"},
            {"id": "2", "name": "Bug"},
            {"id": "3", "name": "Story"},
        ]
        modal = CSOPMNotificationBlocks.build_create_followup_modal(
            ticket, issue_types=issue_types
        )

        # Find issue type block
        issue_type_block = next(
            b for b in modal["blocks"]
            if b.get("block_id") == "issue_type_block"
        )

        # Verify it's a static_select with options
        element = issue_type_block["element"]
        self.assertEqual(element["type"], "static_select")
        self.assertEqual(len(element["options"]), 3)
        self.assertEqual(element["options"][0]["value"], "1")
        self.assertEqual(element["options"][0]["text"]["text"], "Task")

    def test_get_fallback_text(self):
        """Test fallback text generation."""
        from ketchup_csopm_notifier.blocks.notification_blocks import (
            CSOPMNotificationBlocks,
        )

        text = CSOPMNotificationBlocks.get_fallback_text(
            notification_type="assignment",
            ticket_key="CSOPM-1234",
        )

        self.assertIn("CSOPM-1234", text)
        self.assertIn("jira.corp.adobe.com", text)


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
