#!/usr/bin/env python3
"""
CSOPM Protocol Definition Tests.

Tests for the CSOPM notifier protocol definitions to ensure:
1. All protocols are runtime checkable
2. Data classes are properly defined with expected fields
3. Protocols are properly exported from the module hierarchy
4. Protocol method signatures match expected contracts
"""

import inspect
import unittest
from dataclasses import fields
from datetime import datetime


class TestCSOPMDataClasses(unittest.TestCase):
    """Test CSOPM data class definitions."""

    def test_csopm_ticket_dataclass_fields(self):
        """Test CSOPMTicket has all required fields with correct types."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMTicket,
        )

        expected_fields = {
            "key": str,
            "summary": str,
            "assignee_username": str,
            "created_at": datetime,
            "status": str,
            "exigence_id": type(None),  # Optional[str] defaults to None
        }

        actual_fields = {f.name: f.type for f in fields(CSOPMTicket)}

        for field_name, expected_type in expected_fields.items():
            self.assertIn(
                field_name,
                actual_fields,
                f"CSOPMTicket missing field: {field_name}",
            )

    def test_csopm_ticket_instantiation(self):
        """Test CSOPMTicket can be instantiated correctly."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMTicket,
        )

        ticket = CSOPMTicket(
            key="CSOPM-1234",
            summary="Test ticket",
            assignee_username="testuser",
            created_at=datetime.now(),
            status="Open",
            exigence_id="EX-001",
        )

        self.assertEqual(ticket.key, "CSOPM-1234")
        self.assertEqual(ticket.summary, "Test ticket")
        self.assertEqual(ticket.assignee_username, "testuser")
        self.assertEqual(ticket.status, "Open")
        self.assertEqual(ticket.exigence_id, "EX-001")

    def test_notification_record_dataclass_fields(self):
        """Test NotificationRecord has all required fields."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            NotificationRecord,
        )

        expected_fields = {
            "ticket_key",
            "notification_status",
            "ping_count",
            "assignee_slack_id",
            "rca_reminder_sent",
            "closure_reminder_sent",
        }

        actual_fields = {f.name for f in fields(NotificationRecord)}

        self.assertEqual(
            expected_fields,
            actual_fields,
            "NotificationRecord fields mismatch",
        )

    def test_notification_record_instantiation(self):
        """Test NotificationRecord can be instantiated correctly."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            NotificationRecord,
        )

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            ping_count=2,
            assignee_slack_id="U12345678",
            rca_reminder_sent=True,
            closure_reminder_sent=False,
        )

        self.assertEqual(record.ticket_key, "CSOPM-1234")
        self.assertEqual(record.notification_status, "sent")
        self.assertEqual(record.ping_count, 2)
        self.assertEqual(record.assignee_slack_id, "U12345678")
        self.assertTrue(record.rca_reminder_sent)
        self.assertFalse(record.closure_reminder_sent)

    def test_followup_record_dataclass_fields(self):
        """Test FollowupRecord has all required fields."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            FollowupRecord,
        )

        expected_fields = {
            "ticket_key",
            "followup_type",
            "scheduled_at",
            "completed",
            "completed_at",
        }

        actual_fields = {f.name for f in fields(FollowupRecord)}

        self.assertEqual(
            expected_fields,
            actual_fields,
            "FollowupRecord fields mismatch",
        )


class TestCSOPMProtocolsRuntimeCheckable(unittest.TestCase):
    """Test that all CSOPM protocols are runtime checkable."""

    def test_csopm_jira_poller_protocol_is_runtime_checkable(self):
        """Test CSOPMJIRAPollerProtocol is runtime checkable."""

        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMJIRAPollerProtocol,
        )

        # Protocol should have __protocol_attrs__ or be marked as runtime_checkable
        self.assertTrue(
            hasattr(CSOPMJIRAPollerProtocol, "_is_runtime_protocol"),
            "CSOPMJIRAPollerProtocol is not runtime checkable",
        )

    def test_csopm_state_tracker_protocol_is_runtime_checkable(self):
        """Test CSOPMStateTrackerProtocol is runtime checkable."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMStateTrackerProtocol,
        )

        self.assertTrue(
            hasattr(CSOPMStateTrackerProtocol, "_is_runtime_protocol"),
            "CSOPMStateTrackerProtocol is not runtime checkable",
        )

    def test_csopm_slack_notifier_protocol_is_runtime_checkable(self):
        """Test CSOPMSlackNotifierProtocol is runtime checkable."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMSlackNotifierProtocol,
        )

        self.assertTrue(
            hasattr(CSOPMSlackNotifierProtocol, "_is_runtime_protocol"),
            "CSOPMSlackNotifierProtocol is not runtime checkable",
        )

    def test_csopm_reminder_service_protocol_is_runtime_checkable(self):
        """Test CSOPMReminderServiceProtocol is runtime checkable."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMReminderServiceProtocol,
        )

        self.assertTrue(
            hasattr(CSOPMReminderServiceProtocol, "_is_runtime_protocol"),
            "CSOPMReminderServiceProtocol is not runtime checkable",
        )

    def test_csopm_metrics_protocol_is_runtime_checkable(self):
        """Test CSOPMMetricsProtocol is runtime checkable."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMMetricsProtocol,
        )

        self.assertTrue(
            hasattr(CSOPMMetricsProtocol, "_is_runtime_protocol"),
            "CSOPMMetricsProtocol is not runtime checkable",
        )


class TestCSOPMProtocolMethodSignatures(unittest.TestCase):
    """Test CSOPM protocol method signatures match expected contracts."""

    def test_jira_poller_has_poll_method(self):
        """Test CSOPMJIRAPollerProtocol has poll_for_new_assignments method."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMJIRAPollerProtocol,
        )

        self.assertTrue(
            hasattr(CSOPMJIRAPollerProtocol, "poll_for_new_assignments"),
            "CSOPMJIRAPollerProtocol missing poll_for_new_assignments method",
        )

        # Check it's an async method
        method = CSOPMJIRAPollerProtocol.poll_for_new_assignments
        self.assertTrue(
            inspect.iscoroutinefunction(method),
            "poll_for_new_assignments should be async",
        )

    def test_jira_poller_has_get_ticket_details(self):
        """Test CSOPMJIRAPollerProtocol has get_ticket_details method."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMJIRAPollerProtocol,
        )

        self.assertTrue(
            hasattr(CSOPMJIRAPollerProtocol, "get_ticket_details"),
            "CSOPMJIRAPollerProtocol missing get_ticket_details method",
        )

    def test_state_tracker_has_required_methods(self):
        """Test CSOPMStateTrackerProtocol has all required methods."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMStateTrackerProtocol,
        )

        required_methods = [
            "get_notification_record",
            "create_notification_record",
            "update_notification_status",
            "increment_ping_count",
            "mark_rca_reminder_sent",
            "mark_closure_reminder_sent",
            "get_pending_notifications",
            "record_followup",
        ]

        for method_name in required_methods:
            self.assertTrue(
                hasattr(CSOPMStateTrackerProtocol, method_name),
                f"CSOPMStateTrackerProtocol missing {method_name} method",
            )

    def test_slack_notifier_has_required_methods(self):
        """Test CSOPMSlackNotifierProtocol has all required methods."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMSlackNotifierProtocol,
        )

        required_methods = [
            "send_assignment_dm",
            "send_reminder_dm",
            "resolve_slack_user_id",
            "handle_button_action",
        ]

        for method_name in required_methods:
            self.assertTrue(
                hasattr(CSOPMSlackNotifierProtocol, method_name),
                f"CSOPMSlackNotifierProtocol missing {method_name} method",
            )

    def test_reminder_service_has_required_methods(self):
        """Test CSOPMReminderServiceProtocol has all required methods."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMReminderServiceProtocol,
        )

        required_methods = [
            "schedule_rca_reminder",
            "schedule_closure_reminder",
            "get_due_reminders",
            "complete_reminder",
            "check_rca_reminders",
            "check_closure_reminders",
        ]

        for method_name in required_methods:
            self.assertTrue(
                hasattr(CSOPMReminderServiceProtocol, method_name),
                f"CSOPMReminderServiceProtocol missing {method_name} method",
            )

    def test_metrics_protocol_has_required_methods(self):
        """Test CSOPMMetricsProtocol has all required methods."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMMetricsProtocol,
        )

        required_methods = [
            "increment_counter",
            "record_gauge",
            "record_latency",
            "get_metrics_summary",
        ]

        for method_name in required_methods:
            self.assertTrue(
                hasattr(CSOPMMetricsProtocol, method_name),
                f"CSOPMMetricsProtocol missing {method_name} method",
            )


class TestCSOPMProtocolExports(unittest.TestCase):
    """Test CSOPM protocols are properly exported from module hierarchy."""

    def test_protocols_exported_from_csopm_protocols_module(self):
        """Test all CSOPM symbols are in csopm_protocols.__all__."""
        from packages.core.typed_di.service_registrations.protocols import csopm_protocols

        expected_exports = [
            "CSOPMTicket",
            "NotificationRecord",
            "FollowupRecord",
            "CSOPMJIRAPollerProtocol",
            "CSOPMStateTrackerProtocol",
            "CSOPMSlackNotifierProtocol",
            "CSOPMReminderServiceProtocol",
            "CSOPMMetricsProtocol",
        ]

        for export in expected_exports:
            self.assertIn(
                export,
                csopm_protocols.__all__,
                f"{export} not in csopm_protocols.__all__",
            )

    def test_protocols_exported_from_protocols_init(self):
        """Test CSOPM protocols are exported from protocols/__init__.py."""
        from packages.core.typed_di.service_registrations import protocols

        expected_exports = [
            "CSOPMTicket",
            "NotificationRecord",
            "FollowupRecord",
            "CSOPMJIRAPollerProtocol",
            "CSOPMStateTrackerProtocol",
            "CSOPMSlackNotifierProtocol",
            "CSOPMReminderServiceProtocol",
            "CSOPMMetricsProtocol",
        ]

        for export in expected_exports:
            self.assertIn(
                export,
                protocols.__all__,
                f"{export} not in protocols.__all__",
            )
            # Also verify it's actually importable
            self.assertTrue(
                hasattr(protocols, export),
                f"{export} not accessible as protocols.{export}",
            )

    def test_protocols_exported_from_central_protocols(self):
        """Test CSOPM protocols are exported from central protocols.py."""
        from packages.core.typed_di import protocols

        expected_exports = [
            "CSOPMTicket",
            "NotificationRecord",
            "FollowupRecord",
            "CSOPMJIRAPollerProtocol",
            "CSOPMStateTrackerProtocol",
            "CSOPMSlackNotifierProtocol",
            "CSOPMReminderServiceProtocol",
            "CSOPMMetricsProtocol",
        ]

        for export in expected_exports:
            self.assertIn(
                export,
                protocols.__all__,
                f"{export} not in central protocols.__all__",
            )
            # Also verify it's actually importable
            self.assertTrue(
                hasattr(protocols, export),
                f"{export} not accessible as protocols.{export}",
            )


class TestCSOPMProtocolImportPaths(unittest.TestCase):
    """Test CSOPM protocols can be imported from all expected paths."""

    def test_import_from_direct_module(self):
        """Test import directly from csopm_protocols module."""
        from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
            CSOPMJIRAPollerProtocol,
            CSOPMMetricsProtocol,
            CSOPMReminderServiceProtocol,
            CSOPMSlackNotifierProtocol,
            CSOPMStateTrackerProtocol,
            CSOPMTicket,
            FollowupRecord,
            NotificationRecord,
        )

        # Just verify they're all Protocol types or dataclasses
        self.assertIsNotNone(CSOPMTicket)
        self.assertIsNotNone(NotificationRecord)
        self.assertIsNotNone(FollowupRecord)
        self.assertIsNotNone(CSOPMJIRAPollerProtocol)
        self.assertIsNotNone(CSOPMStateTrackerProtocol)
        self.assertIsNotNone(CSOPMSlackNotifierProtocol)
        self.assertIsNotNone(CSOPMReminderServiceProtocol)
        self.assertIsNotNone(CSOPMMetricsProtocol)

    def test_import_from_protocols_package(self):
        """Test import from protocols package __init__."""
        from packages.core.typed_di.service_registrations.protocols import (
            CSOPMJIRAPollerProtocol,
            CSOPMTicket,
        )

        self.assertIsNotNone(CSOPMTicket)
        self.assertIsNotNone(CSOPMJIRAPollerProtocol)

    def test_import_from_central_protocols(self):
        """Test import from central protocols.py."""
        from packages.core.typed_di.protocols import (
            CSOPMJIRAPollerProtocol,
            CSOPMTicket,
        )

        self.assertIsNotNone(CSOPMTicket)
        self.assertIsNotNone(CSOPMJIRAPollerProtocol)


if __name__ == "__main__":
    unittest.main()
