#!/usr/bin/env python3
"""
CSOPM Reminder Service Tests.

Unit tests for the CSOPMReminderService, verifying:
1. Protocol compliance with CSOPMReminderServiceProtocol
2. 7-day RCA reminder logic and 3-ping escalation
3. 45-day closure reminder logic with linked ticket checks
4. Day calculation from ticket creation timestamp
5. Snooze functionality
6. Close via reminder workflow
"""

import unittest
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock

from packages.core.typed_di.protocols import (
    CSOPMReminderServiceProtocol,
    CSOPMTicket,
    FollowupRecord,
    NotificationRecord,
)


class MockStateTracker:
    """Mock CSOPMStateTrackerProtocol for testing."""

    def __init__(self) -> None:
        self.get_notification_record = AsyncMock()
        self.create_notification_record = AsyncMock()
        self.update_notification_status = AsyncMock()
        self.increment_ping_count = AsyncMock()
        self.mark_rca_reminder_sent = AsyncMock()
        self.mark_closure_reminder_sent = AsyncMock()
        self.get_pending_notifications = AsyncMock()
        self.record_followup = AsyncMock()
        self.get_all_active_notifications = AsyncMock()
        self.handle_reassignment = AsyncMock()


class MockMCPClient:
    """Mock AsyncMCPClient for testing."""

    def __init__(self) -> None:
        self.search_issues = AsyncMock()
        self.get_issue = AsyncMock()
        self._call_mcp_tool = AsyncMock()


class MockJIRAPoller:
    """Mock CSOPMJIRAPollerProtocol for testing."""

    def __init__(self) -> None:
        self.poll_for_new_assignments = AsyncMock()
        self.get_ticket_details = AsyncMock()
        self.get_tickets_by_assignee = AsyncMock()


class MockMetrics:
    """Mock CSOPMMetricsProtocol for testing."""

    def __init__(self) -> None:
        self.increment_counter = AsyncMock()
        self.record_gauge = AsyncMock()
        self.record_latency = AsyncMock()
        self.get_metrics_summary = AsyncMock()


def make_ticket(
    key: str = "CSOPM-1234",
    summary: str = "Test Issue",
    assignee: str = "testuser",
    created_at: Optional[datetime] = None,
    status: str = "New",
    exigence_id: Optional[str] = None,
) -> CSOPMTicket:
    """Helper to create a CSOPMTicket with default values."""
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    return CSOPMTicket(
        key=key,
        summary=summary,
        assignee_username=assignee,
        created_at=created_at,
        status=status,
        exigence_id=exigence_id,
    )


def make_notification_record(
    ticket_key: str = "CSOPM-1234",
    notification_status: str = "sent",
    rca_ping_count: int = 0,
    closure_ping_count: int = 0,
    assignee_slack_id: str = "U12345678",
    assignee_jira_username: str = "testuser",
    rca_reminder_sent: bool = False,
    closure_reminder_sent: bool = False,
) -> NotificationRecord:
    """Helper to create a NotificationRecord with default values."""
    return NotificationRecord(
        ticket_key=ticket_key,
        notification_status=notification_status,
        rca_ping_count=rca_ping_count,
        closure_ping_count=closure_ping_count,
        assignee_slack_id=assignee_slack_id,
        assignee_jira_username=assignee_jira_username,
        rca_reminder_sent=rca_reminder_sent,
        closure_reminder_sent=closure_reminder_sent,
    )


