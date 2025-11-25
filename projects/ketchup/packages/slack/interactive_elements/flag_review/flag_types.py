"""
Type definitions and constants for flag review functionality.

This module contains all shared types, constants, and data structures
used across the flag review handler modules.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict

# Channel configuration
REVIEW_CHANNEL_ID = "C095LQ0H4KB"  # #ketchup-feedback-review

# Rate limiting configuration
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
RATE_LIMIT_MAX_FLAGS = 3  # Maximum flags per window

# Modal identifiers
MODAL_FLAG_REVIEW = "flag_review_modal"
MODAL_REPLY_FEEDBACK = "reply_feedback_modal"
MODAL_REPLY_COMMAND_FEEDBACK = "reply_command_feedback_modal"

# Action identifiers
ACTION_FLAG_STATUS_REVIEW = "flag_status_review"
ACTION_ACKNOWLEDGE_FEEDBACK = "acknowledge_feedback"
ACTION_REPLY_TO_FEEDBACK = "reply_to_feedback"
ACTION_COMMAND_FLAG_REVIEW = "command_flag_review"
ACTION_COMMAND_ACKNOWLEDGE = "command_acknowledge_feedback"
ACTION_COMMAND_REPLY = "command_reply_to_feedback"

# Block identifiers
BLOCK_FEEDBACK_INPUT = "feedback_input"
BLOCK_REPLY_INPUT = "reply_input"
BLOCK_STATUS_TEXT = "status_text"
BLOCK_COMMAND_OUTPUT = "command_output"


class FeedbackType(Enum):
    """Types of feedback that can be submitted."""

    INCORRECT_INFO = "incorrect_info"
    MISSING_INFO = "missing_info"
    FORMATTING_ISSUE = "formatting"
    OTHER = "other"


class FeedbackStatus(Enum):
    """Status of feedback items."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    REPLIED = "replied"
    RESOLVED = "resolved"


@dataclass
class FeedbackRecord:
    """Represents a feedback record in the database."""

    feedback_id: str
    user_id: str
    channel_id: str
    message_ts: str
    feedback_text: str
    feedback_type: str
    status: str
    created_at: str
    updated_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    reply_text: Optional[str] = None
    replied_by: Optional[str] = None
    replied_at: Optional[str] = None
    original_content: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ValidationResult(TypedDict):
    """Result of validation operations."""

    is_valid: bool
    errors: List[str]


class RateLimitResult(TypedDict):
    """Result of rate limit check."""

    allowed: bool
    remaining: int
    reset_time: Optional[int]
