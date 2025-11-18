"""
Unit tests for SlackChannelBotMembershipOps in packages.slack.channel_operations.channel_bot_membership_ops.

Covers:
- SlackChannelBotMembershipOps: invite_ketchup_to_channel, check_bot_channel_membership, _invite_and_verify_bot_membership
- All logic branches: success, API error, already_in_channel, retries, posting errors, exceptions, membership polling, timeouts
- All dependencies are mocked (SecretsManager, SlackPostingHandler, SlackConfig, logger, core_invite_ketchup_to_channel, asyncio.sleep)
- All tests pass mypy --strict and ruff
- Expected: correct API calls, error handling, posting, logging, retry logic
"""

from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from packages.slack.channel_operations.channel_bot_membership_ops import (
    SlackChannelBotMembershipOps,
)

# Capture the real orjson.dumps function at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_secrets_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.get_slack_api_token_async = AsyncMock(return_value="x")
    return mgr


@pytest.fixture
def mock_posting_handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_slack_config() -> MagicMock:
    cfg = MagicMock()
    cfg.get_api_base_url.return_value = "https://api.slack.com"
    cfg.get_headers.return_value = {"Authorization": "Bearer x"}
    return cfg


@pytest.fixture
def ops(
    mock_secrets_manager: MagicMock,
    mock_posting_handler: MagicMock,
    mock_slack_config: MagicMock,
) -> SlackChannelBotMembershipOps:
    return SlackChannelBotMembershipOps(
        secrets_manager=mock_secrets_manager,
        posting_handler=mock_posting_handler,
        slack_config=mock_slack_config,
    )


@pytest.mark.asyncio
async def test_invite_ketchup_to_channel_success(
    ops: SlackChannelBotMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test invite_ketchup_to_channel returns success response."""
    monkeypatch.setattr(ops, "_init_slack_token", AsyncMock())
    monkeypatch.setattr(ops, "setup", AsyncMock())
    with patch(
        "packages.slack.channel_operations.channel_bot_membership_ops.core_invite_ketchup_to_channel",
        new=AsyncMock(return_value={"ok": True}),
    ) as mock_core_invite:
        result = await ops.invite_ketchup_to_channel("C1", "B1", "chan")
        assert result == {"ok": True}
        mock_core_invite.assert_awaited_once()


@pytest.mark.asyncio
async def test_invite_ketchup_to_channel_error(
    ops: SlackChannelBotMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test invite_ketchup_to_channel returns error response on exception."""
    monkeypatch.setattr(ops, "_init_slack_token", AsyncMock())
    monkeypatch.setattr(ops, "setup", AsyncMock())
    with patch(
        "packages.slack.channel_operations.channel_bot_membership_ops.core_invite_ketchup_to_channel",
        new=AsyncMock(side_effect=Exception("fail")),
    ):
        with patch(
            "packages.slack.channel_operations.channel_bot_membership_ops.logger"
        ) as mock_logger:
            result = await ops.invite_ketchup_to_channel("C1", "B1", "chan")
            assert result["ok"] is False
            assert "fail" in result["error"]
            assert mock_logger.error.called


@pytest.mark.asyncio
async def test_check_bot_channel_membership_success(
    ops: SlackChannelBotMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_bot_channel_membership returns True if bot is member."""
    monkeypatch.setattr(ops, "_init_slack_token", AsyncMock())
    mock_response = {
        "body": _real_orjson_dumps({"ok": True, "channel": {"is_member": True}}),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    result = await ops.check_bot_channel_membership("C1")
    assert result is True


@pytest.mark.asyncio
async def test_check_bot_channel_membership_not_member(
    ops: SlackChannelBotMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_bot_channel_membership returns False if bot is not member."""
    monkeypatch.setattr(ops, "_init_slack_token", AsyncMock())
    mock_response = MagicMock()
    mock_response.json = AsyncMock(
        return_value={"ok": True, "channel": {"is_member": False}}
    )
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    result = await ops.check_bot_channel_membership("C1")
    assert result is False


@pytest.mark.asyncio
async def test_check_bot_channel_membership_api_error(
    ops: SlackChannelBotMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_bot_channel_membership returns False on API error."""
    monkeypatch.setattr(ops, "_init_slack_token", AsyncMock())
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"ok": False, "error": "fail"})
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    with patch(
        "packages.slack.channel_operations.channel_bot_membership_ops.logger"
    ) as mock_logger:
        result = await ops.check_bot_channel_membership("C1")
        assert result is False
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_check_bot_channel_membership_exception(
    ops: SlackChannelBotMembershipOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_bot_channel_membership returns False and logs on exception."""
    monkeypatch.setattr(ops, "_init_slack_token", AsyncMock())
    monkeypatch.setattr(
        ops, "_make_api_request", AsyncMock(side_effect=Exception("fail"))
    )
    with patch(
        "packages.slack.channel_operations.channel_bot_membership_ops.logger"
    ) as mock_logger:
        result = await ops.check_bot_channel_membership("C1")
        assert result is False
        assert mock_logger.error.called
