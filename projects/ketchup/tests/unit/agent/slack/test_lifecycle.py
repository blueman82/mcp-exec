"""Tests for agent lifecycle handlers."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.slack.lifecycle import handle_channel_archive_agent_cleanup


class TestChannelArchiveCleanup:
    @pytest.mark.asyncio
    async def test_wipes_both_stores(self):
        conv_store = AsyncMock()
        vec_store = AsyncMock()

        await handle_channel_archive_agent_cleanup("C123", conv_store, vec_store)

        conv_store.wipe_channel_data.assert_called_once_with("C123")
        vec_store.delete_by_channel.assert_called_once_with("C123")

    @pytest.mark.asyncio
    async def test_continues_on_dynamo_error(self):
        conv_store = AsyncMock()
        conv_store.wipe_channel_data.side_effect = Exception("DynamoDB error")
        vec_store = AsyncMock()

        # Should not raise
        await handle_channel_archive_agent_cleanup("C123", conv_store, vec_store)

        # Vector store should still be called
        vec_store.delete_by_channel.assert_called_once_with("C123")

    @pytest.mark.asyncio
    async def test_continues_on_chromadb_error(self):
        conv_store = AsyncMock()
        vec_store = AsyncMock()
        vec_store.delete_by_channel.side_effect = Exception("ChromaDB error")

        # Should not raise
        await handle_channel_archive_agent_cleanup("C123", conv_store, vec_store)
        conv_store.wipe_channel_data.assert_called_once_with("C123")
