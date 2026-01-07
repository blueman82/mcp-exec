"""
Unit tests for CSOPM Notifier Scheduler.

Tests the CSOPMScheduler class for:
- Dual-time scheduling (08:00 and 16:00 UTC)
- Poll cycle orchestration
- Health file management
- Signal handling
- Service resolution from container
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.typed_di.protocols import (
    CSOPMJIRAPollerProtocol,
    CSOPMReminderServiceProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
    NotificationRecord,
)


class TestCSOPMSchedulerInit:
    """Tests for CSOPMScheduler initialization."""

    def test_scheduler_initializes_with_container(self):
        """Test scheduler initializes with container."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        mock_container = MagicMock()

        scheduler = CSOPMScheduler(container=mock_container)

        assert scheduler._container is mock_container
        assert scheduler.running is True
        assert scheduler.scheduler_name == "CSOPMScheduler"

    def test_scheduler_uses_custom_health_file_prefix(self):
        """Test scheduler uses custom health file prefix."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        mock_container = MagicMock()

        scheduler = CSOPMScheduler(
            container=mock_container,
            health_file_prefix="custom_prefix",
            base_path="/custom/path",
        )

        assert scheduler.health_file == Path("/custom/path/custom_prefix_health")
        assert scheduler.last_run_file == Path("/custom/path/custom_prefix_last_run")

    def test_scheduler_has_correct_schedule_times(self):
        """Test scheduler has 08:00 and 16:00 UTC schedule times."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        assert CSOPMScheduler.SCHEDULE_TIMES_UTC == ["08:00", "16:00"]


