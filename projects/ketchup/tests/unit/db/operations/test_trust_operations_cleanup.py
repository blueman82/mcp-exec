"""
Test trust operations cleanup functionality.
"""

from unittest.mock import AsyncMock

import pytest

from packages.db.operations.trust_operations import TrustOperations


class TestTrustOperationsCleanup:
    """Test trust operations cleanup methods."""

    @pytest.fixture
    def mock_client(self):
        """Mock DynamoDB client."""
        client = AsyncMock()
        # Mock the underlying client for batch operations
        underlying_client = AsyncMock()
        underlying_client.batch_write_item = AsyncMock()
        client._get_client = AsyncMock(return_value=underlying_client)
        return client

    @pytest.fixture
    def trust_ops(self, mock_client):
        """Trust operations instance with mocked client."""
        ops = TrustOperations(mock_client, "test_table")
        return ops

    @pytest.mark.asyncio
    async def test_cleanup_channel_trust_data_success(self, trust_ops, mock_client):
        """Test successful cleanup of channel trust data."""
        # Mock query response with trust endorsement items
        mock_client.query.return_value = {
            "Items": [
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": "STATUS#1751756295_abc123"},
                },
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": "STATUS#1751756300_def456"},
                },
            ]
        }

        # Mock successful batch delete
        underlying_client = await mock_client._get_client()
        underlying_client.batch_write_item.return_value = {}

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is True

        # Verify query was called correctly
        mock_client.query.assert_called_once_with(
            table_name="test_table",
            key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
            expression_attribute_values={
                ":pk": {"S": "CHANNEL#C1234567890"},
                ":sk_prefix": {"S": "STATUS#"},
            },
        )

        # Verify batch delete was called
        underlying_client = await mock_client._get_client()
        underlying_client.batch_write_item.assert_called_once()

        # Verify delete request structure
        delete_call = underlying_client.batch_write_item.call_args[1]
        request_items = delete_call["RequestItems"]["test_table"]
        assert len(request_items) == 2
        assert request_items[0]["DeleteRequest"]["Key"]["PK"]["S"] == "CHANNEL#C1234567890"
        assert request_items[0]["DeleteRequest"]["Key"]["SK"]["S"] == "STATUS#1751756295_abc123"

    @pytest.mark.asyncio
    async def test_cleanup_channel_trust_data_no_items(self, trust_ops, mock_client):
        """Test cleanup when no trust data exists."""
        # Mock empty query response
        mock_client.query.return_value = {"Items": []}

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is True

        # Verify query was called but no delete
        mock_client.query.assert_called_once()
        underlying_client = await mock_client._get_client()
        underlying_client.batch_write_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_channel_trust_data_large_batch(self, trust_ops, mock_client):
        """Test cleanup with large number of items requiring multiple batches."""
        # Create 50 mock items (requires 2 batches of 25 each)
        items = []
        for i in range(50):
            items.append(
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": f"STATUS#175175629{i:02d}_item{i:03d}"},
                }
            )

        mock_client.query.return_value = {"Items": items}
        underlying_client = await mock_client._get_client()
        underlying_client.batch_write_item.return_value = {}

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is True

        # Verify two batch deletes were called (25 items each)
        underlying_client = await mock_client._get_client()
        assert underlying_client.batch_write_item.call_count == 2

        # Verify batch sizes
        calls = underlying_client.batch_write_item.call_args_list
        first_batch = calls[0][1]["RequestItems"]["test_table"]
        second_batch = calls[1][1]["RequestItems"]["test_table"]

        assert len(first_batch) == 25
        assert len(second_batch) == 25

    @pytest.mark.asyncio
    async def test_cleanup_channel_trust_data_query_error(self, trust_ops, mock_client):
        """Test cleanup when query fails."""
        # Mock query error
        mock_client.query.side_effect = Exception("DynamoDB query failed")

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is False

        # Verify no delete was attempted
        underlying_client = await mock_client._get_client()
        underlying_client.batch_write_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_channel_trust_data_delete_error(self, trust_ops, mock_client):
        """Test cleanup when batch delete fails."""
        # Mock successful query
        mock_client.query.return_value = {
            "Items": [
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": "STATUS#1751756295_abc123"},
                }
            ]
        }

        # Mock batch delete error
        underlying_client = await mock_client._get_client()
        underlying_client.batch_write_item.side_effect = Exception("DynamoDB batch delete failed")

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is False

        # Verify query was called but delete failed
        mock_client.query.assert_called_once()
        underlying_client = await mock_client._get_client()
        underlying_client.batch_write_item.assert_called_once()

    # New tests as specified in task requirements
    @pytest.mark.asyncio
    async def test_cleanup_trust_data_success(self, trust_ops, mock_client):
        """Test successful cleanup of trust data."""
        # Mock query response with trust endorsement items
        mock_client.query.return_value = {
            "Items": [
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": "STATUS#1751756295_abc123"},
                },
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": "STATUS#1751756300_def456"},
                },
            ]
        }

        # Mock _get_client() properly
        underlying_client = AsyncMock()
        underlying_client.batch_write_item = AsyncMock(return_value={})
        mock_client._get_client = AsyncMock(return_value=underlying_client)

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is True

        # Verify query was called correctly
        mock_client.query.assert_called_once_with(
            table_name="test_table",
            key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
            expression_attribute_values={
                ":pk": {"S": "CHANNEL#C1234567890"},
                ":sk_prefix": {"S": "STATUS#"},
            },
        )

        # Verify batch delete was called with correct RequestItems parameter
        underlying_client.batch_write_item.assert_called_once()
        delete_call = underlying_client.batch_write_item.call_args[1]
        request_items = delete_call["RequestItems"]["test_table"]
        assert len(request_items) == 2
        assert request_items[0]["DeleteRequest"]["Key"]["PK"]["S"] == "CHANNEL#C1234567890"

    @pytest.mark.asyncio
    async def test_cleanup_trust_data_empty(self, trust_ops, mock_client):
        """Test cleanup when no trust data exists (empty scenario)."""
        # Mock empty query response
        mock_client.query.return_value = {"Items": []}

        # Mock _get_client() properly (won't be used but ensure it's mocked)
        underlying_client = AsyncMock()
        underlying_client.batch_write_item = AsyncMock(return_value={})
        mock_client._get_client = AsyncMock(return_value=underlying_client)

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is True

        # Verify query was called but no delete
        mock_client.query.assert_called_once()
        underlying_client.batch_write_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_trust_data_large_batch(self, trust_ops, mock_client):
        """Test cleanup with large number of items requiring multiple batches."""
        # Create 50 mock items (requires 2 batches of 25 each)
        items = []
        for i in range(50):
            items.append(
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": f"STATUS#175175629{i:02d}_item{i:03d}"},
                }
            )

        mock_client.query.return_value = {"Items": items}

        # Mock _get_client() properly
        underlying_client = AsyncMock()
        underlying_client.batch_write_item = AsyncMock(return_value={})
        mock_client._get_client = AsyncMock(return_value=underlying_client)

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result
        assert result is True

        # Verify two batch deletes were called (25 items each)
        assert underlying_client.batch_write_item.call_count == 2

        # Verify batch sizes with correct RequestItems parameter
        calls = underlying_client.batch_write_item.call_args_list
        first_batch = calls[0][1]["RequestItems"]["test_table"]
        second_batch = calls[1][1]["RequestItems"]["test_table"]

        assert len(first_batch) == 25
        assert len(second_batch) == 25

    @pytest.mark.asyncio
    async def test_cleanup_trust_data_partial_failure(self, trust_ops, mock_client):
        """Test cleanup when batch delete partially fails."""
        # Mock successful query
        mock_client.query.return_value = {
            "Items": [
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": "STATUS#1751756295_abc123"},
                },
                {
                    "PK": {"S": "CHANNEL#C1234567890"},
                    "SK": {"S": "STATUS#1751756300_def456"},
                },
            ]
        }

        # Mock _get_client() properly with partial failure (unprocessed items)
        underlying_client = AsyncMock()
        underlying_client.batch_write_item = AsyncMock(
            return_value={
                "UnprocessedItems": {
                    "test_table": [
                        {
                            "DeleteRequest": {
                                "Key": {
                                    "PK": {"S": "CHANNEL#C1234567890"},
                                    "SK": {"S": "STATUS#1751756300_def456"},
                                }
                            }
                        }
                    ]
                }
            }
        )
        mock_client._get_client = AsyncMock(return_value=underlying_client)

        # Execute cleanup
        result = await trust_ops.cleanup_channel_trust_data("C1234567890")

        # Verify result (should still be True as partial success is handled)
        assert result is True

        # Verify query was called and delete was attempted
        mock_client.query.assert_called_once()
        underlying_client.batch_write_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_trust_data_no_channel(self, trust_ops, mock_client):
        """Test cleanup with invalid or non-existent channel."""
        # Mock query that finds no items for non-existent channel
        mock_client.query.return_value = {"Items": []}

        # Mock _get_client() properly
        underlying_client = AsyncMock()
        underlying_client.batch_write_item = AsyncMock(return_value={})
        mock_client._get_client = AsyncMock(return_value=underlying_client)

        # Execute cleanup with empty/invalid channel
        result = await trust_ops.cleanup_channel_trust_data("")

        # Verify result (should be True as empty query is handled)
        assert result is True

        # Verify query was called but no delete
        mock_client.query.assert_called_once_with(
            table_name="test_table",
            key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
            expression_attribute_values={
                ":pk": {"S": "CHANNEL#"},
                ":sk_prefix": {"S": "STATUS#"},
            },
        )
        underlying_client.batch_write_item.assert_not_called()
