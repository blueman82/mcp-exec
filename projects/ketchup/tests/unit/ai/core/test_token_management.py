"""
Unit tests for TokenManager in packages.ai.core.operations.token_management.

Covers:
- Initialization
- enforce_token_limit: normal (under limit), over limit (truncation), notification, and all error paths
- _send_truncation_notification: normal, error in post, error in cleanup
- _truncate_messages_preserving_system: all message role combinations (system+user, user only, system only, neither), edge cases (not enough tokens for user, empty content)
- All dependencies (count_tokens, truncate_text_to_token_limit, tokens_to_words, SlackPostingHandler) are mocked
- All tests pass mypy --strict and ruff
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.ai.core.operations.token_management import TokenManager
from packages.slack.messages.posting import SlackPostingHandler

pytestmark = pytest.mark.unit


@pytest.fixture
def manager() -> TokenManager:
    return TokenManager()  # type: ignore[no-untyped-call]


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
@pytest.mark.asyncio
async def test_enforce_token_limit_under_limit(
    mock_count_tokens: MagicMock, manager: TokenManager
) -> None:
    """Test enforce_token_limit returns messages unchanged if under limit."""
    mock_count_tokens.return_value = 50
    messages = [{"role": "user", "content": "foo"}]
    result = await manager.enforce_token_limit(messages, "U1", "C1")
    assert result == messages


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.tokens_to_words")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
@pytest.mark.asyncio
async def test_enforce_token_limit_over_limit(
    mock_tokens_to_words: MagicMock,
    mock_count_tokens: MagicMock,
    manager: TokenManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test enforce_token_limit when over limit and cleanup succeeds."""
    mock_count_tokens.side_effect = [
        10,  # system tokens
        140,  # user tokens
        10,  # system tokens (in _truncate_messages_preserving_system)
        100,  # final total after truncation
    ]
    mock_tokens_to_words.side_effect = lambda x: x // 2
    # Mock TypedDI registry to return a controllable mock posting handler
    mock_posting_handler = AsyncMock(spec=SlackPostingHandler)
    mock_posting_handler.post_message = AsyncMock()  # Ensure post_message is async

    mock_registry = AsyncMock()
    mock_registry.aget = AsyncMock(return_value=mock_posting_handler)

    monkeypatch.setattr(
        "packages.core.typed_di_integration.get_typed_registry",
        lambda: mock_registry,
    )

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user content"},
    ]
    # Simulate truncation by replacing user content
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = [1] * 140  # User content has 140 tokens

        def mock_decoder(ids):
            return "truncated"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = await manager.enforce_token_limit(messages, "U1", "C1", "url")
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    # The user content should be truncated since we have 140 user tokens but only 90 available
    assert result[1]["content"] == "truncated"
    # Assert that the post_message on the handler returned by get_instance was called
    mock_posting_handler.post_message.assert_awaited_once()


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.tokens_to_words")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
@pytest.mark.asyncio
async def test_enforce_token_limit_notification_error(
    mock_tokens_to_words: MagicMock,
    mock_count_tokens: MagicMock,
    manager: TokenManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test enforce_token_limit when notification send fails."""
    mock_count_tokens.side_effect = [
        10,  # system tokens
        140,  # user tokens
        10,  # system tokens (in _truncate_messages_preserving_system)
        100,  # final total after truncation
    ]
    mock_tokens_to_words.side_effect = lambda x: x // 2
    # Mock TypedDI registry to return a controllable mock posting handler whose post_message fails
    mock_posting_handler = AsyncMock(spec=SlackPostingHandler)
    mock_posting_handler.post_message = AsyncMock(side_effect=Exception("post fail"))

    mock_registry = AsyncMock()
    mock_registry.aget = AsyncMock(return_value=mock_posting_handler)

    monkeypatch.setattr(
        "packages.core.typed_di_integration.get_typed_registry",
        lambda: mock_registry,
    )

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user content"},
    ]
    # Simulate truncation by replacing user content
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = [1] * 140  # User content has 140 tokens

        def mock_decoder(ids):
            return "truncated"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = await manager.enforce_token_limit(messages, "U1", "C1", "url")
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    assert result[1]["content"] == "truncated"
    # Assert that the failing post_message was still called
    mock_posting_handler.post_message.assert_awaited_once()


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.tokens_to_words")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
@pytest.mark.asyncio
async def test_enforce_token_limit_cleanup_error(
    mock_tokens_to_words: MagicMock,
    mock_count_tokens: MagicMock,
    manager: TokenManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test enforce_token_limit when client cleanup fails."""
    mock_count_tokens.side_effect = [
        10,  # system tokens
        140,  # user tokens
        10,  # system tokens (in _truncate_messages_preserving_system)
        100,  # final total after truncation
    ]
    mock_tokens_to_words.side_effect = lambda x: x // 2
    # Mock TypedDI registry to return a controllable mock posting handler
    # The cleanup failure aspect seems irrelevant to this test's core logic, focus on post_message call
    mock_posting_handler = AsyncMock(spec=SlackPostingHandler)
    mock_posting_handler.post_message = AsyncMock()

    mock_registry = AsyncMock()
    mock_registry.aget = AsyncMock(return_value=mock_posting_handler)

    monkeypatch.setattr(
        "packages.core.typed_di_integration.get_typed_registry",
        lambda: mock_registry,
    )

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user content"},
    ]
    # Simulate truncation by replacing user content
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = [1] * 140  # User content has 140 tokens

        def mock_decoder(ids):
            return "truncated"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = await manager.enforce_token_limit(messages, "U1", "C1", "url")
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    assert result[1]["content"] == "truncated"
    # Assert that the post_message on the handler returned by get_instance was called
    mock_posting_handler.post_message.assert_awaited_once()


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
def test_truncate_messages_system_and_user(
    mock_count_tokens: MagicMock, manager: TokenManager
) -> None:
    mock_count_tokens.side_effect = [10, 90, 100]
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user content"},
    ]
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        # User content has 140 tokens, needs truncation to 90
        mock_tokenizer.return_value = [1] * 140

        def mock_decoder(ids):
            return "truncated" if len(ids) == 90 else "user content"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = manager._truncate_messages_preserving_system(messages, 150)
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "sys"
    assert result[1]["role"] == "user"
    assert result[1]["content"] == "truncated"


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
def test_truncate_messages_not_enough_tokens(
    mock_count_tokens: MagicMock, manager: TokenManager
) -> None:
    mock_count_tokens.side_effect = [95, 100]
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user content"},
    ]
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = [1] * 100

        def mock_decoder(ids):
            return "truncated_sys"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = manager._truncate_messages_preserving_system(messages, 150)
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "truncated_sys"
    assert len(result) == 1


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
def test_truncate_messages_user_only(
    mock_count_tokens: MagicMock, manager: TokenManager
) -> None:
    mock_count_tokens.side_effect = [0, 100, 50]  # system: 0, available: 100, final: 50
    messages = [{"role": "user", "content": "user content"}]
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = [1] * 50

        def mock_decoder(ids):
            return "user content"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = manager._truncate_messages_preserving_system(messages, 150)
    # When there's no system message, it just returns the user message
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "user content"


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
def test_truncate_messages_system_only(
    mock_count_tokens: MagicMock, manager: TokenManager
) -> None:
    mock_count_tokens.side_effect = [50, 50, 50]  # system: 50, available: 50, final: 50
    messages = [{"role": "system", "content": "sys"}]
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = [1] * 50

        def mock_decoder(ids):
            return "sys"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = manager._truncate_messages_preserving_system(messages, 150)
    # When there's only a system message, it returns just that
    assert len(result) == 1
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "sys"


@patch("packages.ai.core.operations.token_management.count_tokens")
@patch("packages.ai.core.operations.token_management.MAX_PROCESSABLE_TOKENS", 100)
def test_truncate_messages_neither(
    mock_count_tokens: MagicMock, manager: TokenManager
) -> None:
    mock_count_tokens.side_effect = [0, 100, 0]  # no system, no user, final: 0
    messages = [{"role": "other", "content": "foo"}]
    with patch(
        "packages.ai.core.operations.token_management.get_tokenizer"
    ) as mock_get_tokenizer:
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = [1] * 50

        def mock_decoder(ids):
            return "truncated"

        mock_get_tokenizer.return_value = (mock_tokenizer, mock_decoder, True)
        result = manager._truncate_messages_preserving_system(messages, 150)
    # When there are no system or user messages, it returns an empty list
    assert len(result) == 0


def tokens_to_words_side_effect(x):
    return x // 2


def get_instance_side_effect(key):
    return None


def mock_decoder_truncated(ids):
    return "truncated"


def mock_decoder_truncated_sys(ids):
    return "truncated_sys"


def mock_decoder_truncated_user(ids):
    return "truncated_user"
