"""Tests for ConversationStore."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.conversation.models import ConversationTurn
from packages.agent.conversation.store import (
    ConversationStore,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.fixture
def store(mock_client):
    return ConversationStore(dynamodb_client=mock_client)


class TestStoreTurn:
    @pytest.mark.asyncio
    async def test_store_user_turn(self, store, mock_client):
        turn = ConversationTurn(
            channel_id="C123",
            thread_ts="1234.5678",
            timestamp="1710000000000",
            role="user",
            content="What happened yesterday?",
            user_id="U456",
        )
        await store.store_turn(turn)

        mock_client.put_item.assert_called_once()
        call_kwargs = mock_client.put_item.call_args[1]
        item = call_kwargs["item"]
        assert item["PK"]["S"] == "AGENT_CONVERSATION#C123"
        assert item["SK"]["S"] == "TURN#1710000000000"
        assert item["role"]["S"] == "user"
        assert item["user_id"]["S"] == "U456"

    @pytest.mark.asyncio
    async def test_store_assistant_turn_no_user_id(self, store, mock_client):
        turn = ConversationTurn(
            channel_id="C123",
            thread_ts="1234.5678",
            timestamp="1710000001000",
            role="assistant",
            content="Here is what happened...",
        )
        await store.store_turn(turn)

        item = mock_client.put_item.call_args[1]["item"]
        assert "user_id" not in item


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_get_history_returns_turns_chronologically(self, store, mock_client):
        mock_client.query.return_value = {
            "Items": [
                {
                    "channel_id": {"S": "C123"},
                    "thread_ts": {"S": "1234.5678"},
                    "timestamp": {"S": "200"},
                    "role": {"S": "assistant"},
                    "content": {"S": "answer"},
                },
                {
                    "channel_id": {"S": "C123"},
                    "thread_ts": {"S": "1234.5678"},
                    "timestamp": {"S": "100"},
                    "role": {"S": "user"},
                    "content": {"S": "question"},
                    "user_id": {"S": "U1"},
                },
            ]
        }

        turns = await store.get_history("C123", "1234.5678", limit=10)
        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_get_history_empty(self, store, mock_client):
        mock_client.query.return_value = {"Items": []}
        turns = await store.get_history("C123", "1234.5678")
        assert turns == []


class TestAgentThreadRegistry:
    @pytest.mark.asyncio
    async def test_register_thread(self, store, mock_client):
        await store.register_thread("C123", "1234.5678")
        item = mock_client.put_item.call_args[1]["item"]
        assert item["PK"]["S"] == "AGENT_THREAD#C123"
        assert item["SK"]["S"] == "THREAD#1234.5678"
        assert item["status"]["S"] == "active"

    @pytest.mark.asyncio
    async def test_is_agent_thread_true(self, store, mock_client):
        mock_client.get_item.return_value = {"Item": {"PK": {"S": "x"}, "SK": {"S": "y"}}}
        result = await store.is_agent_thread("C123", "1234.5678")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_agent_thread_false(self, store, mock_client):
        mock_client.get_item.return_value = {}
        result = await store.is_agent_thread("C123", "9999.0000")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_agent_thread_ts_set(self, store, mock_client):
        mock_client.query.return_value = {
            "Items": [
                {"thread_ts": {"S": "100.0"}},
                {"thread_ts": {"S": "200.0"}},
            ]
        }
        result = await store.get_agent_thread_ts_set("C123")
        assert result == {"100.0", "200.0"}


class TestWatermark:
    @pytest.mark.asyncio
    async def test_get_watermark_exists(self, store, mock_client):
        mock_client.get_item.return_value = {
            "Item": {
                "PK": {"S": "AGENT_WATERMARK#C123"},
                "SK": {"S": "WATERMARK"},
                "channel_id": {"S": "C123"},
                "latest_ingested_ts": {"S": "1234.5678"},
                "backfill_complete": {"BOOL": True},
                "total_ingested": {"N": "500"},
            }
        }
        wm = await store.get_watermark("C123")
        assert wm is not None
        assert wm.latest_ingested_ts == "1234.5678"
        assert wm.backfill_complete is True
        assert wm.total_ingested == 500

    @pytest.mark.asyncio
    async def test_get_watermark_not_exists(self, store, mock_client):
        mock_client.get_item.return_value = {}
        wm = await store.get_watermark("C999")
        assert wm is None


class TestWipeChannelData:
    @pytest.mark.asyncio
    async def test_wipe_deletes_all_records(self, store, mock_client):
        # Mock conversation turns
        mock_client.query.side_effect = [
            {
                "Items": [
                    {"PK": {"S": "AGENT_CONVERSATION#C123"}, "SK": {"S": "TURN#100"}},
                    {"PK": {"S": "AGENT_CONVERSATION#C123"}, "SK": {"S": "TURN#200"}},
                ]
            },
            {
                "Items": [
                    {"PK": {"S": "AGENT_THREAD#C123"}, "SK": {"S": "THREAD#1.0"}},
                ]
            },
        ]

        await store.wipe_channel_data("C123")

        # 2 turns + 1 thread + 1 watermark = 4 deletes
        assert mock_client.delete_item.call_count == 4
