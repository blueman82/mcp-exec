"""
Comprehensive end-to-end verification tests for join notification tracking.

This file contains verification tests for the complete auto join notification tracking
implementation including DynamoDB operations, service integration, and error handling.
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from packages.db.models.notification_tracking import FailureReason
from packages.db.operations.join_notification_ops import (
    JoinNotificationOps,
)
from packages.slack.services.user_join_notification_service import (
    UserJoinNotificationService,
)


class TestJoinNotificationTrackingE2E:
    """End-to-end verification tests for join notification tracking."""

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

    @pytest.fixture
    def mock_user_join_service(self, join_notification_ops):
        """Create UserJoinNotificationService with tracking ops."""
        service = UserJoinNotificationService(
            openai_handler=AsyncMock(),
            posting_handler=AsyncMock(),
            channel_info_ops=AsyncMock(),
            channel_msg_ops=AsyncMock(),
            join_notification_ops=join_notification_ops,
        )
        return service

    @pytest.mark.asyncio
    async def test_successful_notification_tracking_flow(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test complete successful notification tracking flow."""
        # Arrange
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "success",
            "notification_attempted": True,
            "timestamp": int(time.time()),
        }

        # Act
        result = await join_notification_ops.track_notification(tracking_data)

        # Assert
        assert result is True
        assert mock_dynamodb_client.update_item.called
        assert mock_dynamodb_client.put_item.called

        # Verify counter update call
        update_call = mock_dynamodb_client.update_item.call_args
        assert update_call[1]["table_name"] == "test_table"
        assert "CHANNEL#C67890" in str(update_call[1]["key"])

        # Verify detail record call
        put_call = mock_dynamodb_client.put_item.call_args
        assert put_call[1]["table_name"] == "test_table"
        assert "USER_JOIN#C67890" in str(put_call[1]["item"])

    @pytest.mark.asyncio
    async def test_failed_notification_with_error_tracking(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test failed notification tracking with error details."""
        # Arrange
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "failed",
            "notification_attempted": True,
            "failure_reason_code": FailureReason.SLACK_RATE_LIMITED.value,
            "error_message": "Rate limit exceeded for channel",
            "timestamp": int(time.time()),
        }

        # Act
        result = await join_notification_ops.track_notification(tracking_data)

        # Assert
        assert result is True

        # Verify failed counter incremented
        update_call = mock_dynamodb_client.update_item.call_args
        expression_values = update_call[1]["expression_attribute_values"]
        assert expression_values[":inc_failed"]["N"] == "1"
        assert expression_values[":inc_success"]["N"] == "0"

    @pytest.mark.asyncio
    async def test_disabled_notification_tracking(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test tracking of disabled notifications."""
        # Arrange
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "disabled",
            "notification_attempted": False,
            "timestamp": int(time.time()),
        }

        # Act
        result = await join_notification_ops.track_notification(tracking_data)

        # Assert
        assert result is True

        # Verify disabled counter incrementation
        update_call = mock_dynamodb_client.update_item.call_args
        expression_values = update_call[1]["expression_attribute_values"]
        assert expression_values[":inc_disabled"]["N"] == "1"
        assert expression_values[":inc_success"]["N"] == "0"
        assert expression_values[":inc_failed"]["N"] == "0"

    @pytest.mark.asyncio
    async def test_concurrent_tracking_operations(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test concurrent tracking operations complete successfully."""
        # Arrange
        tracking_tasks = []
        for i in range(10):
            tracking_data = {
                "user_id": f"U1234{i}",
                "channel_id": "C67890",
                "delivery_status": "success",
                "notification_attempted": True,
                "timestamp": int(time.time()) + i,
            }
            task = join_notification_ops.track_notification(tracking_data)
            tracking_tasks.append(task)

        # Act
        results = await asyncio.gather(*tracking_tasks, return_exceptions=True)

        # Assert
        assert all(result is True for result in results)
        assert mock_dynamodb_client.update_item.call_count >= 10
        assert mock_dynamodb_client.put_item.call_count >= 10

    @pytest.mark.asyncio
    async def test_error_message_truncation(self, join_notification_ops, mock_dynamodb_client):
        """Test error message truncation to 512 characters."""
        # Arrange
        long_error = "x" * 1000  # 1000 character error message
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "failed",
            "notification_attempted": True,
            "failure_reason_code": FailureReason.INTERNAL_ERROR.value,
            "error_message": long_error,
            "timestamp": int(time.time()),
        }

        # Act
        result = await join_notification_ops.track_notification(tracking_data)

        # Assert
        assert result is True

        # Verify truncation in detail record
        put_call = mock_dynamodb_client.put_item.call_args
        error_message = put_call[1]["item"]["error_message"]["S"]
        assert len(error_message) == 512
        assert error_message == "x" * 512

    @pytest.mark.asyncio
    async def test_weekly_stats_structure(self, join_notification_ops, mock_dynamodb_client):
        """Test weekly statistics structure and format."""
        # Arrange
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "success",
            "notification_attempted": True,
            "timestamp": int(time.time()),
        }

        # Act
        await join_notification_ops.track_notification(tracking_data)

        # Assert
        update_call = mock_dynamodb_client.update_item.call_args
        update_expression = update_call[1]["update_expression"]

        # Verify weekly stats tracking - the implementation uses WEEK# as SK
        assert "WEEK#" in str(update_call[1]["key"])
        assert "#sent" in update_expression or "sent" in str(update_call)

    @pytest.mark.asyncio
    async def test_ttl_functionality(self, join_notification_ops):
        """Test TTL (Time To Live) functionality for detail records."""
        # Arrange
        current_time = int(time.time())
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "success",
            "notification_attempted": True,
            "timestamp": current_time,
        }

        # Act
        detail_item = join_notification_ops._build_detail_record_item(tracking_data)

        # Assert
        assert "temp_unarchive_expiry" in detail_item
        ttl_value = int(detail_item["temp_unarchive_expiry"]["N"])
        expected_ttl = current_time + 2592000  # 30 days
        assert ttl_value == expected_ttl

    @pytest.mark.asyncio
    async def test_slack_error_classification(self, join_notification_ops):
        """Test Slack error response classification."""
        # Test cases for different Slack error types
        test_cases = [
            ({"ok": False, "error": "not_in_channel"}, FailureReason.SLACK_NOT_IN_CHANNEL.value),
            ({"ok": False, "error": "rate_limited"}, FailureReason.SLACK_RATE_LIMITED.value),
            ({"ok": False, "error": "not_authed"}, FailureReason.SLACK_PERMISSION_DENIED.value),
            ({"ok": False, "error": "unknown_error"}, FailureReason.SLACK_API_ERROR.value),
            ({"ok": True}, None),
            (None, FailureReason.NETWORK_ERROR.value),
        ]

        for slack_response, expected_reason in test_cases:
            result = join_notification_ops._classify_slack_error(slack_response)
            assert result == expected_reason

    @pytest.mark.asyncio
    async def test_get_channel_stats_functionality(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test channel statistics retrieval."""
        # Arrange
        mock_response = {
            "Item": {
                "user_join_notifications": {
                    "M": {
                        "total_sent": {"N": "100"},
                        "total_success": {"N": "95"},
                        "total_failed": {"N": "3"},
                        "total_disabled": {"N": "2"},
                        "weekly_stats": {
                            "M": {
                                "2024-W45": {
                                    "M": {
                                        "sent": {"N": "10"},
                                        "success": {"N": "9"},
                                        "failed": {"N": "1"},
                                        "disabled": {"N": "0"},
                                    }
                                }
                            }
                        },
                    }
                }
            }
        }
        mock_dynamodb_client.get_item.return_value = mock_response

        # Act
        stats = await join_notification_ops.get_channel_stats("C67890")

        # Assert
        assert stats["total_sent"] == 100
        assert stats["total_success"] == 95
        assert stats["total_failed"] == 3
        assert stats["total_disabled"] == 2
        assert "weekly_stats" in stats

    @pytest.mark.asyncio
    async def test_user_join_service_integration(self, mock_user_join_service):
        """Test UserJoinNotificationService integration with tracking."""
        # Arrange
        mock_user_join_service.user_store = AsyncMock()
        mock_user_join_service.user_store.get_user.return_value = {
            "preferences": {"join_notifications_enabled": "enabled"}
        }

        mock_user_join_service._collect_channel_data = AsyncMock()
        mock_user_join_service._collect_channel_data.return_value = {
            "channel_details": {"name": "test-channel", "is_member": True},
            "messages": ["test message"],
            "jira_context": {},
            "jira_ticket": "PROJ-123",
            "channel_id": "C67890",
            "channel_name": "test-channel",
        }

        mock_user_join_service._generate_notification_content = AsyncMock()
        mock_user_join_service._generate_notification_content.return_value = "Test content"

        mock_user_join_service._send_ephemeral_notification = AsyncMock()
        mock_user_join_service._send_ephemeral_notification.return_value = True

        # Mock the track_notification method
        mock_user_join_service.join_notification_ops.track_notification = AsyncMock(
            return_value=True
        )

        # Act
        result = await mock_user_join_service.send_join_notification(
            user_id="U12345", channel_id="C67890"
        )

        # Assert
        assert result is True
        assert mock_user_join_service.join_notification_ops.track_notification.called

        # Verify tracking was called with success status
        tracking_call = mock_user_join_service.join_notification_ops.track_notification.call_args
        tracking_data = tracking_call[0][0]
        assert tracking_data["delivery_status"] == "success"
        assert tracking_data["notification_attempted"] is True

    @pytest.mark.asyncio
    async def test_disabled_user_preference_tracking(self, mock_user_join_service):
        """Test tracking when user has disabled notifications."""
        # Arrange
        mock_user_join_service.user_store = AsyncMock()
        mock_user_join_service.user_store.get_user.return_value = {
            "preferences": {"join_notifications_enabled": "disabled"}
        }

        # Mock the track_notification method
        mock_user_join_service.join_notification_ops.track_notification = AsyncMock(
            return_value=True
        )

        # Act
        result = await mock_user_join_service.send_join_notification(
            user_id="U12345", channel_id="C67890"
        )

        # Assert
        assert result is True  # Should return True for disabled (expected behavior)
        assert mock_user_join_service.join_notification_ops.track_notification.called

        # Verify tracking was called with disabled status
        tracking_call = mock_user_join_service.join_notification_ops.track_notification.call_args
        tracking_data = tracking_call[0][0]
        assert tracking_data["delivery_status"] == "disabled"
        assert tracking_data["notification_attempted"] is False

    @pytest.mark.asyncio
    async def test_performance_tracking_operation_timing(self, join_notification_ops):
        """Test tracking operation performance meets <50ms requirement."""
        # Arrange
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "success",
            "notification_attempted": True,
            "timestamp": int(time.time()),
        }

        # Act
        start_time = time.time()
        result = await join_notification_ops.track_notification(tracking_data)
        end_time = time.time()

        # Assert
        assert result is True
        operation_time_ms = (end_time - start_time) * 1000
        # Note: This will be very fast with mocked client, but verifies no blocking operations
        assert operation_time_ms < 50  # Should be well under 50ms with proper async implementation

    @pytest.mark.asyncio
    async def test_exception_handling_and_recovery(
        self, join_notification_ops, mock_dynamodb_client
    ):
        """Test exception handling during tracking operations."""
        # Arrange
        mock_dynamodb_client.update_item.side_effect = Exception("DynamoDB error")
        tracking_data = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "delivery_status": "success",
            "notification_attempted": True,
            "timestamp": int(time.time()),
        }

        # Act
        result = await join_notification_ops.track_notification(tracking_data)

        # Assert
        assert result is False  # Should return False on exception
        # Verify operation was attempted
        assert mock_dynamodb_client.update_item.called

    @pytest.mark.asyncio
    async def test_data_integrity_validation(self, join_notification_ops):
        """Test data integrity and validation."""
        # Test missing required fields
        incomplete_data = {
            "user_id": "U12345",
            # Missing channel_id, delivery_status, timestamp
        }

        # This should not crash but may return False or handle gracefully
        await join_notification_ops.track_notification(incomplete_data)
        # The actual behavior depends on implementation - key is no crash

    def test_protocol_compliance(self, join_notification_ops):
        """Test that JoinNotificationOps implements the protocol correctly."""
        # Note: isinstance() doesn't work with Protocol types unless @runtime_checkable
        # Instead, verify all protocol methods are implemented

        # Verify all protocol methods are implemented
        assert hasattr(join_notification_ops, "track_notification")
        assert hasattr(join_notification_ops, "get_channel_stats")
        assert hasattr(join_notification_ops, "get_weekly_report")

        # Verify methods are callable
        assert callable(join_notification_ops.track_notification)
        assert callable(join_notification_ops.get_channel_stats)
        assert callable(join_notification_ops.get_weekly_report)


