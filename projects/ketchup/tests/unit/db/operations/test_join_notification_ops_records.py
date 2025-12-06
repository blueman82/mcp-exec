"""
Unit tests for JoinNotificationOps detail record operations.

Covers:
- _put_detail_record with TTL functionality
- _build_detail_record_item with all scenarios
- Error message truncation edge cases
- Detail record structure validation

All external dependencies mocked. Tests follow existing codebase patterns.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.db.models.notification_tracking import FailureReason
from packages.db.operations.join_notification_ops import JoinNotificationOps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for mocked DynamoDBAsyncClient."""
    client = MagicMock()
    client.put_item = AsyncMock()
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


class TestJoinNotificationOpsRecords:
    """Test class for JoinNotificationOps detail record operations."""

    @pytest.mark.asyncio
    async def test_put_detail_record_success(
        self,
        join_ops: JoinNotificationOps,
        mock_client: MagicMock,
        sample_tracking_data: Dict[str, Any],
    ) -> None:
        """Test successful detail record storage."""
        await join_ops._put_detail_record(sample_tracking_data)

        mock_client.put_item.assert_called_once()
        call_args = mock_client.put_item.call_args

        assert call_args[1]["table_name"] == "test-table"
        item = call_args[1]["item"]

        assert item["PK"]["S"] == "USER_JOIN#C1234567890"
        assert item["SK"]["S"] == "TS#1703123456#USER#U1234567890"

        # Verify TTL using temp_unarchive_expiry (30 days = 2592000 seconds)
        expected_ttl = str(1703123456 + 2592000)
        assert item["temp_unarchive_expiry"]["N"] == expected_ttl

    def test_build_detail_record_item_basic(
        self, join_ops: JoinNotificationOps, sample_tracking_data: Dict[str, Any]
    ) -> None:
        """Test building basic detail record item."""
        item = join_ops._build_detail_record_item(sample_tracking_data)

        # Verify required fields
        assert item["PK"]["S"] == "USER_JOIN#C1234567890"
        assert item["SK"]["S"] == "TS#1703123456#USER#U1234567890"
        assert item["user_id"]["S"] == "U1234567890"
        assert item["channel_id"]["S"] == "C1234567890"
        assert item["notification_attempted"]["BOOL"] is True
        assert item["delivery_status"]["S"] == "success"
        assert item["timestamp"]["N"] == "1703123456"

    def test_build_detail_record_item_with_failure(
        self, join_ops: JoinNotificationOps, sample_failed_tracking_data: Dict[str, Any]
    ) -> None:
        """Test building detail record with failure information."""
        item = join_ops._build_detail_record_item(sample_failed_tracking_data)

        # Verify failure fields
        assert item["failure_reason_code"]["S"] == FailureReason.SLACK_RATE_LIMITED.value
        assert item["error_message"]["S"] == "Rate limit exceeded for channel"

    def test_build_detail_record_item_with_long_error(self, join_ops: JoinNotificationOps) -> None:
        """Test detail record with truncated error message."""
        data = {
            "channel_id": "C1234567890",
            "user_id": "U1234567890",
            "timestamp": 1703123456,
            "delivery_status": "failed",
            "notification_attempted": True,
            "error_message": "X" * 600,  # Longer than 512 char limit
        }

        item = join_ops._build_detail_record_item(data)

        # Verify error message truncation
        assert len(item["error_message"]["S"]) == 512
        assert item["error_message"]["S"] == "X" * 512

    def test_build_detail_record_item_without_optional_fields(
        self, join_ops: JoinNotificationOps
    ) -> None:
        """Test detail record without optional failure fields."""
        data = {
            "channel_id": "C1234567890",
            "user_id": "U1234567890",
            "timestamp": 1703123456,
            "delivery_status": "success",
            "notification_attempted": True,
        }

        item = join_ops._build_detail_record_item(data)

        # Verify optional fields are not present
        assert "failure_reason_code" not in item
        assert "error_message" not in item

    def test_build_detail_record_item_with_disabled_status(
        self, join_ops: JoinNotificationOps
    ) -> None:
        """Test detail record for disabled notification."""
        data = {
            "channel_id": "C1234567890",
            "user_id": "U1234567890",
            "timestamp": 1703123456,
            "delivery_status": "disabled",
            "notification_attempted": False,
        }

        item = join_ops._build_detail_record_item(data)

        assert item["delivery_status"]["S"] == "disabled"
        assert item["notification_attempted"]["BOOL"] is False

    def test_error_message_truncation_edge_cases(self, join_ops: JoinNotificationOps) -> None:
        """Test error message truncation edge cases."""
        # Test exactly 512 characters
        data = {
            "channel_id": "C1234567890",
            "user_id": "U1234567890",
            "timestamp": 1703123456,
            "delivery_status": "failed",
            "notification_attempted": True,
            "failure_reason_code": FailureReason.INTERNAL_ERROR.value,
            "error_message": "A" * 512,
        }

        item = join_ops._build_detail_record_item(data)
        assert len(item["error_message"]["S"]) == 512

        # Test less than 512 characters
        data["error_message"] = "Short message"
        item = join_ops._build_detail_record_item(data)
        assert item["error_message"]["S"] == "Short message"

        # Test empty error message (should not be included)
        data["error_message"] = ""
        item = join_ops._build_detail_record_item(data)
        assert "error_message" not in item

        # Test None error message
        data["error_message"] = None
        item = join_ops._build_detail_record_item(data)
        assert "error_message" not in item

    def test_ttl_calculation_accuracy(self, join_ops: JoinNotificationOps) -> None:
        """Test TTL calculation for different timestamps."""
        test_timestamps = [1703123456, 1234567890, 1600000000]

        for timestamp in test_timestamps:
            data = {
                "channel_id": "C1234567890",
                "user_id": "U1234567890",
                "timestamp": timestamp,
                "delivery_status": "success",
                "notification_attempted": True,
            }

            item = join_ops._build_detail_record_item(data)

            # Verify TTL is exactly 30 days (2592000 seconds) from timestamp
            expected_ttl = str(timestamp + 2592000)
            assert item["temp_unarchive_expiry"]["N"] == expected_ttl

    def test_primary_key_structure_variations(self, join_ops: JoinNotificationOps) -> None:
        """Test primary key structure with different input variations."""
        test_cases = [
            {
                "channel_id": "C1234567890",
                "user_id": "U1234567890",
                "timestamp": 1703123456,
            },
            {
                "channel_id": "CWEIRDFORMAT123",
                "user_id": "UANOTHER456789",
                "timestamp": 9999999999,
            },
            {
                "channel_id": "C0123456789",
                "user_id": "U0987654321",
                "timestamp": 1000000000,
            },
        ]

        for case in test_cases:
            data = {
                **case,
                "delivery_status": "success",
                "notification_attempted": True,
            }

            item = join_ops._build_detail_record_item(data)

            expected_pk = f"USER_JOIN#{case['channel_id']}"
            expected_sk = f"TS#{case['timestamp']}#USER#{case['user_id']}"

            assert item["PK"]["S"] == expected_pk
            assert item["SK"]["S"] == expected_sk
