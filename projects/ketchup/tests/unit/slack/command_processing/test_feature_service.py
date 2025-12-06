"""
test_feature_service.py

Unit tests for feature_service.py (FeatureService).

Covers:
- FeatureService initialization
- Legacy message analysis check
- Enable/disable feature for users
- Get users with feature
- Feature status retrieval
- User join notifications feature with all scenarios
- Integration with FeatureFlags class
- Error handling

Edge Cases Covered:
- Feature globally disabled
- Feature globally enabled
- User-specific feature flags
- Database errors
- Unknown features

Expected Outcomes:
- Proper fallback behavior through env vars
- Correct database operations
- Proper error handling and logging
"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.db.operations.channel_operations import ChannelOperations
from packages.db.user_store import UserStore
from packages.slack.command_processing.feature_service import FeatureService


class TestFeatureService:
    """Test FeatureService functionality."""

    @pytest.fixture
    def mock_user_store(self) -> AsyncMock:
        """Create a mock UserStore."""
        mock = AsyncMock(spec=UserStore)
        # Set default return values
        mock.get_user_feature = AsyncMock(return_value=None)
        mock.set_user_feature = AsyncMock(return_value=True)
        mock.get_users_with_feature = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_channel_operations(self) -> AsyncMock:
        """Create a mock ChannelOperations."""
        return AsyncMock(spec=ChannelOperations)

    @pytest.fixture
    def feature_service(
        self, mock_user_store: AsyncMock, mock_channel_operations: AsyncMock
    ) -> FeatureService:
        """Create a FeatureService instance with mocked dependencies."""
        return FeatureService(
            user_store=mock_user_store, channel_operations=mock_channel_operations
        )

    @pytest.mark.asyncio
    async def test_legacy_message_analysis_enabled(self, feature_service: FeatureService) -> None:
        """Test legacy message analysis check."""
        with patch(
            "packages.slack.command_processing.feature_service.FeatureFlags.is_message_analysis_enabled"
        ) as mock:
            mock.return_value = True

            result = await feature_service.is_legacy_message_analysis_enabled()

            assert result is True
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_feature_for_user(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test enabling a feature for a user."""
        result = await feature_service.enable_feature_for_user("U12345", "nlp")

        assert result is True
        mock_user_store.set_user_feature.assert_called_once_with("U12345", "nlp_enabled", True)

    @pytest.mark.asyncio
    async def test_disable_feature_for_user(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test disabling a feature for a user."""
        result = await feature_service.disable_feature_for_user("U12345", "nlp")

        assert result is True
        mock_user_store.set_user_feature.assert_called_once_with("U12345", "nlp_enabled", False)

    @pytest.mark.asyncio
    async def test_get_users_with_feature(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test getting users with a specific feature."""
        expected_users = [
            {"user_id": "U12345", "features": {"nlp_enabled": True}},
            {"user_id": "U67890", "features": {"nlp_enabled": True}},
        ]
        mock_user_store.get_users_with_feature.return_value = expected_users

        result = await feature_service.get_users_with_feature("nlp")

        assert result == expected_users
        mock_user_store.get_users_with_feature.assert_called_once_with("nlp_enabled", True)

    def test_get_unknown_feature_status(self, feature_service: FeatureService) -> None:
        """Test getting status for unknown feature."""
        status = feature_service.get_feature_status("unknown")

        assert status == {
            "feature_enabled": False,
            "global_access": False,
            "error": "Unknown feature: unknown",
        }

    @pytest.mark.asyncio
    async def test_enable_feature_database_error(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test enable feature handles database errors."""
        mock_user_store.set_user_feature.return_value = False

        result = await feature_service.enable_feature_for_user("U12345", "nlp")

        assert result is False

    @pytest.mark.asyncio
    async def test_disable_feature_database_error(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test disable feature handles database errors."""
        mock_user_store.set_user_feature.return_value = False

        result = await feature_service.disable_feature_for_user("U12345", "nlp")

        assert result is False

    # User Join Notifications Feature Tests

    @pytest.mark.asyncio
    async def test_user_join_notifications_disabled_globally(
        self, feature_service: FeatureService
    ) -> None:
        """Test user join notifications disabled when global feature flag is off."""
        with patch(
            "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_enabled"
        ) as mock_enabled:
            mock_enabled.return_value = False

            result = await feature_service.is_user_join_notifications_enabled_for_user("U12345")

            assert result is False
            mock_enabled.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_join_notifications_enabled_globally_for_all(
        self, feature_service: FeatureService
    ) -> None:
        """Test user join notifications enabled for all users when global flag is on."""
        with (
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_enabled"
            ) as mock_enabled,
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_global"
            ) as mock_global,
        ):
            mock_enabled.return_value = True
            mock_global.return_value = True

            result = await feature_service.is_user_join_notifications_enabled_for_user("U12345")

            assert result is True
            mock_global.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_join_notifications_enabled_for_specific_user(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test user join notifications enabled for specific user with database flag."""
        with (
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_enabled"
            ) as mock_enabled,
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_global"
            ) as mock_global,
        ):
            mock_enabled.return_value = True
            mock_global.return_value = False
            mock_user_store.get_user_feature.return_value = True

            result = await feature_service.is_user_join_notifications_enabled_for_user("U12345")

            assert result is True
            mock_user_store.get_user_feature.assert_called_once_with(
                "U12345", "user_join_notifications_enabled"
            )

    @pytest.mark.asyncio
    async def test_user_join_notifications_disabled_for_specific_user(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test user join notifications disabled for specific user without database flag."""
        with (
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_enabled"
            ) as mock_enabled,
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_global"
            ) as mock_global,
        ):
            mock_enabled.return_value = True
            mock_global.return_value = False
            mock_user_store.get_user_feature.return_value = False

            result = await feature_service.is_user_join_notifications_enabled_for_user("U12345")

            assert result is False

    @pytest.mark.asyncio
    async def test_user_join_notifications_disabled_on_database_error(
        self, feature_service: FeatureService, mock_user_store: AsyncMock
    ) -> None:
        """Test user join notifications disabled when database error occurs."""
        with (
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_enabled"
            ) as mock_enabled,
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_global"
            ) as mock_global,
        ):
            mock_enabled.return_value = True
            mock_global.return_value = False
            mock_user_store.get_user_feature.side_effect = Exception("Database error")

            result = await feature_service.is_user_join_notifications_enabled_for_user("U12345")

            assert result is False

    def test_get_user_join_notifications_feature_status(
        self, feature_service: FeatureService
    ) -> None:
        """Test getting user join notifications feature status."""
        with (
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_enabled"
            ) as mock_enabled,
            patch(
                "packages.slack.command_processing.feature_service.FeatureFlags.is_user_join_notifications_global"
            ) as mock_global,
        ):
            mock_enabled.return_value = True
            mock_global.return_value = False

            status = feature_service.get_feature_status("user_join_notifications")

            assert status == {
                "feature_enabled": True,
                "global_access": False,
                "env_var": "KETCHUP_USER_JOIN_NOTIFICATIONS_FEATURE",
                "global_env_var": "KETCHUP_USER_JOIN_NOTIFICATIONS_GLOBAL",
                "user_field": "features.user_join_notifications_enabled",
            }
