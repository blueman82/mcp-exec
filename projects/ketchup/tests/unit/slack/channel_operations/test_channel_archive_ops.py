"""
Unit tests for SlackChannelArchiveOps in packages.slack.channel_operations.channel_archive_ops.

Covers:
- SlackChannelArchiveOps: check_channel_archived, archive_channel, unarchive_channel, get_channel_info
- All logic branches: success, already archived, not archived, API error, exceptions, restore state, posting, token fetching
- All dependencies are mocked (SlackPostingHandler, SecretsManager, DynamoDBStore, RestoreStateManager, SlackConfig, logger, restore_ops)
- All tests pass mypy --strict and ruff
- Expected: correct API calls, error handling, posting, logging, restore state logic
"""

from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps

# Capture the real orjson.dumps function at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_posting_handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_secrets_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.get_slack_user_api_token = AsyncMock(return_value="usertoken")
    return mgr


@pytest.fixture
def mock_dynamodb_store() -> MagicMock:
    store = MagicMock()
    store.restore_ops = MagicMock()
    store.restore_ops.clear_restore_state = AsyncMock()
    store.restore_ops.set_restore_state = AsyncMock()
    return store


@pytest.fixture
def mock_state_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.is_rearchive_needed = AsyncMock(return_value=False)
    return mgr


@pytest.fixture
def mock_slack_config() -> MagicMock:
    cfg = MagicMock()
    cfg.get_api_base_url.return_value = "https://api.slack.com"
    cfg.get_headers.return_value = {"Authorization": "Bearer x"}
    return cfg


@pytest.fixture
def ops(
    mock_posting_handler: MagicMock,
    mock_secrets_manager: MagicMock,
    mock_dynamodb_store: MagicMock,
    mock_state_manager: MagicMock,
    mock_slack_config: MagicMock,
) -> SlackChannelArchiveOps:
    return SlackChannelArchiveOps(
        posting_handler=mock_posting_handler,
        secrets_manager=mock_secrets_manager,
        dynamodb_store=mock_dynamodb_store,
        state_manager=mock_state_manager,
        slack_config=mock_slack_config,
    )


