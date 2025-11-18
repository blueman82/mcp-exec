"""
Unit tests for DynamoDBStore.update_channel_fields delegation method.

Tests that the DynamoDBStore properly delegates update_channel_fields
to the underlying ChannelOperations instance.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.db.dynamodb_store import DynamoDBStore


@pytest.mark.asyncio
class TestDynamoDBStoreUpdateChannelFields:
    """Test the update_channel_fields delegation in DynamoDBStore."""

    async def test_update_channel_fields_delegates_to_channel_ops(self):
        """Test that update_channel_fields properly delegates to channel_ops."""
        # Arrange
        mock_client = MagicMock()
        mock_client.put_item = AsyncMock()

        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock the channel_ops update_channel_fields method
        store.channel_ops.update_channel_fields = AsyncMock(return_value=True)

        channel_id = "C12345"
        updates = {
            "auto_status_last_content": "",
            "auto_status_last_message_ts": "0",
            "auto_status_last_post_ts": "",
            "auto_status_attempt_count": 0,
            "auto_status_enabled": False,
            "auto_status_last_run": 0,
        }

        # Act
        result = await store.update_channel_fields(
            channel_id=channel_id, updates=updates
        )

        # Assert
        assert result is True
        store.channel_ops.update_channel_fields.assert_awaited_once_with(
            channel_id=channel_id, updates=updates
        )

    async def test_update_channel_fields_returns_false_on_failure(self):
        """Test that update_channel_fields returns False when channel_ops fails."""
        # Arrange
        mock_client = MagicMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock the channel_ops to return False
        store.channel_ops.update_channel_fields = AsyncMock(return_value=False)

        # Act
        result = await store.update_channel_fields(
            channel_id="C67890", updates={"field": "value"}
        )

        # Assert
        assert result is False
