"""
Core verification tests for join notification tracking operations.

Tests basic tracking functionality, error handling, and data integrity.
"""

import time
from unittest.mock import AsyncMock

import pytest

from packages.db.models.notification_tracking import FailureReason
from packages.db.operations.join_notification_ops import JoinNotificationOps


class TestJoinNotificationOpsCore:
    """Core verification tests for JoinNotificationOps."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Mock DynamoDB client for testing."""
        client = AsyncMock()
        client.update_item = AsyncMock()
        client.put_item = AsyncMock()
        client.get_item = AsyncMock()
        return client

    @pytest.fixture
    def join_notification_ops(self, mock_dynamodb_client):
        """Create JoinNotificationOps instance with mocked client."""
        return JoinNotificationOps(client=mock_dynamodb_client, table_name="test_table")

    @pytest.mark.asyncio
    async def test_successful_notification_tracking(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test successful notification tracking flow."""
        tracking_data = self._create_tracking_data("success", True)
        result = await join_notification_ops.track_notification(tracking_data)

        assert result is True
        assert mock_dynamodb_client.update_item.called
        assert mock_dynamodb_client.put_item.called

    @pytest.mark.asyncio
    async def test_failed_notification_tracking(self, join_notification_ops, mock_dynamodb_client):
        """Test failed notification tracking with error details."""
        tracking_data = self._create_tracking_data("failed", True)
        tracking_data.update(
            {
                "failure_reason_code": FailureReason.SLACK_RATE_LIMITED.value,
                "error_message": "Rate limit exceeded",
            }
        )

        result = await join_notification_ops.track_notification(tracking_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_disabled_notification_tracking(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test tracking of disabled notifications."""
        tracking_data = self._create_tracking_data("disabled", False)
        result = await join_notification_ops.track_notification(tracking_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_error_message_truncation(self, join_notification_ops):
        """Test error message truncation to 512 characters."""
        tracking_data = self._create_tracking_data("failed", True)
        tracking_data.update(
            {
                "failure_reason_code": FailureReason.INTERNAL_ERROR.value,
                "error_message": "x" * 1000,
            }
        )

        detail_item = join_notification_ops._build_detail_record_item(tracking_data)
        assert len(detail_item["error_message"]["S"]) == 512

    @pytest.mark.asyncio
    async def test_ttl_functionality(self, join_notification_ops):
        """Test TTL functionality for detail records."""
        current_time = int(time.time())
        tracking_data = self._create_tracking_data("success", True, current_time)

        detail_item = join_notification_ops._build_detail_record_item(tracking_data)
        ttl_value = int(detail_item["temp_unarchive_expiry"]["N"])
        assert ttl_value == current_time + 2592000  # 30 days

    @pytest.mark.asyncio
    async def test_slack_error_classification(self, join_notification_ops):
        """Test Slack error response classification."""
        test_cases = [
            ({"ok": False, "error": "not_in_channel"}, FailureReason.SLACK_NOT_IN_CHANNEL.value),
            ({"ok": False, "error": "rate_limited"}, FailureReason.SLACK_RATE_LIMITED.value),
            ({"ok": True}, None),
            (None, FailureReason.NETWORK_ERROR.value),
        ]

        for slack_response, expected_reason in test_cases:
            result = join_notification_ops._classify_slack_error(slack_response)
            assert result == expected_reason

    @pytest.mark.asyncio
    async def test_exception_handling(self, join_notification_ops, mock_dynamodb_client):
        """Test exception handling during tracking operations."""
        mock_dynamodb_client.update_item.side_effect = Exception("DynamoDB error")
        tracking_data = self._create_tracking_data("success", True)

        result = await join_notification_ops.track_notification(tracking_data)
        assert result is False

    def _create_tracking_data(self, status: str, attempted: bool, timestamp: int = None):
        """Helper to create tracking data."""
        return {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": status,
            "notification_attempted": attempted,
            "timestamp": timestamp or int(time.time()),
        }


class TestJoinNotificationRegression:
    """Regression tests for existing functionality."""

    def test_failure_reason_enum_values(self):
        """Test FailureReason enum has expected values."""
        expected_values = {
            "slack_rate_limited",
            "not_in_channel",
            "permission_denied",
            "slack_api_error",
            "ai_generation_failed",
            "ai_timeout",
            "network_error",
            "internal_error",
            "data_collection_failed",
        }
        actual_values = {reason.value for reason in FailureReason}
        assert actual_values == expected_values