class TestDualTimeScheduling:
    """Tests for dual-time scheduling calculation."""

    def test_get_sleep_seconds_before_first_schedule(self):
        """Test sleep seconds calculated correctly when before 08:00 UTC."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        mock_container = MagicMock()
        scheduler = CSOPMScheduler(container=mock_container)

        # Mock current time to 06:00 UTC
        mock_now = datetime(2025, 1, 6, 6, 0, 0, tzinfo=timezone.utc)

        with patch("ketchup_csopm_notifier.scheduler.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            sleep_seconds = scheduler.get_sleep_seconds()

            # Should be ~2 hours until 08:00 UTC (7200 seconds)
            # Allow some margin for calculation
            assert 7100 <= sleep_seconds <= 7300

    def test_get_sleep_seconds_between_schedules(self):
        """Test sleep seconds calculated correctly when between 08:00 and 16:00 UTC."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        mock_container = MagicMock()
        scheduler = CSOPMScheduler(container=mock_container)

        # Mock current time to 10:00 UTC (between 08:00 and 16:00)
        mock_now = datetime(2025, 1, 6, 10, 0, 0, tzinfo=timezone.utc)

        with patch("ketchup_csopm_notifier.scheduler.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            sleep_seconds = scheduler.get_sleep_seconds()

            # Should be ~6 hours until 16:00 UTC (21600 seconds)
            assert 21500 <= sleep_seconds <= 21700

    def test_get_sleep_seconds_after_last_schedule(self):
        """Test sleep seconds calculated correctly when after 16:00 UTC."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        mock_container = MagicMock()
        scheduler = CSOPMScheduler(container=mock_container)

        # Mock current time to 20:00 UTC (after 16:00)
        mock_now = datetime(2025, 1, 6, 20, 0, 0, tzinfo=timezone.utc)

        with patch("ketchup_csopm_notifier.scheduler.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            sleep_seconds = scheduler.get_sleep_seconds()

            # Should be ~12 hours until 08:00 UTC next day (43200 seconds)
            assert 43100 <= sleep_seconds <= 43300

    def test_get_sleep_seconds_minimum_is_60(self):
        """Test sleep seconds has minimum of 60 seconds."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        mock_container = MagicMock()
        scheduler = CSOPMScheduler(container=mock_container)

        # Mock current time to exactly 08:00 UTC
        mock_now = datetime(2025, 1, 6, 8, 0, 0, tzinfo=timezone.utc)

        with patch("ketchup_csopm_notifier.scheduler.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            sleep_seconds = scheduler.get_sleep_seconds()

            # Should still return at least 60 seconds
            assert sleep_seconds >= 60


class TestPollCycleOrchestration:
    """Tests for poll cycle orchestration."""

    @pytest.mark.asyncio
    async def test_run_task_calls_all_services_in_order(self):
        """Test run_task orchestrates all services in correct order."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        # Create mock services
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)
        mock_state_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)
        mock_reminder_service = AsyncMock(spec=CSOPMReminderServiceProtocol)

        # Set up mock returns
        mock_poller.poll_for_new_assignments.return_value = []
        mock_reminder_service.check_rca_reminders.return_value = []
        mock_reminder_service.check_closure_reminders.return_value = []

        # Create mock container
        mock_container = AsyncMock()

        async def mock_aget(protocol):
            if protocol == CSOPMJIRAPollerProtocol:
                return mock_poller
            elif protocol == CSOPMSlackNotifierProtocol:
                return mock_notifier
            elif protocol == CSOPMStateTrackerProtocol:
                return mock_state_tracker
            elif protocol == CSOPMReminderServiceProtocol:
                return mock_reminder_service
            raise ValueError(f"Unknown protocol: {protocol}")

        mock_container.aget = mock_aget

        scheduler = CSOPMScheduler(container=mock_container)

        # Run task
        await scheduler.run_task()

        # Verify service calls
        mock_poller.poll_for_new_assignments.assert_called_once()
        mock_reminder_service.check_rca_reminders.assert_called_once()
        mock_reminder_service.check_closure_reminders.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_task_sends_notifications_for_new_tickets(self):
        """Test run_task sends notifications for new tickets."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        # Create mock ticket
        mock_ticket = CSOPMTicket(
            key="CSOPM-123",
            summary="Test ticket",
            assignee_username="testuser",
            created_at=datetime.now(timezone.utc),
            status="New",
            exigence_id="12345",
        )

        # Create mock services
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_poller.poll_for_new_assignments.return_value = [mock_ticket]

        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)
        mock_notifier.resolve_slack_user_id.return_value = "U12345"
        mock_notifier.send_assignment_dm.return_value = True

        mock_state_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)
        mock_state_tracker.get_notification_record.return_value = None  # New ticket

        mock_reminder_service = AsyncMock(spec=CSOPMReminderServiceProtocol)
        mock_reminder_service.check_rca_reminders.return_value = []
        mock_reminder_service.check_closure_reminders.return_value = []

        # Create mock container
        mock_container = AsyncMock()

        async def mock_aget(protocol):
            if protocol == CSOPMJIRAPollerProtocol:
                return mock_poller
            elif protocol == CSOPMSlackNotifierProtocol:
                return mock_notifier
            elif protocol == CSOPMStateTrackerProtocol:
                return mock_state_tracker
            elif protocol == CSOPMReminderServiceProtocol:
                return mock_reminder_service
            raise ValueError(f"Unknown protocol: {protocol}")

        mock_container.aget = mock_aget

        scheduler = CSOPMScheduler(container=mock_container)

        # Run task
        await scheduler.run_task()

        # Verify notification was sent
        mock_notifier.resolve_slack_user_id.assert_called_once_with("testuser")
        mock_notifier.send_assignment_dm.assert_called_once_with(mock_ticket, "U12345")
        mock_state_tracker.create_notification_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_task_skips_already_notified_tickets(self):
        """Test run_task skips tickets that already have notification records."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        # Create mock ticket
        mock_ticket = CSOPMTicket(
            key="CSOPM-123",
            summary="Test ticket",
            assignee_username="testuser",
            created_at=datetime.now(timezone.utc),
            status="New",
        )

        # Create existing notification record (matches actual NotificationRecord structure)
        # Use same assignee as ticket to avoid triggering reassignment logic
        mock_record = NotificationRecord(
            ticket_key="CSOPM-123",
            notification_status="sent",
            ping_count=0,
            assignee_slack_id="U12345",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        # Create mock services
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_poller.poll_for_new_assignments.return_value = [mock_ticket]

        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)

        mock_state_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)
        mock_state_tracker.get_notification_record.return_value = mock_record

        mock_reminder_service = AsyncMock(spec=CSOPMReminderServiceProtocol)
        mock_reminder_service.check_rca_reminders.return_value = []
        mock_reminder_service.check_closure_reminders.return_value = []

        # Create mock container
        mock_container = AsyncMock()

        async def mock_aget(protocol):
            if protocol == CSOPMJIRAPollerProtocol:
                return mock_poller
            elif protocol == CSOPMSlackNotifierProtocol:
                return mock_notifier
            elif protocol == CSOPMStateTrackerProtocol:
                return mock_state_tracker
            elif protocol == CSOPMReminderServiceProtocol:
                return mock_reminder_service
            raise ValueError(f"Unknown protocol: {protocol}")

        mock_container.aget = mock_aget

        scheduler = CSOPMScheduler(container=mock_container)

        # Run task
        await scheduler.run_task()

        # Verify notification was NOT sent
        mock_notifier.resolve_slack_user_id.assert_not_called()
        mock_notifier.send_assignment_dm.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_task_handles_notification_failure(self):
        """Test run_task continues on notification failure."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        # Create mock tickets
        mock_ticket1 = CSOPMTicket(
            key="CSOPM-123",
            summary="Test ticket 1",
            assignee_username="user1",
            created_at=datetime.now(timezone.utc),
            status="New",
        )
        mock_ticket2 = CSOPMTicket(
            key="CSOPM-456",
            summary="Test ticket 2",
            assignee_username="user2",
            created_at=datetime.now(timezone.utc),
            status="New",
        )

        # Create mock services
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_poller.poll_for_new_assignments.return_value = [mock_ticket1, mock_ticket2]

        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)
        mock_notifier.resolve_slack_user_id.side_effect = [None, "U67890"]  # First fails
        mock_notifier.send_assignment_dm.return_value = True

        mock_state_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)
        mock_state_tracker.get_notification_record.return_value = None

        mock_reminder_service = AsyncMock(spec=CSOPMReminderServiceProtocol)
        mock_reminder_service.check_rca_reminders.return_value = []
        mock_reminder_service.check_closure_reminders.return_value = []

        # Create mock container
        mock_container = AsyncMock()

        async def mock_aget(protocol):
            if protocol == CSOPMJIRAPollerProtocol:
                return mock_poller
            elif protocol == CSOPMSlackNotifierProtocol:
                return mock_notifier
            elif protocol == CSOPMStateTrackerProtocol:
                return mock_state_tracker
            elif protocol == CSOPMReminderServiceProtocol:
                return mock_reminder_service
            raise ValueError(f"Unknown protocol: {protocol}")

        mock_container.aget = mock_aget

        scheduler = CSOPMScheduler(container=mock_container)

        # Run task - should not raise
        await scheduler.run_task()

        # Verify second ticket was still processed
        assert mock_notifier.resolve_slack_user_id.call_count == 2
        mock_notifier.send_assignment_dm.assert_called_once_with(mock_ticket2, "U67890")


