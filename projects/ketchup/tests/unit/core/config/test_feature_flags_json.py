"""Unit tests for structured JSON output feature flag."""

import os
from unittest.mock import patch

from packages.core.config.feature_flags import FeatureFlags


class TestStructuredJsonOutputFeatureFlag:
    """Test suite for structured JSON output feature flag."""

    @patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
    def test_is_structured_json_output_enabled_true(self):
        """Test structured JSON output enabled when env var is true."""
        assert FeatureFlags.is_structured_json_output_enabled() is True

    @patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "false"})
    def test_is_structured_json_output_enabled_false(self):
        """Test structured JSON output disabled when env var is false."""
        assert FeatureFlags.is_structured_json_output_enabled() is False

    @patch.dict(os.environ, {}, clear=True)
    def test_is_structured_json_output_enabled_default(self):
        """Test structured JSON output defaults to false when env var not set."""
        # Remove the env var if it exists
        os.environ.pop("KETCHUP_STRUCTURED_JSON_OUTPUT", None)
        assert FeatureFlags.is_structured_json_output_enabled() is False

    @patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "TRUE"})
    def test_is_structured_json_output_enabled_uppercase(self):
        """Test structured JSON output enabled with uppercase TRUE."""
        assert FeatureFlags.is_structured_json_output_enabled() is True

    @patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "True"})
    def test_is_structured_json_output_enabled_mixed_case(self):
        """Test structured JSON output enabled with mixed case True."""
        assert FeatureFlags.is_structured_json_output_enabled() is True

    @patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
    def test_get_all_flags_includes_structured_json_output(self):
        """Test get_all_flags includes structured JSON output flag."""
        flags = FeatureFlags.get_all_flags()
        assert "structured_json_output_enabled" in flags
        assert flags["structured_json_output_enabled"] is True
        # async_mcp_enabled flag was removed - AsyncMCPClient is always used now
