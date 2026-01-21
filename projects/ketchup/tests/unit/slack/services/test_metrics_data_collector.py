"""Unit tests for metrics data collector."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
    NotificationRecord,
)
from packages.slack.services.metrics_data_collector import MetricsDataCollector


class TestGetMonthlyAggregates:
    """Test monthly aggregate fetching."""

    @pytest.mark.asyncio
    async def test_aggregates_single_month(self):
        """Test aggregating data for a single month."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock data for single month
            mock_store.get_monthly_aggregates.return_value = {
                "2025_09": {
                    "auto_status_posts": 10,
                    "war_room_sent": 100,
                    "war_room_success": 95,
                    "war_room_failed": 5,
                }
            }

            result = await collector._get_monthly_aggregates(["2025_09"])

            assert result["auto_status_posts"] == 10
            assert result["war_room_sent"] == 100
            assert result["war_room_success"] == 95
            assert result["war_room_failed"] == 5

    @pytest.mark.asyncio
    async def test_aggregates_multiple_months(self):
        """Test aggregating data across multiple months."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock data for 2 months
            mock_store.get_monthly_aggregates.return_value = {
                "2025_09": {
                    "auto_status_posts": 10,
                    "war_room_sent": 100,
                    "war_room_success": 95,
                    "war_room_failed": 5,
                },
                "2025_10": {
                    "auto_status_posts": 15,
                    "war_room_sent": 150,
                    "war_room_success": 145,
                    "war_room_failed": 5,
                },
            }

            result = await collector._get_monthly_aggregates(["2025_09", "2025_10"])

            assert result["auto_status_posts"] == 25  # 10 + 15
            assert result["war_room_sent"] == 250  # 100 + 150
            assert result["war_room_success"] == 240  # 95 + 145
            assert result["war_room_failed"] == 10  # 5 + 5

    @pytest.mark.asyncio
    async def test_handles_missing_data(self):
        """Test handling of missing monthly data."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock empty data (no records for requested month)
            mock_store.get_monthly_aggregates.return_value = {"2025_09": {}}  # Empty metrics

            result = await collector._get_monthly_aggregates(["2025_09"])

            # Should return zeros for all counters
            assert result["auto_status_posts"] == 0
            assert result["war_room_sent"] == 0
            assert result["war_room_success"] == 0
            assert result["war_room_failed"] == 0

    @pytest.mark.asyncio
    async def test_quarterly_aggregation(self):
        """Test aggregating data for quarterly period (3 months)."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock data for Q4 (Sept, Oct, Nov)
            mock_store.get_monthly_aggregates.return_value = {
                "2025_09": {
                    "auto_status_posts": 10,
                    "war_room_sent": 100,
                    "war_room_success": 95,
                    "war_room_failed": 5,
                },
                "2025_10": {
                    "auto_status_posts": 15,
                    "war_room_sent": 150,
                    "war_room_success": 145,
                    "war_room_failed": 5,
                },
                "2025_11": {
                    "auto_status_posts": 20,
                    "war_room_sent": 200,
                    "war_room_success": 195,
                    "war_room_failed": 5,
                },
            }

            result = await collector._get_monthly_aggregates(["2025_09", "2025_10", "2025_11"])

            assert result["auto_status_posts"] == 45  # 10 + 15 + 20
            assert result["war_room_sent"] == 450  # 100 + 150 + 200
            assert result["war_room_success"] == 435  # 95 + 145 + 195
            assert result["war_room_failed"] == 15  # 5 + 5 + 5


class TestCollectCSOPMMetrics:
    """Test CSOPM metrics collection including completion and closure timing."""

    def _create_mock_collector(self, csopm_state_tracker=None):
        """Create a MetricsDataCollector with mocked dependencies."""
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"
        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        return MetricsDataCollector(
            mock_channel_ops,
            mock_join_ops,
            mock_membership_ops,
            csopm_state_tracker=csopm_state_tracker,
        )

    @pytest.mark.asyncio
    async def test_returns_empty_metrics_when_state_tracker_unavailable(self):
        """Test that empty metrics are returned when state tracker is not available."""
        collector = self._create_mock_collector(csopm_state_tracker=None)

        result = await collector.collect_csopm_metrics(start_ts=0, end_ts=9999999999)

        assert result["total_notifications"] == 0
        assert result["completed_within_threshold"] == 0
        assert result["completed_after_threshold"] == 0
        assert result["closed_within_threshold"] == 0
        assert result["closed_after_threshold"] == 0

    @pytest.mark.asyncio
    async def test_calculates_completion_within_threshold(self):
        """Test that tickets completed within 7 days are counted correctly."""
        mock_state_tracker = AsyncMock()

        # Created at day 0, completed at day 5 (within 7 days)
        created_ts = 1700000000
        completed_ts = created_ts + (5 * 24 * 60 * 60)  # 5 days later

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=created_ts,
            updated_at=completed_ts,
            completed_at=completed_ts,
            closed_at=None,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=created_ts - 1000, end_ts=completed_ts + 1000
        )

        assert result["completed_within_threshold"] == 1
        assert result["completed_after_threshold"] == 0

    @pytest.mark.asyncio
    async def test_calculates_completion_after_threshold(self):
        """Test that tickets completed after 7 days are counted correctly."""
        mock_state_tracker = AsyncMock()

        # Created at day 0, completed at day 10 (after 7 days)
        created_ts = 1700000000
        completed_ts = created_ts + (10 * 24 * 60 * 60)  # 10 days later

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=created_ts,
            updated_at=completed_ts,
            completed_at=completed_ts,
            closed_at=None,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=created_ts - 1000, end_ts=completed_ts + 1000
        )

        assert result["completed_within_threshold"] == 0
        assert result["completed_after_threshold"] == 1

    @pytest.mark.asyncio
    async def test_calculates_closure_within_threshold(self):
        """Test that tickets closed within 45 days are counted correctly."""
        mock_state_tracker = AsyncMock()

        # Created at day 0, closed at day 30 (within 45 days)
        created_ts = 1700000000
        closed_ts = created_ts + (30 * 24 * 60 * 60)  # 30 days later

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=created_ts,
            updated_at=closed_ts,
            completed_at=None,
            closed_at=closed_ts,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=created_ts - 1000, end_ts=closed_ts + 1000
        )

        assert result["closed_within_threshold"] == 1
        assert result["closed_after_threshold"] == 0

    @pytest.mark.asyncio
    async def test_calculates_closure_after_threshold(self):
        """Test that tickets closed after 45 days are counted correctly."""
        mock_state_tracker = AsyncMock()

        # Created at day 0, closed at day 60 (after 45 days)
        created_ts = 1700000000
        closed_ts = created_ts + (60 * 24 * 60 * 60)  # 60 days later

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=created_ts,
            updated_at=closed_ts,
            completed_at=None,
            closed_at=closed_ts,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=created_ts - 1000, end_ts=closed_ts + 1000
        )

        assert result["closed_within_threshold"] == 0
        assert result["closed_after_threshold"] == 1

    @pytest.mark.asyncio
    async def test_handles_records_without_completed_at(self):
        """Test that records without completed_at are not counted in completion metrics."""
        mock_state_tracker = AsyncMock()

        created_ts = 1700000000

        # Record without completed_at (ticket not yet completed)
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="sent",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=created_ts,
            updated_at=created_ts,
            completed_at=None,
            closed_at=None,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=created_ts - 1000, end_ts=created_ts + 1000
        )

        assert result["completed_within_threshold"] == 0
        assert result["completed_after_threshold"] == 0
        assert result["closed_within_threshold"] == 0
        assert result["closed_after_threshold"] == 0

    @pytest.mark.asyncio
    async def test_handles_records_without_created_at(self):
        """Test that records without created_at are not counted in timing metrics."""
        mock_state_tracker = AsyncMock()

        completed_ts = 1700500000

        # Record without created_at (legacy record)
        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=None,  # Missing created_at
            updated_at=completed_ts,
            completed_at=completed_ts,
            closed_at=None,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(start_ts=0, end_ts=9999999999)

        # Should not count because created_at is missing
        assert result["completed_within_threshold"] == 0
        assert result["completed_after_threshold"] == 0

    @pytest.mark.asyncio
    async def test_mixed_completion_and_closure_timing(self):
        """Test counting multiple records with various completion and closure states."""
        mock_state_tracker = AsyncMock()

        base_ts = 1700000000

        records = [
            # Record 1: Completed within 7 days
            NotificationRecord(
                ticket_key="CSOPM-0001",
                notification_status="ack",
                rca_ping_count=0,
                closure_ping_count=0,
                assignee_slack_id="U12345678",
                assignee_jira_username="testuser",
                rca_reminder_sent=False,
                closure_reminder_sent=False,
                created_at=base_ts,
                updated_at=base_ts + (3 * 24 * 60 * 60),
                completed_at=base_ts + (3 * 24 * 60 * 60),  # 3 days
                closed_at=None,
            ),
            # Record 2: Completed after 7 days, closed within 45 days
            NotificationRecord(
                ticket_key="CSOPM-0002",
                notification_status="ack",
                rca_ping_count=0,
                closure_ping_count=0,
                assignee_slack_id="U12345678",
                assignee_jira_username="testuser",
                rca_reminder_sent=False,
                closure_reminder_sent=False,
                created_at=base_ts,
                updated_at=base_ts + (20 * 24 * 60 * 60),
                completed_at=base_ts + (10 * 24 * 60 * 60),  # 10 days
                closed_at=base_ts + (20 * 24 * 60 * 60),  # 20 days
            ),
            # Record 3: Closed after 45 days
            NotificationRecord(
                ticket_key="CSOPM-0003",
                notification_status="ack",
                rca_ping_count=0,
                closure_ping_count=0,
                assignee_slack_id="U12345678",
                assignee_jira_username="testuser",
                rca_reminder_sent=False,
                closure_reminder_sent=False,
                created_at=base_ts,
                updated_at=base_ts + (50 * 24 * 60 * 60),
                completed_at=None,
                closed_at=base_ts + (50 * 24 * 60 * 60),  # 50 days
            ),
            # Record 4: Not yet completed or closed
            NotificationRecord(
                ticket_key="CSOPM-0004",
                notification_status="sent",
                rca_ping_count=0,
                closure_ping_count=0,
                assignee_slack_id="U12345678",
                assignee_jira_username="testuser",
                rca_reminder_sent=False,
                closure_reminder_sent=False,
                created_at=base_ts,
                updated_at=base_ts,
                completed_at=None,
                closed_at=None,
            ),
        ]
        mock_state_tracker.get_all_notification_records.return_value = records

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=base_ts - 1000, end_ts=base_ts + (100 * 24 * 60 * 60)
        )

        # Record 1: completed within threshold
        # Record 2: completed after threshold
        assert result["completed_within_threshold"] == 1
        assert result["completed_after_threshold"] == 1

        # Record 2: closed within threshold
        # Record 3: closed after threshold
        assert result["closed_within_threshold"] == 1
        assert result["closed_after_threshold"] == 1

    @pytest.mark.asyncio
    async def test_exact_boundary_completion_threshold(self):
        """Test that tickets completed exactly at 7 days are counted as within threshold."""
        mock_state_tracker = AsyncMock()

        created_ts = 1700000000
        # Exactly 7 days (in seconds)
        seven_days_seconds = 7 * 24 * 60 * 60
        completed_ts = created_ts + seven_days_seconds

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=created_ts,
            updated_at=completed_ts,
            completed_at=completed_ts,
            closed_at=None,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=created_ts - 1000, end_ts=completed_ts + 1000
        )

        # Exactly at threshold should count as "within"
        assert result["completed_within_threshold"] == 1
        assert result["completed_after_threshold"] == 0

    @pytest.mark.asyncio
    async def test_exact_boundary_closure_threshold(self):
        """Test that tickets closed exactly at 45 days are counted as within threshold."""
        mock_state_tracker = AsyncMock()

        created_ts = 1700000000
        # Exactly 45 days (in seconds)
        forty_five_days_seconds = 45 * 24 * 60 * 60
        closed_ts = created_ts + forty_five_days_seconds

        record = NotificationRecord(
            ticket_key="CSOPM-1234",
            notification_status="ack",
            rca_ping_count=0,
            closure_ping_count=0,
            assignee_slack_id="U12345678",
            assignee_jira_username="testuser",
            rca_reminder_sent=False,
            closure_reminder_sent=False,
            created_at=created_ts,
            updated_at=closed_ts,
            completed_at=None,
            closed_at=closed_ts,
        )
        mock_state_tracker.get_all_notification_records.return_value = [record]

        collector = self._create_mock_collector(csopm_state_tracker=mock_state_tracker)

        result = await collector.collect_csopm_metrics(
            start_ts=created_ts - 1000, end_ts=closed_ts + 1000
        )

        # Exactly at threshold should count as "within"
        assert result["closed_within_threshold"] == 1
        assert result["closed_after_threshold"] == 0
