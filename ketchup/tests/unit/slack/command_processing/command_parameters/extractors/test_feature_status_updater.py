"""Unit tests for feature command parameter extraction with status_updater."""

import pytest

from packages.slack.command_processing.command_parameters.extractors.feature import (
    extract_feature_params,
)
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


class TestFeatureStatusUpdaterExtractor:
    """Test suite for feature command parameter extraction with status_updater."""

    def test_extract_status_updater_enable_channel_id(self):
        """Test extracting status_updater enable command with channel ID."""
        command = "/ketchup feature status_updater enable C1234567890"
        params = extract_feature_params(command, CommandContext.DIRECT_MESSAGE)

        assert params.command_type == CommandType.FEATURE
        assert params.feature_name == "status_updater"
        assert params.action == "enable"
        assert params.target_channel_id == "C1234567890"
        assert params.target_user_id is None

    def test_extract_status_updater_enable_channel_mention(self):
        """Test extracting status_updater enable command with channel mention."""
        command = "/ketchup feature status_updater enable <#C1234567890|general>"
        params = extract_feature_params(command, CommandContext.DIRECT_MESSAGE)

        assert params.feature_name == "status_updater"
        assert params.action == "enable"
        assert params.target_channel_id == "C1234567890"
        assert params.target_user_id is None

    def test_extract_status_updater_disable_channel(self):
        """Test extracting status_updater disable command."""
        command = "/ketchup feature status_updater disable C0987654321"
        params = extract_feature_params(command, CommandContext.PUBLIC_CHANNEL)

        assert params.feature_name == "status_updater"
        assert params.action == "disable"
        assert params.target_channel_id == "C0987654321"

    def test_extract_status_updater_list(self):
        """Test extracting status_updater list command."""
        command = "/ketchup feature status_updater list"
        params = extract_feature_params(command, CommandContext.DIRECT_MESSAGE)

        assert params.feature_name == "status_updater"
        assert params.action == "list"
        assert params.target_channel_id is None
        assert params.target_user_id is None

    def test_extract_status_updater_status(self):
        """Test extracting status_updater status command."""
        command = "/ketchup feature status_updater status"
        params = extract_feature_params(command, CommandContext.PUBLIC_CHANNEL)

        assert params.feature_name == "status_updater"
        assert params.action == "status"

    def test_extract_status_updater_invalid_channel_format(self):
        """Test error when channel format is invalid."""
        command = "/ketchup feature status_updater enable invalid-channel"

        with pytest.raises(ValidationError) as exc_info:
            extract_feature_params(command, CommandContext.DIRECT_MESSAGE)

        assert "Invalid channel format" in str(exc_info.value)

    def test_extract_status_updater_missing_channel(self):
        """Test error when channel is missing for enable/disable."""
        command = "/ketchup feature status_updater enable"

        with pytest.raises(ValidationError) as exc_info:
            extract_feature_params(command, CommandContext.DIRECT_MESSAGE)

        assert "Missing channel" in str(exc_info.value)

    def test_extract_status_updater_enable_with_channel_mention_pipe(self):
        """Test that status_updater feature extraction works with channel mentions including pipe."""
        command = "/ketchup feature status_updater enable <#C1234567890|general>"
        params = extract_feature_params(command, CommandContext.DIRECT_MESSAGE)

        assert params.feature_name == "status_updater"
        assert params.action == "enable"
        assert params.target_user_id is None
        assert params.target_channel_id == "C1234567890"

    def test_extract_invalid_feature_name(self):
        """Test error when feature name is invalid."""
        command = "/ketchup feature invalid_feature enable"

        with pytest.raises(ValidationError) as exc_info:
            extract_feature_params(command, CommandContext.DIRECT_MESSAGE)

        assert "Invalid feature name" in str(exc_info.value)
        assert (
            "status_updater" in exc_info.value.user_message
            and "jira_reporter" in exc_info.value.user_message
            and "trust_endorsement" in exc_info.value.user_message
            and "access_management" in exc_info.value.user_message
        )
