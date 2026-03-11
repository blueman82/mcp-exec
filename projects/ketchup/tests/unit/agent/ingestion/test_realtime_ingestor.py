"""Tests for RealtimeIngestor (async queue, per-message embedding)."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from packages.agent.ingestion.realtime_ingestor import (
    RealtimeIngestor,
)


@pytest.fixture
def mock_deps():
    return {
        "embeddings_client": AsyncMock(),
        "vector_store": AsyncMock(),
        "conversation_store": AsyncMock(),
        "bot_user_id": "UBOT123",
    }


@pytest.fixture
def ingestor(mock_deps):
    mock_deps["conversation_store"].is_agent_thread.return_value = False
    mock_deps["conversation_store"].get_watermark.return_value = None
    return RealtimeIngestor(**mock_deps)


class TestMessageFiltering:
    @pytest.mark.asyncio
    async def test_filters_bot_own_messages(self, ingestor):
        await ingestor.ingest_message("C1", {"user": "UBOT123", "text": "hi", "ts": "1"})
        assert ingestor._queue.empty()

    @pytest.mark.asyncio
    async def test_filters_bot_id_messages(self, ingestor):
        await ingestor.ingest_message("C1", {"bot_id": "B1", "text": "hi", "ts": "1"})
        assert ingestor._queue.empty()

    @pytest.mark.asyncio
    async def test_filters_system_subtypes(self, ingestor):
        await ingestor.ingest_message(
            "C1", {"subtype": "channel_join", "user": "U1", "text": "joined", "ts": "1"}
        )
        assert ingestor._queue.empty()

    @pytest.mark.asyncio
    async def test_filters_agent_thread_messages(self, ingestor, mock_deps):
        mock_deps["conversation_store"].is_agent_thread.return_value = True
        await ingestor.ingest_message(
            "C1", {"user": "U1", "text": "hello", "ts": "2", "thread_ts": "1.0"}
        )
        assert ingestor._queue.empty()

    @pytest.mark.asyncio
    async def test_filters_slash_commands(self, ingestor):
        await ingestor.ingest_message("C1", {"user": "U1", "text": "/ketchup status", "ts": "1"})
        assert ingestor._queue.empty()

    @pytest.mark.asyncio
    async def test_queues_valid_message(self, ingestor):
        await ingestor.ingest_message("C1", {"user": "U1", "text": "hello world", "ts": "1.0"})
        assert not ingestor._queue.empty()


class TestAsyncQueue:
    @pytest.mark.asyncio
    async def test_processes_queued_message(self, ingestor, mock_deps):
        mock_deps["embeddings_client"].embed_texts.return_value = [[0.1] * 1536]

        await ingestor.ingest_message("C1", {"user": "U1", "text": "hello world", "ts": "1.0"})

        # Wait for the queue to process
        await asyncio.sleep(0.1)
        await ingestor.flush_all()

        # Should have embedded and stored
        mock_deps["embeddings_client"].embed_texts.assert_called()
        mock_deps["vector_store"].add_documents.assert_called()

    @pytest.mark.asyncio
    async def test_starts_processor_on_first_message(self, ingestor):
        assert ingestor._processor_task is None

        await ingestor.ingest_message("C1", {"user": "U1", "text": "hello", "ts": "1.0"})

        assert ingestor._processor_task is not None
