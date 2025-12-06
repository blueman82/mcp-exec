"""
Unit tests for packages/slack/channel_events/eligibility/ineligible_handler.py

Covers:
- handle_ineligible_bot_join
- All error and edge cases, including age-based ineligibility, temporary unarchive, DB errors, and standard handling.

All dependencies are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.eligibility.ineligible_handler as ineligible_handler


@pytest.mark.asyncio
class TestHandleIneligibleBotJoin:
    @patch(
        "packages.slack.channel_events.eligibility.ineligible_handler.ELIGIBILITY_REASON_PREFIX_AGE",
        "AGE:",
    )
    async def test_age_reason_temporary_unarchive(self):
        channel_eligibility_service = MagicMock()
        channel_eligibility_service.handle_ineligible_channel = AsyncMock()
        dynamodb_store = MagicMock()
        dynamodb_store.check_if_temporary_unarchive = AsyncMock(return_value=True)
        await ineligible_handler.handle_ineligible_bot_join(
            channel_id="C1",
            inviter_id="U1",
            reason="AGE: too old",
            channel_eligibility_service=channel_eligibility_service,
            dynamodb_store=dynamodb_store,
        )
        channel_eligibility_service.handle_ineligible_channel.assert_not_awaited()

    @patch(
        "packages.slack.channel_events.eligibility.ineligible_handler.ELIGIBILITY_REASON_PREFIX_AGE",
        "AGE:",
    )
    async def test_age_reason_not_temporary_unarchive(self):
        channel_eligibility_service = MagicMock()
        channel_eligibility_service.handle_ineligible_channel = AsyncMock()
        dynamodb_store = MagicMock()
        dynamodb_store.check_if_temporary_unarchive = AsyncMock(return_value=False)
        await ineligible_handler.handle_ineligible_bot_join(
            channel_id="C2",
            inviter_id="U2",
            reason="AGE: too old",
            channel_eligibility_service=channel_eligibility_service,
            dynamodb_store=dynamodb_store,
        )
        channel_eligibility_service.handle_ineligible_channel.assert_awaited_once_with(
            channel_id="C2", inviter_id="U2", reason="AGE: too old"
        )

    @patch(
        "packages.slack.channel_events.eligibility.ineligible_handler.ELIGIBILITY_REASON_PREFIX_AGE",
        "AGE:",
    )
    async def test_age_reason_db_error(self):
        channel_eligibility_service = MagicMock()
        channel_eligibility_service.handle_ineligible_channel = AsyncMock()
        dynamodb_store = MagicMock()
        dynamodb_store.check_if_temporary_unarchive = AsyncMock(side_effect=Exception("fail"))
        await ineligible_handler.handle_ineligible_bot_join(
            channel_id="C3",
            inviter_id="U3",
            reason="AGE: too old",
            channel_eligibility_service=channel_eligibility_service,
            dynamodb_store=dynamodb_store,
        )
        channel_eligibility_service.handle_ineligible_channel.assert_awaited_once_with(
            channel_id="C3", inviter_id="U3", reason="AGE: too old"
        )

    async def test_non_age_reason(self):
        channel_eligibility_service = MagicMock()
        channel_eligibility_service.handle_ineligible_channel = AsyncMock()
        dynamodb_store = MagicMock()
        await ineligible_handler.handle_ineligible_bot_join(
            channel_id="C4",
            inviter_id=None,
            reason="OTHER: not allowed",
            channel_eligibility_service=channel_eligibility_service,
            dynamodb_store=dynamodb_store,
        )
        channel_eligibility_service.handle_ineligible_channel.assert_awaited_once_with(
            channel_id="C4", inviter_id=None, reason="OTHER: not allowed"
        )
