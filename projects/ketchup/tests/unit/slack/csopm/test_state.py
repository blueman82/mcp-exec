#!/usr/bin/env python3
"""
CSOPM State Tracker Tests.

Unit tests for the CSOPMStateTracker service, verifying:
1. Protocol compliance with CSOPMStateTrackerProtocol
2. DynamoDB operations for notification records
3. Followup record management
4. Reassignment handling with history tracking
5. Error handling for database operations

These tests were moved from tests/unit/csopm_notifier/test_state_tracker.py
to align with the new package structure in packages/slack/csopm/state.py.
"""

import unittest
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock

from packages.core.typed_di.protocols import (
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
    FollowupRecord,
    NotificationRecord,
)


class MockDynamoDBAsyncClient:
    """Mock DynamoDBAsyncClient for testing."""

    def __init__(self) -> None:
        self.get_item = AsyncMock()
        self.put_item = AsyncMock()
        self.update_item = AsyncMock()
        self.scan = AsyncMock()
        self.query = AsyncMock()
        self.delete_item = AsyncMock()


class TestCSOPMStateTrackerProtocolCompliance(unittest.TestCase):
    """Test that CSOPMStateTracker implements the protocol correctly."""

    def test_implements_protocol(self):
        """Test CSOPMStateTracker implements CSOPMStateTrackerProtocol."""
        from packages.slack.csopm.state import CSOPMStateTracker

        # Verify it's recognized as implementing the protocol
        mock_client = MockDynamoDBAsyncClient()
        tracker = CSOPMStateTracker(client=mock_client, table_name="test-table")

        self.assertIsInstance(tracker, CSOPMStateTrackerProtocol)

    def test_has_get_notification_record_method(self):
        """Test CSOPMStateTracker has get_notification_record method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "get_notification_record"))

    def test_has_create_notification_record_method(self):
        """Test CSOPMStateTracker has create_notification_record method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "create_notification_record"))

    def test_has_update_notification_status_method(self):
        """Test CSOPMStateTracker has update_notification_status method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "update_notification_status"))

    def test_has_increment_rca_ping_count_method(self):
        """Test CSOPMStateTracker has increment_rca_ping_count method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "increment_rca_ping_count"))

    def test_has_increment_closure_ping_count_method(self):
        """Test CSOPMStateTracker has increment_closure_ping_count method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "increment_closure_ping_count"))

    def test_has_mark_rca_reminder_sent_method(self):
        """Test CSOPMStateTracker has mark_rca_reminder_sent method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "mark_rca_reminder_sent"))

    def test_has_mark_closure_reminder_sent_method(self):
        """Test CSOPMStateTracker has mark_closure_reminder_sent method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "mark_closure_reminder_sent"))

    def test_has_get_pending_notifications_method(self):
        """Test CSOPMStateTracker has get_pending_notifications method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "get_pending_notifications"))

    def test_has_record_followup_method(self):
        """Test CSOPMStateTracker has record_followup method."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.assertTrue(hasattr(CSOPMStateTracker, "record_followup"))


class TestCSOPMStateTrackerKeyGeneration(unittest.TestCase):
    """Test DynamoDB key generation."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    def test_make_pk_format(self):
        """Test partition key is generated correctly."""
        pk = self.tracker._make_pk("CSOPM-1234")
        self.assertEqual(pk, "CSOPM_NOTIFICATION#CSOPM-1234")

    def test_make_followup_sk_format(self):
        """Test followup sort key is generated correctly."""
        scheduled_at = datetime(2024, 1, 15, 10, 30, 0)
        sk = self.tracker._make_followup_sk("rca_reminder", scheduled_at)

        expected_timestamp = int(scheduled_at.timestamp())
        self.assertEqual(sk, f"FOLLOWUP#rca_reminder#{expected_timestamp}")


