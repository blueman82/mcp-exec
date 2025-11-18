"""
Unit tests for TrustOperations
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.operations.trust_operations import TrustOperations


@pytest.fixture
def mock_client():
    """Create a mock DynamoDB client."""
    client = MagicMock()
    client.put_item = AsyncMock()
    client.get_item = AsyncMock()
    client.update_item = AsyncMock()
    return client


@pytest.fixture
def trust_ops(mock_client):
    """Create a TrustOperations instance with mocked client."""
    return TrustOperations(client=mock_client, table_name="test-table")


class TestTrustOperations:
    """Test cases for TrustOperations."""

    @pytest.mark.asyncio
    async def test_store_status_update_metadata_success(self, trust_ops, mock_client):
        """Test successful storage of status update metadata."""
        channel_id = "C123456"
        status_update_id = "1234567890_abcd1234"
        timestamp = 1234567890
        content_preview = "Test status content"

        # Mock successful put
        mock_client.put_item.return_value = {}

        result = await trust_ops.store_status_update_metadata(
            channel_id=channel_id,
            status_update_id=status_update_id,
            timestamp=timestamp,
            content_preview=content_preview,
        )

        assert result is True

        # Verify put_item was called correctly
        mock_client.put_item.assert_called_once()
        call_args = mock_client.put_item.call_args[1]

        assert call_args["table_name"] == "test-table"
        item = call_args["item"]

        assert item["PK"]["S"] == f"CHANNEL#{channel_id}"
        assert item["SK"]["S"] == f"STATUS#{timestamp}#abcd1234"
        assert item["status_update_id"]["S"] == status_update_id
        assert item["timestamp"]["N"] == str(timestamp)
        assert item["content_preview"]["S"] == content_preview[:200]
        assert "ttl" in item

    @pytest.mark.asyncio
    async def test_get_trust_data_success(self, trust_ops, mock_client):
        """Test successful retrieval of trust data."""
        channel_id = "C123456"
        status_update_id = "1234567890_abcd1234"

        # Mock item response
        mock_item = {
            "PK": {"S": f"CHANNEL#{channel_id}"},
            "SK": {"S": "STATUS#1234567890#abcd1234"},
            "status_update_id": {"S": status_update_id},
            "timestamp": {"N": "1234567890"},
            "trust_count": {"N": "2"},
            "trusted_by": {
                "L": [
                    {
                        "M": {
                            "user_id": {"S": "U123"},
                            "user_name": {"S": "user1"},
                            "trusted_at": {"N": "1234567890"},
                        }
                    },
                    {
                        "M": {
                            "user_id": {"S": "U456"},
                            "user_name": {"S": "user2"},
                            "trusted_at": {"N": "1234567891"},
                        }
                    },
                ]
            },
        }

        mock_client.get_item.return_value = {"Item": mock_item}

        result = await trust_ops.get_trust_data(channel_id, status_update_id)

        assert result is not None
        assert result["status_update_id"] == status_update_id
        assert result["trust_count"] == 2
        assert len(result["trusted_by"]) == 2
        assert result["trusted_by"][0]["user_id"] == "U123"
        assert result["trusted_by"][1]["user_id"] == "U456"

    @pytest.mark.asyncio
    async def test_get_trust_data_not_found(self, trust_ops, mock_client):
        """Test get_trust_data when item doesn't exist."""
        mock_client.get_item.return_value = {}

        result = await trust_ops.get_trust_data("C123456", "1234567890_abcd1234")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_trust_data_invalid_format(self, trust_ops, mock_client):
        """Test get_trust_data with invalid status_update_id format."""
        # Should not even call get_item due to invalid format
        result = await trust_ops.get_trust_data("C123456", "invalid_format")

        assert result is None
        # Verify get_item was not called due to early validation failure
        mock_client.get_item.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(TrustOperations, "get_trust_data")
    async def test_add_trust_endorsement_success(
        self, mock_get_trust, trust_ops, mock_client
    ):
        """Test successful addition of trust endorsement."""
        channel_id = "C123456"
        status_update_id = "1234567890_abcd1234"
        user_id = "U789"
        user_name = "newuser"

        # Mock existing trust data for first call
        # Then mock updated trust data for second call (after update_item)
        mock_get_trust.side_effect = [
            {
                "status_update_id": status_update_id,
                "trusted_by": [
                    {"user_id": "U123", "user_name": "user1", "trusted_at": 1234567890}
                ],
                "trust_count": 1,
            },
            {
                "status_update_id": status_update_id,
                "trusted_by": [
                    {"user_id": "U123", "user_name": "user1", "trusted_at": 1234567890},
                    {"user_id": "U789", "user_name": "newuser", "trusted_at": 1234567891}
                ],
                "trust_count": 2,
            }
        ]

        # Mock update response (doesn't need to return data since method calls get_trust_data again)
        mock_client.update_item.return_value = {}

        result = await trust_ops.add_trust_endorsement(
            channel_id=channel_id,
            status_update_id=status_update_id,
            user_id=user_id,
            user_name=user_name,
        )

        assert result is not None
        assert result["trust_count"] == 2
        assert len(result["trusted_by"]) == 2

        # Verify update_item was called
        mock_client.update_item.assert_called_once()

        # Verify get_trust_data was called twice (once for check, once for return)
        assert mock_get_trust.call_count == 2

    @pytest.mark.asyncio
    @patch.object(TrustOperations, "get_trust_data")
    async def test_add_trust_endorsement_already_trusted(
        self, mock_get_trust, trust_ops
    ):
        """Test add_trust_endorsement when user already trusted."""
        user_id = "U123"

        # Mock existing trust data showing user already trusted
        mock_get_trust.return_value = {
            "status_update_id": "1234567890_abcd1234",
            "trusted_by": [
                {"user_id": user_id, "user_name": "user1", "trusted_at": 1234567890}
            ],
            "trust_count": 1,
        }

        result = await trust_ops.add_trust_endorsement(
            channel_id="C123456",
            status_update_id="1234567890_abcd1234",
            user_id=user_id,
            user_name="user1",
        )

        assert result is not None
        assert result["user_already_trusted"] is True
        assert result["trust_count"] == 1

    @pytest.mark.asyncio
    @patch.object(TrustOperations, "get_trust_data")
    async def test_add_trust_endorsement_not_found(self, mock_get_trust, trust_ops):
        """Test add_trust_endorsement when status update doesn't exist."""
        mock_get_trust.return_value = None

        result = await trust_ops.add_trust_endorsement(
            channel_id="C123456",
            status_update_id="1234567890_abcd1234",
            user_id="U123",
            user_name="user1",
        )

        assert result is None

    def test_serialize_trust_entry(self, trust_ops):
        """Test trust entry serialization."""
        entry = {"user_id": "U123", "user_name": "testuser", "trusted_at": 1234567890}

        result = trust_ops._serialize_trust_entry(entry)

        assert result == {
            "M": {
                "user_id": {"S": "U123"},
                "user_name": {"S": "testuser"},
                "trusted_at": {"N": "1234567890"},
            }
        }

    def test_deserialize_trust_item(self, trust_ops):
        """Test trust item deserialization."""
        item = {
            "status_update_id": {"S": "1234567890_abcd1234"},
            "timestamp": {"N": "1234567890"},
            "trust_count": {"N": "2"},
            "trusted_by": {
                "L": [
                    {
                        "M": {
                            "user_id": {"S": "U123"},
                            "user_name": {"S": "user1"},
                            "trusted_at": {"N": "1234567890"},
                        }
                    }
                ]
            },
        }

        result = trust_ops._deserialize_trust_item(item)

        assert result["status_update_id"] == "1234567890_abcd1234"
        assert result["timestamp"] == 1234567890
        assert result["trust_count"] == 2
        assert len(result["trusted_by"]) == 1
        assert result["trusted_by"][0]["user_id"] == "U123"
