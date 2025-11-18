"""
validation_orchestrator.py

Handles feedback validation, rate limiting, and input sanitization for flag review functionality.
Provides centralized validation logic and security checks.

This module contains the same validation logic as the original implementation,
with some methods simplified to their essential functionality.
"""

from typing import Dict, List, Any

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class ValidationOrchestrator:
    """Handles feedback validation, rate limiting, and input sanitization."""

    def __init__(self):
        """Initialize the validation orchestrator."""
        self._rate_limits: Dict[str, List[float]] = {}

    async def validate_feedback(
        self, text: str, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Validate feedback text for potential issues.

        Args:
            text: The feedback text to validate.
            user_id: The ID of the user providing feedback.
            channel_id: The channel ID where feedback was provided.

        Returns:
            Dictionary with validation results including 'valid' boolean and 'issues' list.
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

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "sanitized_text": text,  # Could implement actual sanitization
        }

    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit.

        Args:
            user_id: The user ID to check.

        Returns:
            True if user is within rate limit, False if rate limited.
        """
        import time
        from packages.slack.interactive_elements.flag_review.flag_types import (
            RATE_LIMIT_WINDOW_SECONDS,
            RATE_LIMIT_MAX_FLAGS,
        )

        current_time = time.time()

        # Initialize user rate limit if not exists
        if user_id not in self._rate_limits:
            self._rate_limits[user_id] = []

        # Clean old entries
        self._rate_limits[user_id] = [
            timestamp
            for timestamp in self._rate_limits[user_id]
            if current_time - timestamp < RATE_LIMIT_WINDOW_SECONDS
        ]

        # Check if within limit
        if len(self._rate_limits[user_id]) >= RATE_LIMIT_MAX_FLAGS:
            return False

        # Add current request
        self._rate_limits[user_id].append(current_time)
        return True

    def validate_trigger_id(self, trigger_id: str) -> bool:
        """Validate Slack trigger ID format and length.

        Args:
            trigger_id: The Slack trigger ID to validate.

        Returns:
            True if trigger ID is valid, False otherwise.
        """
        if not trigger_id or len(trigger_id) < 25:
            logger.error(
                f"Invalid trigger_id: {trigger_id} (length: {len(trigger_id) if trigger_id else 0})"
            )
            return False
        return True

    def sanitize_input(self, text: str) -> str:
        """Sanitize user input to prevent XSS and other issues.

        Args:
            text: The input text to sanitize.

        Returns:
            Sanitized text.
        """
        # Basic sanitization - remove potentially dangerous patterns
        import re

        # Remove script tags and javascript
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)

        # Trim whitespace
        return text.strip()

    def validate_channel_access(self, user_id: str, channel_id: str) -> bool:
        """Validate if user has access to the specified channel.

        This method is a placeholder and always returns True.
        In the original implementation, this validation was not needed.

        Args:
            user_id: The user ID to check.
            channel_id: The channel ID to check access for.

        Returns:
            Always True (no validation performed).
        """
        return True

    def validate_message_exists(self, channel_id: str, message_ts: str) -> bool:
        """Validate if a message exists in the specified channel.

        This method is a placeholder and always returns True.
        In the original implementation, this validation was not needed.

        Args:
            channel_id: The channel ID where the message should be.
            message_ts: The message timestamp to check.

        Returns:
            Always True (no validation performed).
        """
        return True