class TestCSOPMReminderServiceProtocolCompliance(unittest.TestCase):
    """Test that CSOPMReminderService implements the protocol correctly."""

    def test_implements_protocol(self):
        """Test CSOPMReminderService implements CSOPMReminderServiceProtocol."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        mock_state_tracker = MockStateTracker()
        mock_mcp_client = MockMCPClient()

        service = CSOPMReminderService(
            state_tracker=mock_state_tracker,
            mcp_client=mock_mcp_client,
        )

        self.assertIsInstance(service, CSOPMReminderServiceProtocol)

    def test_has_schedule_rca_reminder_method(self):
        """Test CSOPMReminderService has schedule_rca_reminder method."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.assertTrue(hasattr(CSOPMReminderService, "schedule_rca_reminder"))

    def test_has_schedule_closure_reminder_method(self):
        """Test CSOPMReminderService has schedule_closure_reminder method."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.assertTrue(hasattr(CSOPMReminderService, "schedule_closure_reminder"))

    def test_has_get_due_reminders_method(self):
        """Test CSOPMReminderService has get_due_reminders method."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.assertTrue(hasattr(CSOPMReminderService, "get_due_reminders"))

    def test_has_complete_reminder_method(self):
        """Test CSOPMReminderService has complete_reminder method."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.assertTrue(hasattr(CSOPMReminderService, "complete_reminder"))

    def test_has_check_rca_reminders_method(self):
        """Test CSOPMReminderService has check_rca_reminders method."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.assertTrue(hasattr(CSOPMReminderService, "check_rca_reminders"))

    def test_has_check_closure_reminders_method(self):
        """Test CSOPMReminderService has check_closure_reminders method."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.assertTrue(hasattr(CSOPMReminderService, "check_closure_reminders"))


class TestDaysCalculation(unittest.TestCase):
    """Test day calculation from ticket creation."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
        )

    def test_days_old_calculation_today(self):
        """Test days calculation for ticket created today."""
        created_at = datetime.now(timezone.utc)
        days = self.service._calculate_days_old(created_at)
        self.assertEqual(days, 0)

    def test_days_old_calculation_7_days_ago(self):
        """Test days calculation for ticket created 7 days ago."""
        created_at = datetime.now(timezone.utc) - timedelta(days=7)
        days = self.service._calculate_days_old(created_at)
        self.assertEqual(days, 7)

    def test_days_old_calculation_45_days_ago(self):
        """Test days calculation for ticket created 45 days ago."""
        created_at = datetime.now(timezone.utc) - timedelta(days=45)
        days = self.service._calculate_days_old(created_at)
        self.assertEqual(days, 45)

    def test_days_old_calculation_naive_datetime(self):
        """Test days calculation handles naive datetime (assumes UTC)."""
        created_at = datetime.now() - timedelta(days=10)  # Naive datetime
        days = self.service._calculate_days_old(created_at)
        self.assertEqual(days, 10)


class TestRCAReminder(unittest.IsolatedAsyncioTestCase):
    """Test 7-day RCA reminder logic."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
        )

    def test_rca_reminder_not_due_for_new_ticket(self):
        """Test RCA reminder not due for ticket less than 7 days old."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=3))
        record = {"rca_reminder_sent": False, "notification_status": "sent"}

        result = self.service._is_rca_reminder_due(ticket, record)
        self.assertFalse(result)

    def test_rca_reminder_due_for_old_ticket(self):
        """Test RCA reminder is due for ticket 7+ days old."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=8))
        record = {"rca_reminder_sent": False, "notification_status": "sent"}

        result = self.service._is_rca_reminder_due(ticket, record)
        self.assertTrue(result)

    def test_rca_reminder_not_due_if_already_sent(self):
        """Test RCA reminder not due if already sent."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=10))
        record = {"rca_reminder_sent": True, "notification_status": "sent"}

        result = self.service._is_rca_reminder_due(ticket, record)
        self.assertFalse(result)

    def test_rca_reminder_not_due_if_escalated(self):
        """Test RCA reminder not due if notification escalated."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=10))
        record = {"rca_reminder_sent": False, "notification_status": "escalated"}

        result = self.service._is_rca_reminder_due(ticket, record)
        self.assertFalse(result)

    async def test_schedule_rca_reminder(self):
        """Test scheduling an RCA reminder."""
        ticket = make_ticket()
        expected_followup = FollowupRecord(
            ticket_key=ticket.key,
            followup_type="rca_reminder",
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=24),
            completed=False,
        )
        self.mock_state_tracker.record_followup.return_value = expected_followup

        result = await self.service.schedule_rca_reminder(ticket, delay_hours=24)

        self.mock_state_tracker.record_followup.assert_called_once()
        call_args = self.mock_state_tracker.record_followup.call_args
        self.assertEqual(call_args.kwargs["ticket_key"], ticket.key)
        self.assertEqual(call_args.kwargs["followup_type"], "rca_reminder")

    async def test_check_rca_reminders_returns_due_records(self):
        """Test check_rca_reminders returns records that are 7+ days old and due."""
        records = [
            make_notification_record("CSOPM-1001", rca_reminder_sent=False),
            make_notification_record("CSOPM-1002", rca_reminder_sent=True),  # Skip
            make_notification_record("CSOPM-1003", rca_reminder_sent=False),
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        # Set up mock ticket details with 8-day old tickets
        old_ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=8))
        self.mock_mcp_client.get_issue.return_value = {
            "key": "CSOPM-1001",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "assignee": {"name": "testuser"},
                "created": old_ticket.created_at.isoformat(),
            },
        }

        result = await self.service.check_rca_reminders()

        self.assertEqual(len(result), 2)
        ticket_keys = [r.ticket_key for r in result]
        self.assertIn("CSOPM-1001", ticket_keys)
        self.assertIn("CSOPM-1003", ticket_keys)

    async def test_check_rca_reminders_filters_by_7_day_age(self):
        """Test check_rca_reminders only returns tickets 7+ days old."""
        records = [
            make_notification_record("CSOPM-1001", rca_reminder_sent=False),  # Will be 8 days old
            make_notification_record("CSOPM-1002", rca_reminder_sent=False),  # Will be 3 days old
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        # Mock get_issue to return different ages for each ticket
        def mock_get_issue(issue_key, fields):
            if issue_key == "CSOPM-1001":
                created = datetime.now(timezone.utc) - timedelta(days=8)
            else:
                created = datetime.now(timezone.utc) - timedelta(days=3)
            return {
                "key": issue_key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "New"},
                    "assignee": {"name": "testuser"},
                    "created": created.isoformat(),
                },
            }

        self.mock_mcp_client.get_issue.side_effect = mock_get_issue

        result = await self.service.check_rca_reminders()

        # Only the 8-day old ticket should be returned
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ticket_key, "CSOPM-1001")

    async def test_check_rca_reminders_skips_escalated(self):
        """Test check_rca_reminders skips escalated records."""
        records = [
            NotificationRecord(
                ticket_key="CSOPM-1001",
                notification_status="escalated",
                rca_ping_count=3,
                closure_ping_count=0,
                assignee_slack_id="U12345678",
                assignee_jira_username="testuser",
                rca_reminder_sent=False,
                closure_reminder_sent=False,
            ),
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records
        result = await self.service.check_rca_reminders()
        self.assertEqual(len(result), 0)

    async def test_process_rca_reminder_first_ping(self):
        """Test processing first RCA reminder ping."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=8))

        result = await self.service.process_rca_reminder(ticket, rca_ping_count=0)

        self.assertIsNotNone(result)
        self.assertTrue(result["sent"])
        self.assertFalse(result["escalated"])
        self.assertEqual(result["new_ping_count"], 1)

    async def test_process_rca_reminder_escalate_at_three(self):
        """Test RCA reminder escalates at 3 pings."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=10))

        result = await self.service.process_rca_reminder(ticket, rca_ping_count=2)

        self.assertIsNotNone(result)
        self.assertTrue(result["sent"])
        self.assertTrue(result["escalated"])
        self.assertEqual(result["new_ping_count"], 3)

    async def test_process_rca_reminder_skips_young_ticket(self):
        """Test RCA reminder processing skips young tickets."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=3))

        result = await self.service.process_rca_reminder(ticket, rca_ping_count=0)

        self.assertIsNone(result)