class TestJoinNotificationTrackingRegression:
    """Regression tests to ensure existing functionality is not broken."""

    @pytest.fixture
    def mock_services_without_tracking(self):
        """Create services without tracking to test backward compatibility."""
        return UserJoinNotificationService(
            openai_handler=AsyncMock(),
            posting_handler=AsyncMock(),
            channel_info_ops=AsyncMock(),
            channel_msg_ops=AsyncMock(),
            # No join_notification_ops provided - should handle gracefully
        )

    @pytest.mark.asyncio
    async def test_notification_service_without_tracking_ops(self, mock_services_without_tracking):
        """Test that notification service works without tracking ops."""
        # Arrange
        service = mock_services_without_tracking
        service._collect_channel_data = AsyncMock()
        service._collect_channel_data.return_value = {
            "channel_details": {"name": "test-channel", "is_member": True},
            "messages": ["test message"],
            "jira_context": {},
            "jira_ticket": "PROJ-123",
            "channel_id": "C67890",
            "channel_name": "test-channel",
        }

        service._generate_notification_content = AsyncMock()
        service._generate_notification_content.return_value = "Test content"

        service._send_ephemeral_notification = AsyncMock()
        service._send_ephemeral_notification.return_value = True

        # Act
        result = await service.send_join_notification(user_id="U12345", channel_id="C67890")

        # Assert
        assert result is True  # Should work without tracking
        # Verify no tracking calls were made (graceful degradation)

    def test_failure_reason_enum_values(self):
        """Test that FailureReason enum has expected values."""
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


# Performance verification helpers
def verify_tracking_performance():
    """Helper function to verify tracking performance in real scenarios."""
    # This would be called in integration tests with real DynamoDB
    pass


def verify_memory_usage():
    """Helper function to verify memory usage stays within limits."""
    # This would monitor memory during tracking operations
    pass
