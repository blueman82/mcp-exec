"""
test_real_names_display.py

Unit tests for verifying that admin stats display real names instead of usernames.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from packages.db.operations.command_tracking_operations import CommandTrackingOperations


class TestRealNamesDisplay:
    """Test suite for real names display in admin stats."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create a mock DynamoDB client."""
        return Mock()

    @pytest.fixture
    def command_tracking_ops(self, mock_dynamodb_client):
        """Create CommandTrackingOperations instance with mocked client."""
        return CommandTrackingOperations(mock_dynamodb_client, "test-table")

    @pytest.mark.asyncio
    async def test_get_user_real_names(self, command_tracking_ops, mock_dynamodb_client):
        """Test the _get_user_real_names helper method."""
        # Mock the underlying client
        mock_underlying_client = Mock()
        mock_dynamodb_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock batch_get_item response
        mock_underlying_client.batch_get_item = AsyncMock(
            return_value={
                "Responses": {
                    "test-table": [
                        {
                            "PK": {"S": "USER#U12345"},
                            "SK": {"S": "METADATA"},
                            "real_name": {"S": "Harrison O'Meara"},
                        },
                        {
                            "PK": {"S": "USER#U67890"},
                            "SK": {"S": "METADATA"},
                            "real_name": {"S": "John Doe"},
                        },
                    ]
                }
            }
        )

        # Test fetching real names
        user_ids = ["U12345", "U67890", "U99999"]  # U99999 won't be in response
        real_names = await command_tracking_ops._get_user_real_names(user_ids)

        # Verify results
        assert real_names == {"U12345": "Harrison O'Meara", "U67890": "John Doe"}

        # Verify batch_get_item was called with correct keys
        mock_underlying_client.batch_get_item.assert_called_once()
        call_args = mock_underlying_client.batch_get_item.call_args[1]  # kwargs
        assert "RequestItems" in call_args
        assert "test-table" in call_args["RequestItems"]
        assert len(call_args["RequestItems"]["test-table"]["Keys"]) == 3

    @pytest.mark.asyncio
    async def test_get_top_users_with_real_names(self, command_tracking_ops, mock_dynamodb_client):
        """Test that get_top_users returns real names instead of usernames."""
        # Mock scan response for command records
        mock_dynamodb_client.scan = AsyncMock(
            return_value={
                "Items": [
                    {
                        "PK": {"S": "USER#U12345"},
                        "SK": {"S": "COMMAND#1234567890#status"},
                        "user_id": {"S": "U12345"},
                        "user_name": {"S": "harrison"},  # Username
                        "timestamp": {"N": "1234567890"},
                    },
                    {
                        "PK": {"S": "USER#U12345"},
                        "SK": {"S": "COMMAND#1234567891#report"},
                        "user_id": {"S": "U12345"},
                        "user_name": {"S": "harrison"},  # Username
                        "timestamp": {"N": "1234567891"},
                    },
                    {
                        "PK": {"S": "USER#U67890"},
                        "SK": {"S": "COMMAND#1234567892#status"},
                        "user_id": {"S": "U67890"},
                        "user_name": {"S": "jdoe"},  # Username
                        "timestamp": {"N": "1234567892"},
                    },
                ]
            }
        )

        # Mock the underlying client for batch_get_item
        mock_underlying_client = Mock()
        mock_dynamodb_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock batch_get_item response for real names
        mock_underlying_client.batch_get_item = AsyncMock(
            return_value={
                "Responses": {
                    "test-table": [
                        {
                            "PK": {"S": "USER#U12345"},
                            "SK": {"S": "METADATA"},
                            "real_name": {"S": "Harrison O'Meara"},
                        },
                        {
                            "PK": {"S": "USER#U67890"},
                            "SK": {"S": "METADATA"},
                            "real_name": {"S": "John Doe"},
                        },
                    ]
                }
            }
        )

        # Get top users
        top_users = await command_tracking_ops.get_top_users()

        # Verify real names are returned
        assert len(top_users) == 2
        assert top_users[0] == ("U12345", "Harrison O'Meara", 2)  # 2 commands
        assert top_users[1] == ("U67890", "John Doe", 1)  # 1 command

    @pytest.mark.asyncio
    async def test_get_user_command_breakdown_with_real_names(
        self, command_tracking_ops, mock_dynamodb_client
    ):
        """Test that get_user_command_breakdown returns real names."""
        # Mock scan response
        mock_dynamodb_client.scan = AsyncMock(
            return_value={
                "Items": [
                    {
                        "PK": {"S": "USER#U12345"},
                        "SK": {"S": "COMMAND#1234567890#status"},
                        "user_id": {"S": "U12345"},
                        "user_name": {"S": "harrison"},
                        "command_type": {"S": "status"},
                        "timestamp": {"N": "1234567890"},
                    },
                    {
                        "PK": {"S": "USER#U12345"},
                        "SK": {"S": "COMMAND#1234567891#report"},
                        "user_id": {"S": "U12345"},
                        "user_name": {"S": "harrison"},
                        "command_type": {"S": "report"},
                        "timestamp": {"N": "1234567891"},
                    },
                ]
            }
        )

        # Mock the underlying client for batch_get_item
        mock_underlying_client = Mock()
        mock_dynamodb_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock batch_get_item response
        mock_underlying_client.batch_get_item = AsyncMock(
            return_value={
                "Responses": {
                    "test-table": [
                        {
                            "PK": {"S": "USER#U12345"},
                            "SK": {"S": "METADATA"},
                            "real_name": {"S": "Harrison O'Meara"},
                        }
                    ]
                }
            }
        )

        # Get command breakdown
        breakdown = await command_tracking_ops.get_user_command_breakdown()

        # Verify real name is used
        assert "U12345" in breakdown
        assert breakdown["U12345"]["user_name"] == "Harrison O'Meara"
        assert breakdown["U12345"]["commands"] == {"status": 1, "report": 1}
        assert breakdown["U12345"]["total_count"] == 2

    @pytest.mark.asyncio
    async def test_fallback_to_username_when_no_real_name(
        self, command_tracking_ops, mock_dynamodb_client
    ):
        """Test that system falls back to username when real name is not available."""
        # Mock scan response
        mock_dynamodb_client.scan = AsyncMock(
            return_value={
                "Items": [
                    {
                        "PK": {"S": "USER#U99999"},
                        "SK": {"S": "COMMAND#1234567890#status"},
                        "user_id": {"S": "U99999"},
                        "user_name": {"S": "unknownuser"},
                        "timestamp": {"N": "1234567890"},
                    }
                ]
            }
        )

        # Mock the underlying client for batch_get_item
        mock_underlying_client = Mock()
        mock_dynamodb_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock empty batch_get_item response (no real name found)
        mock_underlying_client.batch_get_item = AsyncMock(
            return_value={"Responses": {"test-table": []}}
        )

        # Get top users
        top_users = await command_tracking_ops.get_top_users()

        # Verify fallback to username
        assert len(top_users) == 1
        assert top_users[0] == ("U99999", "unknownuser", 1)  # Falls back to username
