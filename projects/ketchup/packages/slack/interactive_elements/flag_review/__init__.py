"""
Flag Review Handler Module

This package contains the modularized components of the flag review handler.
The modules are organized to provide clear separation of concerns while
maintaining backward compatibility with the existing FlagReviewHandler interface.
"""

from packages.slack.interactive_elements.flag_review.flag_types import (
    ACTION_ACKNOWLEDGE_FEEDBACK,
    ACTION_COMMAND_ACKNOWLEDGE,
    ACTION_COMMAND_FLAG_REVIEW,
    ACTION_COMMAND_REPLY,
    ACTION_FLAG_STATUS_REVIEW,
    ACTION_REPLY_TO_FEEDBACK,
    BLOCK_COMMAND_OUTPUT,
    BLOCK_FEEDBACK_INPUT,
    BLOCK_REPLY_INPUT,
    BLOCK_STATUS_TEXT,
    MODAL_FLAG_REVIEW,
    MODAL_REPLY_COMMAND_FEEDBACK,
    MODAL_REPLY_FEEDBACK,
    RATE_LIMIT_MAX_FLAGS,
    RATE_LIMIT_WINDOW_SECONDS,
    REVIEW_CHANNEL_ID,
    FeedbackRecord,
    FeedbackStatus,
    FeedbackType,
    RateLimitResult,
    ValidationResult,
)

__all__ = [
    # Constants
    "REVIEW_CHANNEL_ID",
    "RATE_LIMIT_WINDOW_SECONDS",
    "RATE_LIMIT_MAX_FLAGS",
    "MODAL_FLAG_REVIEW",
    "MODAL_REPLY_FEEDBACK",
    "MODAL_REPLY_COMMAND_FEEDBACK",
    "ACTION_FLAG_STATUS_REVIEW",
    "ACTION_ACKNOWLEDGE_FEEDBACK",
    "ACTION_REPLY_TO_FEEDBACK",
    "ACTION_COMMAND_FLAG_REVIEW",
    "ACTION_COMMAND_ACKNOWLEDGE",
    "ACTION_COMMAND_REPLY",
    "BLOCK_FEEDBACK_INPUT",
    "BLOCK_REPLY_INPUT",
    "BLOCK_STATUS_TEXT",
    "BLOCK_COMMAND_OUTPUT",
    # Enums
    "FeedbackType",
    "FeedbackStatus",
    # Data classes
    "FeedbackRecord",
    # Type definitions
    "ValidationResult",
    "RateLimitResult",
]
