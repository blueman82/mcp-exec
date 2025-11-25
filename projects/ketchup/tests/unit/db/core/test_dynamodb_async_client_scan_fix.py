"""Test DynamoDB async client scan method with proper value formatting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.config.dynamodb_config import DynamoDBConfig
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient


class TestDynamoDBAsyncClientScanFix:
    """Test the scan method properly formats expression attribute values."""

    @pytest.mark.asyncio
    async def test_scan_with_plain_string_values(self):
        """Test scan converts plain string values to DynamoDB format."""
        # Setup
        config = MagicMock(spec=DynamoDBConfig)
        config.get_table_name.return_value = "test-table"

        client = DynamoDBAsyncClient(config)

        # Mock the boto3 client
        mock_boto_client = AsyncMock()
        mock_boto_client.scan = AsyncMock(
            return_value={
                "Items": [
                    {"PK": {"S": "CHANNEL#D123"}, "SK": {"S": "COMMAND#123#abc"}}
                ],
                "Count": 1,
            }
        )

        with patch.object(client, "_get_client", return_value=mock_boto_client):
            # Call scan with plain string values
            result = await client.scan(
                filter_expression="SK = :sk",
                expression_attribute_values={
                    ":sk": "COMMAND#123#abc"  # Plain string value
                },
            )

        # Verify the boto3 client was called with properly formatted values
        mock_boto_client.scan.assert_called_once()
        call_args = mock_boto_client.scan.call_args[1]

        # Check that plain string was converted to DynamoDB format
        assert call_args["ExpressionAttributeValues"] == {
            ":sk": {"S": "COMMAND#123#abc"}
        }
        assert result["Count"] == 1

    @pytest.mark.asyncio
    async def test_scan_with_already_formatted_values(self):
        """Test scan preserves already formatted DynamoDB values."""
        # Setup
        config = MagicMock(spec=DynamoDBConfig)
        config.get_table_name.return_value = "test-table"

        client = DynamoDBAsyncClient(config)

        # Mock the boto3 client
        mock_boto_client = AsyncMock()
        mock_boto_client.scan = AsyncMock(return_value={"Items": [], "Count": 0})

        with patch.object(client, "_get_client", return_value=mock_boto_client):
            # Call scan with already formatted values
            await client.scan(
                filter_expression="channel_id = :channel AND timestamp > :ts",
                expression_attribute_values={
                    ":channel": {"S": "D0840EX80R5"},  # Already formatted
                    ":ts": {"N": "1755808886"},  # Already formatted
                },
            )

        # Verify formatted values were preserved
        call_args = mock_boto_client.scan.call_args[1]
        assert call_args["ExpressionAttributeValues"] == {
            ":channel": {"S": "D0840EX80R5"},
            ":ts": {"N": "1755808886"},
        }

    @pytest.mark.asyncio
    async def test_scan_with_mixed_value_types(self):
        """Test scan handles mixed value types correctly."""
        # Setup
        config = MagicMock(spec=DynamoDBConfig)
        config.get_table_name.return_value = "test-table"

        client = DynamoDBAsyncClient(config)

        # Mock the boto3 client
        mock_boto_client = AsyncMock()
        mock_boto_client.scan = AsyncMock(return_value={"Items": [], "Count": 0})

        with patch.object(client, "_get_client", return_value=mock_boto_client):
            # Call scan with mixed value types
            await client.scan(
                filter_expression="test = :str AND count = :num AND active = :bool",
                expression_attribute_values={
                    ":str": "test-value",  # Plain string
                    ":num": 42,  # Plain number
                    ":bool": True,  # Plain boolean
                },
            )

        # Verify all types were converted correctly
        call_args = mock_boto_client.scan.call_args[1]
        assert call_args["ExpressionAttributeValues"] == {
            ":str": {"S": "test-value"},
            ":num": {"N": "42"},
            ":bool": {"BOOL": True},
        }

    @pytest.mark.asyncio
    async def test_query_with_plain_values(self):
        """Test query also converts plain values to DynamoDB format."""
        # Setup
        config = MagicMock(spec=DynamoDBConfig)
        config.get_table_name.return_value = "test-table"

        client = DynamoDBAsyncClient(config)

        # Mock the boto3 client
        mock_boto_client = AsyncMock()
        mock_boto_client.query = AsyncMock(return_value={"Items": [], "Count": 0})

        with patch.object(client, "_get_client", return_value=mock_boto_client):
            # Call query with plain values
            await client.query(
                key_condition_expression="PK = :pk",
                expression_attribute_values={
                    ":pk": "CHANNEL#D0840EX80R5"  # Plain string
                },
            )

        # Verify the value was converted
        call_args = mock_boto_client.query.call_args[1]
        assert call_args["ExpressionAttributeValues"] == {
            ":pk": {"S": "CHANNEL#D0840EX80R5"}
        }

    def test_convert_to_dynamodb_format(self):
        """Test the value conversion helper method."""
        config = MagicMock(spec=DynamoDBConfig)
        client = DynamoDBAsyncClient(config)

        # Test various value types
        assert client._convert_to_dynamodb_format("test") == {"S": "test"}
        assert client._convert_to_dynamodb_format(123) == {"N": "123"}
        assert client._convert_to_dynamodb_format(45.67) == {"N": "45.67"}
        assert client._convert_to_dynamodb_format(True) == {"BOOL": True}
        assert client._convert_to_dynamodb_format(False) == {"BOOL": False}
        assert client._convert_to_dynamodb_format(None) == {"NULL": True}
        assert client._convert_to_dynamodb_format(b"bytes") == {"B": b"bytes"}

        # Test lists
        assert client._convert_to_dynamodb_format(["a", "b"]) == {"SS": ["a", "b"]}
        assert client._convert_to_dynamodb_format([1, 2, 3]) == {"NS": ["1", "2", "3"]}
        assert client._convert_to_dynamodb_format(["a", 1, True]) == {
            "L": [{"S": "a"}, {"N": "1"}, {"BOOL": True}]
        }

        # Test dict/map
        assert client._convert_to_dynamodb_format({"key": "value"}) == {
            "M": {"key": {"S": "value"}}
        }
