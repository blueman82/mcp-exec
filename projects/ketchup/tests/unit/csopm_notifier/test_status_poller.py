#!/usr/bin/env python3
"""
CSOPM Ticket Status Poller Tests.

Unit tests for the CSOPMTicketStatusPoller service, verifying:
1. Protocol compliance with CSOPMTicketStatusPollerProtocol
2. Status extraction from JIRA issue data
3. Terminal status classification (completed vs closed)
4. Batch fetching and state updates
5. Error handling for various edge cases
"""

import unittest
from unittest.mock import AsyncMock

from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
    CSOPMTicketStatusPollerProtocol,
    NotificationRecord,
    StatusCheckResult,
)


class MockAsyncMCPClient:
    """Mock AsyncMCPClient for testing."""

    def __init__(self) -> None:
        self.get_issue = AsyncMock()
        self.get_issues_batch = AsyncMock()
        self.search_issues = AsyncMock()


class MockStateTracker:
    """Mock CSOPMStateTracker for testing."""

    def __init__(self) -> None:
        self.get_all_notification_records = AsyncMock()
        self.mark_completed = AsyncMock()
        self.mark_closed = AsyncMock()


class TestCSOPMTicketStatusPollerProtocolCompliance(unittest.TestCase):
    """Test that CSOPMTicketStatusPoller implements the protocol correctly."""

    def test_implements_protocol(self):
        """Test CSOPMTicketStatusPoller implements CSOPMTicketStatusPollerProtocol."""
        from ketchup_csopm_notifier.services.status_poller import CSOPMTicketStatusPoller

        # Verify it's recognized as implementing the protocol
        mock_mcp = MockAsyncMCPClient()
        mock_state = MockStateTracker()
        poller = CSOPMTicketStatusPoller(mcp_client=mock_mcp, state_tracker=mock_state)

        self.assertIsInstance(poller, CSOPMTicketStatusPollerProtocol)

    def test_has_poll_ticket_statuses_method(self):
        """Test CSOPMTicketStatusPoller has poll_ticket_statuses method."""
        from ketchup_csopm_notifier.services.status_poller import CSOPMTicketStatusPoller

        self.assertTrue(hasattr(CSOPMTicketStatusPoller, "poll_ticket_statuses"))

    def test_has_get_ticket_status_method(self):
        """Test CSOPMTicketStatusPoller has get_ticket_status method."""
        from ketchup_csopm_notifier.services.status_poller import CSOPMTicketStatusPoller

        self.assertTrue(hasattr(CSOPMTicketStatusPoller, "get_ticket_status"))


class TestCSOPMTicketStatusPollerStatusExtraction(unittest.TestCase):
    """Test status extraction from JIRA issue data."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.status_poller import CSOPMTicketStatusPoller

        self.mock_mcp = MockAsyncMCPClient()
        self.mock_state = MockStateTracker()
        self.poller = CSOPMTicketStatusPoller(
            mcp_client=self.mock_mcp,
            state_tracker=self.mock_state,
        )

    def test_get_status_from_issue_success(self):
        """Test extracting status from a valid issue."""
        issue = {
            "key": "CSOPM-1234",
            "fields": {
                "status": {"name": "Complete"},
            },
        }

        result = self.poller._get_status_from_issue(issue)

        self.assertEqual(result, "Complete")

    def test_get_status_from_issue_none(self):
        """Test extracting status from None returns None."""
        result = self.poller._get_status_from_issue(None)

        self.assertIsNone(result)

    def test_get_status_from_issue_missing_fields(self):
        """Test extracting status from issue with missing fields."""
        issue = {"key": "CSOPM-1234"}

        result = self.poller._get_status_from_issue(issue)

        self.assertIsNone(result)

    def test_get_status_from_issue_missing_status(self):
        """Test extracting status from issue with missing status field."""
        issue = {
            "key": "CSOPM-1234",
            "fields": {},
        }

        result = self.poller._get_status_from_issue(issue)

        self.assertIsNone(result)


class TestCSOPMTicketStatusPollerStatusClassification(unittest.TestCase):
    """Test terminal status classification."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.status_poller import CSOPMTicketStatusPoller

        self.mock_mcp = MockAsyncMCPClient()
        self.mock_state = MockStateTracker()
        self.poller = CSOPMTicketStatusPoller(
            mcp_client=self.mock_mcp,
            state_tracker=self.mock_state,
        )

    def test_is_completed_status_complete(self):
        """Test that 'Complete' is recognized as completed."""
        self.assertTrue(self.poller._is_completed_status("Complete"))

    def test_is_completed_status_not_complete(self):
        """Test that other statuses are not recognized as completed."""
        self.assertFalse(self.poller._is_completed_status("In Progress"))
        self.assertFalse(self.poller._is_completed_status("Closed"))
        self.assertFalse(self.poller._is_completed_status("New"))

    def test_is_closed_status_closed(self):
        """Test that 'Closed' is recognized as closed."""
        self.assertTrue(self.poller._is_closed_status("Closed"))

    def test_is_closed_status_done(self):
        """Test that 'Done' is recognized as closed."""
        self.assertTrue(self.poller._is_closed_status("Done"))

    def test_is_closed_status_resolved(self):
        """Test that 'Resolved' is recognized as closed."""
        self.assertTrue(self.poller._is_closed_status("Resolved"))

    def test_is_closed_status_not_closed(self):
        """Test that other statuses are not recognized as closed."""
        self.assertFalse(self.poller._is_closed_status("In Progress"))
        self.assertFalse(self.poller._is_closed_status("Complete"))
        self.assertFalse(self.poller._is_closed_status("New"))


