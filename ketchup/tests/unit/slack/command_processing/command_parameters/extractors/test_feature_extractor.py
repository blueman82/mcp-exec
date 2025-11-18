"""
test_feature_extractor.py

Unit tests for extractors/feature.py (extract_feature_params).

Covers:
- extract_feature_params: All actions (enable, disable, list, status)
- All logic branches and error handling
- User mention parsing with regex
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- Missing feature name
- Missing action
- Invalid feature name
- Invalid action
- Enable/disable without user mention
- Invalid user mention format
- Valid user mention with and without pipe
- All valid actions with proper parameters

Expected Outcomes:
- Returns FeatureCommandParams for valid input
- Raises ValidationError for all invalid input cases
"""

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


class TestExtractFeatureParams:
    """Test feature parameter extraction."""

    def test_missing_feature_name(self) -> None:
        """Test raises ValidationError if feature name is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_feature_params("/ketchup feature", CommandContext.DIRECT_MESSAGE)
        assert "Incomplete feature command" in exc.value.message
        assert (
            "requires at least a feature name and an action" in exc.value.user_message
        )

    def test_missing_action(self) -> None:
        """Test raises ValidationError if action is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_feature_params(
                "/ketchup feature status_updater", CommandContext.DIRECT_MESSAGE
            )
        assert "Missing action for feature command" in exc.value.message
        assert "Available actions:" in exc.value.user_message

    def test_invalid_feature_name(self) -> None:
        """Test raises ValidationError for invalid feature name."""
        with pytest.raises(ValidationError) as exc:
            extract_feature_params(
                "/ketchup feature unknown status", CommandContext.DIRECT_MESSAGE
            )
        assert "Invalid feature name: unknown" in exc.value.message
        assert "Currently supported features: status_updater, jira_reporter, trust_endorsement, access_management" in exc.value.user_message

    def test_invalid_action(self) -> None:
        """Test raises ValidationError for invalid action."""
        with pytest.raises(ValidationError) as exc:
            extract_feature_params(
                "/ketchup feature status_updater invalid", CommandContext.DIRECT_MESSAGE
            )
        assert "Invalid feature action: invalid" in exc.value.message
        assert (
            "Available actions: enable, disable, list, status, grant, revoke" in exc.value.user_message
        )

    def test_enable_without_user(self) -> None:
        """Test raises ValidationError for enable without user mention."""
        with pytest.raises(ValidationError) as exc:
            extract_feature_params(
                "/ketchup feature status_updater enable", CommandContext.DIRECT_MESSAGE
            )
        assert "Missing channel for enable action" in exc.value.message
        assert "channel ID" in exc.value.user_message

    def test_disable_without_user(self) -> None:
        """Test raises ValidationError for disable without user mention."""
        with pytest.raises(ValidationError) as exc:
            extract_feature_params(
                "/ketchup feature status_updater disable", CommandContext.DIRECT_MESSAGE
            )
        assert "Missing channel for disable action" in exc.value.message
        assert "channel ID" in exc.value.user_message

    def test_invalid_user_mention_format(self) -> None:
        """Test raises ValidationError for invalid channel mention format."""
        with pytest.raises(ValidationError) as exc:
            extract_feature_params(
                "/ketchup feature status_updater enable @user", CommandContext.DIRECT_MESSAGE
            )
        assert "Invalid channel format: @user" in exc.value.message

    def test_valid_status_action(self) -> None:
        """Test valid status action extraction."""
        params = extract_feature_params(
            "/ketchup feature status_updater status", CommandContext.DIRECT_MESSAGE
        )
        assert params.command_type == CommandType.FEATURE
        assert params.feature_name == "status_updater"
        assert params.action == "status"
        assert params.target_user_id is None

    def test_valid_list_action(self) -> None:
        """Test valid list action extraction."""
        params = extract_feature_params(
            "/ketchup feature status_updater list", CommandContext.DIRECT_MESSAGE
        )
        assert params.command_type == CommandType.FEATURE
        assert params.feature_name == "status_updater"
        assert params.action == "list"
        assert params.target_user_id is None

    def test_valid_enable_with_user(self) -> None:
        """Test valid enable action with channel mention."""
        params = extract_feature_params(
            "/ketchup feature status_updater enable <#C12345678|general>", CommandContext.DIRECT_MESSAGE
        )
        assert params.command_type == CommandType.FEATURE
        assert params.feature_name == "status_updater"
        assert params.action == "enable"
        assert params.target_channel_id == "C12345678"

    def test_valid_disable_with_user(self) -> None:
        """Test valid disable action with channel mention."""
        params = extract_feature_params(
            "/ketchup feature status_updater disable <#C67890123|random>", CommandContext.DIRECT_MESSAGE
        )
        assert params.command_type == CommandType.FEATURE
        assert params.feature_name == "status_updater"
        assert params.action == "disable"
        assert params.target_channel_id == "C67890123"

    def test_user_mention_with_pipe(self) -> None:
        """Test channel mention with pipe format (Slack display name)."""
        # Note: The current regex doesn't capture the pipe portion, only the channel ID
        params = extract_feature_params(
            "/ketchup feature status_updater enable <#C12345678|general>",
            CommandContext.DIRECT_MESSAGE,
        )
        assert params.command_type == CommandType.FEATURE
        assert params.feature_name == "status_updater"
        assert params.action == "enable"
        assert params.target_channel_id == "C12345678"

    def test_feature_name_case_insensitive(self) -> None:
        """Test feature name is converted to lowercase."""
        params = extract_feature_params(
            "/ketchup feature STATUS_UPDATER status", CommandContext.DIRECT_MESSAGE
        )
        assert params.feature_name == "status_updater"

    def test_action_case_insensitive(self) -> None:
        """Test action is converted to lowercase."""
        params = extract_feature_params(
            "/ketchup feature status_updater STATUS", CommandContext.DIRECT_MESSAGE
        )
        assert params.action == "status"

    def test_public_channel_context(self) -> None:
        """Test feature commands work in public channel context."""
        params = extract_feature_params(
            "/ketchup feature status_updater status", CommandContext.PUBLIC_CHANNEL
        )
        assert params.command_type == CommandType.FEATURE
        assert params.context == CommandContext.PUBLIC_CHANNEL

    def test_original_command_preserved(self) -> None:
        """Test original command is preserved in params."""
        command = "/ketchup feature status_updater enable <#C12345678|general>"
        params = extract_feature_params(command, CommandContext.DIRECT_MESSAGE)
        assert params.original_command == command

    def test_extra_spaces_handled(self) -> None:
        """Test command with extra spaces is handled correctly."""
        params = extract_feature_params(
            "/ketchup  feature   status_updater    status", CommandContext.DIRECT_MESSAGE
        )
        assert params.feature_name == "status_updater"
        assert params.action == "status"
