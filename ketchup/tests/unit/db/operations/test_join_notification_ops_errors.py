"""
Unit tests for JoinNotificationOps error classification and handling.

Covers:
- _classify_slack_error for all error mappings
- Slack error response handling
- FailureReason enum validation
- Edge cases in error classification

All external dependencies mocked. Tests follow existing codebase patterns.
"""

import pytest

from packages.db.models.notification_tracking import FailureReason
from packages.db.operations.join_notification_ops import JoinNotificationOps

pytestmark = pytest.mark.unit


@pytest.fixture
def join_ops() -> JoinNotificationOps:
    """Fixture for JoinNotificationOps with dummy client."""
    # Use None client since we're only testing error classification
    return JoinNotificationOps(None, "test-table")


class TestJoinNotificationOpsErrors:
    """Test class for JoinNotificationOps error classification."""

    def test_classify_slack_error_success_response(self, join_ops: JoinNotificationOps) -> None:
        """Test classification of successful Slack response."""
        response = {"ok": True}
        result = join_ops._classify_slack_error(response)
        assert result is None

    def test_classify_slack_error_success_with_data(self, join_ops: JoinNotificationOps) -> None:
        """Test classification of successful response with additional data."""
        response = {"ok": True, "channel": "C1234567890", "ts": "1703123456.123"}
        result = join_ops._classify_slack_error(response)
        assert result is None

    def test_classify_slack_error_empty_response(self, join_ops: JoinNotificationOps) -> None:
        """Test classification of empty response."""
        result = join_ops._classify_slack_error(None)
        assert result == FailureReason.NETWORK_ERROR.value

        result = join_ops._classify_slack_error({})
        assert result == FailureReason.NETWORK_ERROR.value

    def test_classify_slack_error_false_ok(self, join_ops: JoinNotificationOps) -> None:
        """Test classification when ok is explicitly False."""
        response = {"ok": False}
        result = join_ops._classify_slack_error(response)
        assert result == FailureReason.SLACK_API_ERROR.value

    @pytest.mark.parametrize(
        "slack_error,expected_reason",
        [
            ("not_in_channel", FailureReason.SLACK_NOT_IN_CHANNEL.value),
            ("channel_not_found", FailureReason.SLACK_NOT_IN_CHANNEL.value),
            ("is_archived", FailureReason.SLACK_NOT_IN_CHANNEL.value),
            ("rate_limited", FailureReason.SLACK_RATE_LIMITED.value),
            ("ratelimited", FailureReason.SLACK_RATE_LIMITED.value),
            ("not_authed", FailureReason.SLACK_PERMISSION_DENIED.value),
            ("invalid_auth", FailureReason.SLACK_PERMISSION_DENIED.value),
            ("missing_scope", FailureReason.SLACK_PERMISSION_DENIED.value),
            ("cannot_post_ephemeral", FailureReason.SLACK_PERMISSION_DENIED.value),
            ("restricted_action", FailureReason.SLACK_PERMISSION_DENIED.value),
        ]
    )
    def test_classify_slack_error_known_mappings(
        self, join_ops: JoinNotificationOps, slack_error: str, expected_reason: str
    ) -> None:
        """Test all known Slack error to FailureReason mappings."""
        response = {"ok": False, "error": slack_error}
        result = join_ops._classify_slack_error(response)
        assert result == expected_reason

    def test_classify_slack_error_unknown_error(self, join_ops: JoinNotificationOps) -> None:
        """Test classification of unknown Slack errors."""
        unknown_errors = [
            "unknown_error",
            "new_slack_error",
            "random_failure",
            "unexpected_response"
        ]

        for error in unknown_errors:
            response = {"ok": False, "error": error}
            result = join_ops._classify_slack_error(response)
            assert result == FailureReason.SLACK_API_ERROR.value

    def test_classify_slack_error_empty_error_string(self, join_ops: JoinNotificationOps) -> None:
        """Test classification when error string is empty."""
        response = {"ok": False, "error": ""}
        result = join_ops._classify_slack_error(response)
        assert result == FailureReason.SLACK_API_ERROR.value

    def test_classify_slack_error_missing_error_field(self, join_ops: JoinNotificationOps) -> None:
        """Test classification when error field is missing."""
        response = {"ok": False}
        result = join_ops._classify_slack_error(response)
        assert result == FailureReason.SLACK_API_ERROR.value

    def test_classify_slack_error_case_sensitivity(self, join_ops: JoinNotificationOps) -> None:
        """Test that error classification is case sensitive."""
        # Test uppercase versions should not match
        uppercase_errors = [
            "NOT_IN_CHANNEL",
            "RATE_LIMITED",
            "INVALID_AUTH"
        ]

        for error in uppercase_errors:
            response = {"ok": False, "error": error}
            result = join_ops._classify_slack_error(response)
            assert result == FailureReason.SLACK_API_ERROR.value

    def test_get_slack_error_mappings_completeness(self, join_ops: JoinNotificationOps) -> None:
        """Test Slack error mappings completeness and correctness."""
        mappings = join_ops._get_slack_error_mappings()

        expected_mappings = {
            "not_in_channel": FailureReason.SLACK_NOT_IN_CHANNEL.value,
            "channel_not_found": FailureReason.SLACK_NOT_IN_CHANNEL.value,
            "is_archived": FailureReason.SLACK_NOT_IN_CHANNEL.value,
            "rate_limited": FailureReason.SLACK_RATE_LIMITED.value,
            "ratelimited": FailureReason.SLACK_RATE_LIMITED.value,
            "not_authed": FailureReason.SLACK_PERMISSION_DENIED.value,
            "invalid_auth": FailureReason.SLACK_PERMISSION_DENIED.value,
            "missing_scope": FailureReason.SLACK_PERMISSION_DENIED.value,
            "cannot_post_ephemeral": FailureReason.SLACK_PERMISSION_DENIED.value,
            "restricted_action": FailureReason.SLACK_PERMISSION_DENIED.value,
        }

        assert len(mappings) == len(expected_mappings)

        for error, expected_reason in expected_mappings.items():
            assert mappings[error] == expected_reason

    def test_slack_error_mappings_categorization(self, join_ops: JoinNotificationOps) -> None:
        """Test that error mappings are properly categorized."""
        mappings = join_ops._get_slack_error_mappings()

        # Channel-related errors
        channel_errors = ["not_in_channel", "channel_not_found", "is_archived"]
        for error in channel_errors:
            assert mappings[error] == FailureReason.SLACK_NOT_IN_CHANNEL.value

        # Rate limiting errors
        rate_limit_errors = ["rate_limited", "ratelimited"]
        for error in rate_limit_errors:
            assert mappings[error] == FailureReason.SLACK_RATE_LIMITED.value

        # Permission errors
        permission_errors = [
            "not_authed", "invalid_auth", "missing_scope",
            "cannot_post_ephemeral", "restricted_action"
        ]
        for error in permission_errors:
            assert mappings[error] == FailureReason.SLACK_PERMISSION_DENIED.value


