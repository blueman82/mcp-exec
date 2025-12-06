"""
Unit tests for the thread message classification fix in message_preparation.py
Tests for CPGNCX-60117 - Thread messages incorrectly counted as channel messages
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.ai.core.operations.message_preparation import MessagePreparer


@pytest.mark.asyncio
async def test_prepare_messages_for_auto_status_thread_classification():
    """Test that thread messages are correctly classified separately from channel messages."""

    # Mock dependencies
    mock_token_tracker = MagicMock()
    mock_channel_msg_ops = AsyncMock()
    mock_channel_info_ops = AsyncMock()

    preparer = MessagePreparer(
        token_tracker=mock_token_tracker,
        channel_msg_ops=mock_channel_msg_ops,
        channel_info_ops=mock_channel_info_ops,
    )

    channel_id = "C091GU7LT6J"
    since_ts = "1736350000.000000"

    # Test Case 1: Only thread messages
    mock_channel_msg_ops.check_recent_thread_activity.return_value = (
        True,  # has_thread_activity
        "1736358000.000000",  # latest_thread_ts
        ["1736357000.000000", "1736357500.000000"],  # active_thread_timestamps
    )

    # Mock messages that are clearly thread replies
    mock_channel_msg_ops.fetch_channel_messages.return_value = [
        "[Thread] User1: Thread reply 1",
        "[Thread] User2: Thread reply 2",
    ]

    # Latest message timestamp should be old (no new channel messages)
    mock_channel_msg_ops.latest_message_ts = since_ts

    formatted_messages, metadata = await preparer.prepare_messages_for_auto_status(
        channel_id=channel_id, since_ts=since_ts
    )

    # Assert thread activity detected but no channel messages
    assert metadata["has_thread_activity"]
    assert not metadata["has_channel_messages"]
    assert metadata["thread_count"] == 2
    assert metadata["message_count"] == 2

    # Test Case 2: Both channel and thread messages
    mock_channel_msg_ops.fetch_channel_messages.return_value = [
        "User3: Channel message 1",
        "User4: Channel message 2",
        "[Thread] User1: Thread reply 1",
        "[Thread] User2: Thread reply 2",
    ]

    # Latest message timestamp should be recent (new channel messages)
    mock_channel_msg_ops.latest_message_ts = "1736358560.000000"

    formatted_messages, metadata = await preparer.prepare_messages_for_auto_status(
        channel_id=channel_id, since_ts=since_ts
    )

    # Assert both types detected
    assert metadata["has_thread_activity"]
    assert metadata["has_channel_messages"]
    assert metadata["thread_count"] == 2
    assert metadata["message_count"] == 4

    # Test Case 3: Only channel messages
    mock_channel_msg_ops.check_recent_thread_activity.return_value = (
        False,  # has_thread_activity
        since_ts,  # latest_thread_ts (unchanged)
        [],  # no active_thread_timestamps
    )

    mock_channel_msg_ops.fetch_channel_messages.return_value = [
        "User5: Channel message only",
        "User6: Another channel message",
    ]

    formatted_messages, metadata = await preparer.prepare_messages_for_auto_status(
        channel_id=channel_id, since_ts=since_ts
    )

    # Assert only channel messages detected
    assert not metadata["has_thread_activity"]
    assert metadata["has_channel_messages"]
    assert metadata["thread_count"] == 0
    assert metadata["message_count"] == 2

    # Test Case 4: No messages at all
    mock_channel_msg_ops.fetch_channel_messages.return_value = []

    formatted_messages, metadata = await preparer.prepare_messages_for_auto_status(
        channel_id=channel_id, since_ts=since_ts
    )

    # Assert no activity
    assert not metadata["has_thread_activity"]
    assert not metadata["has_channel_messages"]
    assert formatted_messages == "No messages found"


@pytest.mark.asyncio
async def test_prepare_messages_for_auto_status_error_handling():
    """Test error handling in prepare_messages_for_auto_status."""

    mock_token_tracker = MagicMock()
    mock_channel_msg_ops = AsyncMock()
    mock_channel_info_ops = AsyncMock()

    preparer = MessagePreparer(
        token_tracker=mock_token_tracker,
        channel_msg_ops=mock_channel_msg_ops,
        channel_info_ops=mock_channel_info_ops,
    )

    # Simulate an error in check_recent_thread_activity
    mock_channel_msg_ops.check_recent_thread_activity.side_effect = Exception("API Error")

    formatted_messages, metadata = await preparer.prepare_messages_for_auto_status(
        channel_id="C091GU7LT6J", since_ts="1736350000.000000"
    )

    # Should handle error gracefully
    assert formatted_messages == "Error fetching messages"
    assert not metadata["has_channel_messages"]
    assert not metadata["has_thread_activity"]


@pytest.mark.asyncio
async def test_backward_compatibility():
    """Test that existing code using the old metadata format still works."""

    mock_token_tracker = MagicMock()
    mock_channel_msg_ops = AsyncMock()
    mock_channel_info_ops = AsyncMock()

    preparer = MessagePreparer(
        token_tracker=mock_token_tracker,
        channel_msg_ops=mock_channel_msg_ops,
        channel_info_ops=mock_channel_info_ops,
    )

    mock_channel_msg_ops.check_recent_thread_activity.return_value = (
        True,
        "123",
        ["456"],
    )
    mock_channel_msg_ops.fetch_channel_messages.return_value = ["Message 1"]
    mock_channel_msg_ops.latest_message_ts = "1736358560.000000"

    formatted_messages, metadata = await preparer.prepare_messages_for_auto_status(
        channel_id="C091GU7LT6J", since_ts="1736350000.000000"
    )

    # Old fields should still exist
    assert "latest_ts" in metadata
    assert "has_thread_activity" in metadata

    # New fields should also exist
    assert "has_channel_messages" in metadata
    assert "message_count" in metadata
    assert "thread_count" in metadata
