"""Unit tests for status updater feature flags."""

import os
from unittest.mock import patch

from packages.core.config.feature_flags import FeatureFlags


class TestStatusUpdaterFeatureFlags:
    """Test suite for status updater feature flags."""

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_FEATURE": "true"})
    def test_is_status_updater_enabled_true(self):
        """Test status updater enabled when env var is true."""
        assert FeatureFlags.is_status_updater_enabled() is True

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_FEATURE": "false"})
    def test_is_status_updater_enabled_false(self):
        """Test status updater disabled when env var is false."""
        assert FeatureFlags.is_status_updater_enabled() is False

    @patch.dict(os.environ, {}, clear=True)
    def test_is_status_updater_enabled_default(self):
        """Test status updater defaults to false when env var not set."""
        # Remove the env var if it exists
        os.environ.pop("KETCHUP_STATUS_UPDATER_FEATURE", None)
        assert FeatureFlags.is_status_updater_enabled() is False

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_GLOBAL": "true"})
    def test_is_status_updater_global_true(self):
        """Test status updater global when env var is true."""
        assert FeatureFlags.is_status_updater_global() is True

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_GLOBAL": "false"})
    def test_is_status_updater_global_false(self):
        """Test status updater not global when env var is false."""
        assert FeatureFlags.is_status_updater_global() is False

    @patch.dict(os.environ, {}, clear=True)
    def test_is_status_updater_global_default(self):
        """Test status updater global defaults to false when env var not set."""
        # Remove the env var if it exists
        os.environ.pop("KETCHUP_STATUS_UPDATER_GLOBAL", None)
        assert FeatureFlags.is_status_updater_global() is False

    @patch.dict(
        os.environ,
        {
            "KETCHUP_STATUS_UPDATER_FEATURE": "true",
            "KETCHUP_STATUS_UPDATER_GLOBAL": "true",
        },
    )
    def test_get_all_flags_includes_status_updater(self):
        """Test get_all_flags includes status updater flags."""
        flags = FeatureFlags.get_all_flags()
        assert "status_updater_enabled" in flags
        assert "status_updater_global" in flags
        assert flags["status_updater_enabled"] is True
        assert flags["status_updater_global"] is True
