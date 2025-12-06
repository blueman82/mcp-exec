"""
Unit tests for FlagReviewValidator.

Tests validation and rate limiting for flag review functionality.
"""

import pytest

from packages.slack.interactive_elements.flag_review.validators import (
    FlagReviewValidator,
)


class TestFlagReviewValidator:
    """Test suite for FlagReviewValidator."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return FlagReviewValidator()

    def test_validate_flag_input_valid(self, validator):
        """Test validation of valid flag input."""
        result = validator.validate_flag_input(
            text="This is valid feedback text", user_id="U123", channel_id="C123"
        )

        assert result["valid"] is True
        assert result["issues"] == []

    def test_validate_flag_input_too_short(self, validator):
        """Test validation of too short text."""
        result = validator.validate_flag_input(text="Short", user_id="U123", channel_id="C123")

        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert "too short" in result["issues"][0]

    def test_validate_flag_input_too_long(self, validator):
        """Test validation of too long text."""
        long_text = "a" * 3001  # Over 3000 character limit
        result = validator.validate_flag_input(text=long_text, user_id="U123", channel_id="C123")

        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert "length" in result["issues"][0]

    def test_check_rate_limit_within_limit(self, validator):
        """Test rate limiting within allowed limits."""
        user_id = "U123"

        # First 3 should pass (within rate limit)
        for i in range(3):
            assert validator.check_rate_limit(user_id) is True

    def test_check_rate_limit_exceeded(self, validator):
        """Test rate limiting when exceeded."""
        user_id = "U123"

        # Use up the rate limit
        for i in range(3):
            validator.check_rate_limit(user_id)

        # 4th should fail
        assert validator.check_rate_limit(user_id) is False

    def test_check_rate_limit_different_users(self, validator):
        """Test rate limiting works independently for different users."""
        user1 = "U123"
        user2 = "U456"

        # Use up rate limit for user1
        for i in range(3):
            validator.check_rate_limit(user1)

        # User1 should be rate limited
        assert validator.check_rate_limit(user1) is False

        # User2 should still pass
        assert validator.check_rate_limit(user2) is True

    def test_initialization(self, validator):
        """Test that validator initializes correctly."""
        assert hasattr(validator, "validate_flag_input")
        assert hasattr(validator, "check_rate_limit")
        assert callable(validator.validate_flag_input)
        assert callable(validator.check_rate_limit)
