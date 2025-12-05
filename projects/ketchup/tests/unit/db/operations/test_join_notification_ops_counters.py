"""
Unit tests for JoinNotificationOps counter operations and DynamoDB integration.

Covers:
- _update_channel_counters with atomic operations
- Expression building methods
- Counter increment logic for different statuses
- Failure tracking integration

All external dependencies mocked. Tests follow existing codebase patterns.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.models.notification_tracking import FailureReason
from packages.db.operations.join_notification_ops import JoinNotificationOps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for mocked DynamoDBAsyncClient."""
    client = MagicMock()
    client.update_item = AsyncMock()
    return client


@pytest.fixture
def join_ops(mock_client: MagicMock) -> JoinNotificationOps:
    """Fixture for JoinNotificationOps with mocked client."""
    return JoinNotificationOps(mock_client, "test-table")


@pytest.fixture
def sample_failed_tracking_data() -> Dict[str, Any]:
    """Sample failed tracking data for tests."""
    return {
        "channel_id": "C1234567890",
        "user_id": "U1234567890",
        "timestamp": 1703123456,
        "delivery_status": "failed",
        "notification_attempted": True,
        "failure_reason_code": FailureReason.SLACK_RATE_LIMITED.value,
        "error_message": "Rate limit exceeded for channel",
    }


class TestJoinNotificationOpsCounters:
    """Test class for JoinNotificationOps counter operations."""

    @pytest.mark.asyncio
    async def test_update_channel_counters_success_status(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test counter updates for success status - PK/SK model with 2 updates."""
        data = {
            "channel_id": "C1234567890",
            "delivery_status": "success",
            "timestamp": 1703123456,
        }

        with patch.object(join_ops, "_get_iso_week", return_value="2024-W45"):
            await join_ops._update_channel_counters(data)

            # Should make 3 calls: map initialization + aggregate + weekly (after split operations fix)
            assert mock_client.update_item.call_count == 3
            calls = mock_client.update_item.call_args_list

            # First call: Map initialization
            init_call = calls[0][1]
            assert init_call["table_name"] == "test-table"
            assert init_call["key"]["PK"]["S"] == "CHANNEL#C1234567890"
            assert init_call["key"]["SK"]["S"] == "CSO_DETAILS"
            assert ":empty_map" in init_call["expression_attribute_values"]

            # Second call: CSO_DETAILS aggregate with counters
            aggregate_call = calls[1][1]
            assert aggregate_call["table_name"] == "test-table"
            assert aggregate_call["key"]["PK"]["S"] == "CHANNEL#C1234567890"
            assert aggregate_call["key"]["SK"]["S"] == "CSO_DETAILS"

            aggregate_values = aggregate_call["expression_attribute_values"]
            assert aggregate_values[":inc_success"]["N"] == "1"
            assert aggregate_values[":inc_failed"]["N"] == "0"
            assert aggregate_values[":inc_disabled"]["N"] == "0"
            assert aggregate_values[":timestamp"]["N"] == "1703123456"

            # Third call: WEEK#2024-W45 item
            weekly_call = calls[2][1]
            assert weekly_call["table_name"] == "test-table"
            assert weekly_call["key"]["PK"]["S"] == "CHANNEL#C1234567890"
            assert weekly_call["key"]["SK"]["S"] == "WEEK#2024-W45"

            weekly_values = weekly_call["expression_attribute_values"]
            assert weekly_values[":inc_success"]["N"] == "1"
            assert weekly_values[":inc_failed"]["N"] == "0"
            assert weekly_values[":inc_disabled"]["N"] == "0"
            assert weekly_values[":week_key"]["S"] == "2024-W45"

    @pytest.mark.asyncio
    async def test_update_channel_counters_failed_status(
        self,
        join_ops: JoinNotificationOps,
        mock_client: MagicMock,
        sample_failed_tracking_data: Dict[str, Any],
    ) -> None:
        """Test counter updates for failed status with failure tracking."""
        with patch.object(join_ops, "_get_iso_week", return_value="2024-W45"):
            await join_ops._update_channel_counters(sample_failed_tracking_data)

            # Should make 3 calls: map initialization + aggregate + weekly (after split operations fix)
            assert mock_client.update_item.call_count == 3
            calls = mock_client.update_item.call_args_list

            # Second call (calls[1]): CSO_DETAILS aggregate with failure tracking
            aggregate_call = calls[1][1]
            aggregate_values = aggregate_call["expression_attribute_values"]

            assert aggregate_values[":inc_success"]["N"] == "0"
            assert aggregate_values[":inc_failed"]["N"] == "1"
            assert aggregate_values[":inc_disabled"]["N"] == "0"
            assert aggregate_values[":reason_code"]["S"] == FailureReason.SLACK_RATE_LIMITED.value
            assert ":reason_msg" in aggregate_values

            # Second call: WEEK#2024-W45 item
            weekly_call = calls[1][1]
            weekly_values = weekly_call["expression_attribute_values"]

            assert weekly_values[":inc_success"]["N"] == "0"
            assert weekly_values[":inc_failed"]["N"] == "1"
            assert weekly_values[":inc_disabled"]["N"] == "0"

    @pytest.mark.asyncio
    async def test_update_channel_counters_disabled_status(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test counter updates for disabled status."""
        data = {
            "channel_id": "C1234567890",
            "delivery_status": "disabled",
            "timestamp": 1703123456,
        }

        with patch.object(join_ops, "_get_iso_week", return_value="2024-W45"):
            await join_ops._update_channel_counters(data)

            # Should make 3 calls: map initialization + aggregate + weekly (after split operations fix)
            assert mock_client.update_item.call_count == 3
            calls = mock_client.update_item.call_args_list

            # Check aggregate (calls[1]) and weekly (calls[2]) updates have correct disabled increments
            for call in calls[1:]:  # Skip first call (map initialization)
                values = call[1]["expression_attribute_values"]
                assert values[":inc_success"]["N"] == "0"
                assert values[":inc_failed"]["N"] == "0"
                assert values[":inc_disabled"]["N"] == "1"

    @pytest.mark.asyncio
    async def test_update_channel_aggregate_with_failure_tracking(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test aggregate update includes failure tracking fields."""
        data = {
            "failure_reason_code": "SLACK_API_ERROR",
            "error_message": "Test error message" * 100,  # Long message for truncation
        }

        await join_ops._update_channel_aggregate("C123", "failed", 1703123456, data)

        call_args = mock_client.update_item.call_args[1]

        # Verify failure tracking fields are included
        assert "#lfrc" in call_args["expression_attribute_names"]
        assert "#lfrm" in call_args["expression_attribute_names"]
        assert ":reason_code" in call_args["expression_attribute_values"]
        assert ":reason_msg" in call_args["expression_attribute_values"]

        # Verify message truncation
        assert len(call_args["expression_attribute_values"][":reason_msg"]["S"]) <= 512

    @pytest.mark.asyncio
    async def test_update_weekly_item_structure(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test weekly item update has correct PK/SK structure."""
        await join_ops._update_weekly_item("C123", "2024-W45", "success", 1703123456)

        call_args = mock_client.update_item.call_args[1]

        # Verify PK/SK structure
        assert call_args["key"]["PK"]["S"] == "CHANNEL#C123"
        assert call_args["key"]["SK"]["S"] == "WEEK#2024-W45"

        # Verify ADD operations for counters
        assert "ADD #sent :one" in call_args["update_expression"]
        assert "SET #lut = :timestamp" in call_args["update_expression"]
        assert call_args["expression_attribute_values"][":week_key"]["S"] == "2024-W45"