class TestCSOPMTicketStatusPollerPollTicketStatuses(unittest.IsolatedAsyncioTestCase):
    """Test poll_ticket_statuses method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.status_poller import CSOPMTicketStatusPoller

        self.mock_mcp = MockAsyncMCPClient()
        self.mock_state = MockStateTracker()
        self.poller = CSOPMTicketStatusPoller(
            mcp_client=self.mock_mcp,
            state_tracker=self.mock_state,
        )

    async def test_poll_ticket_statuses_no_records(self):
        """Test polling returns empty results when no records exist."""
        self.mock_state.get_all_notification_records.return_value = []

        result = await self.poller.poll_ticket_statuses()

        self.assertEqual(result, {})

    async def test_poll_ticket_statuses_marks_completed(self):
        """Test polling marks tickets as completed when status is Complete."""
        # Set up notification record without completed_at
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            completed_at=None,
            closed_at=None,
        )
        self.mock_state.get_all_notification_records.return_value = [record]

        # Set up JIRA response with Complete status
        self.mock_mcp.get_issues_batch.return_value = {
            "CSOPM-1234": {
                "key": "CSOPM-1234",
                "fields": {"status": {"name": "Complete"}},
            }
        }
        self.mock_state.mark_completed.return_value = True

        result = await self.poller.poll_ticket_statuses()

        self.assertIn("CSOPM-1234", result)
        self.assertTrue(result["CSOPM-1234"].was_completed)
        self.assertFalse(result["CSOPM-1234"].was_closed)
        self.mock_state.mark_completed.assert_called_once_with("CSOPM-1234")
        self.mock_state.mark_closed.assert_not_called()

    async def test_poll_ticket_statuses_marks_closed(self):
        """Test polling marks tickets as closed when status is Closed."""
        # Set up notification record without closed_at
        record = NotificationRecord(
            ticket_key="CSOPM-5678",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            completed_at=None,
            closed_at=None,
        )
        self.mock_state.get_all_notification_records.return_value = [record]

        # Set up JIRA response with Closed status
        self.mock_mcp.get_issues_batch.return_value = {
            "CSOPM-5678": {
                "key": "CSOPM-5678",
                "fields": {"status": {"name": "Closed"}},
            }
        }
        self.mock_state.mark_closed.return_value = True

        result = await self.poller.poll_ticket_statuses()

        self.assertIn("CSOPM-5678", result)
        self.assertFalse(result["CSOPM-5678"].was_completed)
        self.assertTrue(result["CSOPM-5678"].was_closed)
        self.mock_state.mark_completed.assert_not_called()
        self.mock_state.mark_closed.assert_called_once_with("CSOPM-5678")

    async def test_poll_ticket_statuses_skips_already_completed(self):
        """Test polling skips tickets that are already marked as completed."""
        # Set up notification record with completed_at already set
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            completed_at=1700000000,  # Already completed
            closed_at=None,
        )
        self.mock_state.get_all_notification_records.return_value = [record]

        # Set up JIRA response with Complete status
        self.mock_mcp.get_issues_batch.return_value = {
            "CSOPM-1234": {
                "key": "CSOPM-1234",
                "fields": {"status": {"name": "Complete"}},
            }
        }

        result = await self.poller.poll_ticket_statuses()

        self.assertIn("CSOPM-1234", result)
        self.assertFalse(result["CSOPM-1234"].was_completed)
        self.mock_state.mark_completed.assert_not_called()

    async def test_poll_ticket_statuses_skips_already_closed(self):
        """Test polling skips tickets that are already marked as closed."""
        # Set up notification record with closed_at already set
        record = NotificationRecord(
            ticket_key="CSOPM-5678",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            completed_at=None,
            closed_at=1700000000,  # Already closed
        )
        self.mock_state.get_all_notification_records.return_value = [record]

        # Set up JIRA response with Closed status
        self.mock_mcp.get_issues_batch.return_value = {
            "CSOPM-5678": {
                "key": "CSOPM-5678",
                "fields": {"status": {"name": "Closed"}},
            }
        }

        result = await self.poller.poll_ticket_statuses()

        self.assertIn("CSOPM-5678", result)
        self.assertFalse(result["CSOPM-5678"].was_closed)
        self.mock_state.mark_closed.assert_not_called()

    async def test_poll_ticket_statuses_handles_in_progress_status(self):
        """Test polling handles non-terminal statuses correctly."""
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            completed_at=None,
            closed_at=None,
        )
        self.mock_state.get_all_notification_records.return_value = [record]

        # Set up JIRA response with In Progress status
        self.mock_mcp.get_issues_batch.return_value = {
            "CSOPM-1234": {
                "key": "CSOPM-1234",
                "fields": {"status": {"name": "In Progress"}},
            }
        }

        result = await self.poller.poll_ticket_statuses()

        self.assertIn("CSOPM-1234", result)
        self.assertEqual(result["CSOPM-1234"].current_status, "In Progress")
        self.assertFalse(result["CSOPM-1234"].was_completed)
        self.assertFalse(result["CSOPM-1234"].was_closed)
        self.mock_state.mark_completed.assert_not_called()
        self.mock_state.mark_closed.assert_not_called()

    async def test_poll_ticket_statuses_handles_missing_issue(self):
        """Test polling handles case where issue is not found in JIRA."""
        record = NotificationRecord(
            ticket_key="CSOPM-9999",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            completed_at=None,
            closed_at=None,
        )
        self.mock_state.get_all_notification_records.return_value = [record]

        # Set up JIRA response with None for the issue
        self.mock_mcp.get_issues_batch.return_value = {
            "CSOPM-9999": None,
        }

        result = await self.poller.poll_ticket_statuses()

        self.assertIn("CSOPM-9999", result)
        self.assertIsNone(result["CSOPM-9999"].current_status)
        self.assertFalse(result["CSOPM-9999"].was_completed)
        self.assertFalse(result["CSOPM-9999"].was_closed)

    async def test_poll_ticket_statuses_includes_followup_tickets(self):
        """Test polling includes followup tickets in batch fetch."""
        # Set up notification record with followup ticket keys
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            completed_at=None,
            closed_at=None,
            followup_ticket_keys=["CSOPM-5678", "CSOPM-9012"],
        )
        self.mock_state.get_all_notification_records.return_value = [record]

        # Set up JIRA response
        self.mock_mcp.get_issues_batch.return_value = {
            "CSOPM-1234": {
                "key": "CSOPM-1234",
                "fields": {"status": {"name": "In Progress"}},
            },
            "CSOPM-5678": {
                "key": "CSOPM-5678",
                "fields": {"status": {"name": "Closed"}},
            },
            "CSOPM-9012": {
                "key": "CSOPM-9012",
                "fields": {"status": {"name": "Complete"}},
            },
        }

        result = await self.poller.poll_ticket_statuses()

        # Verify batch fetch was called with all keys
        call_args = self.mock_mcp.get_issues_batch.call_args
        issue_keys = call_args.kwargs.get("issue_keys", [])
        self.assertIn("CSOPM-1234", issue_keys)
        self.assertIn("CSOPM-5678", issue_keys)
        self.assertIn("CSOPM-9012", issue_keys)

        # Verify results include followup tickets
        self.assertIn("CSOPM-5678", result)
        self.assertIn("CSOPM-9012", result)
        self.assertTrue(result["CSOPM-5678"].is_followup)
        self.assertTrue(result["CSOPM-9012"].is_followup)


class TestCSOPMTicketStatusPollerGetTicketStatus(unittest.IsolatedAsyncioTestCase):
    """Test get_ticket_status method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.status_poller import CSOPMTicketStatusPoller

        self.mock_mcp = MockAsyncMCPClient()
        self.mock_state = MockStateTracker()
        self.poller = CSOPMTicketStatusPoller(
            mcp_client=self.mock_mcp,
            state_tracker=self.mock_state,
        )

    async def test_get_ticket_status_success(self):
        """Test getting status for a single ticket."""
        self.mock_mcp.get_issue.return_value = {
            "key": "CSOPM-1234",
            "fields": {"status": {"name": "In Progress"}},
        }

        result = await self.poller.get_ticket_status("CSOPM-1234")

        self.assertEqual(result, "In Progress")

    async def test_get_ticket_status_not_found(self):
        """Test getting status for a non-existent ticket."""
        self.mock_mcp.get_issue.return_value = None

        result = await self.poller.get_ticket_status("CSOPM-9999")

        self.assertIsNone(result)

    async def test_get_ticket_status_error(self):
        """Test getting status handles errors gracefully."""
        self.mock_mcp.get_issue.side_effect = Exception("API Error")

        result = await self.poller.get_ticket_status("CSOPM-1234")

        self.assertIsNone(result)


class TestStatusCheckResultDataclass(unittest.TestCase):
    """Test StatusCheckResult dataclass."""

    def test_status_check_result_defaults(self):
        """Test StatusCheckResult default values."""
        result = StatusCheckResult(
            ticket_key="CSOPM-1234",
            current_status="Complete",
            was_completed=True,
            was_closed=False,
        )

        self.assertEqual(result.ticket_key, "CSOPM-1234")
        self.assertEqual(result.current_status, "Complete")
        self.assertTrue(result.was_completed)
        self.assertFalse(result.was_closed)
        self.assertFalse(result.is_followup)  # Default

    def test_status_check_result_followup_flag(self):
        """Test StatusCheckResult with is_followup flag."""
        result = StatusCheckResult(
            ticket_key="CSOPM-5678",
            current_status="Closed",
            was_completed=False,
            was_closed=True,
            is_followup=True,
        )

        self.assertTrue(result.is_followup)


if __name__ == "__main__":
    unittest.main()
