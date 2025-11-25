"""Unit tests for system channel exclusion configuration."""

import os
from unittest.mock import patch


class TestSystemChannelExclusions:
    """Test suite for system channel exclusion config."""

    def test_default_exclusions_loaded(self):
        """Test default exclusions when env var not set."""
        from packages.core.config.system_channels import get_excluded_channels

        with patch.dict(os.environ, {}, clear=True):
            excluded = get_excluded_channels()

        assert "C090V88CB1N" in excluded  # ketchup_access
        assert "C08CQN1JCSC" in excluded  # ketchup_feedback
        assert len(excluded) == 2

    def test_custom_exclusions_from_env(self):
        """Test loading exclusions from environment variable."""
        from packages.core.config.system_channels import get_excluded_channels

        with patch.dict(os.environ, {"EXCLUDED_CSO_CHANNELS": "C123,C456,C789"}):
            excluded = get_excluded_channels()

        assert "C123" in excluded
        assert "C456" in excluded
        assert "C789" in excluded
        assert len(excluded) == 3

    def test_empty_exclusions_handled(self):
        """Test empty string in env var returns empty set."""
        from packages.core.config.system_channels import get_excluded_channels

        with patch.dict(os.environ, {"EXCLUDED_CSO_CHANNELS": ""}):
            excluded = get_excluded_channels()

        assert len(excluded) == 0
        assert isinstance(excluded, set)
