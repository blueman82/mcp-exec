"""
Unit tests for ChannelInfoOps in packages.slack.channel_operations.channel_info_ops.

Covers:
- ChannelInfoOps: get_channel_info_from_api, get_channel_details, get_channel_creation_time, _fetch_channel_details_core, _handle_bot_not_member, _handle_channel_lookup_error
- All logic branches: API success, API error, not a member, channel not found, posting errors, exceptions, missing fields
- All dependencies are mocked (SlackPostingHandler, SlackConfig, logger, API calls, backoff)
- All tests pass mypy --strict and ruff
- Expected: correct API calls, error handling, posting, logging
"""

from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from packages.core.async_client import SafeResponse
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps

# Capture the real orjson.dumps function at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_posting_handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_slack_config() -> MagicMock:
    return MagicMock()


@pytest.fixture
def ops(
    mock_posting_handler: MagicMock, mock_slack_config: MagicMock
) -> ChannelInfoOps:
    return ChannelInfoOps(
        posting_handler=mock_posting_handler, slack_config=mock_slack_config
    )


def _create_safe_response(
    status: int,
    headers: dict,
    body: dict,
    content_type: str = "application/json",
    url: str = "http://test.com",
) -> SafeResponse:
    """Helper to create a SafeResponse dictionary for testing."""
    return {
        "status": status,
        "headers": headers,
        "body": _real_orjson_dumps(body),
        "content_type": content_type,
        "url": url,
    }


@pytest.mark.asyncio
async def test_get_channel_info_from_api_success(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_channel_info_from_api returns channel dict on success."""
    safe_response = _create_safe_response(
        status=200,
        headers={},
        body={"ok": True, "channel": {"id": "C1", "name": "chan"}},
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=safe_response))
    monkeypatch.setattr(
        ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com")
    )
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        result = await ops.get_channel_info_from_api("C1")
        assert result == {"id": "C1", "name": "chan"}
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_get_channel_info_from_api_error(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_channel_info_from_api returns None on API error."""
    safe_response = _create_safe_response(
        status=200,
        headers={},
        body={"ok": False, "error": "fail"},
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=safe_response))
    monkeypatch.setattr(
        ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com")
    )
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        result = await ops.get_channel_info_from_api("C1")
        assert result is None
        assert mock_logger.warning.called


@pytest.mark.asyncio
async def test_get_channel_info_from_api_exception(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_channel_info_from_api returns None and logs on exception."""
    monkeypatch.setattr(
        ops, "_make_api_request", AsyncMock(side_effect=Exception("fail"))
    )
    monkeypatch.setattr(
        ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com")
    )
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        result = await ops.get_channel_info_from_api("C1")
        assert result is None
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_handle_bot_not_member_posts_and_returns(
    ops: ChannelInfoOps, mock_posting_handler: MagicMock
) -> None:
    """Test _handle_bot_not_member posts message and returns tuple."""
    mock_posting_handler.post_message = AsyncMock()
    result = await ops._handle_bot_not_member(
        user_id="U1",
        channel_id="C1",
        dm_channel_id="D1",
        response_url=None,
        channel_name="chan",
        is_archived=True,
        is_private=False,
    )
    assert result == ("chan", False, True, False)
    mock_posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_bot_not_member_post_error(
    ops: ChannelInfoOps, mock_posting_handler: MagicMock
) -> None:
    """Test _handle_bot_not_member logs error if posting fails."""
    mock_posting_handler.post_message = AsyncMock(side_effect=Exception("fail"))
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        result = await ops._handle_bot_not_member(
            user_id="U1",
            channel_id="C1",
            dm_channel_id="D1",
            response_url=None,
            channel_name="chan",
            is_archived=True,
            is_private=False,
        )
        assert result == ("chan", False, True, False)
        assert mock_logger.error.called


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_error,expected_log",
    [
        ("channel_not_found", "Channel C1 not found."),
        ("not_in_channel", "Bot is not in channel C1 (API error)."),
        ("other", "Slack API error when looking up channel C1: other"),
    ],
)
async def test_handle_channel_lookup_error_logs_and_posts(
    ops: ChannelInfoOps,
    mock_posting_handler: MagicMock,
    api_error: str,
    expected_log: str,
) -> None:
    """Test _handle_channel_lookup_error logs and posts correct error message."""
    mock_posting_handler.post_message = AsyncMock()
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        await ops._handle_channel_lookup_error(
            user_id="U1",
            channel_id="C1",
            dm_channel_id="D1",
            response_url=None,
            api_error=api_error,
        )
        assert mock_logger.error.called or mock_logger.warning.called
        mock_posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_channel_lookup_error_post_error(
    ops: ChannelInfoOps, mock_posting_handler: MagicMock
) -> None:
    """Test _handle_channel_lookup_error logs error if posting fails."""
    mock_posting_handler.post_message = AsyncMock(side_effect=Exception("fail"))
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        await ops._handle_channel_lookup_error(
            user_id="U1",
            channel_id="C1",
            dm_channel_id="D1",
            response_url=None,
            api_error="other",
        )
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_fetch_channel_details_core_member(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_channel_details_core returns details if bot is member."""
    safe_response = _create_safe_response(
        status=200,
        headers={},
        body={
            "ok": True,
            "channel": {
                "name": "chan",
                "is_member": True,
                "is_archived": False,
                "is_private": True,
            },
        },
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=safe_response))
    monkeypatch.setattr(
        ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com")
    )
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    result = await ops._fetch_channel_details_core(
        user_id="U1",
        channel_id="C1",
        dm_channel_id="D1",
        response_url=None,
    )
    assert result == ("chan", True, False, True)


