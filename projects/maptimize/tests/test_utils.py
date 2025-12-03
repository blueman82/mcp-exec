"""Tests for maptimize.utils module."""

from maptimize.utils import setup_logging, validate_slack_event


def test_setup_logging():
    """Test logging setup initializes logger."""
    logger = setup_logging()
    assert logger is not None
    # Verify it has structlog logger interface
    assert hasattr(logger, "msg")
    assert hasattr(logger, "bind")


def test_validate_slack_event_valid():
    """Test validation of valid Slack events."""
    event = {"type": "app_mention", "user": "U123", "text": "<@U_BOT> hello"}
    assert validate_slack_event(event) is True


def test_validate_slack_event_valid_message():
    """Test validation of valid message events."""
    event = {"type": "message", "user": "U456", "text": "hello world"}
    assert validate_slack_event(event) is True


def test_validate_slack_event_invalid_missing_type():
    """Test validation rejects events without type."""
    event = {"user": "U123", "text": "hello"}
    assert validate_slack_event(event) is False


def test_validate_slack_event_invalid_missing_user():
    """Test validation rejects events without user."""
    event = {"type": "app_mention", "text": "hello"}
    assert validate_slack_event(event) is False


def test_validate_slack_event_invalid_not_dict():
    """Test validation rejects non-dict inputs."""
    assert validate_slack_event("not a dict") is False
    assert validate_slack_event(None) is False
    assert validate_slack_event([]) is False


def test_validate_slack_event_empty_dict():
    """Test validation rejects empty dicts."""
    event = {}
    assert validate_slack_event(event) is False
