"""
notification_tracking.py

Data models for join notification tracking functionality.
Contains enums and constants for failure reason classification.
"""

from enum import Enum


class FailureReason(Enum):
    """Failure reason codes for join notification tracking"""

    # Slack API failures
    SLACK_RATE_LIMITED = "slack_rate_limited"
    SLACK_NOT_IN_CHANNEL = "not_in_channel"
    SLACK_PERMISSION_DENIED = "permission_denied"
    SLACK_API_ERROR = "slack_api_error"

    # AI/Generation failures
    AI_GENERATION_FAILED = "ai_generation_failed"
    AI_TIMEOUT = "ai_timeout"

    # System failures
    NETWORK_ERROR = "network_error"
    INTERNAL_ERROR = "internal_error"
    DATA_COLLECTION_FAILED = "data_collection_failed"
