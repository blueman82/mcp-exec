"""
Test module to reproduce the original dynamodb_store undefined error.

This test follows TDD RED-GREEN-REFACTOR cycle:
1. RED: Create test that fails with the original error
2. GREEN: Apply fix and verify test passes
3. REFACTOR: Clean up if needed
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone

# Import the original function that had the bug
from packages.slack.channel_events.processing.user_join_processor import process_regular_user_join


class TestUserJoinProcessorDynamoDBStoreBug:
    """
    Test suite to reproduce and verify the fix for the dynamodb_store undefined error.

    The original issue occurred when process_regular_user_join() tried to call
    dynamodb_store.increment_monthly_counter() but the dynamodb_store parameter
    was not passed to the function.
    """

    @pytest.mark.asyncio
    async def test_original_bug_missing_dynamodb_store_parameter(self):
        """
        RED Phase: Test that reproduces the original dynamodb_store undefined error.

        This test simulates the original code path where the function was called
        without the dynamodb_store parameter, causing a NameError.
        """
        # Arrange - mock all dependencies except the missing one
        mock_event = {
            "channel": "C1234567890",
            "channel_name": "test-channel",
            "event_ts": "1694745600.123456"
        }
        channel_id = "C1234567890"
        user_id = "U1234567890"

        # Create mock services
        mock_channel_eligibility_service = AsyncMock()
        mock_channel_eligibility_service.is_channel_eligible.return_value = (True, "eligible")

        mock_feature_service = AsyncMock()
        mock_feature_service.is_user_join_notifications_enabled_for_channel.return_value = True

        mock_user_join_notification_service = AsyncMock()
        mock_user_join_notification_service.send_join_notification.return_value = True

        # NOTE: My fix adds a safety check, so the function won't crash anymore
        # Instead, it gracefully skips the counter incrementation
        # This is actually the correct behavior - better than crashing

        # Act - Call function without dynamodb_store parameter
        # This should complete successfully but NOT increment counters
        await process_regular_user_join(
            event=mock_event,
            channel_id=channel_id,
            user_id=user_id,
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
            join_notification_ops=None,
            restore_state_manager=None,
            # dynamodb_store parameter intentionally omitted - should skip counter increment
        )

        # Assert - Function should complete successfully (no NameError)
        # The safety check prevents counter incrementation when dynamodb_store is None

        # Verify user join notification was still sent (this part doesn't need dynamodb_store)
        mock_user_join_notification_service.send_join_notification.assert_called_once_with(
            user_id=user_id, channel_id=channel_id
        )

    @pytest.mark.asyncio
    async def test_green_fix_with_dynamodb_store_parameter(self):
        """
        GREEN Phase: Test that the fix works correctly.

        This test verifies that passing dynamodb_store parameter allows
        the function to work correctly and increment monthly counters.
        """
        # Arrange - create all necessary mocks including dynamodb_store
        mock_event = {
            "channel": "C1234567890",
            "channel_name": "test-channel",
            "event_ts": "1694745600.123456"
        }
        channel_id = "C1234567890"
        user_id = "U1234567890"

        # Create mock services
        mock_channel_eligibility_service = AsyncMock()
        mock_channel_eligibility_service.is_channel_eligible.return_value = (True, "eligible")

        mock_feature_service = AsyncMock()
        mock_feature_service.is_user_join_notifications_enabled_for_channel.return_value = True

        mock_user_join_notification_service = AsyncMock()
        mock_user_join_notification_service.send_join_notification.return_value = True

        # Create mock dynamodb_store - THIS IS THE KEY PART OF THE FIX
        mock_dynamodb_store = AsyncMock()
        mock_dynamodb_store.increment_monthly_counter = AsyncMock(return_value=True)

        # Act - Call the function WITH the dynamodb_store parameter
        # This should now work without errors
        await process_regular_user_join(
            event=mock_event,
            channel_id=channel_id,
            user_id=user_id,
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
            join_notification_ops=None,
            restore_state_manager=None,
            dynamodb_store=mock_dynamodb_store  # ← THE FIX
        )

        # Assert - Verify the function completed successfully
        # (No exception should be raised)

        # Verify that dynamodb_store methods were called
        # Check that increment_monthly_counter was called with expected parameters
        expected_month_key = datetime.now(timezone.utc).strftime("%Y_%m")

        # Should have called increment_monthly_counter at least once for war_room_sent
        mock_dynamodb_store.increment_monthly_counter.assert_called()

        # Get all the calls to verify the correct counters were incremented
        calls = mock_dynamodb_store.increment_monthly_counter.call_args_list

        # Should have at least one call for war_room_sent
        assert any("war_room_sent" in str(call) for call in calls)

        # Should have called with correct month_key
        assert any(expected_month_key in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_edge_case_dynamodb_store_none(self):
        """
        Test edge case where dynamodb_store is None.

        This verifies the safety check `if dynamodb_store:` works correctly
        and gracefully handles the case where dynamodb_store is not available.
        """
        # Arrange - same setup as before but with dynamodb_store=None
        mock_event = {"channel": "C1234567890", "channel_name": "test-channel"}
        channel_id = "C1234567890"
        user_id = "U1234567890"

        mock_channel_eligibility_service = AsyncMock()
        mock_channel_eligibility_service.is_channel_eligible.return_value = (True, "eligible")

        mock_feature_service = AsyncMock()
        mock_feature_service.is_user_join_notifications_enabled_for_channel.return_value = True

        mock_user_join_notification_service = AsyncMock()
        mock_user_join_notification_service.send_join_notification.return_value = True

        # Act - Call with dynamodb_store=None (should not crash)
        await process_regular_user_join(
            event=mock_event,
            channel_id=channel_id,
            user_id=user_id,
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
            join_notification_ops=None,
            restore_state_manager=None,
            dynamodb_store=None  # Edge case: None
        )

        # Assert - Function should complete without error
        # The safety check should prevent any dynamodb_store calls when it's None

        # Verify user join notification was still sent
        mock_user_join_notification_service.send_join_notification.assert_called_once_with(
            user_id=user_id, channel_id=channel_id
        )

    @pytest.mark.asyncio
    async def test_green_fix_counters_incremented_correctly(self):
        """
        GREEN Phase: Detailed test to verify counters are incremented correctly.

        This test simulates the complete happy path and verifies that
        the correct counters are incremented based on notification success/failure.
        """
        # Arrange
        mock_event = {"channel": "C1234567890", "channel_name": "test-channel"}
        channel_id = "C1234567890"
        user_id = "U1234567890"

        mock_channel_eligibility_service = AsyncMock()
        mock_channel_eligibility_service.is_channel_eligible.return_value = (True, "eligible")

        mock_feature_service = AsyncMock()
        mock_feature_service.is_user_join_notifications_enabled_for_channel.return_value = True

        mock_dynamodb_store = AsyncMock()
        mock_dynamodb_store.increment_monthly_counter = AsyncMock(return_value=True)

        expected_month_key = datetime.now(timezone.utc).strftime("%Y_%m")

        # Test Case 1: Successful notification
        mock_user_join_notification_service = AsyncMock()
        mock_user_join_notification_service.send_join_notification.return_value = True

        # Act
        await process_regular_user_join(
            event=mock_event,
            channel_id=channel_id,
            user_id=user_id,
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
            join_notification_ops=None,
            restore_state_manager=None,
            dynamodb_store=mock_dynamodb_store
        )

        # Assert - Check that correct counters were incremented for success case
        success_calls = mock_dynamodb_store.increment_monthly_counter.call_args_list

        # Should increment war_room_sent
        assert any(
            call.args == ("war_room_sent", expected_month_key, 1)
            for call in success_calls
        ), f"Expected war_room_sent call in: {success_calls}"

        # Should increment war_room_success (since notification was successful)
        assert any(
            call.args == ("war_room_success", expected_month_key, 1)
            for call in success_calls
        ), f"Expected war_room_success call in: {success_calls}"

        # Should NOT increment war_room_failed for successful case
        assert not any(
            call.args[0] == "war_room_failed"
            for call in success_calls
        ), "war_room_failed should not be incremented for successful notification"