"""
Unit tests for ChannelQueryOperations consistent read functionality.

Tests the get_channel_details_consistent method.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.db.operations.channel_query_operations import ChannelQueryOperations


@pytest.mark.asyncio
class TestChannelQueryOperationsConsistentRead:
    """Test consistent read functionality in ChannelQueryOperations."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock DynamoDB client."""
        client = MagicMock()
        client.get_item = AsyncMock()
        return client

    async def test_get_channel_details_consistent_success(self, mock_client):
        """Test successful retrieval with consistent read."""
        # Setup
        mock_client.get_item.return_value = {
            "Item": {
                "PK": {"S": "CHANNEL#C123"},
                "SK": {"S": "CSO_DETAILS"},
                "channel_id": {"S": "C123"},
                "channel_name": {"S": "test-channel"},
                "archived": {"BOOL": False},
                "archived_at": {"N": "0"},
            }
        }

        ops = ChannelQueryOperations(client=mock_client, table_name="test-table")

        # Execute
        result = await ops.get_channel_details_consistent("C123")

        # Verify
        mock_client.get_item.assert_called_once_with(
            key={"PK": {"S": "CHANNEL#C123"}, "SK": {"S": "CSO_DETAILS"}},
            table_name="test-table",
            consistent_read=True,
        )

        assert result is not None
        assert result["channel_id"] == "C123"
        assert result["channel_name"] == "test-channel"
        assert result["archived"] is False

    async def test_get_channel_details_consistent_not_found(self, mock_client):
        """Test behavior when channel is not found with consistent read."""
        # Setup
        mock_client.get_item.return_value = {}  # No Item key means not found

        ops = ChannelQueryOperations(client=mock_client, table_name="test-table")

        # Execute
        result = await ops.get_channel_details_consistent("C404")

        # Verify
        mock_client.get_item.assert_called_once_with(
            key={"PK": {"S": "CHANNEL#C404"}, "SK": {"S": "CSO_DETAILS"}},
            table_name="test-table",
            consistent_read=True,
        )

        assert result is None

    async def test_get_channel_details_consistent_error_handling(self, mock_client):
        """Test error handling in consistent read method."""
        # Setup
        mock_client.get_item.side_effect = Exception("DynamoDB error")

        ops = ChannelQueryOperations(client=mock_client, table_name="test-table")

        # Execute
        result = await ops.get_channel_details_consistent("C500")

        # Verify
        mock_client.get_item.assert_called_once()
        assert result is None  # Should return None on error

    async def test_get_channel_details_regular_vs_consistent(self, mock_client):
        """Test that regular and consistent methods use different parameters."""
        # Setup
        mock_client.get_item.return_value = {
            "Item": {
                "PK": {"S": "CHANNEL#C789"},
                "SK": {"S": "CSO_DETAILS"},
                "channel_id": {"S": "C789"},
            }
        }

        ops = ChannelQueryOperations(client=mock_client, table_name="test-table")

        # Execute regular read
        await ops.get_channel_details("C789")

        # Verify regular read doesn't use consistent_read
        regular_call = mock_client.get_item.call_args_list[0]
        assert "consistent_read" not in regular_call[1]

        # Reset mock
        mock_client.get_item.reset_mock()

        # Execute consistent read
        await ops.get_channel_details_consistent("C789")

        # Verify consistent read uses consistent_read=True
        consistent_call = mock_client.get_item.call_args_list[0]
        assert consistent_call[1]["consistent_read"] is True
