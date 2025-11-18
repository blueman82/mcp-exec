"""
Unit tests for DynamoDBStore.is_duplicate_event method.

Tests the event deduplication functionality using atomic conditional puts.
"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.db.dynamodb_store import DynamoDBStore


@pytest.mark.asyncio
class TestDynamoDBStoreDeduplication:
    """Test the is_duplicate_event method in DynamoDBStore."""

    async def test_is_duplicate_event_new_event_returns_false(self):
        """Test that is_duplicate_event returns False for a new event."""
        # Arrange
        mock_client = AsyncMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock successful put_item (no exception means item was created)
        mock_client.put_item = AsyncMock(return_value={})

        # Act
        with patch("time.time", return_value=1234567890):
            result = await store.is_duplicate_event(
                team_id="T123", user_id="U456", timestamp="1234567890.123"
            )

        # Assert
        assert result is False  # New event, not a duplicate

        # Verify put_item was called with correct parameters
        mock_client.put_item.assert_awaited_once()
        call_args = mock_client.put_item.call_args

        assert call_args.kwargs["table_name"] == "test-table"
        assert call_args.kwargs["item"]["PK"]["S"] == "EVENT#T123#U456#1234567890.123"
        assert call_args.kwargs["item"]["SK"]["S"] == "DEDUP"
        assert call_args.kwargs["item"]["ttl"]["N"] == str(1234567890 + 60)
        assert call_args.kwargs["condition_expression"] == "attribute_not_exists(PK)"

    async def test_is_duplicate_event_duplicate_returns_true(self):
        """Test that is_duplicate_event returns True for a duplicate event."""
        # Arrange
        mock_client = AsyncMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock put_item to raise an exception with ConditionalCheckFailedException in the message
        mock_client.put_item = AsyncMock(
            side_effect=Exception(
                "ConditionalCheckFailedException: Item already exists"
            )
        )

        # Act
        result = await store.is_duplicate_event(
            team_id="T123", user_id="U456", timestamp="1234567890.123"
        )

        # Assert
        assert result is True  # Duplicate event
        mock_client.put_item.assert_awaited_once()

    async def test_is_duplicate_event_error_returns_false(self):
        """Test that is_duplicate_event returns False on unexpected errors to allow processing."""
        # Arrange
        mock_client = AsyncMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        # Mock put_item to raise a general exception
        mock_client.put_item = AsyncMock(
            side_effect=Exception("Unexpected DynamoDB error")
        )

        # Act
        result = await store.is_duplicate_event(
            team_id="T123", user_id="U456", timestamp="1234567890.123"
        )

        # Assert
        assert result is False  # On error, allow processing to continue
        mock_client.put_item.assert_awaited_once()

    async def test_is_duplicate_event_ttl_calculation(self):
        """Test that TTL is correctly calculated as 60 seconds from current time."""
        # Arrange
        mock_client = AsyncMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        mock_client.put_item = AsyncMock(return_value={})

        # Mock specific time
        mock_time = 1700000000

        # Act
        with patch("time.time", return_value=mock_time):
            await store.is_duplicate_event(
                team_id="T123", user_id="U456", timestamp="1234567890.123"
            )

        # Assert
        call_args = mock_client.put_item.call_args
        ttl_value = int(call_args.kwargs["item"]["ttl"]["N"])
        assert ttl_value == mock_time + 60  # TTL should be 60 seconds from mock_time

    async def test_is_duplicate_event_different_users_not_duplicates(self):
        """Test that events from different users are not considered duplicates."""
        # Arrange
        mock_client = AsyncMock()
        store = DynamoDBStore(client=mock_client, table_name="test-table")

        mock_client.put_item = AsyncMock(return_value={})

        # Act - First event from user U456
        result1 = await store.is_duplicate_event(
            team_id="T123", user_id="U456", timestamp="1234567890.123"
        )

        # Act - Second event from user U789 with same timestamp
        result2 = await store.is_duplicate_event(
            team_id="T123", user_id="U789", timestamp="1234567890.123"
        )

        # Assert
        assert result1 is False
        assert result2 is False

        # Verify different PKs were used
        first_call = mock_client.put_item.call_args_list[0]
        second_call = mock_client.put_item.call_args_list[1]

        assert first_call.kwargs["item"]["PK"]["S"] == "EVENT#T123#U456#1234567890.123"
        assert second_call.kwargs["item"]["PK"]["S"] == "EVENT#T123#U789#1234567890.123"