class TestClosureReminder(unittest.IsolatedAsyncioTestCase):
    """Test 45-day closure reminder logic."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
        )

    def test_closure_reminder_not_due_for_new_ticket(self):
        """Test closure reminder not due for ticket less than 45 days old."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=30))
        record = {"closure_reminder_sent": False, "notification_status": "sent"}

        result = self.service._is_closure_reminder_due(ticket, record)
        self.assertFalse(result)

    def test_closure_reminder_due_for_old_ticket(self):
        """Test closure reminder is due for ticket 45+ days old."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))
        record = {"closure_reminder_sent": False, "notification_status": "sent"}

        result = self.service._is_closure_reminder_due(ticket, record)
        self.assertTrue(result)

    def test_closure_reminder_not_due_if_already_sent(self):
        """Test closure reminder not due if already sent."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))
        record = {"closure_reminder_sent": True, "notification_status": "sent"}

        result = self.service._is_closure_reminder_due(ticket, record)
        self.assertFalse(result)

    def test_closure_reminder_not_due_if_snoozed(self):
        """Test closure reminder not due if snoozed until future."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))
        future_snooze = datetime.now(timezone.utc) + timedelta(days=7)
        record = {
            "closure_reminder_sent": False,
            "notification_status": "sent",
            "closure_snoozed_until": int(future_snooze.timestamp()),
        }

        result = self.service._is_closure_reminder_due(ticket, record)
        self.assertFalse(result)

    def test_closure_reminder_due_after_snooze_expires(self):
        """Test closure reminder is due after snooze expires."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))
        past_snooze = datetime.now(timezone.utc) - timedelta(days=1)
        record = {
            "closure_reminder_sent": False,
            "notification_status": "sent",
            "closure_snoozed_until": int(past_snooze.timestamp()),
        }

        result = self.service._is_closure_reminder_due(ticket, record)
        self.assertTrue(result)

    async def test_schedule_closure_reminder(self):
        """Test scheduling a closure reminder."""
        ticket = make_ticket()
        expected_followup = FollowupRecord(
            ticket_key=ticket.key,
            followup_type="closure_reminder",
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=48),
            completed=False,
        )
        self.mock_state_tracker.record_followup.return_value = expected_followup

        result = await self.service.schedule_closure_reminder(ticket, delay_hours=48)

        self.mock_state_tracker.record_followup.assert_called_once()
        call_args = self.mock_state_tracker.record_followup.call_args
        self.assertEqual(call_args.kwargs["ticket_key"], ticket.key)
        self.assertEqual(call_args.kwargs["followup_type"], "closure_reminder")

    async def test_check_closure_reminders_does_not_check_linked_tickets_option_b(self):
        """Test check_closure_reminders does NOT check linked tickets (Option B behavior)."""
        records = [
            make_notification_record("CSOPM-1001", closure_reminder_sent=False),
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        # Mock ticket details with 50-day old ticket
        old_ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))
        self.mock_mcp_client.get_issue.return_value = {
            "key": "CSOPM-1001",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "assignee": {"name": "testuser"},
                "created": old_ticket.created_at.isoformat(),
            },
        }

        result = await self.service.check_closure_reminders()

        # Option B: search_issues should NOT be called in check_closure_reminders
        # The linked ticket check is now done in process_closure_reminder instead
        self.mock_mcp_client.search_issues.assert_not_called()
        # But should still return the ticket
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ticket_key, "CSOPM-1001")

    async def test_check_closure_reminders_filters_by_45_day_age(self):
        """Test check_closure_reminders only returns tickets 45+ days old."""
        records = [
            make_notification_record(
                "CSOPM-1001", closure_reminder_sent=False
            ),  # Will be 50 days old
            make_notification_record(
                "CSOPM-1002", closure_reminder_sent=False
            ),  # Will be 30 days old
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        # Mock get_issue to return different ages for each ticket
        def mock_get_issue(issue_key, fields):
            if issue_key == "CSOPM-1001":
                created = datetime.now(timezone.utc) - timedelta(days=50)
            else:
                created = datetime.now(timezone.utc) - timedelta(days=30)
            return {
                "key": issue_key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "New"},
                    "assignee": {"name": "testuser"},
                    "created": created.isoformat(),
                },
            }

        self.mock_mcp_client.get_issue.side_effect = mock_get_issue
        self.mock_mcp_client.search_issues.return_value = {"issues": []}

        result = await self.service.check_closure_reminders()

        # Only the 50-day old ticket should be returned
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ticket_key, "CSOPM-1001")

    async def test_check_closure_reminders_includes_with_open_linked_option_b(self):
        """Test check_closure_reminders includes tickets with open linked tickets (Option B)."""
        records = [
            make_notification_record("CSOPM-1001", closure_reminder_sent=False),
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        # Mock ticket details with 50-day old ticket
        old_ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))
        self.mock_mcp_client.get_issue.return_value = {
            "key": "CSOPM-1001",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "assignee": {"name": "testuser"},
                "created": old_ticket.created_at.isoformat(),
            },
        }
        # Note: Option B does NOT check for linked tickets in check_closure_reminders

        result = await self.service.check_closure_reminders()

        # Option B: Should return the ticket regardless of linked status
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ticket_key, "CSOPM-1001")

    async def test_process_closure_reminder_sends_with_open_linked_option_b(self):
        """Test closure reminder processing sends reminder with open linked info (Option B)."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))

        # Mock state tracker to return record with no followups
        record = NotificationRecord(
            ticket_key=ticket.key,
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=[],
        )
        self.mock_state_tracker.get_notification_record.return_value = record
        self.mock_mcp_client.search_issues.return_value = {"issues": [{"key": "LINKED-1"}]}

        result = await self.service.process_closure_reminder(ticket, closure_ping_count=0)

        # Option B: Should SEND the reminder even with open linked tickets
        self.assertIsNotNone(result)
        self.assertTrue(result["sent"])  # Option B always sends
        self.assertTrue(result["has_open_linked"])
        self.assertEqual(result["new_ping_count"], 1)  # Ping count incremented
        self.assertIn("open_followups", result)  # Should include followups field

    async def test_process_closure_reminder_first_ping(self):
        """Test processing first closure reminder ping."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))

        # Mock state tracker to return record with no followups
        record = NotificationRecord(
            ticket_key=ticket.key,
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=[],
        )
        self.mock_state_tracker.get_notification_record.return_value = record
        self.mock_mcp_client.search_issues.return_value = {"issues": []}

        result = await self.service.process_closure_reminder(ticket, closure_ping_count=0)

        self.assertIsNotNone(result)
        self.assertTrue(result["sent"])
        self.assertFalse(result["escalated"])
        self.assertEqual(result["new_ping_count"], 1)
        self.assertFalse(result["has_open_linked"])
        self.assertEqual(result["open_followups"], [])

    async def test_process_closure_reminder_escalate_at_three(self):
        """Test closure reminder escalates at 3 pings."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))

        # Mock state tracker to return record with no followups
        record = NotificationRecord(
            ticket_key=ticket.key,
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=2,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=[],
        )
        self.mock_state_tracker.get_notification_record.return_value = record
        self.mock_mcp_client.search_issues.return_value = {"issues": []}

        result = await self.service.process_closure_reminder(ticket, closure_ping_count=2)

        self.assertIsNotNone(result)
        self.assertTrue(result["sent"])
        self.assertTrue(result["escalated"])
        self.assertEqual(result["new_ping_count"], 3)


class TestLinkedTicketCheck(unittest.IsolatedAsyncioTestCase):
    """Test linked ticket checking via JQL."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
        )

    async def test_has_open_linked_tickets_true(self):
        """Test returns True when open linked tickets exist."""
        self.mock_mcp_client.search_issues.return_value = {
            "issues": [{"key": "LINKED-1", "fields": {"status": {"name": "In Progress"}}}]
        }

        result = await self.service._has_open_linked_tickets("CSOPM-1234")

        self.assertTrue(result)

    async def test_has_open_linked_tickets_false(self):
        """Test returns False when no open linked tickets."""
        self.mock_mcp_client.search_issues.return_value = {"issues": []}

        result = await self.service._has_open_linked_tickets("CSOPM-1234")

        self.assertFalse(result)

    async def test_has_open_linked_tickets_uses_correct_jql(self):
        """Test uses correct JQL with linkedIssues function."""
        self.mock_mcp_client.search_issues.return_value = {"issues": []}

        await self.service._has_open_linked_tickets("CSOPM-1234")

        self.mock_mcp_client.search_issues.assert_called_once()
        call_args = self.mock_mcp_client.search_issues.call_args

        jql = call_args.kwargs.get("jql", "")
        self.assertIn("linkedIssues('CSOPM-1234')", jql)
        self.assertIn("NOT IN ('Closed', 'Done', 'Resolved')", jql)

    async def test_has_open_linked_tickets_on_error(self):
        """Test returns False on error (allows reminder to proceed)."""
        self.mock_mcp_client.search_issues.side_effect = Exception("JIRA error")

        result = await self.service._has_open_linked_tickets("CSOPM-1234")

        self.assertFalse(result)


