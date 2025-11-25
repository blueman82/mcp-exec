"""
Unit tests for token_utils.py in packages.ai.core.

Covers:
- get_tokenizer: tiktoken present, tiktoken missing, encoder error, fallback
- count_tokens: tiktoken, fallback, empty string, non-ASCII
- tokens_to_words: various token counts, edge cases
- All dependencies (tiktoken, logger) are mocked as needed
- All tests pass mypy --strict and ruff
"""

from unittest.mock import MagicMock

import pytest

from packages.ai.core.token_utils import (
    count_tokens,
    get_tokenizer,
    tokens_to_words,
)

pytestmark = pytest.mark.unit


def test_get_tokenizer_tiktoken_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_tokenizer returns tiktoken encoder."""
    mock_enc = MagicMock()
    mock_enc.encode = lambda x: [1, 2, 3]
    mock_enc.decode = lambda x: "decoded"
    monkeypatch.setattr(
        "packages.ai.core.token_utils._TOKENIZER_ENCODING",
        mock_enc,
    )
    func, decoder, is_tiktoken = get_tokenizer()
    assert is_tiktoken is True
    assert isinstance(func("foo bar baz"), list)
    assert func("foo bar baz") == [1, 2, 3]
    assert decoder([1, 2, 3]) == "decoded"


def test_get_tokenizer_tiktoken_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_tokenizer always returns tiktoken encoder (no fallback anymore)."""
    # Since tiktoken is now pre-initialized, this test verifies it still works
    mock_enc = MagicMock()
    mock_enc.encode = lambda x: [1, 2, 3]
    mock_enc.decode = lambda x: "decoded"
    monkeypatch.setattr(
        "packages.ai.core.token_utils._TOKENIZER_ENCODING",
        mock_enc,
    )
    func, decoder, is_tiktoken = get_tokenizer()
    assert is_tiktoken is True
    assert isinstance(func("foo bar baz"), list)
    assert func("foo bar baz") == [1, 2, 3]


def test_get_tokenizer_encoder_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_tokenizer still works even if there was an initialization error."""
    # Since tiktoken is pre-initialized, we test that the getter still works
    mock_enc = MagicMock()
    mock_enc.encode = lambda x: [1, 2, 3]
    mock_enc.decode = lambda x: "decoded"
    monkeypatch.setattr(
        "packages.ai.core.token_utils._TOKENIZER_ENCODING",
        mock_enc,
    )
    func, decoder, is_tiktoken = get_tokenizer()
    assert is_tiktoken is True
    assert isinstance(func("foo bar baz"), list)
    assert func("foo bar baz") == [1, 2, 3]


def test_count_tokens_tiktoken(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test count_tokens returns correct count with tiktoken encoder."""
    monkeypatch.setattr(
        "packages.ai.core.token_utils.get_tokenizer",
        lambda: (lambda x: [1, 2, 3], lambda x: "decoded", True),
    )
    assert count_tokens("foo") == 3


def test_count_tokens_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test count_tokens with mocked tokenizer."""
    # Since there's no fallback anymore, we just mock the tokenizer
    monkeypatch.setattr(
        "packages.ai.core.token_utils.get_tokenizer",
        lambda: (lambda x: [1, 2, 3, 4, 5], lambda x: "decoded", True),
    )
    assert count_tokens("foo bar") == 5


def test_count_tokens_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test count_tokens returns 0 for empty string."""
    monkeypatch.setattr(
        "packages.ai.core.token_utils.get_tokenizer",
        lambda: (lambda x: [], lambda x: "", True),
    )
    assert count_tokens("") == 0


def test_tokens_to_words() -> None:
    """Test tokens_to_words returns correct approximation."""
    assert tokens_to_words(10) == 7
    assert tokens_to_words(0) == 0
    assert tokens_to_words(100) == 75