class TestCSOPMStateTrackerItemParsing(unittest.TestCase):
    """Test DynamoDB item parsing."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    def test_item_to_notification_record(self):
        """Test converting DynamoDB item to NotificationRecord."""
        item = {
            "PK": {"S": "CSOPM_NOTIFICATION#CSOPM-1234"},
            "SK": {"S": "NOTIFICATION"},
            "ticket_key": {"S": "CSOPM-1234"},
            "notification_status": {"S": "sent"},
            "rca_ping_count": {"N": "2"},
            "closure_ping_count": {"N": "0"},
            "assignee_slack_id": {"S": "U12345678"},
            "rca_reminder_sent": {"BOOL": True},
            "closure_reminder_sent": {"BOOL": False},
        }

        result = self.tracker._item_to_notification_record(item)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, NotificationRecord)
        self.assertEqual(result.ticket_key, "CSOPM-1234")
        self.assertEqual(result.notification_status, "sent")
        self.assertEqual(result.rca_ping_count, 2)
        self.assertEqual(result.assignee_slack_id, "U12345678")
        self.assertTrue(result.rca_reminder_sent)
        self.assertFalse(result.closure_reminder_sent)

    def test_item_to_notification_record_defaults(self):
        """Test parsing with missing optional fields uses defaults."""
        item = {
            "ticket_key": {"S": "CSOPM-5678"},
        }

        result = self.tracker._item_to_notification_record(item)

        self.assertIsNotNone(result)
        self.assertEqual(result.ticket_key, "CSOPM-5678")
        self.assertEqual(result.notification_status, "pending")
        self.assertEqual(result.rca_ping_count, 0)
        self.assertFalse(result.rca_reminder_sent)
        self.assertFalse(result.closure_reminder_sent)

    def test_item_to_followup_record(self):
        """Test converting DynamoDB item to FollowupRecord."""
        scheduled_time = int(datetime(2024, 1, 15, 10, 30, 0).timestamp())
        completed_time = int(datetime(2024, 1, 15, 12, 0, 0).timestamp())

        item = {
            "PK": {"S": "CSOPM_NOTIFICATION#CSOPM-1234"},
            "SK": {"S": f"FOLLOWUP#rca_reminder#{scheduled_time}"},
            "ticket_key": {"S": "CSOPM-1234"},
            "followup_type": {"S": "rca_reminder"},
            "scheduled_at": {"N": str(scheduled_time)},
            "completed": {"BOOL": True},
            "completed_at": {"N": str(completed_time)},
        }

        result = self.tracker._item_to_followup_record(item)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, FollowupRecord)
        self.assertEqual(result.ticket_key, "CSOPM-1234")
        self.assertEqual(result.followup_type, "rca_reminder")
        self.assertTrue(result.completed)
        self.assertIsNotNone(result.completed_at)

    def test_item_to_followup_record_not_completed(self):
        """Test parsing followup record that is not completed."""
        scheduled_time = int(datetime(2024, 1, 15, 10, 30, 0).timestamp())

        item = {
            "ticket_key": {"S": "CSOPM-1234"},
            "followup_type": {"S": "closure_reminder"},
            "scheduled_at": {"N": str(scheduled_time)},
            "completed": {"BOOL": False},
        }

        result = self.tracker._item_to_followup_record(item)

        self.assertIsNotNone(result)
        self.assertFalse(result.completed)
        self.assertIsNone(result.completed_at)


class TestCSOPMStateTrackerGetNotificationRecord(unittest.IsolatedAsyncioTestCase):
    """Test get_notification_record method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_get_notification_record_found(self):
        """Test get_notification_record returns record when found."""
        self.mock_client.get_item.return_value = {
            "Item": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "1"},
                "closure_ping_count": {"N": "0"},
                "assignee_slack_id": {"S": "U12345678"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        result = await self.tracker.get_notification_record("CSOPM-1234")

        self.assertIsNotNone(result)
        self.assertEqual(result.ticket_key, "CSOPM-1234")
        self.assertEqual(result.notification_status, "sent")

    async def test_get_notification_record_not_found(self):
        """Test get_notification_record returns None when not found."""
        self.mock_client.get_item.return_value = {}

        result = await self.tracker.get_notification_record("CSOPM-9999")

        self.assertIsNone(result)

    async def test_get_notification_record_uses_correct_key(self):
        """Test get_notification_record uses correct DynamoDB key."""
        self.mock_client.get_item.return_value = {}

        await self.tracker.get_notification_record("CSOPM-1234")

        self.mock_client.get_item.assert_called_once()
        call_args = self.mock_client.get_item.call_args

        key = call_args.kwargs.get("key", {})
        self.assertEqual(key["PK"]["S"], "CSOPM_NOTIFICATION#CSOPM-1234")
        self.assertEqual(key["SK"]["S"], "NOTIFICATION")

    async def test_get_notification_record_on_error(self):
        """Test get_notification_record returns None on error."""
        self.mock_client.get_item.side_effect = Exception("DynamoDB error")

        result = await self.tracker.get_notification_record("CSOPM-1234")

        self.assertIsNone(result)


class TestCSOPMStateTrackerCreateNotificationRecord(unittest.IsolatedAsyncioTestCase):
    """Test create_notification_record method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    def _make_ticket(
        self,
        key: str = "CSOPM-1234",
        summary: str = "Test Issue",
        assignee: str = "testuser",
        exigence_id: Optional[str] = None,
    ) -> CSOPMTicket:
        """Helper to create a CSOPMTicket."""
        return CSOPMTicket(
            key=key,
            summary=summary,
            assignee_username=assignee,
            created_at=datetime.now(),
            status="New",
            exigence_id=exigence_id,
        )

    async def test_create_notification_record_success(self):
        """Test create_notification_record creates and returns record."""
        self.mock_client.put_item.return_value = {}
        ticket = self._make_ticket()

        result = await self.tracker.create_notification_record(ticket=ticket, slack_id="U12345678")

        self.assertIsInstance(result, NotificationRecord)
        self.assertEqual(result.ticket_key, "CSOPM-1234")
        self.assertEqual(result.notification_status, "pending")
        self.assertEqual(result.rca_ping_count, 0)
        self.assertEqual(result.assignee_slack_id, "U12345678")
        self.assertFalse(result.rca_reminder_sent)
        self.assertFalse(result.closure_reminder_sent)

    async def test_create_notification_record_includes_exigence_id(self):
        """Test create_notification_record includes exigence_id when present."""
        self.mock_client.put_item.return_value = {}
        ticket = self._make_ticket(exigence_id="12345")

        await self.tracker.create_notification_record(ticket=ticket, slack_id="U12345678")

        self.mock_client.put_item.assert_called_once()
        call_args = self.mock_client.put_item.call_args
        item = call_args.kwargs.get("item", {})

        self.assertIn("exigence_id", item)
        self.assertEqual(item["exigence_id"]["S"], "12345")

    async def test_create_notification_record_without_exigence_id(self):
        """Test create_notification_record omits exigence_id when not present."""
        self.mock_client.put_item.return_value = {}
        ticket = self._make_ticket(exigence_id=None)

        await self.tracker.create_notification_record(ticket=ticket, slack_id="U12345678")

        self.mock_client.put_item.assert_called_once()
        call_args = self.mock_client.put_item.call_args
        item = call_args.kwargs.get("item", {})

        self.assertNotIn("exigence_id", item)

    async def test_create_notification_record_includes_assignee_history(self):
        """Test create_notification_record initializes assignee_history."""
        self.mock_client.put_item.return_value = {}
        ticket = self._make_ticket(assignee="jdoe")

        await self.tracker.create_notification_record(ticket=ticket, slack_id="U12345678")

        self.mock_client.put_item.assert_called_once()
        call_args = self.mock_client.put_item.call_args
        item = call_args.kwargs.get("item", {})

        self.assertIn("assignee_history", item)
        history = item["assignee_history"]["L"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["M"]["jira_username"]["S"], "jdoe")
        self.assertEqual(history[0]["M"]["slack_id"]["S"], "U12345678")

    async def test_create_notification_record_on_error(self):
        """Test create_notification_record raises on DynamoDB error."""
        self.mock_client.put_item.side_effect = Exception("DynamoDB error")
        ticket = self._make_ticket()

        with self.assertRaises(Exception):
            await self.tracker.create_notification_record(ticket=ticket, slack_id="U12345678")


class TestCSOPMStateTrackerUpdateNotificationStatus(unittest.IsolatedAsyncioTestCase):
    """Test update_notification_status method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_update_notification_status_success(self):
        """Test update_notification_status updates and returns record."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "1"},
                "closure_ping_count": {"N": "0"},
                "assignee_slack_id": {"S": "U12345678"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        result = await self.tracker.update_notification_status("CSOPM-1234", "sent")

        self.assertIsNotNone(result)
        self.assertEqual(result.notification_status, "sent")

    async def test_update_notification_status_not_found(self):
        """Test update_notification_status returns None when record not found."""
        self.mock_client.update_item.return_value = {}

        result = await self.tracker.update_notification_status("CSOPM-9999", "sent")

        self.assertIsNone(result)

    async def test_update_notification_status_uses_return_values(self):
        """Test update_notification_status requests ALL_NEW return values."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "0"},
                "closure_ping_count": {"N": "0"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        await self.tracker.update_notification_status("CSOPM-1234", "sent")

        self.mock_client.update_item.assert_called_once()
        call_args = self.mock_client.update_item.call_args

        self.assertEqual(call_args.kwargs.get("return_values"), "ALL_NEW")


class TestCSOPMStateTrackerIncrementPingCount(unittest.IsolatedAsyncioTestCase):
    """Test increment_rca_ping_count and increment_closure_ping_count methods."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_increment_rca_ping_count_success(self):
        """Test increment_rca_ping_count increments and returns updated record."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "3"},
                "closure_ping_count": {"N": "0"},
                "assignee_slack_id": {"S": "U12345678"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        result = await self.tracker.increment_rca_ping_count("CSOPM-1234")

        self.assertIsNotNone(result)
        self.assertEqual(result.rca_ping_count, 3)

    async def test_increment_rca_ping_count_uses_atomic_increment(self):
        """Test increment_rca_ping_count uses atomic ADD operation."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "pending"},
                "rca_ping_count": {"N": "1"},
                "closure_ping_count": {"N": "0"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        await self.tracker.increment_rca_ping_count("CSOPM-1234")

        call_args = self.mock_client.update_item.call_args
        update_expr = call_args.kwargs.get("update_expression", "")

        self.assertIn("rca_ping_count", update_expr)

    async def test_increment_closure_ping_count_success(self):
        """Test increment_closure_ping_count increments and returns updated record."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "0"},
                "closure_ping_count": {"N": "2"},
                "assignee_slack_id": {"S": "U12345678"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        result = await self.tracker.increment_closure_ping_count("CSOPM-1234")

        self.assertIsNotNone(result)
        self.assertEqual(result.closure_ping_count, 2)


class TestCSOPMStateTrackerReminderMethods(unittest.IsolatedAsyncioTestCase):
    """Test mark_rca_reminder_sent and mark_closure_reminder_sent methods."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_mark_rca_reminder_sent_success(self):
        """Test mark_rca_reminder_sent updates record."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "1"},
                "closure_ping_count": {"N": "0"},
                "assignee_slack_id": {"S": "U12345678"},
                "rca_reminder_sent": {"BOOL": True},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        result = await self.tracker.mark_rca_reminder_sent("CSOPM-1234")

        self.assertIsNotNone(result)
        self.assertTrue(result.rca_reminder_sent)

    async def test_mark_rca_reminder_sent_sets_timestamp(self):
        """Test mark_rca_reminder_sent includes timestamp."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "1"},
                "closure_ping_count": {"N": "0"},
                "rca_reminder_sent": {"BOOL": True},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        await self.tracker.mark_rca_reminder_sent("CSOPM-1234")

        call_args = self.mock_client.update_item.call_args
        update_expr = call_args.kwargs.get("update_expression", "")

        self.assertIn("rca_reminder_sent_at", update_expr)

    async def test_mark_closure_reminder_sent_success(self):
        """Test mark_closure_reminder_sent updates record."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "sent"},
                "rca_ping_count": {"N": "1"},
                "closure_ping_count": {"N": "0"},
                "assignee_slack_id": {"S": "U12345678"},
                "rca_reminder_sent": {"BOOL": True},
                "closure_reminder_sent": {"BOOL": True},
            }
        }

        result = await self.tracker.mark_closure_reminder_sent("CSOPM-1234")

        self.assertIsNotNone(result)
        self.assertTrue(result.closure_reminder_sent)


class TestCSOPMStateTrackerGetPendingNotifications(unittest.IsolatedAsyncioTestCase):
    """Test get_pending_notifications method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_get_pending_notifications_returns_list(self):
        """Test get_pending_notifications returns list of pending records."""
        self.mock_client.scan.return_value = {
            "Items": [
                {
                    "ticket_key": {"S": "CSOPM-1001"},
                    "notification_status": {"S": "pending"},
                    "rca_ping_count": {"N": "0"},
                    "closure_ping_count": {"N": "0"},
                    "assignee_slack_id": {"S": "U11111111"},
                    "rca_reminder_sent": {"BOOL": False},
                    "closure_reminder_sent": {"BOOL": False},
                },
                {
                    "ticket_key": {"S": "CSOPM-1002"},
                    "notification_status": {"S": "pending"},
                    "rca_ping_count": {"N": "0"},
                    "closure_ping_count": {"N": "0"},
                    "assignee_slack_id": {"S": "U22222222"},
                    "rca_reminder_sent": {"BOOL": False},
                    "closure_reminder_sent": {"BOOL": False},
                },
            ]
        }

        result = await self.tracker.get_pending_notifications()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].ticket_key, "CSOPM-1001")
        self.assertEqual(result[1].ticket_key, "CSOPM-1002")

    async def test_get_pending_notifications_empty(self):
        """Test get_pending_notifications returns empty list when none pending."""
        self.mock_client.scan.return_value = {"Items": []}

        result = await self.tracker.get_pending_notifications()

        self.assertEqual(result, [])

    async def test_get_pending_notifications_uses_correct_filter(self):
        """Test get_pending_notifications uses correct filter expression."""
        self.mock_client.scan.return_value = {"Items": []}

        await self.tracker.get_pending_notifications()

        self.mock_client.scan.assert_called_once()
        call_args = self.mock_client.scan.call_args

        filter_expr = call_args.kwargs.get("filter_expression", "")
        self.assertIn("notification_status = :status", filter_expr)
        self.assertIn("begins_with(PK, :pk_prefix)", filter_expr)

        expr_values = call_args.kwargs.get("expression_attribute_values", {})
        self.assertEqual(expr_values[":status"]["S"], "pending")

    async def test_get_pending_notifications_on_error(self):
        """Test get_pending_notifications returns empty list on error."""
        self.mock_client.scan.side_effect = Exception("DynamoDB error")

        result = await self.tracker.get_pending_notifications()

        self.assertEqual(result, [])


class TestCSOPMStateTrackerRecordFollowup(unittest.IsolatedAsyncioTestCase):
    """Test record_followup method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_record_followup_success(self):
        """Test record_followup creates and returns FollowupRecord."""
        self.mock_client.put_item.return_value = {}
        scheduled_at = datetime.now() + timedelta(hours=24)

        result = await self.tracker.record_followup(
            ticket_key="CSOPM-1234",
            followup_type="rca_reminder",
            scheduled_at=scheduled_at,
        )

        self.assertIsInstance(result, FollowupRecord)
        self.assertEqual(result.ticket_key, "CSOPM-1234")
        self.assertEqual(result.followup_type, "rca_reminder")
        self.assertFalse(result.completed)
        self.assertIsNone(result.completed_at)

    async def test_record_followup_uses_composite_sk(self):
        """Test record_followup uses composite sort key with timestamp."""
        self.mock_client.put_item.return_value = {}
        scheduled_at = datetime(2024, 1, 15, 10, 30, 0)
        expected_timestamp = int(scheduled_at.timestamp())

        await self.tracker.record_followup(
            ticket_key="CSOPM-1234",
            followup_type="closure_reminder",
            scheduled_at=scheduled_at,
        )

        self.mock_client.put_item.assert_called_once()
        call_args = self.mock_client.put_item.call_args
        item = call_args.kwargs.get("item", {})

        self.assertEqual(item["SK"]["S"], f"FOLLOWUP#closure_reminder#{expected_timestamp}")

    async def test_record_followup_on_error(self):
        """Test record_followup raises on DynamoDB error."""
        self.mock_client.put_item.side_effect = Exception("DynamoDB error")

        with self.assertRaises(Exception):
            await self.tracker.record_followup(
                ticket_key="CSOPM-1234",
                followup_type="ping",
                scheduled_at=datetime.now(),
            )


class TestCSOPMStateTrackerGetAllActiveNotifications(unittest.IsolatedAsyncioTestCase):
    """Test get_all_active_notifications method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_get_all_active_notifications_excludes_escalated(self):
        """Test get_all_active_notifications excludes escalated records."""
        self.mock_client.scan.return_value = {"Items": []}

        await self.tracker.get_all_active_notifications()

        self.mock_client.scan.assert_called_once()
        call_args = self.mock_client.scan.call_args

        filter_expr = call_args.kwargs.get("filter_expression", "")
        self.assertIn("notification_status <> :escalated_status", filter_expr)

        expr_values = call_args.kwargs.get("expression_attribute_values", {})
        self.assertEqual(expr_values[":escalated_status"]["S"], "escalated")

    async def test_get_all_active_notifications_returns_records(self):
        """Test get_all_active_notifications returns list of active records."""
        self.mock_client.scan.return_value = {
            "Items": [
                {
                    "ticket_key": {"S": "CSOPM-1001"},
                    "notification_status": {"S": "pending"},
                    "rca_ping_count": {"N": "0"},
                    "closure_ping_count": {"N": "0"},
                    "assignee_slack_id": {"S": "U11111111"},
                    "rca_reminder_sent": {"BOOL": False},
                    "closure_reminder_sent": {"BOOL": False},
                },
                {
                    "ticket_key": {"S": "CSOPM-1002"},
                    "notification_status": {"S": "sent"},
                    "rca_ping_count": {"N": "2"},
                    "closure_ping_count": {"N": "0"},
                    "assignee_slack_id": {"S": "U22222222"},
                    "rca_reminder_sent": {"BOOL": True},
                    "closure_reminder_sent": {"BOOL": False},
                },
            ]
        }

        result = await self.tracker.get_all_active_notifications()

        self.assertEqual(len(result), 2)


class TestCSOPMStateTrackerHandleReassignment(unittest.IsolatedAsyncioTestCase):
    """Test handle_reassignment method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_handle_reassignment_success(self):
        """Test handle_reassignment updates record correctly."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "pending"},
                "rca_ping_count": {"N": "1"},
                "closure_ping_count": {"N": "0"},
                "assignee_slack_id": {"S": "U99999999"},
                "assignee_jira_username": {"S": "newuser"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        result = await self.tracker.handle_reassignment(
            ticket_key="CSOPM-1234",
            new_jira_username="newuser",
            new_slack_id="U99999999",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.assignee_slack_id, "U99999999")
        self.assertEqual(result.rca_ping_count, 1)

    async def test_handle_reassignment_resets_ping_count_to_one(self):
        """Test handle_reassignment resets ping counts to 0."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "pending"},
                "rca_ping_count": {"N": "0"},
                "closure_ping_count": {"N": "0"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        await self.tracker.handle_reassignment(
            ticket_key="CSOPM-1234",
            new_jira_username="newuser",
            new_slack_id="U99999999",
        )

        call_args = self.mock_client.update_item.call_args
        expr_values = call_args.kwargs.get("expression_attribute_values", {})

        self.assertEqual(expr_values[":zero"]["N"], "0")

    async def test_handle_reassignment_appends_to_history(self):
        """Test handle_reassignment appends new assignee to history."""
        self.mock_client.update_item.return_value = {
            "Attributes": {
                "ticket_key": {"S": "CSOPM-1234"},
                "notification_status": {"S": "pending"},
                "rca_ping_count": {"N": "0"},
                "closure_ping_count": {"N": "0"},
                "rca_reminder_sent": {"BOOL": False},
                "closure_reminder_sent": {"BOOL": False},
            }
        }

        await self.tracker.handle_reassignment(
            ticket_key="CSOPM-1234",
            new_jira_username="newuser",
            new_slack_id="U99999999",
        )

        call_args = self.mock_client.update_item.call_args
        update_expr = call_args.kwargs.get("update_expression", "")

        self.assertIn("list_append", update_expr)
        self.assertIn("assignee_history", update_expr)

    async def test_handle_reassignment_not_found(self):
        """Test handle_reassignment returns None when record not found."""
        self.mock_client.update_item.return_value = {}

        result = await self.tracker.handle_reassignment(
            ticket_key="CSOPM-9999",
            new_jira_username="newuser",
            new_slack_id="U99999999",
        )

        self.assertIsNone(result)


class TestCSOPMStateTrackerDynamoDBTypeDescriptors(unittest.IsolatedAsyncioTestCase):
    """Test that all DynamoDB operations use proper type descriptors."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_create_uses_proper_type_descriptors(self):
        """Test create_notification_record uses proper DynamoDB types."""
        self.mock_client.put_item.return_value = {}
        ticket = CSOPMTicket(
            key="CSOPM-1234",
            summary="Test",
            assignee_username="user",
            created_at=datetime.now(),
            status="New",
        )

        await self.tracker.create_notification_record(ticket, "U12345678")

        call_args = self.mock_client.put_item.call_args
        item = call_args.kwargs.get("item", {})

        # Verify string type descriptors
        self.assertIn("S", item["PK"])
        self.assertIn("S", item["ticket_key"])

        # Verify number type descriptors
        self.assertIn("N", item["rca_ping_count"])
        self.assertIn("N", item["closure_ping_count"])
        self.assertIn("N", item["created_at"])

        # Verify boolean type descriptors
        self.assertIn("BOOL", item["rca_reminder_sent"])
        self.assertIn("BOOL", item["closure_reminder_sent"])

        # Verify list type descriptors
        self.assertIn("L", item["assignee_history"])


class TestCSOPMStateTrackerAddFollowupTicket(unittest.IsolatedAsyncioTestCase):
    """Test add_followup_ticket method."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    async def test_add_followup_ticket_success(self):
        """Test add_followup_ticket returns True on success."""
        self.mock_client.update_item.return_value = {}

        result = await self.tracker.add_followup_ticket("CSOPM-1234", "CSOPM-5678")

        self.assertTrue(result)

    async def test_add_followup_ticket_uses_list_append(self):
        """Test add_followup_ticket uses list_append with if_not_exists."""
        self.mock_client.update_item.return_value = {}

        await self.tracker.add_followup_ticket("CSOPM-1234", "CSOPM-5678")

        call_args = self.mock_client.update_item.call_args
        update_expr = call_args.kwargs.get("update_expression", "")

        # Verify list_append and if_not_exists are used
        self.assertIn("list_append", update_expr)
        self.assertIn("if_not_exists", update_expr)
        self.assertIn("followup_ticket_keys", update_expr)

    async def test_add_followup_ticket_includes_followup_key(self):
        """Test add_followup_ticket includes the followup key in expression values."""
        self.mock_client.update_item.return_value = {}

        await self.tracker.add_followup_ticket("CSOPM-1234", "CSOPM-5678")

        call_args = self.mock_client.update_item.call_args
        expr_values = call_args.kwargs.get("expression_attribute_values", {})

        # Verify the new key is in the expression values
        self.assertIn(":new_key", expr_values)
        self.assertEqual(expr_values[":new_key"], {"L": [{"S": "CSOPM-5678"}]})

    async def test_add_followup_ticket_uses_correct_key(self):
        """Test add_followup_ticket uses correct PK and SK."""
        self.mock_client.update_item.return_value = {}

        await self.tracker.add_followup_ticket("CSOPM-1234", "CSOPM-5678")

        call_args = self.mock_client.update_item.call_args
        key = call_args.kwargs.get("key", {})

        self.assertEqual(key["PK"]["S"], "CSOPM_NOTIFICATION#CSOPM-1234")
        self.assertEqual(key["SK"]["S"], "NOTIFICATION")

    async def test_add_followup_ticket_returns_false_on_error(self):
        """Test add_followup_ticket returns False on error."""
        self.mock_client.update_item.side_effect = Exception("DynamoDB error")

        result = await self.tracker.add_followup_ticket("CSOPM-1234", "CSOPM-5678")

        self.assertFalse(result)


class TestCSOPMStateTrackerFollowupTicketKeysParsing(unittest.TestCase):
    """Test followup_ticket_keys field parsing in _item_to_notification_record."""

    def setUp(self):
        """Set up test fixtures."""
        from packages.slack.csopm.state import CSOPMStateTracker

        self.mock_client = MockDynamoDBAsyncClient()
        self.tracker = CSOPMStateTracker(client=self.mock_client, table_name="test-table")

    def test_item_to_notification_record_parses_followup_ticket_keys(self):
        """Test _item_to_notification_record parses followup_ticket_keys list."""
        item = {
            "ticket_key": {"S": "CSOPM-1234"},
            "notification_status": {"S": "pending"},
            "rca_ping_count": {"N": "0"},
            "closure_ping_count": {"N": "0"},
            "rca_reminder_sent": {"BOOL": False},
            "closure_reminder_sent": {"BOOL": False},
            "followup_ticket_keys": {"L": [{"S": "CSOPM-5678"}, {"S": "CSOPM-9012"}]},
        }

        result = self.tracker._item_to_notification_record(item)

        self.assertIsNotNone(result)
        self.assertEqual(result.followup_ticket_keys, ["CSOPM-5678", "CSOPM-9012"])

    def test_item_to_notification_record_defaults_empty_followup_keys(self):
        """Test _item_to_notification_record defaults to empty list when missing."""
        item = {
            "ticket_key": {"S": "CSOPM-1234"},
            "notification_status": {"S": "pending"},
            "rca_ping_count": {"N": "0"},
            "closure_ping_count": {"N": "0"},
            "rca_reminder_sent": {"BOOL": False},
            "closure_reminder_sent": {"BOOL": False},
        }

        result = self.tracker._item_to_notification_record(item)

        self.assertIsNotNone(result)
        self.assertEqual(result.followup_ticket_keys, [])


if __name__ == "__main__":
    unittest.main()