class TestCompleteReminder(unittest.IsolatedAsyncioTestCase):
    """Test complete_reminder method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
        )

    async def test_complete_rca_reminder(self):
        """Test completing an RCA reminder."""
        self.mock_state_tracker.mark_rca_reminder_sent.return_value = make_notification_record(
            rca_reminder_sent=True
        )

        result = await self.service.complete_reminder("CSOPM-1234", "rca_reminder")

        self.assertTrue(result)
        self.mock_state_tracker.mark_rca_reminder_sent.assert_called_once_with("CSOPM-1234")

    async def test_complete_closure_reminder(self):
        """Test completing a closure reminder."""
        self.mock_state_tracker.mark_closure_reminder_sent.return_value = make_notification_record(
            closure_reminder_sent=True
        )

        result = await self.service.complete_reminder("CSOPM-1234", "closure_reminder")

        self.assertTrue(result)
        self.mock_state_tracker.mark_closure_reminder_sent.assert_called_once_with("CSOPM-1234")

    async def test_complete_unknown_reminder_type(self):
        """Test completing unknown reminder type returns False."""
        result = await self.service.complete_reminder("CSOPM-1234", "unknown_type")

        self.assertFalse(result)

    async def test_complete_reminder_not_found(self):
        """Test completing reminder when record not found."""
        self.mock_state_tracker.mark_rca_reminder_sent.return_value = None

        result = await self.service.complete_reminder("CSOPM-9999", "rca_reminder")

        self.assertFalse(result)


class TestSnoozeClosureReminder(unittest.IsolatedAsyncioTestCase):
    """Test snooze_closure_reminder method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
        )

    async def test_snooze_closure_reminder_success(self):
        """Test snoozing closure reminder."""
        result = await self.service.snooze_closure_reminder("CSOPM-1234", snooze_days=7)

        self.assertTrue(result)

    async def test_snooze_closure_reminder_custom_days(self):
        """Test snoozing closure reminder with custom duration."""
        result = await self.service.snooze_closure_reminder("CSOPM-1234", snooze_days=14)

        self.assertTrue(result)