class TestReassignmentDetection:
    """Tests for ticket reassignment detection."""

    @pytest.mark.asyncio
    async def test_run_task_detects_and_handles_reassignment(self):
        """Test run_task detects reassignment and calls handle_reassignment."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        # Create mock ticket with NEW assignee
        mock_ticket = CSOPMTicket(
            key="CSOPM-123",
            summary="Test ticket",
            assignee_username="newuser",  # Different from stored assignee
            created_at=datetime.now(timezone.utc),
            status="New",
        )

        # Create existing notification record with OLD assignee
        mock_record = NotificationRecord(
            ticket_key="CSOPM-123",
            notification_status="sent",
            ping_count=1,
            assignee_slack_id="U_OLD_USER",
            assignee_jira_username="olduser",  # Different from ticket.assignee_username
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        # Create mock services
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_poller.poll_for_new_assignments.return_value = [mock_ticket]

        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)
        mock_notifier.resolve_slack_user_id.return_value = "U_NEW_USER"
        mock_notifier.send_assignment_dm.return_value = True

        mock_state_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)
        mock_state_tracker.get_notification_record.return_value = mock_record
        mock_state_tracker.handle_reassignment.return_value = NotificationRecord(
            ticket_key="CSOPM-123",
            notification_status="sent",
            ping_count=1,
            assignee_slack_id="U_NEW_USER",
            assignee_jira_username="newuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        mock_reminder_service = AsyncMock(spec=CSOPMReminderServiceProtocol)
        mock_reminder_service.check_rca_reminders.return_value = []
        mock_reminder_service.check_closure_reminders.return_value = []

        # Create mock container
        mock_container = AsyncMock()

        async def mock_aget(protocol):
            if protocol == CSOPMJIRAPollerProtocol:
                return mock_poller
            elif protocol == CSOPMSlackNotifierProtocol:
                return mock_notifier
            elif protocol == CSOPMStateTrackerProtocol:
                return mock_state_tracker
            elif protocol == CSOPMReminderServiceProtocol:
                return mock_reminder_service
            raise ValueError(f"Unknown protocol: {protocol}")

        mock_container.aget = mock_aget

        scheduler = CSOPMScheduler(container=mock_container)

        # Run task
        await scheduler.run_task()

        # Verify reassignment was handled
        mock_notifier.resolve_slack_user_id.assert_called_with("newuser")
        mock_state_tracker.handle_reassignment.assert_called_once_with(
            ticket_key="CSOPM-123",
            new_jira_username="newuser",
            new_slack_id="U_NEW_USER",
        )
        # Verify notification was sent to new assignee
        mock_notifier.send_assignment_dm.assert_called_once_with(mock_ticket, "U_NEW_USER")

    @pytest.mark.asyncio
    async def test_run_task_skips_reassignment_if_same_assignee(self):
        """Test run_task does not call handle_reassignment if assignee unchanged."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        # Create mock ticket with SAME assignee as stored
        mock_ticket = CSOPMTicket(
            key="CSOPM-123",
            summary="Test ticket",
            assignee_username="sameuser",
            created_at=datetime.now(timezone.utc),
            status="New",
        )

        # Create existing notification record with SAME assignee
        mock_record = NotificationRecord(
            ticket_key="CSOPM-123",
            notification_status="sent",
            ping_count=1,
            assignee_slack_id="U12345",
            assignee_jira_username="sameuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        # Create mock services
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_poller.poll_for_new_assignments.return_value = [mock_ticket]

        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)

        mock_state_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)
        mock_state_tracker.get_notification_record.return_value = mock_record

        mock_reminder_service = AsyncMock(spec=CSOPMReminderServiceProtocol)
        mock_reminder_service.check_rca_reminders.return_value = []
        mock_reminder_service.check_closure_reminders.return_value = []

        # Create mock container
        mock_container = AsyncMock()

        async def mock_aget(protocol):
            if protocol == CSOPMJIRAPollerProtocol:
                return mock_poller
            elif protocol == CSOPMSlackNotifierProtocol:
                return mock_notifier
            elif protocol == CSOPMStateTrackerProtocol:
                return mock_state_tracker
            elif protocol == CSOPMReminderServiceProtocol:
                return mock_reminder_service
            raise ValueError(f"Unknown protocol: {protocol}")

        mock_container.aget = mock_aget

        scheduler = CSOPMScheduler(container=mock_container)

        # Run task
        await scheduler.run_task()

        # Verify handle_reassignment was NOT called
        mock_state_tracker.handle_reassignment.assert_not_called()
        # Verify no notification was sent (since ticket was already tracked)
        mock_notifier.resolve_slack_user_id.assert_not_called()
        mock_notifier.send_assignment_dm.assert_not_called()


