"""
Test auto-status behavior when trying to delete a non-existent message.

This test verifies that when the auto-status system tries to delete a previous
message that no longer exists (user deleted it), the system gracefully continues
and posts a new message instead of failing.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_auto_status_continues_when_delete_fails():
    """
    Test that auto-status posts new message even when delete of previous message fails.

    Scenario:
    1. User deletes the previous auto-status message from Slack
    2. Auto-status tries to delete the (already deleted) message -> FAILS
    3. Auto-status should continue and post a NEW message -> SUCCESS

    This is the ACTUAL behavior per lines 633-639 in status_generator.py:
    - Delete failure logs warning
    - System continues with new post (doesn't fail)
    """
    from ketchup_status_updater.status_generator import AutoStatusGenerator

    # Create mocks
    mock_posting_handler = AsyncMock()
    mock_posting_handler._slack_token = "xoxb-test-token"

    # Mock delete_message to FAIL (message already deleted by user)
    mock_posting_handler.delete_message = AsyncMock(
        return_value={
            "ok": False,
            "error": "message_not_found",  # Slack API error when message doesn't exist
        }
    )

    # Mock _post_channel_message to SUCCEED
    mock_posting_handler._post_channel_message = AsyncMock(
        return_value={"ok": True, "ts": "1234567890.123456"}
    )

    # Mock update_message (for adding flag button)
    mock_posting_handler.update_message = AsyncMock(return_value={"ok": True})

    # Mock channel operations
    mock_channel_ops = AsyncMock()
    mock_channel_ops.get_channel_details = AsyncMock(
        return_value={
            "channel_id": "C123",
            "channel_name": "test-channel",
            "auto_status_last_post_ts": "9999999999.999999",  # Timestamp of deleted message
        }
    )
    mock_channel_ops.update_channel_fields = AsyncMock()

    # Mock query_ops for get_channel_details
    mock_query_ops = AsyncMock()
    mock_query_ops.get_channel_details = mock_channel_ops.get_channel_details
    mock_channel_ops.query_ops = mock_query_ops

    # Create AutoStatusGenerator instance with all required params in correct order
    generator = AutoStatusGenerator(
        db_store=MagicMock(),
        mcp_client=MagicMock(),
        secrets_manager=MagicMock(),
        slack_config=MagicMock(),
        openai_handler=MagicMock(),
        channel_info_ops=MagicMock(),
        channel_msg_ops=MagicMock(),
        posting_handler=mock_posting_handler,
        channel_operations=mock_channel_ops,
    )

    # Call the method that deletes old message and posts new one
    result = await generator._post_to_slack_public(
        channel_id="C123",
        content="*Overview:* Test status update\n\n*What's been done / What's next:*\n• Item 1",
        status_update_id="1234567890_abc123",
    )

    # VERIFY: Delete was attempted (and failed)
    mock_posting_handler.delete_message.assert_called_once_with(
        channel_id="C123", message_ts="9999999999.999999"
    )

    # VERIFY: Despite delete failure, new message was posted
    mock_posting_handler._post_channel_message.assert_called_once()

    # VERIFY: Result indicates success
    assert result["success"] is True
    assert result["message_ts"] == "1234567890.123456"

    # VERIFY: New timestamp was stored for future deletion
    mock_channel_ops.update_channel_fields.assert_called()
