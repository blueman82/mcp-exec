"""Tests for BackfillIngestor."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from packages.agent.conversation.models import MessageWatermark
from packages.agent.ingestion.backfill_ingestor import BackfillIngestor


@pytest.fixture
def mock_deps():
    return {
        "embeddings_client": AsyncMock(),
        "vector_store": AsyncMock(),
        "conversation_store": AsyncMock(),
        "posting_handler": AsyncMock(),
        "bot_user_id": "UBOT123",
    }


@pytest.fixture
def ingestor(mock_deps):
    return BackfillIngestor(**mock_deps)


class TestScheduleBackfill:
    @pytest.mark.asyncio
    async def test_skips_when_disabled(self, ingestor, mock_deps):
        with patch.dict(os.environ, {"KETCHUP_AGENT_BACKFILL_ENABLED": "false"}):
            await ingestor.schedule_backfill("C123")
            mock_deps["conversation_store"].mark_backfill_started.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_already_backfilled(self, ingestor, mock_deps):
        mock_deps["conversation_store"].get_watermark.return_value = MessageWatermark(
            channel_id="C123",
            latest_ingested_ts="999",
            backfill_complete=True,
            total_ingested=100,
        )
        with patch.dict(os.environ, {"KETCHUP_AGENT_BACKFILL_ENABLED": "true"}):
            await ingestor.schedule_backfill("C123")
            mock_deps["conversation_store"].mark_backfill_started.assert_not_called()


class TestFilterMessages:
    def test_filters_bot_messages(self, ingestor):
        messages = [
            {"user": "UBOT123", "text": "bot msg", "ts": "1"},
            {"user": "U1", "text": "user msg", "ts": "2"},
            {"bot_id": "B1", "text": "other bot", "ts": "3"},
        ]
        result = ingestor._filter_messages(messages)
        assert len(result) == 1
        assert result[0]["user"] == "U1"

    def test_filters_system_subtypes(self, ingestor):
        messages = [
            {"user": "U1", "text": "joined", "ts": "1", "subtype": "channel_join"},
            {"user": "U1", "text": "actual message", "ts": "2"},
        ]
        result = ingestor._filter_messages(messages)
        assert len(result) == 1
        assert result[0]["ts"] == "2"

    def test_filters_slash_commands(self, ingestor):
        messages = [
            {"user": "U1", "text": "/ketchup status", "ts": "1"},
            {"user": "U1", "text": "normal message", "ts": "2"},
        ]
        result = ingestor._filter_messages(messages)
        assert len(result) == 1


class TestBackfillChannel:
    """Tests for the streaming page-by-page backfill with incremental checkpointing."""

    @pytest.mark.asyncio
    async def test_streams_page_by_page_with_checkpoints(self, ingestor, mock_deps):
        """Each page should be embedded, stored, and checkpointed before next page."""
        mock_deps["conversation_store"].get_watermark.return_value = None
        mock_deps["embeddings_client"].embed_texts.side_effect = lambda texts: [[0.1] * 1536] * len(
            texts
        )

        # Two pages of messages
        page1_response = {
            "ok": True,
            "messages": [{"user": "U1", "text": "msg1", "ts": "100.0"}],
            "response_metadata": {"next_cursor": "cursor_abc"},
        }
        page2_response = {
            "ok": True,
            "messages": [{"user": "U1", "text": "msg2", "ts": "200.0"}],
            "response_metadata": {"next_cursor": ""},
        }
        mock_deps["posting_handler"].api_get = AsyncMock(
            side_effect=[page1_response, page2_response]
        )

        with patch.dict(os.environ, {"KETCHUP_AGENT_BACKFILL_ENABLED": "true"}):
            await ingestor._backfill_channel("C123")

        # Watermark updated after EACH page, plus final completion
        update_calls = mock_deps["conversation_store"].update_watermark.call_args_list
        assert len(update_calls) == 3  # page1 checkpoint + page2 checkpoint + final

        # Page 1 checkpoint: not complete
        assert update_calls[0].kwargs["backfill_complete"] is False
        assert update_calls[0].kwargs["latest_ts"] == "100.0"

        # Page 2 checkpoint: not complete
        assert update_calls[1].kwargs["backfill_complete"] is False
        assert update_calls[1].kwargs["latest_ts"] == "200.0"

        # Final: complete
        assert update_calls[2].kwargs["backfill_complete"] is True

    @pytest.mark.asyncio
    async def test_resumes_from_watermark(self, ingestor, mock_deps):
        """Resumed backfill should pass oldest= to skip already-ingested messages."""
        mock_deps["conversation_store"].get_watermark.return_value = MessageWatermark(
            channel_id="C123",
            latest_ingested_ts="500.0",
            backfill_complete=False,
            total_ingested=50,
        )
        mock_deps["embeddings_client"].embed_texts.side_effect = lambda texts: [[0.1] * 1536] * len(
            texts
        )

        mock_deps["posting_handler"].api_get = AsyncMock(
            return_value={
                "ok": True,
                "messages": [{"user": "U1", "text": "msg after resume", "ts": "600.0"}],
                "response_metadata": {"next_cursor": ""},
            }
        )

        with patch.dict(os.environ, {"KETCHUP_AGENT_BACKFILL_ENABLED": "true"}):
            await ingestor._backfill_channel("C123")

        # Verify oldest= was passed with 5-second buffer (500.0 - 5 = 495.0)
        api_call = mock_deps["posting_handler"].api_get.call_args
        assert api_call.args[1]["oldest"] == "495.0"

        # Should NOT call mark_backfill_started (already started)
        mock_deps["conversation_store"].mark_backfill_started.assert_not_called()

        # Final total should include previous ingested count
        final_call = mock_deps["conversation_store"].update_watermark.call_args_list[-1]
        assert final_call.kwargs["total_ingested"] == 51  # 50 previous + 1 new

    @pytest.mark.asyncio
    async def test_respects_message_cap(self, ingestor, mock_deps):
        """Backfill should stop when message cap is reached."""
        mock_deps["conversation_store"].get_watermark.return_value = None
        # Return N embeddings matching N input texts
        mock_deps["embeddings_client"].embed_texts.side_effect = lambda texts: [[0.1] * 1536] * len(
            texts
        )

        # Return messages that would exceed a cap of 2
        mock_deps["posting_handler"].api_get = AsyncMock(
            return_value={
                "ok": True,
                "messages": [
                    {"user": "U1", "text": "m1", "ts": "1.0"},
                    {"user": "U1", "text": "m2", "ts": "2.0"},
                    {"user": "U1", "text": "m3", "ts": "3.0"},
                ],
                "response_metadata": {"next_cursor": "more_data"},
            }
        )

        with patch.dict(
            os.environ,
            {
                "KETCHUP_AGENT_BACKFILL_ENABLED": "true",
                "KETCHUP_AGENT_MAX_BACKFILL_MESSAGES": "2",
            },
        ):
            await ingestor._backfill_channel("C123")

        # Count total documents stored across all add_documents calls
        total_stored = sum(
            len(call.args[0]) for call in mock_deps["vector_store"].add_documents.call_args_list
        )
        assert total_stored == 2

    @pytest.mark.asyncio
    async def test_deduplicates_broadcast_replies(self, ingestor, mock_deps):
        """Broadcast replies appearing in both history and thread replies should be deduplicated."""
        mock_deps["conversation_store"].get_watermark.return_value = None
        mock_deps["embeddings_client"].embed_texts.side_effect = lambda texts: [[0.1] * 1536] * len(
            texts
        )

        # Message with reply_count triggers thread fetch; ts "200.0" appears in both
        history_response = {
            "ok": True,
            "messages": [
                {"user": "U1", "text": "parent", "ts": "100.0", "reply_count": 1},
                {"user": "U1", "text": "broadcast reply", "ts": "200.0"},
            ],
            "response_metadata": {"next_cursor": ""},
        }
        # Thread replies include the parent (filtered) AND the broadcast reply (duplicate)
        thread_response = {
            "ok": True,
            "messages": [
                {"user": "U1", "text": "parent", "ts": "100.0"},  # parent — excluded by ts filter
                {"user": "U1", "text": "broadcast reply", "ts": "200.0"},  # duplicate of history
            ],
            "response_metadata": {"next_cursor": ""},
        }
        mock_deps["posting_handler"].api_get = AsyncMock(
            side_effect=[history_response, thread_response]
        )

        with patch.dict(os.environ, {"KETCHUP_AGENT_BACKFILL_ENABLED": "true"}):
            await ingestor._backfill_channel("C123")

        # Should store 2 unique messages, not 3 (broadcast reply deduplicated)
        total_stored = sum(
            len(call.args[0]) for call in mock_deps["vector_store"].add_documents.call_args_list
        )
        assert total_stored == 2

    @pytest.mark.asyncio
    async def test_empty_channel_marks_complete(self, ingestor, mock_deps):
        """Empty channel should mark backfill as complete immediately."""
        mock_deps["conversation_store"].get_watermark.return_value = None
        mock_deps["posting_handler"].api_get = AsyncMock(
            return_value={
                "ok": True,
                "messages": [],
                "response_metadata": {"next_cursor": ""},
            }
        )

        with patch.dict(os.environ, {"KETCHUP_AGENT_BACKFILL_ENABLED": "true"}):
            await ingestor._backfill_channel("C123")

        final = mock_deps["conversation_store"].update_watermark.call_args
        assert final.kwargs["backfill_complete"] is True
        assert final.kwargs["total_ingested"] == 0
