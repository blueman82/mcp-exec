"""Utility functions for shared functionality including logging and validation."""

from typing import Any, Optional

import structlog


def setup_logging() -> structlog.BoundLogger:
    """Initialize structlog for structured logging.

    Configures structlog with JSON output format for production-grade
    structured logging that is easy to parse and search.

    Returns:
        structlog.BoundLogger: Configured logger instance.
    """
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    return structlog.get_logger()


def validate_slack_event(event: Any) -> bool:
    """Validate Slack event structure.

    Checks that the event is a dictionary with required fields:
    - type: The event type (e.g., 'app_mention', 'message')
    - user: The user ID who triggered the event

    Args:
        event: The event object to validate.

    Returns:
        bool: True if the event is valid, False otherwise.
    """
    if not isinstance(event, dict):
        return False

    required_fields = ["type", "user"]
    return all(field in event for field in required_fields)


def handle_validation_error(field: str, message: str = None) -> str:
    """Generate a user-friendly validation error message.

    Args:
        field: The field that failed validation.
        message: Optional custom error message. If not provided,
                a default message will be generated.

    Returns:
        str: A formatted error message.
    """
    if message:
        return f"Invalid {field}: {message}"
    return f"Invalid {field}"


def safe_get_nested(obj: dict, keys: list, default: Any = None) -> Any:
    """Safely get a nested value from a dictionary.

    Args:
        obj: The dictionary to query.
        keys: A list of keys representing the path to the value.
        default: The default value to return if the path doesn't exist.

    Returns:
        The value at the path, or default if not found.
    """
    current = obj
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