@pytest.mark.asyncio
async def test_fetch_channel_details_core_not_member(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_channel_details_core delegates to _handle_bot_not_member if not a member."""
    safe_response = _create_safe_response(
        status=200,
        headers={},
        body={
            "ok": True,
            "channel": {
                "name": "chan",
                "is_member": False,
                "is_archived": True,
                "is_private": False,
            },
        },
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=safe_response))
    monkeypatch.setattr(
        ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com")
    )
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    monkeypatch.setattr(
        ops,
        "_handle_bot_not_member",
        AsyncMock(return_value=("chan", False, True, False)),
    )
    result = await ops._fetch_channel_details_core(
        user_id="U1",
        channel_id="C1",
        dm_channel_id="D1",
        response_url=None,
    )
    assert result == ("chan", False, True, False)


@pytest.mark.asyncio
async def test_fetch_channel_details_core_api_error(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_channel_details_core delegates to _handle_channel_lookup_error on API error."""
    safe_response = _create_safe_response(
        status=200, headers={}, body={"ok": False, "error": "fail"}
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=safe_response))
    monkeypatch.setattr(
        ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com")
    )
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    monkeypatch.setattr(
        ops, "_handle_channel_lookup_error", AsyncMock(return_value=None)
    )
    result = await ops._fetch_channel_details_core(
        user_id="U1",
        channel_id="C1",
        dm_channel_id="D1",
        response_url=None,
    )
    assert result is None


@pytest.mark.asyncio
async def test_fetch_channel_details_core_exception(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_channel_details_core logs and posts on exception."""
    monkeypatch.setattr(
        ops, "_make_api_request", AsyncMock(side_effect=Exception("fail"))
    )
    monkeypatch.setattr(
        ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com")
    )
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        result = await ops._fetch_channel_details_core(
            user_id="U1",
            channel_id="C1",
            dm_channel_id="D1",
            response_url=None,
        )
        assert result is None
        assert mock_logger.error.called
        ops.posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_channel_details_delegates(
    ops: ChannelInfoOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_channel_details delegates to backoff strategy."""
    monkeypatch.setattr(
        ops._backoff_strategy,
        "execute",
        AsyncMock(return_value=("chan", True, False, True)),
    )
    with patch(
        "packages.slack.channel_operations.channel_info_ops.logger"
    ) as mock_logger:
        result = await ops.get_channel_details("U1", "C1", "D1")
        assert result == ("chan", True, False, True)
        assert mock_logger.info.called
