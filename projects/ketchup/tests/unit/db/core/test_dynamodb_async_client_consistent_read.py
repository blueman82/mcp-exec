"""
Unit tests for DynamoDBAsyncClient consistent read functionality.

Tests that the consistent_read parameter is properly passed to the AWS DynamoDB client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.config.dynamodb_config import DynamoDBConfig
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient


@pytest.mark.asyncio
class TestDynamoDBAsyncClientConsistentRead:
    """Test consistent read functionality in DynamoDBAsyncClient."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock DynamoDB config."""
        config = MagicMock(spec=DynamoDBConfig)
        config.get_table_name.return_value = "test-table"
        config.get_region.return_value = "us-east-1"
        return config

    @pytest.fixture
    def mock_aioboto3_session(self):
        """Create a mock aioboto3 session with async context manager."""
        mock_client = AsyncMock()
        mock_client.get_item = AsyncMock()

        # Create async context manager for client
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__.return_value = mock_client
        mock_client_cm.__aexit__.return_value = None

        # Create mock session
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client_cm

        return mock_session, mock_client

    async def test_get_item_without_consistent_read(self, mock_config, mock_aioboto3_session):
        """Test that get_item works without consistent_read parameter (default behavior)."""
        mock_session, mock_client = mock_aioboto3_session

        with patch("aioboto3.Session", return_value=mock_session):
            client = DynamoDBAsyncClient(config=mock_config)

            # Setup the mock response
            mock_client.get_item.return_value = {"Item": {"id": {"S": "123"}}}

            # Call get_item without consistent_read
            key = {"PK": {"S": "TEST#123"}, "SK": {"S": "DETAILS"}}
            result = await client.get_item(key=key)

            # Verify the call was made without ConsistentRead
            mock_client.get_item.assert_called_once_with(TableName="test-table", Key=key)
            assert result == {"Item": {"id": {"S": "123"}}}

    async def test_get_item_with_consistent_read_false(self, mock_config, mock_aioboto3_session):
        """Test that get_item with consistent_read=False doesn't add ConsistentRead."""
        mock_session, mock_client = mock_aioboto3_session

        with patch("aioboto3.Session", return_value=mock_session):
            client = DynamoDBAsyncClient(config=mock_config)

            # Setup the mock response
            mock_client.get_item.return_value = {"Item": {"id": {"S": "456"}}}

            # Call get_item with consistent_read=False
            key = {"PK": {"S": "TEST#456"}, "SK": {"S": "DETAILS"}}
            result = await client.get_item(key=key, consistent_read=False)

            # Verify the call was made without ConsistentRead
            mock_client.get_item.assert_called_once_with(TableName="test-table", Key=key)
            assert result == {"Item": {"id": {"S": "456"}}}

    async def test_get_item_with_consistent_read_true(self, mock_config, mock_aioboto3_session):
        """Test that get_item with consistent_read=True adds ConsistentRead parameter."""
        mock_session, mock_client = mock_aioboto3_session

        with patch("aioboto3.Session", return_value=mock_session):
            client = DynamoDBAsyncClient(config=mock_config)

            # Setup the mock response
            mock_client.get_item.return_value = {"Item": {"id": {"S": "789"}}}

            # Call get_item with consistent_read=True
            key = {"PK": {"S": "TEST#789"}, "SK": {"S": "DETAILS"}}
            result = await client.get_item(key=key, consistent_read=True)

            # Verify the call was made WITH ConsistentRead
            mock_client.get_item.assert_called_once_with(
                TableName="test-table", Key=key, ConsistentRead=True
            )
            assert result == {"Item": {"id": {"S": "789"}}}

    async def test_get_item_with_custom_table_and_consistent_read(
        self, mock_config, mock_aioboto3_session
    ):
        """Test that both table_name and consistent_read parameters work together."""
        mock_session, mock_client = mock_aioboto3_session

        with patch("aioboto3.Session", return_value=mock_session):
            client = DynamoDBAsyncClient(config=mock_config)

            # Setup the mock response
            mock_client.get_item.return_value = {"Item": {"data": {"S": "test"}}}

            # Call get_item with both parameters
            key = {"PK": {"S": "CUSTOM#123"}, "SK": {"S": "DATA"}}
            result = await client.get_item(key=key, table_name="custom-table", consistent_read=True)

            # Verify both parameters were used
            mock_client.get_item.assert_called_once_with(
                TableName="custom-table", Key=key, ConsistentRead=True
            )
            assert result == {"Item": {"data": {"S": "test"}}}
