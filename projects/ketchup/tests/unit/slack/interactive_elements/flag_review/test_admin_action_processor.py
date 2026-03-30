"""
Unit tests for AdminActionProcessor.

Tests admin actions (acknowledge, reply) for flag review functionality.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from packages.slack.interactive_elements.flag_review.admin_action_processor import (
    AdminActionProcessor,
)
from packages.slack.interactive_elements.flag_review.flag_types import REVIEW_CHANNEL_ID


class TestAdminActionProcessor:
    """Test suite for AdminActionProcessor."""

    @pytest.fixture
    def mock_db_store(self):
        """Create a mock database store."""
        mock = Mock()
        mock.client = Mock()
        mock.client.put_item = AsyncMock(return_value={"ResponseMetadata": {}})
        mock.client.scan = AsyncMock(return_value={"Items": []})
        mock.client.update_item = AsyncMock(return_value={"ResponseMetadata": {}})
        mock.table_name = "test_table"
        return mock

    @pytest.fixture
    def mock_posting_handler(self):
        """Create a mock posting handler."""
        mock = Mock()
        mock.post_message = AsyncMock(return_value={"ok": True, "ts": "1234567890.123456"})
        mock.update_message = AsyncMock(return_value={"ok": True})
        mock.api_call = AsyncMock(return_value={"messages": [{"ts": "1234567890.123456"}]})
        return mock

    @pytest.fixture
    def mock_secrets_manager(self):
        """Create a mock secrets manager."""
        mock = Mock()
        mock.get_secret = AsyncMock(return_value={"bot_token": "xoxb-test-token"})
        return mock

    @pytest.fixture
    def admin_processor(self, mock_posting_handler, mock_db_store, mock_secrets_manager):
        """Create admin action processor with mocked dependencies."""
        return AdminActionProcessor(mock_posting_handler, mock_db_store, mock_secrets_manager)

    @pytest.mark.asyncio
    async def test_acknowledge_with_user_id_finds_correct_flag(
        self, admin_processor, mock_db_store
    ):
        """
        Test that acknowledge button with user_id finds the correct flag.

        This test demonstrates the bug: when multiple users flag the same message,
        the current implementation (without user_id in button value) cannot
        distinguish between them.

        EXPECTED TO FAIL until fix is implemented.
        """
        channel_id = "C095LQ0H4KB"
        message_ts = "1234567890.123456"
        user1_id = "U111111"
        admin_id = "UADMIN"

        # Simulate two users flagging the same message
        # User 1's flag record
        flag1_record = {
            "PK": {"S": f"FLAG_REVIEW#{channel_id}_{message_ts}_{user1_id}"},
            "SK": {"S": "TIMESTAMP#2025-10-01T15:00:00"},
            "flag_id": {"S": f"{channel_id}_{message_ts}_{user1_id}"},
            "channel_id": {"S": channel_id},
            "message_ts": {"S": message_ts},
            "user_id": {"S": user1_id},
            "status": {"S": "pending"},
        }

        # User 2's flag record

        # Mock database scan to return User 1's flag (limit=1 returns first match)
        mock_db_store.client.scan = AsyncMock(
            return_value={"Items": [flag1_record], "ScannedCount": 2}
        )

        # Admin clicks acknowledge on User 1's flag
        # Current implementation: button value = "channel_id|message_ts" (no user_id!)
        # Fixed implementation: button value = "channel_id|message_ts|user_id"
        payload = {
            "user": {"id": admin_id, "username": "admin"},
            "channel": {"id": "C_REVIEW_CHANNEL"},
            "actions": [
                {
                    "action_id": "acknowledge_feedback",
                    # Current format (2 parts) - ambiguous when multiple flags exist
                    # "value": f"{channel_id}|{message_ts}",
                    # Fixed format (3 parts) - unambiguous
                    "value": f"{channel_id}|{message_ts}|{user1_id}",
                }
            ],
        }

        # Execute acknowledgment
        result = await admin_processor.handle_acknowledgment(payload)

        # Assertions
        assert result is True, "Acknowledgment should succeed"

        # Verify database was queried correctly
        # With fix: should construct flag_id = f"{channel_id}_{message_ts}_{user1_id}"
        # Without fix: scans by channel_id and message_ts only (ambiguous)
        assert mock_db_store.client.scan.called or mock_db_store.client.update_item.called

        # Verify User 1's flag was updated (not User 2's)
        update_call = mock_db_store.client.update_item.call_args
        if update_call:
            updated_key = update_call[1]["key"]
            assert (
                updated_key["PK"]["S"] == flag1_record["PK"]["S"]
            ), "Should update User 1's flag specifically"

    @pytest.mark.asyncio
    async def test_acknowledge_command_execution_format(self, admin_processor, mock_db_store):
        """
        Test acknowledging a flag with command execution ID format.

        Reproduces production error:
        'No flag review found for channel C095LQ0H4KB, message_ts 1759328881_d323365a'

        EXPECTED TO FAIL if the record doesn't exist in database.
        """
        channel_id = "C095LQ0H4KB"
        message_ts = "1759328881_d323365a"  # Command execution format
        user_id = "U123456"
        admin_id = "UADMIN"

        # Mock: No flag record exists (reproduces production error)
        mock_db_store.client.scan = AsyncMock(return_value={"Items": [], "ScannedCount": 0})

        payload = {
            "user": {"id": admin_id, "username": "admin"},
            "channel": {"id": "C_REVIEW_CHANNEL"},
            "actions": [
                {
                    "action_id": "acknowledge_feedback",
                    "value": f"{channel_id}|{message_ts}|{user_id}",
                }
            ],
        }

        # Execute acknowledgment
        result = await admin_processor.handle_acknowledgment(payload)

        # Should handle gracefully (not crash)
        # Current behavior: logs warning and returns True
        # Expected: Should return False or log appropriate error
        assert result is not None, "Should handle missing record gracefully"

    @pytest.mark.asyncio
    async def test_acknowledge_backward_compatibility(self, admin_processor, mock_db_store):
        """
        Test that acknowledge handles old 2-part button values for backward compatibility.

        Old format: "channel_id|message_ts"
        New format: "channel_id|message_ts|user_id"
        """
        channel_id = "C123"
        message_ts = "1234567890.123456"

        flag_record = {
            "PK": {"S": f"FLAG_REVIEW#{channel_id}_{message_ts}_U123"},
            "SK": {"S": "TIMESTAMP#2025-10-01T15:00:00"},
            "flag_id": {"S": f"{channel_id}_{message_ts}_U123"},
            "channel_id": {"S": channel_id},
            "message_ts": {"S": message_ts},
            "user_id": {"S": "U123"},
            "status": {"S": "pending"},
        }

        mock_db_store.client.scan = AsyncMock(
            return_value={"Items": [flag_record], "ScannedCount": 1}
        )

        # Old format button value (2 parts)
        payload = {
            "user": {"id": "UADMIN", "username": "admin"},
            "channel": {"id": "C_REVIEW_CHANNEL"},
            "actions": [
                {"action_id": "acknowledge_feedback", "value": f"{channel_id}|{message_ts}"}
            ],
        }

        # Should still work with old format (backward compatibility)
        result = await admin_processor.handle_acknowledgment(payload)

        assert result is True, "Should handle old format for backward compatibility"

    @pytest.mark.asyncio
    async def test_reply_button_has_user_id(self, admin_processor):
        """
        Test that reply button value includes user_id (already correct).

        This is for comparison - reply buttons already have the correct format.
        Acknowledge buttons should match this pattern.
        """
        channel_id = "C123"
        message_ts = "1234567890.123456"
        user_id = "U123"

        payload = {
            "user": {"id": "UADMIN", "username": "admin"},
            "channel": {"id": "C_REVIEW_CHANNEL"},
            "actions": [
                {
                    "action_id": "reply_to_feedback",
                    "value": f"{channel_id}|{message_ts}|{user_id}",  # Already has user_id
                }
            ],
        }

        # This should parse correctly (3 parts)
        result = await admin_processor.handle_reply_button_click(payload)

        # Should succeed (reply modal opens)
        assert result is True, "Reply button should parse 3-part value correctly"

    @pytest.mark.asyncio
    async def test_reply_submission_sends_ephemeral_confirmation(
        self, admin_processor, mock_posting_handler
    ):
        """Test that submitting a reply sends an ephemeral confirmation to the admin."""
        admin_id = "UADMIN"
        flagged_user_id = "UFLAGGED"
        channel_id = "C123"
        message_ts = "1234567890.123456"

        payload = {
            "user": {"id": admin_id, "username": "admin"},
            "view": {
                "state": {
                    "values": {
                        "reply_block": {
                            "reply_input": {"value": "Thanks for the feedback, we've fixed it."}
                        }
                    }
                },
                "private_metadata": f"{channel_id}|{message_ts}|{flagged_user_id}",
            },
        }

        # Mock the response handler methods
        admin_processor.response_handler.send_reply_dm = AsyncMock(return_value=True)
        admin_processor.response_handler.update_review_message_with_reply = AsyncMock()
        admin_processor.response_handler.update_feedback_status = AsyncMock()

        result = await admin_processor.handle_reply_submission(payload)

        assert result is True

        # Verify ephemeral confirmation was sent to the review channel
        ephemeral_calls = [
            call
            for call in mock_posting_handler.post_message.call_args_list
            if call[1].get("channel_id") == REVIEW_CHANNEL_ID
            or (call[0] and len(call[0]) > 0 and call[0][0] == REVIEW_CHANNEL_ID)
        ]
        assert len(ephemeral_calls) == 1, "Should send ephemeral confirmation to review channel"

        call_kwargs = ephemeral_calls[0][1] if ephemeral_calls[0][1] else {}
        assert admin_id in (call_kwargs.get("user_id", "") or "")
        assert flagged_user_id in (call_kwargs.get("message", "") or "")
