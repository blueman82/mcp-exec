"""
Test JIRA reporter feature flag implementation
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from packages.core.config.feature_flags import FeatureFlags
from packages.slack.command_processing.feature_service import FeatureService


class TestJiraReporterFeatureFlag:
    """Test JIRA reporter feature flag functionality."""

    def test_feature_flags_default_disabled(self):
        """Test that JIRA reporter feature flags are disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert FeatureFlags.is_jira_reporter_enabled() is False
            assert FeatureFlags.is_jira_reporter_global() is False

    def test_feature_flags_enabled_beta(self):
        """Test JIRA reporter beta mode (feature enabled, not global)."""
        with patch.dict(
            os.environ,
            {
                "KETCHUP_JIRA_REPORTER_FEATURE": "true",
                "KETCHUP_JIRA_REPORTER_GLOBAL": "false",
            },
        ):
            assert FeatureFlags.is_jira_reporter_enabled() is True
            assert FeatureFlags.is_jira_reporter_global() is False

    def test_feature_flags_global_rollout(self):
        """Test JIRA reporter global rollout mode."""
        with patch.dict(
            os.environ,
            {
                "KETCHUP_JIRA_REPORTER_FEATURE": "true",
                "KETCHUP_JIRA_REPORTER_GLOBAL": "true",
            },
        ):
            assert FeatureFlags.is_jira_reporter_enabled() is True
            assert FeatureFlags.is_jira_reporter_global() is True

    def test_get_all_flags_includes_jira_reporter(self):
        """Test that get_all_flags includes JIRA reporter flags."""
        with patch.dict(
            os.environ,
            {
                "KETCHUP_JIRA_REPORTER_FEATURE": "true",
                "KETCHUP_JIRA_REPORTER_GLOBAL": "false",
            },
        ):
            flags = FeatureFlags.get_all_flags()
            assert "jira_reporter_enabled" in flags
            assert "jira_reporter_global" in flags
            assert flags["jira_reporter_enabled"] is True
            assert flags["jira_reporter_global"] is False


class TestJiraReporterFeatureService:
    """Test JIRA reporter feature service integration."""

    @pytest.mark.asyncio
    async def test_is_jira_reporter_enabled_for_channel_global(self):
        """Test that global flag enables JIRA reporter for all channels."""
        # Mock dependencies
        user_store = AsyncMock()
        channel_ops = AsyncMock()

        service = FeatureService(user_store, channel_ops)

        # Test with global flag enabled
        with patch.dict(os.environ, {"KETCHUP_JIRA_REPORTER_GLOBAL": "true"}):
            result = await service.is_jira_reporter_enabled_for_channel("C1234567890")
            assert result is True
            # Should not check individual channel flag
            user_store.get_channel_feature.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_jira_reporter_enabled_for_channel_individual(self):
        """Test individual channel flag when global is disabled."""
        # Mock dependencies
        user_store = AsyncMock()
        user_store.get_channel_feature.return_value = True
        channel_ops = AsyncMock()

        service = FeatureService(user_store, channel_ops)

        # Test with global flag disabled
        with patch.dict(os.environ, {"KETCHUP_JIRA_REPORTER_GLOBAL": "false"}):
            result = await service.is_jira_reporter_enabled_for_channel("C1234567890")
            assert result is True
            user_store.get_channel_feature.assert_called_once_with(
                "C1234567890", "jira_reporter_enabled"
            )

    @pytest.mark.asyncio
    async def test_enable_disable_jira_reporter_for_channel(self):
        """Test enabling and disabling JIRA reporter for a channel."""
        # Mock dependencies
        user_store = AsyncMock()
        user_store.set_channel_feature.return_value = True
        channel_ops = AsyncMock()

        service = FeatureService(user_store, channel_ops)

        # Test enable
        result = await service.enable_feature_for_channel("C1234567890", "jira_reporter")
        assert result is True
        user_store.set_channel_feature.assert_called_with(
            "C1234567890", "jira_reporter_enabled", True
        )

        # Test disable
        result = await service.disable_feature_for_channel("C1234567890", "jira_reporter")
        assert result is True
        user_store.set_channel_feature.assert_called_with(
            "C1234567890", "jira_reporter_enabled", False
        )

    def test_get_feature_status_jira_reporter(self):
        """Test getting JIRA reporter feature status."""
        # Mock dependencies
        user_store = AsyncMock()
        channel_ops = AsyncMock()

        service = FeatureService(user_store, channel_ops)

        with patch.dict(
            os.environ,
            {
                "KETCHUP_JIRA_REPORTER_FEATURE": "true",
                "KETCHUP_JIRA_REPORTER_GLOBAL": "false",
            },
        ):
            status = service.get_feature_status("jira_reporter")

            assert status["feature_enabled"] is True
            assert status["global_access"] is False
            assert status["env_var"] == "KETCHUP_JIRA_REPORTER_FEATURE"
            assert status["global_env_var"] == "KETCHUP_JIRA_REPORTER_GLOBAL"
            assert status["channel_field"] == "features.jira_reporter_enabled"
