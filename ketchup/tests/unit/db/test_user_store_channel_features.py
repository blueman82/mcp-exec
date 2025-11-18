"""Unit tests for UserStore channel feature methods."""

from unittest.mock import AsyncMock

import pytest

from packages.db.user_store import UserStore

pytestmark = pytest.mark.unit


class TestUserStoreChannelFeatures:
    """Test suite for UserStore channel feature methods."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock DynamoDB client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def user_store(self, mock_client):
        """Create a UserStore instance with mocked client."""
        return UserStore(mock_client, "test_table")

    @pytest.mark.asyncio
    async def test_set_channel_feature_success(self, user_store, mock_client):
        """Test successfully setting a channel feature."""
        # Mock successful update
        mock_client.update_item = AsyncMock()

        result = await user_store.set_channel_feature(
            "C1234567890", "status_updater_enabled", True
        )

        assert result is True
        # Check that update_item was called (implementation has fallback logic)
        assert mock_client.update_item.called

    @pytest.mark.asyncio
    async def test_set_channel_feature_failure(self, user_store, mock_client):
        """Test handling error when setting channel feature."""
        # Mock failed update
        mock_client.update_item = AsyncMock(side_effect=Exception("DynamoDB error"))

        result = await user_store.set_channel_feature(
            "C1234567890", "status_updater_enabled", True
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_channel_feature_exists(self, user_store, mock_client):
        """Test getting an existing channel feature."""
        # Mock response with feature
        mock_client.get_item = AsyncMock(
            return_value={
                "Item": {"features": {"M": {"status_updater_enabled": {"BOOL": True}}}}
            }
        )

        result = await user_store.get_channel_feature(
            "C1234567890", "status_updater_enabled"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_get_channel_feature_not_exists(self, user_store, mock_client):
        """Test getting a non-existent channel feature."""
        # Mock empty response
        mock_client.get_item = AsyncMock(return_value={})

        result = await user_store.get_channel_feature(
            "C1234567890", "status_updater_enabled"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_channels_with_feature(self, user_store, mock_client):
        """Test getting all channels with a specific feature enabled."""
        # Mock _get_client to return a mock underlying client
        mock_underlying_client = AsyncMock()
        mock_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock scan response
        mock_underlying_client.scan = AsyncMock(
            return_value={
                "Items": [
                    {"PK": {"S": "CHANNEL#C1234567890"}},
                    {"PK": {"S": "CHANNEL#C0987654321"}},
                ]
            }
        )

        result = await user_store.get_channels_with_feature(
            "status_updater_enabled", True
        )

        assert result == ["C1234567890", "C0987654321"]
        mock_underlying_client.scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_channels_with_feature_pagination(self, user_store, mock_client):
        """Test getting channels with feature handles pagination."""
        # Mock _get_client
        mock_underlying_client = AsyncMock()
        mock_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock paginated responses
        mock_underlying_client.scan = AsyncMock(
            side_effect=[
                {
                    "Items": [{"PK": {"S": "CHANNEL#C1234567890"}}],
                    "LastEvaluatedKey": {"PK": {"S": "CHANNEL#C1234567890"}},
                },
                {"Items": [{"PK": {"S": "CHANNEL#C0987654321"}}]},
            ]
        )

        result = await user_store.get_channels_with_feature(
            "status_updater_enabled", True
        )

        assert result == ["C1234567890", "C0987654321"]
        assert mock_underlying_client.scan.call_count == 2

    @pytest.mark.asyncio
    async def test_get_channel_features_success(self, user_store, mock_client):
        """Test successfully getting channel features."""
        # Mock response with features
        mock_client.get_item = AsyncMock(
            return_value={
                "Item": {
                    "features": {
                        "M": {
                            "status_updater_enabled": {"BOOL": True},
                            "nlp_enabled": {"BOOL": False}
                        }
                    }
                }
            }
        )

        result = await user_store.get_channel_feature(
            "C1234567890", "status_updater_enabled"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_get_channel_features_no_item(self, user_store, mock_client):
        """Test getting channel features when no item exists."""
        # Mock empty response
        mock_client.get_item = AsyncMock(return_value={})

        result = await user_store.get_channel_feature(
            "C1234567890", "status_updater_enabled"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_set_channel_features_new(self, user_store, mock_client):
        """Test setting channel features for new channel."""
        # Mock update_item to raise ConditionalCheckFailedException first, then succeed
        mock_client.update_item = AsyncMock(
            side_effect=[
                Exception("ConditionalCheckFailedException"),
                None  # Second call succeeds
            ]
        )

        result = await user_store.set_channel_feature(
            "C1234567890", "status_updater_enabled", True
        )

        assert result is True
        assert mock_client.update_item.call_count == 2

    @pytest.mark.asyncio
    async def test_set_channel_features_update(self, user_store, mock_client):
        """Test updating existing channel features."""
        # Mock successful update on first try
        mock_client.update_item = AsyncMock()

        result = await user_store.set_channel_feature(
            "C1234567890", "status_updater_enabled", True
        )

        assert result is True
        mock_client.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_channels_with_feature_enabled(self, user_store, mock_client):
        """Test getting channels with a specific feature enabled."""
        # Mock _get_client to return a mock underlying client
        mock_underlying_client = AsyncMock()
        mock_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock scan response
        mock_underlying_client.scan = AsyncMock(
            return_value={
                "Items": [
                    {"PK": {"S": "CHANNEL#C1234567890"}},
                    {"PK": {"S": "CHANNEL#C0987654321"}},
                    {"PK": {"S": "CHANNEL#C1111111111"}},
                ]
            }
        )

        result = await user_store.get_channels_with_feature(
            "status_updater_enabled", True
        )

        assert result == ["C1234567890", "C0987654321", "C1111111111"]
        mock_underlying_client.scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_channels_with_feature_paginated(self, user_store, mock_client):
        """Test getting channels with feature handles pagination correctly."""
        # Mock _get_client
        mock_underlying_client = AsyncMock()
        mock_client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Mock paginated responses
        mock_underlying_client.scan = AsyncMock(
            side_effect=[
                {
                    "Items": [
                        {"PK": {"S": "CHANNEL#C1234567890"}},
                        {"PK": {"S": "CHANNEL#C2222222222"}}
                    ],
                    "LastEvaluatedKey": {"PK": {"S": "CHANNEL#C2222222222"}},
                },
                {
                    "Items": [
                        {"PK": {"S": "CHANNEL#C0987654321"}},
                        {"PK": {"S": "CHANNEL#C3333333333"}}
                    ]
                },
            ]
        )

        result = await user_store.get_channels_with_feature(
            "status_updater_enabled", True
        )

        assert result == ["C1234567890", "C2222222222", "C0987654321", "C3333333333"]
        assert mock_underlying_client.scan.call_count == 2
