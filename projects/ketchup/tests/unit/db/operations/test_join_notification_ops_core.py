"""
Unit tests for JoinNotificationOps core functionality.

Covers:
- Initialization and basic methods
- track_notification with success, failure, and disabled scenarios
- Concurrent operation validation
- Basic error handling

All external dependencies mocked. Tests follow existing codebase patterns.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.operations.join_notification_ops import JoinNotificationOps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for mocked DynamoDBAsyncClient."""
    client = MagicMock()
    client.update_item = AsyncMock()
    client.put_item = AsyncMock()
    client.get_item = AsyncMock()
    return client


@pytest.fixture
def join_ops(mock_client: MagicMock) -> JoinNotificationOps:
    """Fixture for JoinNotificationOps with mocked client."""
    return JoinNotificationOps(mock_client, "test-table")


@pytest.fixture
def sample_tracking_data() -> Dict[str, Any]:
    """Sample tracking data for tests."""
    return {
        "channel_id": "C1234567890",
        "user_id": "U1234567890",
        "timestamp": 1703123456,
        "delivery_status": "success",
        "notification_attempted": True,
    }


class TestJoinNotificationOpsCore:
    """Test class for JoinNotificationOps core functionality."""

    def test_init_sets_client_and_table(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test initialization sets client and table name."""
        assert join_ops.client is mock_client
        assert join_ops.table_name == "test-table"

    def test_get_iso_week_format(self, join_ops: JoinNotificationOps) -> None:
        """Test ISO week format generation."""
        with patch("packages.db.operations.join_notification_ops.datetime") as mock_dt:
            mock_dt.now.return_value.isocalendar.return_value = (2024, 45, 1)
            result = join_ops._get_iso_week()
            assert result == "2024-W45"

    @pytest.mark.asyncio
    async def test_track_notification_success(
        self, join_ops: JoinNotificationOps, sample_tracking_data: Dict[str, Any]
    ) -> None:
        """Test successful notification tracking."""
        with patch.object(join_ops, "_update_channel_counters", new_callable=AsyncMock) as mock_update:
            with patch.object(join_ops, "_put_detail_record", new_callable=AsyncMock) as mock_put:
                result = await join_ops.track_notification(sample_tracking_data)

                assert result is True
                mock_update.assert_called_once_with(sample_tracking_data)
                mock_put.assert_called_once_with(sample_tracking_data)

    @pytest.mark.asyncio
    async def test_track_notification_failure_in_counter_update(
        self, join_ops: JoinNotificationOps, sample_tracking_data: Dict[str, Any]
    ) -> None:
        """Test tracking failure when counter update fails."""
        with patch.object(join_ops, "_update_channel_counters", new_callable=AsyncMock) as mock_update:
            with patch.object(join_ops, "_put_detail_record", new_callable=AsyncMock) as mock_put:
                mock_update.side_effect = Exception("DynamoDB error")

                result = await join_ops.track_notification(sample_tracking_data)

                assert result is False
                mock_update.assert_called_once()
                mock_put.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_notification_disabled_scenario(
        self, join_ops: JoinNotificationOps
    ) -> None:
        """Test tracking when notification is disabled."""
        disabled_data = {
            "channel_id": "C1234567890",
            "user_id": "U1234567890",
            "timestamp": 1703123456,
            "delivery_status": "disabled",
            "notification_attempted": False,
        }

        with patch.object(join_ops, "_update_channel_counters", new_callable=AsyncMock) as mock_update:
            with patch.object(join_ops, "_put_detail_record", new_callable=AsyncMock) as mock_put:
                result = await join_ops.track_notification(disabled_data)

                assert result is True
                mock_update.assert_called_once_with(disabled_data)
                mock_put.assert_called_once_with(disabled_data)

    @pytest.mark.asyncio
    async def test_track_notification_exception_handling(
        self, join_ops: JoinNotificationOps, sample_tracking_data: Dict[str, Any]
    ) -> None:
        """Test exception handling in track_notification."""
        with patch.object(join_ops, "_update_channel_counters", new_callable=AsyncMock) as mock_update:
            mock_update.side_effect = Exception("Unexpected error")

            result = await join_ops.track_notification(sample_tracking_data)

            assert result is False

    def test_validate_tracking_results_success(self, join_ops: JoinNotificationOps) -> None:
        """Test validation of successful tracking results."""
        results = [None, None]  # Both operations succeeded
        assert join_ops._validate_tracking_results(results) is True

    def test_validate_tracking_results_failure(self, join_ops: JoinNotificationOps) -> None:
        """Test validation of failed tracking results."""
        results = [Exception("Counter failed"), None]
        assert join_ops._validate_tracking_results(results) is False

        results = [None, Exception("Detail failed")]
        assert join_ops._validate_tracking_results(results) is False

    @pytest.mark.asyncio
    async def test_concurrent_tracking_operations(
        self, join_ops: JoinNotificationOps, sample_tracking_data: Dict[str, Any]
    ) -> None:
        """Test concurrent tracking operations for race condition handling."""
        tasks = []
        for i in range(5):
            data = sample_tracking_data.copy()
            data["user_id"] = f"U123456789{i}"

            with patch.object(join_ops, "_update_channel_counters", new_callable=AsyncMock):
                with patch.object(join_ops, "_put_detail_record", new_callable=AsyncMock):
                    tasks.append(join_ops.track_notification(data))

        results = await asyncio.gather(*tasks)
        assert all(results)

    @pytest.mark.asyncio
    async def test_duplicate_event_handling(
        self, join_ops: JoinNotificationOps
    ) -> None:
        """Test handling of duplicate events within time window."""
        data = {
            "channel_id": "C1234567890",
            "user_id": "U1234567890",
            "timestamp": 1703123456,
            "delivery_status": "success",
            "notification_attempted": True,
        }

        with patch.object(join_ops, "_update_channel_counters", new_callable=AsyncMock):
            with patch.object(join_ops, "_put_detail_record", new_callable=AsyncMock):
                result1 = await join_ops.track_notification(data)
                result2 = await join_ops.track_notification(data)

                assert result1 is True
                assert result2 is True