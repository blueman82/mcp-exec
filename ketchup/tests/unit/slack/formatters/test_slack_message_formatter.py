"""
Unit tests for SlackMessageFormatter in packages.slack.channel_operations.slack_message_formatter.

Covers:
- SlackMessageFormatter: convert_timestamp_to_utc, replace_user_ids_with_names, clean_text, process_message_batch
- All logic branches: valid/invalid timestamps, empty/HTML text, unknown user IDs, multiple mentions, unordered messages
- All dependencies are mocked (SlackUserOps, logger)
- All tests pass mypy --strict and ruff
- Expected: correct formatting, cleaning, user replacement, batch processing
"""

from typing import Dict, List, Set
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.channel_operations.slack_message_formatter import (
    SlackMessageFormatter,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_user_ops() -> MagicMock:
    return MagicMock()


@pytest.fixture
def formatter(mock_user_ops: MagicMock) -> SlackMessageFormatter:
    return SlackMessageFormatter(user_ops=mock_user_ops)


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("1625846400.000100", "2021-07-09 16:00:00 UTC"),
        ("not_a_timestamp", "Invalid Timestamp"),
        (None, "Invalid Timestamp"),
    ],
)
def test_convert_timestamp_to_utc(
    formatter: SlackMessageFormatter, timestamp: str | None, expected: str
) -> None:
    """Test convert_timestamp_to_utc handles valid and invalid timestamps."""
    with patch(
        "packages.slack.channel_operations.slack_message_formatter.logger"
    ) as mock_logger:
        result = formatter.convert_timestamp_to_utc(timestamp)
        assert result == expected
        if expected == "Invalid Timestamp":
            assert mock_logger.error.called


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,user_cache,expected",
    [
        ("Hello <@U123>", {"U123": "alice"}, "Hello @alice"),
        ("<@U123|bob> and <@U456>", {"U123": "bob", "U456": "eve"}, "@bob and @eve"),
        ("No mentions", {}, "No mentions"),
        ("<@U999>", {}, "@<@U999>"),
    ],
)
async def test_replace_user_ids_with_names(
    formatter: SlackMessageFormatter,
    text: str,
    user_cache: Dict[str, str],
    expected: str,
) -> None:
    """Test replace_user_ids_with_names replaces user IDs with names or leaves unknowns."""
    result = await formatter.replace_user_ids_with_names(text, user_cache)
    assert result == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hello &amp; &lt;world&gt;", "Hello & world"),
        ("", ""),
        (None, ""),
        ("Multiple   spaces\n\n", "Multiple spaces"),
        ("<left> and <right>", "left and right"),
    ],
)
def test_clean_text(formatter: SlackMessageFormatter, text: str, expected: str) -> None:
    """Test clean_text unescapes HTML, normalizes whitespace, removes brackets."""
    result = formatter.clean_text(text)
    assert result == expected


@pytest.mark.asyncio
async def test_process_message_batch_basic(
    formatter: SlackMessageFormatter, mock_user_ops: MagicMock
) -> None:
    """Test process_message_batch formats messages, sorts, replaces users, cleans text."""
    messages = [
        {"ts": "2", "user": "U1", "text": "Hi <@U2>"},
        {"ts": "1", "user": "U2", "text": "Hello &amp; <@U1>"},
    ]
    user_mentions: Set[str] = {"U1", "U2"}
    mock_user_ops.get_user_names = AsyncMock(return_value={"U1": "alice", "U2": "bob"})
    fmt = SlackMessageFormatter(user_ops=mock_user_ops)
    with patch("packages.slack.channel_operations.slack_message_formatter.logger"):
        result, user_cache = await fmt.process_message_batch(messages, user_mentions)
    # Should be sorted by ts: "1" then "2"
    assert result[0].endswith("bob: Hello & @alice")
    assert result[1].endswith("alice: Hi @bob")
    assert user_cache == {"U1": "alice", "U2": "bob"}


@pytest.mark.asyncio
async def test_process_message_batch_empty_and_unknowns(
    formatter: SlackMessageFormatter, mock_user_ops: MagicMock
) -> None:
    """Test process_message_batch handles empty messages and unknown users."""
    messages: List[Dict[str, str]] = []
    user_mentions: Set[str] = set()
    mock_user_ops.get_user_names = AsyncMock(return_value={})
    fmt = SlackMessageFormatter(user_ops=mock_user_ops)
    with patch("packages.slack.channel_operations.slack_message_formatter.logger"):
        result, user_cache = await fmt.process_message_batch(messages, user_mentions)
    assert result == []
    assert user_cache == {}

    # Unknown user in message
    messages = [{"ts": "1", "user": "U999", "text": "Hi <@U999>"}]
    user_mentions = {"U999"}
    mock_user_ops.get_user_names = AsyncMock(return_value={})
    fmt = SlackMessageFormatter(user_ops=mock_user_ops)
    with patch("packages.slack.channel_operations.slack_message_formatter.logger"):
        result, user_cache = await fmt.process_message_batch(messages, user_mentions)
    assert "Unknown User" in result[0] or "U999" in result[0]
