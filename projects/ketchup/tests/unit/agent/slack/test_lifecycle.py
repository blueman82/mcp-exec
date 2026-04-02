"""Tests for agent lifecycle handlers."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.slack.lifecycle import handle_channel_archive_agent_cleanup


class TestChannelArchiveCleanup:
    @pytest.mark.asyncio
    async def test_wipes_conversation_data(self):
        conv_store = AsyncMock()

        await handle_channel_archive_agent_cleanup("C123", conv_store)

        conv_store.wipe_channel_data.assert_called_once_with("C123")

    @pytest.mark.asyncio
    async def test_continues_on_dynamo_error(self):
        conv_store = AsyncMock()
        conv_store.wipe_channel_data.side_effect = Exception("DynamoDB error")

        # Should not raise
        await handle_channel_archive_agent_cleanup("C123", conv_store)
