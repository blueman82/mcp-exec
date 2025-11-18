"""Unit tests for FeatureService status_updater methods."""

from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.command_processing.feature_service import FeatureService


class TestFeatureServiceStatusUpdater:
    """Test suite for FeatureService status_updater methods."""

    @pytest.fixture
    def mock_user_store(self):
        """Create a mock UserStore."""
        return AsyncMock()

    @pytest.fixture
    def mock_channel_operations(self):
        """Create a mock ChannelOperations."""
        return AsyncMock()

    @pytest.fixture
    def feature_service(self, mock_user_store, mock_channel_operations):
        """Create a FeatureService instance with mocked dependencies."""
        return FeatureService(
            user_store=mock_user_store, channel_operations=mock_channel_operations
        )

    @pytest.mark.asyncio
    async def test_enable_feature_for_channel(self, feature_service, mock_user_store):
        """Test enabling a feature for a channel."""
        mock_user_store.set_channel_feature = AsyncMock(return_value=True)

        result = await feature_service.enable_feature_for_channel(
            "C1234567890", "status_updater"
        )

        assert result is True
        mock_user_store.set_channel_feature.assert_called_once_with(
            "C1234567890", "status_updater_enabled", True
        )

    @pytest.mark.asyncio
    async def test_disable_feature_for_channel(self, feature_service, mock_user_store):
        """Test disabling a feature for a channel."""
        mock_user_store.set_channel_feature = AsyncMock(return_value=True)

        result = await feature_service.disable_feature_for_channel(
            "C1234567890", "status_updater"
        )

        assert result is True
        mock_user_store.set_channel_feature.assert_called_once_with(
            "C1234567890", "status_updater_enabled", False
        )

    @pytest.mark.asyncio
    async def test_get_channels_with_feature(
        self, feature_service, mock_user_store, mock_channel_operations
    ):
        """Test getting channels with a feature enabled."""
        # Mock user store returning channel IDs
        mock_user_store.get_channels_with_feature = AsyncMock(
            return_value=["C1234567890", "C0987654321"]
        )

        # Mock channel operations returning channel details
        mock_channel_operations.get_channel_details = AsyncMock(
            side_effect=[
                {"channel_name": "general", "channel_id": "C1234567890"},
                {"channel_name": "random", "channel_id": "C0987654321"},
            ]
        )

        result = await feature_service.get_channels_with_feature("status_updater")

        assert result == [
            {"channel_id": "C1234567890", "channel_name": "general"},
            {"channel_id": "C0987654321", "channel_name": "random"},
        ]

    @pytest.mark.asyncio
    async def test_get_channels_with_feature_missing_details(
        self, feature_service, mock_user_store, mock_channel_operations
    ):
        """Test getting channels when some channel details are missing."""
        mock_user_store.get_channels_with_feature = AsyncMock(
            return_value=["C1234567890", "C0987654321"]
        )

        # Mock one channel found, one not found
        mock_channel_operations.get_channel_details = AsyncMock(
            side_effect=[
                {"channel_name": "general", "channel_id": "C1234567890"},
                None,  # Channel not found
            ]
        )

        result = await feature_service.get_channels_with_feature("status_updater")

        assert result == [
            {"channel_id": "C1234567890", "channel_name": "general"},
            {"channel_id": "C0987654321", "channel_name": "unknown"},
        ]

    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_is_status_updater_enabled_for_channel_global(
        self, mock_global, feature_service
    ):
        """Test status updater enabled when global flag is true."""
        mock_global.return_value = True

        result = await feature_service.is_status_updater_enabled_for_channel(
            "C1234567890"
        )

        assert result is True

    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_is_status_updater_enabled_for_channel_specific(
        self, mock_global, feature_service, mock_user_store
    ):
        """Test status updater enabled based on channel-specific flag."""
        mock_global.return_value = False
        mock_user_store.get_channel_feature = AsyncMock(return_value=True)

        result = await feature_service.is_status_updater_enabled_for_channel(
            "C1234567890"
        )

        assert result is True
        mock_user_store.get_channel_feature.assert_called_once_with(
            "C1234567890", "status_updater_enabled"
        )

    def test_get_feature_status_status_updater(self, feature_service):
        """Test getting feature status for status_updater."""
        with patch(
            "packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled",
            return_value=True,
        ), patch(
            "packages.core.config.feature_flags.FeatureFlags.is_status_updater_global",
            return_value=False,
        ):

            status = feature_service.get_feature_status("status_updater")

            assert status == {
                "feature_enabled": True,
                "global_access": False,
                "env_var": "KETCHUP_STATUS_UPDATER_FEATURE",
                "global_env_var": "KETCHUP_STATUS_UPDATER_GLOBAL",
                "channel_field": "features.status_updater_enabled",
            }