class TestFailureReasonEnum:
    """Test FailureReason enum values and completeness."""

    def test_failure_reason_slack_values(self) -> None:
        """Test Slack-related FailureReason enum values."""
        assert FailureReason.SLACK_RATE_LIMITED.value == "slack_rate_limited"
        assert FailureReason.SLACK_NOT_IN_CHANNEL.value == "not_in_channel"
        assert FailureReason.SLACK_PERMISSION_DENIED.value == "permission_denied"
        assert FailureReason.SLACK_API_ERROR.value == "slack_api_error"

    def test_failure_reason_ai_values(self) -> None:
        """Test AI-related FailureReason enum values."""
        assert FailureReason.AI_GENERATION_FAILED.value == "ai_generation_failed"
        assert FailureReason.AI_TIMEOUT.value == "ai_timeout"

    def test_failure_reason_system_values(self) -> None:
        """Test system-related FailureReason enum values."""
        assert FailureReason.NETWORK_ERROR.value == "network_error"
        assert FailureReason.INTERNAL_ERROR.value == "internal_error"
        assert FailureReason.DATA_COLLECTION_FAILED.value == "data_collection_failed"

    def test_failure_reason_enum_completeness(self) -> None:
        """Test that all expected failure reasons are defined."""
        expected_reasons = {
            "slack_rate_limited", "not_in_channel", "permission_denied", "slack_api_error",
            "ai_generation_failed", "ai_timeout", "network_error", "internal_error",
            "data_collection_failed"
        }

        actual_reasons = {reason.value for reason in FailureReason}
        assert actual_reasons == expected_reasons

    def test_failure_reason_uniqueness(self) -> None:
        """Test that all FailureReason values are unique."""
        values = [reason.value for reason in FailureReason]
        assert len(values) == len(set(values))

    def test_failure_reason_string_format(self) -> None:
        """Test that all FailureReason values follow expected string format."""
        for reason in FailureReason:
            value = reason.value
            # Should be lowercase with underscores
            assert value.islower()
            assert " " not in value
            assert value.replace("_", "").isalnum()