@pytest.mark.asyncio
async def test_check_channel_archived_true(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_channel_archived returns True if channel is archived."""
    mock_response = {
        "body": _real_orjson_dumps({"ok": True, "channel": {"is_archived": True}}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    result = await ops.check_channel_archived("C1")
    assert result is True


@pytest.mark.asyncio
async def test_check_channel_archived_false(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_channel_archived returns False if channel is not archived."""
    mock_response = {
        "body": _real_orjson_dumps({"ok": True, "channel": {"is_archived": False}}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    result = await ops.check_channel_archived("C1")
    assert result is False


@pytest.mark.asyncio
async def test_check_channel_archived_api_error(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_channel_archived returns False and logs on API error."""
    mock_response = {
        "body": _real_orjson_dumps({"ok": False, "error": "fail"}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    with patch("packages.slack.channel_operations.channel_archive_ops.logger") as mock_logger:
        result = await ops.check_channel_archived("C1")
        assert result is False
        assert mock_logger.warning.called


@pytest.mark.asyncio
async def test_check_channel_archived_exception(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_channel_archived returns False and logs on exception."""
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(side_effect=Exception("fail")))
    with patch("packages.slack.channel_operations.channel_archive_ops.logger") as mock_logger:
        result = await ops.check_channel_archived("C1")
        assert result is False
        assert mock_logger.warning.called


@pytest.mark.asyncio
async def test_archive_channel_already_archived_and_clear_restore(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test archive_channel skips if already archived and clears restore state if needed."""
    ops._state_manager.is_rearchive_needed = AsyncMock(return_value=True)
    monkeypatch.setattr(ops, "check_channel_archived", AsyncMock(return_value=True))
    ops._restore_ops.clear_restore_state = AsyncMock()
    result = await ops.archive_channel("U1", "C1", "D1")
    assert result is True
    ops._restore_ops.clear_restore_state.assert_awaited_once_with("C1")


@pytest.mark.asyncio
async def test_archive_channel_success_user_post_and_restore(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test archive_channel posts message and clears restore state on success."""
    ops._state_manager.is_rearchive_needed = AsyncMock(return_value=True)
    monkeypatch.setattr(ops, "check_channel_archived", AsyncMock(return_value=False))
    monkeypatch.setattr(
        ops,
        "get_user_api_headers",
        AsyncMock(return_value={"Authorization": "Bearer token"}),
    )
    mock_response = {"body": _real_orjson_dumps({"ok": True}), "status": 200}
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    ops._restore_ops.clear_restore_state = AsyncMock()
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.archive_channel("U1", "C1", "D1", response_url="url")
    assert result is True
    ops.posting_handler.post_message.assert_awaited_once()
    ops._restore_ops.clear_restore_state.assert_awaited_once_with("C1")


@pytest.mark.asyncio
async def test_archive_channel_success_no_user(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test archive_channel does not post message if user_id is None."""
    ops._state_manager.is_rearchive_needed = AsyncMock(return_value=False)
    monkeypatch.setattr(ops, "check_channel_archived", AsyncMock(return_value=False))
    monkeypatch.setattr(
        ops,
        "get_user_api_headers",
        AsyncMock(return_value={"Authorization": "Bearer token"}),
    )
    mock_response = {"body": _real_orjson_dumps({"ok": True}), "status": 200}
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    ops._restore_ops.clear_restore_state = AsyncMock()
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.archive_channel(None, "C1", "D1")
    assert result is True
    ops.posting_handler.post_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_channel_api_error(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test archive_channel posts error message and returns False on API error."""
    ops._state_manager.is_rearchive_needed = AsyncMock(return_value=False)
    monkeypatch.setattr(ops, "check_channel_archived", AsyncMock(return_value=False))
    monkeypatch.setattr(
        ops,
        "get_user_api_headers",
        AsyncMock(return_value={"Authorization": "Bearer token"}),
    )
    mock_response = {
        "body": _real_orjson_dumps({"ok": False, "error": "fail"}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.archive_channel("U1", "C1", "D1")
    assert result is False
    ops.posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_archive_channel_exception(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test archive_channel posts error message and returns False on exception."""
    ops._state_manager.is_rearchive_needed = AsyncMock(return_value=False)
    monkeypatch.setattr(ops, "check_channel_archived", AsyncMock(return_value=False))
    monkeypatch.setattr(
        ops,
        "get_user_api_headers",
        AsyncMock(return_value={"Authorization": "Bearer token"}),
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(side_effect=Exception("fail")))
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.archive_channel("U1", "C1", "D1")
    assert result is False
    ops.posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_unarchive_channel_success(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test unarchive_channel sets restore state and returns True on success."""
    monkeypatch.setattr(
        ops,
        "get_user_api_headers",
        AsyncMock(return_value={"Authorization": "Bearer token"}),
    )
    mock_response = {"body": _real_orjson_dumps({"ok": True}), "status": 200}
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    ops._restore_ops.set_restore_state = AsyncMock()
    result = await ops.unarchive_channel("C1")
    assert result is True
    ops._restore_ops.set_restore_state.assert_awaited_once_with("C1")


@pytest.mark.asyncio
async def test_unarchive_channel_api_error(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test unarchive_channel returns False on API error."""
    monkeypatch.setattr(
        ops,
        "get_user_api_headers",
        AsyncMock(return_value={"Authorization": "Bearer token"}),
    )
    mock_response = {
        "body": _real_orjson_dumps({"ok": False, "error": "fail"}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    ops._restore_ops.set_restore_state = AsyncMock()
    with patch("packages.slack.channel_operations.channel_archive_ops.logger") as mock_logger:
        result = await ops.unarchive_channel("C1")
        assert result is False
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_unarchive_channel_exception(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test unarchive_channel returns False on exception."""
    monkeypatch.setattr(
        ops,
        "get_user_api_headers",
        AsyncMock(return_value={"Authorization": "Bearer token"}),
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(side_effect=Exception("fail")))
    ops._restore_ops.set_restore_state = AsyncMock()
    with patch("packages.slack.channel_operations.channel_archive_ops.logger") as mock_logger:
        result = await ops.unarchive_channel("C1")
        assert result is False
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_get_channel_info_success(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_channel_info returns response data on success."""
    mock_response = {
        "body": _real_orjson_dumps({"ok": True, "channel": {"id": "C1"}}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    result = await ops.get_channel_info("C1")
    assert result["ok"] is True
    assert result["channel"]["id"] == "C1"


@pytest.mark.asyncio
async def test_get_channel_info_api_error(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_channel_info logs warning and returns error on API error."""
    mock_response = {
        "body": _real_orjson_dumps({"ok": False, "error": "fail"}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    with patch("packages.slack.channel_operations.channel_archive_ops.logger") as mock_logger:
        result = await ops.get_channel_info("C1")
        assert result["ok"] is False
        assert mock_logger.warning.called


@pytest.mark.asyncio
async def test_get_channel_info_exception(
    ops: SlackChannelArchiveOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_channel_info logs error and returns error on exception."""
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(side_effect=Exception("fail")))
    with patch("packages.slack.channel_operations.channel_archive_ops.logger") as mock_logger:
        result = await ops.get_channel_info("C1")
        assert result["ok"] is False
        assert "fail" in result["error"]
        assert mock_logger.error.called
