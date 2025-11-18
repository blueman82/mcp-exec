"""
Unit tests for ApiExecutor in packages.ai.core.operations.api_interaction.

Covers:
- Initialization with mocked dependencies
- build_openai_payload: all command types (default, long, status, report), edge cases
- execute_request: normal, error in API call, re-archive path, no re-archive, token/cost tracking, metadata block
- All dependencies (api_request_func, TokenTracker, SlackChannelArchiveOps) are mocked
- All tests pass mypy --strict and ruff
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.ai.core.operations.api_interaction import ApiExecutor

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_token_tracker() -> MagicMock:
    tracker = MagicMock()
    tracker.calculate_cost.return_value = {"Total Cost": 1.23}
    return tracker


@pytest.fixture
def mock_channel_archive_ops() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_api_request_func() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def executor(
    mock_api_request_func: AsyncMock,
    mock_token_tracker: MagicMock,
    mock_channel_archive_ops: MagicMock,
) -> ApiExecutor:
    return ApiExecutor(
        api_request_func=mock_api_request_func,
        endpoint="https://endpoint",
        api_key="key",
        token_tracker=mock_token_tracker,
        channel_archive_ops=mock_channel_archive_ops,
    )


def test_build_openai_payload_default(executor: ApiExecutor) -> None:
    """Test build_openai_payload returns correct payload for default command."""
    messages = [{"role": "user", "content": "foo"}]
    payload = executor.build_openai_payload(messages, "short")
    assert payload["max_tokens"] == 1024
    assert payload["messages"] == messages
    assert payload["temperature"] == 0.1
    assert payload["top_p"] == 0.9


def test_build_openai_payload_long_status_report(executor: ApiExecutor) -> None:
    """Test build_openai_payload returns double tokens for long/status/report commands."""
    for cmd in ["long", "status", "report"]:
        payload = executor.build_openai_payload(
            [{"role": "user", "content": "foo"}], cmd
        )
        assert payload["max_tokens"] == 2048


def test_build_openai_payload_none_command(executor: ApiExecutor) -> None:
    """Test build_openai_payload handles None as command."""
    payload = executor.build_openai_payload([{"role": "user", "content": "foo"}], None)
    assert payload["max_tokens"] == 1024


def test_build_openai_payload_with_normalized_prefs(executor: ApiExecutor) -> None:
    """Test build_openai_payload respects normalized preferences."""
    messages = [{"role": "user", "content": "foo"}]
    normalized_prefs = {"temperature": 0.0, "max_tokens": 512, "top_p": 0.95}
    payload = executor.build_openai_payload(messages, "short", normalized_prefs)
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 512
    assert payload["top_p"] == 0.95
    assert payload["messages"] == messages


def test_build_openai_payload_partial_prefs(executor: ApiExecutor) -> None:
    """Test build_openai_payload with partial preferences uses defaults for missing values."""
    messages = [{"role": "user", "content": "foo"}]
    normalized_prefs = {"temperature": 0.3}  # Only temperature specified
    payload = executor.build_openai_payload(messages, "status", normalized_prefs)
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 2048  # Should still get status command default
    assert payload["top_p"] == 0.9  # Should use default


@pytest.mark.asyncio
async def test_execute_request_normal(
    executor: ApiExecutor,
    mock_api_request_func: AsyncMock,
    mock_token_tracker: MagicMock,
) -> None:
    """Test execute_request processes response, tracks tokens, and returns metadata."""
    mock_api_request_func.return_value = {
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "choices": [{"message": {"content": "result"}}],
    }
    payload = {"model": "gpt"}
    channel_info = {"originally_archived": False}
    result = await executor.execute_request(payload, channel_info, "U1", "C1")
    assert result["usage"]["total_tokens"] == 30
    assert "metadata" in result
    assert result["metadata"]["input_tokens"] == 10
    assert result["metadata"]["output_tokens"] == 20
    assert result["metadata"]["model_used"] == "gpt"
    mock_token_tracker.add_usage.assert_called_with(10, 20)
    mock_token_tracker.calculate_cost.assert_called_with(10, 20)


@pytest.mark.asyncio
async def test_execute_request_rearchive(
    executor: ApiExecutor,
    mock_api_request_func: AsyncMock,
    mock_channel_archive_ops: MagicMock,
) -> None:
    """Test execute_request triggers re-archive if originally_archived is True."""
    mock_api_request_func.return_value = {
        "usage": {},
        "choices": [{"message": {"content": "result"}}],
    }
    mock_channel_archive_ops.archive_channel = AsyncMock()
    channel_info = {"originally_archived": True, "target_channel": "T1"}
    await executor.execute_request({}, channel_info, "U1", "C1")
    mock_channel_archive_ops.archive_channel.assert_awaited_once_with(
        user_id="U1", channel_id="T1", incoming_channel="C1"
    )


@pytest.mark.asyncio
async def test_execute_request_rearchive_error(
    executor: ApiExecutor,
    mock_api_request_func: AsyncMock,
    mock_channel_archive_ops: MagicMock,
) -> None:
    """Test execute_request logs error if re-archive fails but continues."""
    mock_api_request_func.return_value = {
        "usage": {},
        "choices": [{"message": {"content": "result"}}],
    }
    mock_channel_archive_ops.archive_channel = AsyncMock(side_effect=Exception("fail"))
    channel_info = {"originally_archived": True, "target_channel": "T1"}
    await executor.execute_request({}, channel_info, "U1", "C1")
    mock_channel_archive_ops.archive_channel.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_request_error(
    executor: ApiExecutor, mock_api_request_func: AsyncMock
) -> None:
    """Test execute_request logs and raises error from API call."""
    mock_api_request_func.side_effect = Exception("fail")
    with pytest.raises(Exception):
        await executor.execute_request({}, None, "U1", "C1")
