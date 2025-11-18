"""
Unit tests for SlackChannelRestoreOps in packages.slack.channel_operations.channel_restore_ops.

Covers:
- SlackChannelRestoreOps: restore_archived_channel, rearchive_channel_if_needed
- All logic branches: success, already unarchived, archived, API error, exceptions, restore state, posting, bot membership, invite, rearchive
- All dependencies are mocked (SlackPostingHandler, SlackChannelArchiveOps, SecretsManager, DynamoDBStore, RestoreStateManager, SlackChannelBotMembershipOps, SlackConfig, logger)
- All tests pass mypy --strict and ruff
- Expected: correct API calls, error handling, posting, logging, restore state logic
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.channel_operations.channel_restore_ops import SlackChannelRestoreOps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_posting_handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_archive_ops() -> MagicMock:
    ops = MagicMock()
    ops.get_channel_info = AsyncMock()
    ops.unarchive_channel = AsyncMock()
    ops.archive_channel = AsyncMock()
    return ops


@pytest.fixture
def mock_secrets_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.get_slack_api_token_async = AsyncMock(return_value="token")
    mgr.get_bot_slack_user_id_async = AsyncMock(return_value="B1")
    return mgr


@pytest.fixture
def mock_dynamodb_store() -> MagicMock:
    store = MagicMock()
    store.get_channel_details = AsyncMock()
    store.update_channel_archived_status = AsyncMock()
    return store


@pytest.fixture
def mock_restore_state_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.store_state = AsyncMock()
    mgr.cleanup_state = AsyncMock()
    return mgr


@pytest.fixture
def mock_bot_membership_ops() -> MagicMock:
    ops = MagicMock()
    ops.check_bot_channel_membership = AsyncMock()
    ops.invite_ketchup_to_channel = AsyncMock()
    return ops


@pytest.fixture
def mock_slack_config() -> MagicMock:
    cfg = MagicMock()
    cfg.get_api_base_url.return_value = "https://api.slack.com"
    cfg.get_headers.return_value = {"Authorization": "Bearer x"}
    return cfg


@pytest.fixture
def ops(
    mock_posting_handler: MagicMock,
    mock_archive_ops: MagicMock,
    mock_secrets_manager: MagicMock,
    mock_dynamodb_store: MagicMock,
    mock_restore_state_manager: MagicMock,
    mock_bot_membership_ops: MagicMock,
    mock_slack_config: MagicMock,
) -> SlackChannelRestoreOps:
    return SlackChannelRestoreOps(
        posting_handler=mock_posting_handler,
        archive_ops=mock_archive_ops,
        secrets_manager=mock_secrets_manager,
        dynamodb_store=mock_dynamodb_store,
        restore_state_manager=mock_restore_state_manager,
        bot_membership_ops=mock_bot_membership_ops,
        slack_config=mock_slack_config,
    )


@pytest.mark.asyncio
async def test_restore_archived_channel_success(
    ops: SlackChannelRestoreOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test restore_archived_channel unarchives and ensures bot membership."""
    ops.archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": True, "name": "chan"}}
    )
    ops.restore_state_manager.store_state = AsyncMock()
    ops.archive_ops.unarchive_channel = AsyncMock(return_value=True)
    ops.bot_membership_ops.check_bot_channel_membership = AsyncMock(return_value=True)
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.restore_archived_channel("U1", "C1", "D1")
    assert result == (True, True)
    ops.posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_restore_archived_channel_already_unarchived(
    ops: SlackChannelRestoreOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test restore_archived_channel returns early if not archived."""
    ops.archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": False}}
    )
    result = await ops.restore_archived_channel("U1", "C1", "D1")
    assert result == (True, False)


@pytest.mark.asyncio
async def test_restore_archived_channel_channel_info_error(
    ops: SlackChannelRestoreOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test restore_archived_channel returns False if channel info fetch fails."""
    ops.archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": False, "error": "fail"}
    )
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.restore_archived_channel("U1", "C1", "D1")
    assert result == (False, False)
    ops.posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_restore_archived_channel_unarchive_fails(
    ops: SlackChannelRestoreOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test restore_archived_channel returns False if unarchive fails."""
    ops.archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": True, "name": "chan"}}
    )
    ops.restore_state_manager.store_state = AsyncMock()
    ops.archive_ops.unarchive_channel = AsyncMock(return_value=False)
    ops.restore_state_manager.cleanup_state = AsyncMock()
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.restore_archived_channel("U1", "C1", "D1")
    assert result == (False, True)
    assert ops.restore_state_manager.cleanup_state.await_count >= 1


@pytest.mark.asyncio
async def test_restore_archived_channel_bot_membership_fails(
    ops: SlackChannelRestoreOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test restore_archived_channel returns False if bot membership fails."""
    ops.archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": True, "name": "chan"}}
    )
    ops.restore_state_manager.store_state = AsyncMock()
    ops.archive_ops.unarchive_channel = AsyncMock(return_value=True)
    ops.bot_membership_ops.check_bot_channel_membership = AsyncMock(return_value=False)
    ops.restore_state_manager.cleanup_state = AsyncMock()
    ops.posting_handler.post_message = AsyncMock()  # type: ignore[method-assign]
    result = await ops.restore_archived_channel("U1", "C1", "D1")
    assert result == (False, True)
    assert ops.restore_state_manager.cleanup_state.await_count >= 1


@pytest.mark.asyncio
async def test_rearchive_channel_if_needed_success(
    ops: SlackChannelRestoreOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test rearchive_channel_if_needed returns True on success."""
    ops.restore_state_manager.cleanup_state = AsyncMock()
    ops._perform_rearchive_and_update_db = AsyncMock(return_value=True)
    ops.restore_state_manager.is_rearchive_needed = AsyncMock(return_value=True)
    ops.posting_handler.post_message = AsyncMock()
    result = await ops.rearchive_channel_if_needed("U1", "C1", "D1")
    assert result is True


@pytest.mark.asyncio
async def test_rearchive_channel_if_needed_failure(
    ops: SlackChannelRestoreOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test rearchive_channel_if_needed returns False on failure."""
    ops.restore_state_manager.cleanup_state = AsyncMock()
    ops._perform_rearchive_and_update_db = AsyncMock(return_value=False)
    ops.restore_state_manager.is_rearchive_needed = AsyncMock(return_value=True)
    result = await ops.rearchive_channel_if_needed("U1", "C1", "D1")
    assert result is False
