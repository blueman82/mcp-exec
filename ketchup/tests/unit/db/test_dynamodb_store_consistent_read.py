"""
Unit tests for DynamoDBStore.get_channel_details_consistent delegation.

Tests that the DynamoDBStore properly delegates consistent read requests
to the underlying ChannelQueryOperations instance.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.db.dynamodb_store import DynamoDBStore


@pytest.mark.asyncio
class TestDynamoDBStoreConsistentRead:
    """Test the get_channel_details_consistent delegation in DynamoDBStore."""

    async def test_get_channel_details_consistent_delegates_correctly(self):
        """Test that get_channel_details_consistent properly delegates to channel_ops.query_ops."""
        # Arrange
        mock_client = MagicMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock the query_ops method
        expected_result = {
            "channel_id": "C12345",
            "channel_name": "test-channel",
            "archived": False,
        }
        store.channel_ops.query_ops.get_channel_details_consistent = AsyncMock(
            return_value=expected_result
        )

        # Act
        result = await store.get_channel_details_consistent("C12345")

        # Assert
        assert result == expected_result
        store.channel_ops.query_ops.get_channel_details_consistent.assert_awaited_once_with(
            "C12345"
        )

    async def test_get_channel_details_consistent_returns_none_on_not_found(self):
        """Test that get_channel_details_consistent returns None when channel not found."""
        # Arrange
        mock_client = MagicMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock to return None (channel not found)
        store.channel_ops.query_ops.get_channel_details_consistent = AsyncMock(
            return_value=None
        )

        # Act
        result = await store.get_channel_details_consistent("C404")

        # Assert
        assert result is None
        store.channel_ops.query_ops.get_channel_details_consistent.assert_awaited_once_with(
            "C404"
        )

    async def test_get_channel_details_consistent_propagates_exceptions(self):
        """Test that exceptions from query_ops are propagated correctly."""
        # Arrange
        mock_client = MagicMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock to raise an exception
        store.channel_ops.query_ops.get_channel_details_consistent = AsyncMock(
            side_effect=Exception("DynamoDB error")
        )

        # Act & Assert
        with pytest.raises(Exception, match="DynamoDB error"):
            await store.get_channel_details_consistent("C500")
