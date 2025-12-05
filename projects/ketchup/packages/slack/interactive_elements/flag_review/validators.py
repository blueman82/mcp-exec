"""
Validation logic for flag review functionality.

This module handles input validation, rate limiting, and security checks
for flag review submissions.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.slack.interactive_elements.flag_review.flag_types import (
    RATE_LIMIT_MAX_FLAGS,
    RATE_LIMIT_WINDOW_SECONDS,
    RateLimitResult,
    ValidationResult,
)

logger = setup_logger(__name__)


class FlagReviewValidator:
    """Handles validation logic for flag review functionality."""

    def __init__(self):
        """Initialize the validator with rate limit tracking."""
        self.rate_limit_store = defaultdict(list)  # user_id -> list of timestamps

    def validate_flag_input(self, text: str, user_id: str, channel_id: str) -> Dict[str, Any]:
        """
        Validate feedback text for potential issues.

        Args:
            text: The feedback text to validate
            user_id: The ID of the user submitting feedback
            channel_id: The channel where feedback is submitted

        Returns:
            Dict containing validation results with keys:
                - valid: Boolean indicating if input is valid
                - issues: List of validation issues found
                - sanitized_text: The sanitized version of the text
        """
        issues = []

        # Check length
        if len(text) < 10:
            issues.append("Feedback too short")
        elif len(text) > 3000:
            issues.append("Feedback exceeds maximum length")

        # Check for potential security issues
        suspicious_patterns = ["<script", "javascript:", "onclick=", "onerror="]
        for pattern in suspicious_patterns:
            if pattern.lower() in text.lower():
                issues.append("Contains potentially unsafe content")
                break

        # Check for spam patterns
        if text.count("http") > 5:
            issues.append("Contains too many URLs")

        # Check for excessive whitespace
        if len(text.strip()) < len(text) * 0.5:
            issues.append("Contains excessive whitespace")

        # Check for repetitive characters
        for char in text:
            if text.count(char * 10) > 0:  # 10 repeated characters
                issues.append("Contains repetitive characters")
                break

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "sanitized_text": text.strip(),  # Basic sanitization
        }

    def check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user is within rate limits.

        Args:
            user_id: The ID of the user to check

        Returns:
            True if user is within rate limits, False otherwise
        """
        current_time = datetime.now(timezone.utc)

        # Clean old entries
        self.rate_limit_store[user_id] = [
            ts
            for ts in self.rate_limit_store[user_id]
            if (current_time - ts).total_seconds() < RATE_LIMIT_WINDOW_SECONDS
        ]

        # Check limit
        if len(self.rate_limit_store[user_id]) >= RATE_LIMIT_MAX_FLAGS:
            return False

        # Add current timestamp
        self.rate_limit_store[user_id].append(current_time)
        return True

    def validate_user_permissions(
        self, user_id: str, channel_id: str, workspace_id: str = "T018BPFUD75"
    ) -> ValidationResult:
        """
        Validate user permissions for the action.

        Args:
            user_id: The ID of the user
            channel_id: The channel ID
            workspace_id: The workspace ID (defaults to Adobe workspace)

        Returns:
            ValidationResult with is_valid and any errors
        """
        errors = []

        # Check if user ID is valid format
        if not user_id or not user_id.startswith("U"):
            errors.append("Invalid user ID format")

        # Check if channel ID is valid format
        if not channel_id or not channel_id.startswith("C"):
            errors.append("Invalid channel ID format")

        # Check workspace ID
        if workspace_id != "T018BPFUD75":
            errors.append("Invalid workspace")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate_channel_context(
        self, channel_id: str, channel_type: str = "public"
    ) -> ValidationResult:
        """
        Validate the channel context for flag submission.

        Args:
            channel_id: The channel ID
            channel_type: The type of channel (public, private, dm)

        Returns:
            ValidationResult with is_valid and any errors
        """
        errors = []

        # Check channel ID format
        if not channel_id:
            errors.append("Channel ID is required")
        elif channel_id.startswith("D"):
            # Direct message - different validation
            if channel_type != "dm":
                errors.append("Channel type mismatch for DM")
        elif channel_id.startswith("C"):
            # Public channel
            if channel_type not in ["public", "channel"]:
                errors.append("Channel type mismatch for public channel")
        elif channel_id.startswith("G"):
            # Private channel/group
            if channel_type not in ["private", "group"]:
                errors.append("Channel type mismatch for private channel")
        else:
            errors.append("Invalid channel ID format")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def get_rate_limit_status(self, user_id: str) -> RateLimitResult:
        """
        Get the current rate limit status for a user.

        Args:
            user_id: The ID of the user

        Returns:
            RateLimitResult with current status
        """
        current_time = datetime.now(timezone.utc)

        # Clean old entries
        self.rate_limit_store[user_id] = [
            ts
            for ts in self.rate_limit_store[user_id]
            if (current_time - ts).total_seconds() < RATE_LIMIT_WINDOW_SECONDS
        ]

        current_count = len(self.rate_limit_store[user_id])
        remaining = max(0, RATE_LIMIT_MAX_FLAGS - current_count)

        # Calculate reset time (when oldest entry expires)
        reset_time = None
        if self.rate_limit_store[user_id]:
            oldest_entry = min(self.rate_limit_store[user_id])
            reset_timestamp = oldest_entry.timestamp() + RATE_LIMIT_WINDOW_SECONDS
            reset_time = int(reset_timestamp)

        return RateLimitResult(allowed=remaining > 0, remaining=remaining, reset_time=reset_time)

    def sanitize_text(self, text: str) -> str:
        """
        Sanitize text input for safe storage and display.

        Args:
            text: The text to sanitize

        Returns:
            Sanitized text
        """
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Remove control characters
        text = "".join(char for char in text if ord(char) >= 32 or char == "\n")

        # Truncate if too long
        if len(text) > 3000:
            text = text[:2997] + "..."

        return text.strip()
