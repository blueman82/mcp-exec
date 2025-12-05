"""
Unit tests for packages/slack/channel_events/processing/unarchive_processor.py

Covers:
- invite_and_verify_bot_after_unarchive
- All error and edge cases, including bot already member, invite errors, verification loop, and exceptions.

All dependencies are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.processing.unarchive_processor as unarchive_processor


@pytest.mark.asyncio
class TestInviteAndVerifyBotAfterUnarchive:
    async def test_bot_user_id_missing(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value=None)
        channel_restore_ops = MagicMock()
        channel_info_ops = MagicMock()
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C1", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is False

    async def test_bot_already_member(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_info_ops = MagicMock()
        channel_info_ops.get_channel_info_from_api = AsyncMock(return_value={"is_member": True})
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C2", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is True

    async def test_channel_info_check_exception(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_info_ops = MagicMock()
        channel_info_ops.get_channel_info_from_api = AsyncMock(side_effect=Exception("fail"))
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C3", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is False

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_invite_success_and_verification(self, mock_sleep):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(return_value={"ok": True})
        channel_info_ops = MagicMock()
        # Simulate not a member for first 2 checks, then member
        channel_info_ops.get_channel_info_from_api = AsyncMock(
            side_effect=[
                {"is_member": False},
                {"is_member": False},
                {"is_member": True},
            ]
        )
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C4", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is True
        assert channel_info_ops.get_channel_info_from_api.call_count == 3

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_invite_success_but_never_verified(self, mock_sleep):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(return_value={"ok": True})
        channel_info_ops = MagicMock()
        # Always not a member
        channel_info_ops.get_channel_info_from_api = AsyncMock(return_value={"is_member": False})
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C5", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is False
        assert channel_info_ops.get_channel_info_from_api.call_count == 6

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_invite_already_in_channel(self, mock_sleep):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(
            return_value={"error": "already_in_channel"}
        )
        channel_info_ops = MagicMock()
        channel_info_ops.get_channel_info_from_api = AsyncMock(side_effect=[{"is_member": True}])
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C6", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is True

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_invite_failed(self, mock_sleep):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(
            return_value={"ok": False, "error": "invite_failed"}
        )
        channel_info_ops = MagicMock()
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C7", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is False

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_invite_exception(self, mock_sleep):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(side_effect=Exception("fail"))
        channel_info_ops = MagicMock()
        result = await unarchive_processor.invite_and_verify_bot_after_unarchive(
            "C8", "chan", secrets_manager, channel_restore_ops, channel_info_ops
        )
        assert result is False