class TestCloseTicketViaReminder(unittest.IsolatedAsyncioTestCase):
    """Test close_ticket_via_reminder method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.mock_metrics = MockMetrics()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
            metrics=self.mock_metrics,
        )

    async def test_close_ticket_success(self):
        """Test successfully closing a ticket via reminder."""
        self.mock_mcp_client._call_mcp_tool.return_value = {"success": True}
        self.mock_state_tracker.get_notification_record.return_value = make_notification_record(
            closure_reminder_sent=False
        )
        self.mock_state_tracker.mark_closure_reminder_sent.return_value = make_notification_record(
            closure_reminder_sent=True
        )

        result = await self.service.close_ticket_via_reminder("CSOPM-1234")

        self.assertTrue(result)
        self.mock_mcp_client._call_mcp_tool.assert_called_once_with(
            "transition_jira_status_by_name",
            {"issueIdOrKey": "CSOPM-1234", "statusName": "Closed"},
        )
        self.mock_state_tracker.mark_closure_reminder_sent.assert_called_once()

    async def test_close_ticket_increments_metric_when_closure_reminder_sent(self):
        """Test that closing a ticket increments csopm_closed_via_reminder when closure_reminder_sent was true."""
        self.mock_mcp_client._call_mcp_tool.return_value = {"success": True}
        # The record already had closure_reminder_sent=True before this close
        self.mock_state_tracker.get_notification_record.return_value = make_notification_record(
            closure_reminder_sent=True
        )
        self.mock_state_tracker.mark_closure_reminder_sent.return_value = make_notification_record(
            closure_reminder_sent=True
        )

        result = await self.service.close_ticket_via_reminder("CSOPM-1234")

        self.assertTrue(result)
        # Should increment the metric because closure_reminder_sent was true
        self.mock_metrics.increment_counter.assert_called_once_with("csopm_closed_via_reminder")

    async def test_close_ticket_does_not_increment_metric_when_closure_reminder_not_sent(self):
        """Test that closing a ticket does not increment metric when closure_reminder_sent was false."""
        self.mock_mcp_client._call_mcp_tool.return_value = {"success": True}
        # The record had closure_reminder_sent=False before this close
        self.mock_state_tracker.get_notification_record.return_value = make_notification_record(
            closure_reminder_sent=False
        )
        self.mock_state_tracker.mark_closure_reminder_sent.return_value = make_notification_record(
            closure_reminder_sent=True
        )

        result = await self.service.close_ticket_via_reminder("CSOPM-1234")

        self.assertTrue(result)
        # Should NOT increment the metric because closure_reminder_sent was false
        self.mock_metrics.increment_counter.assert_not_called()

    async def test_close_ticket_failure(self):
        """Test handling failure when closing a ticket."""
        self.mock_state_tracker.get_notification_record.return_value = make_notification_record(
            closure_reminder_sent=True
        )
        self.mock_mcp_client._call_mcp_tool.return_value = {
            "success": False,
            "message": "Transition not available",
        }

        result = await self.service.close_ticket_via_reminder("CSOPM-1234")

        self.assertFalse(result)
        # Should NOT increment metric on failure
        self.mock_metrics.increment_counter.assert_not_called()

    async def test_close_ticket_error(self):
        """Test handling error when closing a ticket."""
        self.mock_mcp_client._call_mcp_tool.side_effect = Exception("MCP error")

        result = await self.service.close_ticket_via_reminder("CSOPM-1234")

        self.assertFalse(result)


class TestGetDueReminders(unittest.IsolatedAsyncioTestCase):
    """Test get_due_reminders method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
        )

    async def test_get_due_reminders_returns_both_types(self):
        """Test get_due_reminders returns both RCA and closure reminders."""
        records = [
            make_notification_record(
                "CSOPM-1001", rca_reminder_sent=False, closure_reminder_sent=False
            ),
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        result = await self.service.get_due_reminders()

        # Should return 2 reminders (1 RCA + 1 closure)
        self.assertEqual(len(result), 2)
        types = [r.followup_type for r in result]
        self.assertIn("rca_reminder", types)
        self.assertIn("closure_reminder", types)

    async def test_get_due_reminders_skips_sent(self):
        """Test get_due_reminders skips already sent reminders."""
        records = [
            make_notification_record(
                "CSOPM-1001", rca_reminder_sent=True, closure_reminder_sent=True
            ),
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        result = await self.service.get_due_reminders()

        self.assertEqual(len(result), 0)

    async def test_get_due_reminders_on_error(self):
        """Test get_due_reminders returns empty list on error."""
        self.mock_state_tracker.get_all_active_notifications.side_effect = Exception("DB error")

        result = await self.service.get_due_reminders()

        self.assertEqual(result, [])


class TestReminderConstants(unittest.TestCase):
    """Test reminder timing constants."""

    def test_rca_reminder_threshold(self):
        """Test RCA reminder threshold is 7 days."""
        from ketchup_csopm_notifier.services.reminder_service import (
            RCA_REMINDER_THRESHOLD_DAYS,
        )

        self.assertEqual(RCA_REMINDER_THRESHOLD_DAYS, 7)

    def test_closure_reminder_threshold(self):
        """Test closure reminder threshold is 45 days."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CLOSURE_REMINDER_THRESHOLD_DAYS,
        )

        self.assertEqual(CLOSURE_REMINDER_THRESHOLD_DAYS, 45)

    def test_max_ping_count(self):
        """Test maximum ping count is 3."""
        from ketchup_csopm_notifier.services.reminder_service import MAX_PING_COUNT

        self.assertEqual(MAX_PING_COUNT, 3)


class TestJQLConstruction(unittest.TestCase):
    """Test JQL query construction."""

    def test_linked_tickets_jql_format(self):
        """Test linked tickets JQL uses correct format."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        jql = CSOPMReminderService.LINKED_TICKETS_JQL.format(ticket_key="CSOPM-1234")

        self.assertIn("linkedIssues('CSOPM-1234')", jql)
        self.assertIn("NOT IN ('Closed', 'Done', 'Resolved')", jql)


class MockStatusPoller:
    """Mock CSOPMTicketStatusPollerProtocol for testing."""

    def __init__(self) -> None:
        self.get_followup_statuses = AsyncMock()
        self.poll_ticket_status = AsyncMock()
        self.poll_all_active_tickets = AsyncMock()
        self.check_followup_completion = AsyncMock()


class TestGetOpenFollowupTickets(unittest.IsolatedAsyncioTestCase):
    """Test _get_open_followup_tickets method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.mock_status_poller = MockStatusPoller()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
            status_poller=self.mock_status_poller,
        )

    async def test_returns_empty_list_when_no_followups(self):
        """Test returns empty list when record has no followup_ticket_keys."""
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=[],
        )

        result = await self.service._get_open_followup_tickets(record)

        self.assertEqual(result, [])

    async def test_returns_open_followups_via_status_poller(self):
        """Test returns open followups using status poller data."""
        from packages.core.typed_di.protocols import StatusCheckResult

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=["CAMP-123", "CPGNTT-456"],
        )

        # Mock status poller to return mixed statuses
        self.mock_status_poller.get_followup_statuses.return_value = {
            "CAMP-123": StatusCheckResult(
                ticket_key="CAMP-123",
                current_status="In Progress",
                was_completed=False,
                was_closed=False,
                is_followup=True,
            ),
            "CPGNTT-456": StatusCheckResult(
                ticket_key="CPGNTT-456",
                current_status="Closed",
                was_completed=True,
                was_closed=True,
                is_followup=True,
            ),
        }

        result = await self.service._get_open_followup_tickets(record)

        # Should only return non-terminal status (not Closed)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "CAMP-123")
        self.assertEqual(result[0]["status"], "In Progress")

    async def test_falls_back_to_direct_query_on_poller_error(self):
        """Test falls back to direct JIRA query when status poller fails."""
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=["CAMP-123"],
        )

        # Make status poller fail
        self.mock_status_poller.get_followup_statuses.side_effect = Exception("Poller error")

        # Mock direct JIRA query
        self.mock_mcp_client.get_issue.return_value = {
            "key": "CAMP-123",
            "fields": {"status": {"name": "Open"}},
        }

        result = await self.service._get_open_followup_tickets(record)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "CAMP-123")
        self.assertEqual(result[0]["status"], "Open")

    async def test_filters_terminal_statuses(self):
        """Test filters out tickets with terminal statuses."""
        from packages.core.typed_di.protocols import StatusCheckResult

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=["CAMP-1", "CAMP-2", "CAMP-3", "CAMP-4"],
        )

        # Mock status poller with various terminal statuses
        self.mock_status_poller.get_followup_statuses.return_value = {
            "CAMP-1": StatusCheckResult(
                ticket_key="CAMP-1",
                current_status="Closed",
                was_completed=False,
                was_closed=True,
                is_followup=True,
            ),
            "CAMP-2": StatusCheckResult(
                ticket_key="CAMP-2",
                current_status="Done",
                was_completed=True,
                was_closed=False,
                is_followup=True,
            ),
            "CAMP-3": StatusCheckResult(
                ticket_key="CAMP-3",
                current_status="Resolved",
                was_completed=True,
                was_closed=False,
                is_followup=True,
            ),
            "CAMP-4": StatusCheckResult(
                ticket_key="CAMP-4",
                current_status="In Progress",
                was_completed=False,
                was_closed=False,
                is_followup=True,
            ),
        }

        result = await self.service._get_open_followup_tickets(record)

        # Should only return CAMP-4 which is not terminal (not Closed/Done/Resolved)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "CAMP-4")
        self.assertEqual(result[0]["status"], "In Progress")


class TestClosureReminderOptionB(unittest.IsolatedAsyncioTestCase):
    """Test Option B closure reminder behavior (send reminder with open followups info)."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        self.mock_state_tracker = MockStateTracker()
        self.mock_mcp_client = MockMCPClient()
        self.mock_status_poller = MockStatusPoller()
        self.service = CSOPMReminderService(
            state_tracker=self.mock_state_tracker,
            mcp_client=self.mock_mcp_client,
            status_poller=self.mock_status_poller,
        )

    async def test_process_closure_reminder_always_sends_option_b(self):
        """Test closure reminder is always sent even with open followups (Option B)."""
        from packages.core.typed_di.protocols import StatusCheckResult

        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))

        # Set up notification record with open followups
        record = NotificationRecord(
            ticket_key=ticket.key,
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=["CAMP-123"],
        )
        self.mock_state_tracker.get_notification_record.return_value = record

        # Mock status poller with open followup
        self.mock_status_poller.get_followup_statuses.return_value = {
            "CAMP-123": StatusCheckResult(
                ticket_key="CAMP-123",
                current_status="In Progress",
                was_completed=False,
                was_closed=False,
                is_followup=True,
            ),
        }

        # Also has open linked tickets in JIRA
        self.mock_mcp_client.search_issues.return_value = {"issues": [{"key": "LINKED-1"}]}

        result = await self.service.process_closure_reminder(ticket, closure_ping_count=0)

        # Option B: Should still send the reminder
        self.assertIsNotNone(result)
        self.assertTrue(result["sent"])
        self.assertTrue(result["has_open_linked"])
        self.assertEqual(len(result["open_followups"]), 1)
        self.assertEqual(result["open_followups"][0]["key"], "CAMP-123")
        self.assertEqual(result["open_followups"][0]["status"], "In Progress")

    async def test_process_closure_reminder_includes_open_followups(self):
        """Test closure reminder includes open followups in result."""
        from packages.core.typed_di.protocols import StatusCheckResult

        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))

        record = NotificationRecord(
            ticket_key=ticket.key,
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=["CAMP-123", "CPGNTT-456"],
        )
        self.mock_state_tracker.get_notification_record.return_value = record

        # Two open followups
        self.mock_status_poller.get_followup_statuses.return_value = {
            "CAMP-123": StatusCheckResult(
                ticket_key="CAMP-123",
                current_status="In Progress",
                was_completed=False,
                was_closed=False,
                is_followup=True,
            ),
            "CPGNTT-456": StatusCheckResult(
                ticket_key="CPGNTT-456",
                current_status="Open",
                was_completed=False,
                was_closed=False,
                is_followup=True,
            ),
        }
        self.mock_mcp_client.search_issues.return_value = {"issues": []}

        result = await self.service.process_closure_reminder(ticket, closure_ping_count=0)

        self.assertEqual(len(result["open_followups"]), 2)

    async def test_check_closure_reminders_includes_tickets_with_open_linked(self):
        """Test check_closure_reminders includes tickets with open linked (Option B)."""
        records = [
            make_notification_record("CSOPM-1001", closure_reminder_sent=False),
        ]
        self.mock_state_tracker.get_all_active_notifications.return_value = records

        # Mock ticket details with 50-day old ticket
        old_ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))
        self.mock_mcp_client.get_issue.return_value = {
            "key": "CSOPM-1001",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "assignee": {"name": "testuser"},
                "created": old_ticket.created_at.isoformat(),
            },
        }

        # Note: Option B does NOT check for linked tickets in check_closure_reminders
        # So we don't need to mock search_issues here

        result = await self.service.check_closure_reminders()

        # Should return the ticket regardless of linked status
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ticket_key, "CSOPM-1001")

    async def test_process_closure_reminder_empty_followups_no_linked(self):
        """Test closure reminder works with no followups and no linked tickets."""
        ticket = make_ticket(created_at=datetime.now(timezone.utc) - timedelta(days=50))

        record = NotificationRecord(
            ticket_key=ticket.key,
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            followup_ticket_keys=[],
        )
        self.mock_state_tracker.get_notification_record.return_value = record
        self.mock_mcp_client.search_issues.return_value = {"issues": []}

        result = await self.service.process_closure_reminder(ticket, closure_ping_count=0)

        self.assertIsNotNone(result)
        self.assertTrue(result["sent"])
        self.assertFalse(result["has_open_linked"])
        self.assertEqual(result["open_followups"], [])
        self.assertEqual(result["new_ping_count"], 1)


if __name__ == "__main__":
    unittest.main()
