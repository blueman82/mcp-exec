"""
Unit tests for structured JSON output in ApiExecutor.

Covers:
- build_openai_payload with JSON mode enabled (response_format parameter)
- build_openai_payload with JSON mode disabled (no response_format parameter)
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.ai.core.operations.api_interaction import ApiExecutor

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_token_tracker() -> MagicMock:
    """Create mock TokenTracker."""
    tracker = MagicMock()
    tracker.calculate_cost.return_value = {"Total Cost": 1.23}
    return tracker


@pytest.fixture
def mock_channel_archive_ops() -> MagicMock:
    """Create mock SlackChannelArchiveOps."""
    return MagicMock()


@pytest.fixture
def mock_api_request_func() -> AsyncMock:
    """Create mock API request function."""
    return AsyncMock()


@pytest.fixture
def executor(
    mock_api_request_func: AsyncMock,
    mock_token_tracker: MagicMock,
    mock_channel_archive_ops: MagicMock,
) -> ApiExecutor:
    """Create ApiExecutor with mocked dependencies."""
    return ApiExecutor(
        api_request_func=mock_api_request_func,
        endpoint="https://endpoint",
        api_key="key",
        token_tracker=mock_token_tracker,
        channel_archive_ops=mock_channel_archive_ops,
    )


@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
def test_build_payload_with_json_mode_enabled(executor: ApiExecutor) -> None:
    """Test build_openai_payload includes response_format when JSON mode enabled."""
    messages = [{"role": "user", "content": "test"}]
    payload = executor.build_openai_payload(messages, "status")
    assert "response_format" in payload
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"] == messages
    assert payload["max_tokens"] == 2048
    assert payload["reasoning_effort"] == "low"
    assert "top_p" not in payload


@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "false"})
def test_build_payload_with_json_mode_disabled(executor: ApiExecutor) -> None:
    """Test build_openai_payload does NOT include response_format when JSON mode disabled."""
    messages = [{"role": "user", "content": "test"}]
    payload = executor.build_openai_payload(messages, "status")
    assert "response_format" not in payload
    assert payload["messages"] == messages
    assert payload["max_tokens"] == 2048
    assert payload["reasoning_effort"] == "low"
    assert "top_p" not in payload


@patch.dict(os.environ, {}, clear=True)
def test_build_payload_json_mode_default(executor: ApiExecutor) -> None:
    """Test build_openai_payload defaults to no response_format when env var not set."""
    # Remove the env var if it exists
    os.environ.pop("KETCHUP_STRUCTURED_JSON_OUTPUT", None)
    messages = [{"role": "user", "content": "test"}]
    payload = executor.build_openai_payload(messages, "query")
    assert "response_format" not in payload
    assert payload["messages"] == messages


@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
def test_build_payload_json_mode_with_custom_prefs(executor: ApiExecutor) -> None:
    """Test build_openai_payload with JSON mode and custom preferences."""
    messages = [{"role": "user", "content": "test"}]
    normalized_prefs = {"temperature": 0.5, "max_tokens": 1500, "top_p": 0.95}
    payload = executor.build_openai_payload(messages, "report", normalized_prefs)
    assert "response_format" in payload
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0.5
    assert payload["max_tokens"] == 1500
    assert payload["top_p"] == 0.95


@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "TRUE"})
def test_build_payload_json_mode_uppercase(executor: ApiExecutor) -> None:
    """Test build_openai_payload with uppercase TRUE env var."""
    messages = [{"role": "user", "content": "test"}]
    payload = executor.build_openai_payload(messages, "status")
    assert "response_format" in payload
    assert payload["response_format"] == {"type": "json_object"}