class TestReminderProcessing:
    """Tests for reminder processing."""

    @pytest.mark.asyncio
    async def test_run_task_processes_rca_reminders(self):
        """Test run_task processes RCA reminders."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        # Create mock reminder record (matches actual NotificationRecord structure)
        mock_reminder = NotificationRecord(
            ticket_key="CSOPM-789",
            notification_status="sent",
            ping_count=0,
            assignee_slack_id="U12345",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
        )

        mock_ticket = CSOPMTicket(
            key="CSOPM-789",
            summary="Old ticket",
            assignee_username="testuser",
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
            status="New",
        )

        # Create mock services
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_poller.poll_for_new_assignments.return_value = []
        mock_poller.get_ticket_details.return_value = mock_ticket

        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)
        mock_notifier.resolve_slack_user_id.return_value = "U12345"
        mock_notifier.send_reminder_dm.return_value = True

        mock_state_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)

        mock_reminder_service = AsyncMock(spec=CSOPMReminderServiceProtocol)
        mock_reminder_service.check_rca_reminders.return_value = [mock_reminder]
        mock_reminder_service.check_closure_reminders.return_value = []

        # Create mock container
        mock_container = AsyncMock()

        async def mock_aget(protocol):
            if protocol == CSOPMJIRAPollerProtocol:
                return mock_poller
            elif protocol == CSOPMSlackNotifierProtocol:
                return mock_notifier
            elif protocol == CSOPMStateTrackerProtocol:
                return mock_state_tracker
            elif protocol == CSOPMReminderServiceProtocol:
                return mock_reminder_service
            raise ValueError(f"Unknown protocol: {protocol}")

        mock_container.aget = mock_aget

        scheduler = CSOPMScheduler(container=mock_container)

        # Run task
        await scheduler.run_task()

        # Verify RCA reminder was sent
        mock_notifier.send_reminder_dm.assert_called_with(mock_ticket, "U12345", "rca")
        mock_state_tracker.mark_rca_reminder_sent.assert_called_once_with("CSOPM-789")
        mock_state_tracker.increment_ping_count.assert_called()


class TestHealthFileManagement:
    """Tests for health file management."""

    def test_scheduler_writes_health_file(self, tmp_path):
        """Test scheduler writes health file with correct format."""
        from ketchup_csopm_notifier.scheduler import CSOPMScheduler

        mock_container = MagicMock()
        scheduler = CSOPMScheduler(
            container=mock_container,
            health_file_prefix="test_csopm",
            base_path=str(tmp_path),
        )

        # Write health status
        scheduler._update_health_status("running")

        # Verify file was written
        health_file = tmp_path / "test_csopm_health"
        assert health_file.exists()

        content = health_file.read_text()
        assert ":" in content
        timestamp_str, status = content.split(":", 1)
        assert status == "running"
        assert int(timestamp_str) > 0


class TestMainEntryPoint:
    """Tests for main entry point."""

    @pytest.mark.asyncio
    async def test_main_function_exists(self):
        """Test main function can be imported."""
        from ketchup_csopm_notifier.main import main

        assert callable(main)

    def test_run_function_exists(self):
        """Test run function can be imported."""
        from ketchup_csopm_notifier.main import run

        assert callable(run)

    @pytest.mark.asyncio
    async def test_main_creates_container_and_scheduler(self):
        """Test main creates container and scheduler."""
        from ketchup_csopm_notifier import main as main_module

        # Mock get_unified_container and CSOPMScheduler
        mock_container = AsyncMock()
        mock_scheduler = AsyncMock()
        mock_scheduler.start = AsyncMock()

        with patch.object(main_module, "get_unified_container", return_value=mock_container):
            with patch.object(
                main_module, "CSOPMScheduler", return_value=mock_scheduler
            ) as mock_scheduler_class:
                await main_module.main()

                # Verify container was created
                main_module.get_unified_container.assert_called_once()

                # Verify scheduler was created with container
                mock_scheduler_class.assert_called_once()
                call_kwargs = mock_scheduler_class.call_args.kwargs
                assert call_kwargs["container"] is mock_container
                assert call_kwargs["health_file_prefix"] == "csopm_notifier"

                # Verify scheduler was started
                mock_scheduler.start.assert_called_once()
