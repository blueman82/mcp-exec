"""Tests verifying Round 2 audit bug fixes for Ketchup Agent.

Each test targets a specific bug discovered during the second deep audit.
Tests verify the fixes are working correctly.

Run with:  pytest tests/unit/agent/test_audit_round2_bugs.py -v
"""

import inspect
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
#  R2-1 (HIGH): get_history() paginates past DynamoDB Limit+Filter interaction
# ---------------------------------------------------------------------------


class TestBugR2_1_GetHistoryLimitFilter:
    """Verify get_history paginates to fill the requested limit."""

    @pytest.mark.asyncio
    async def test_paginates_when_first_page_insufficient(self):
        """When first DynamoDB page yields fewer than limit matching items,
        get_history should paginate to collect more."""
        from packages.agent.conversation.store import ConversationStore

        mock_client = AsyncMock()
        store = ConversationStore(dynamodb_client=mock_client)

        # Page 1: 3 matching items with continuation token
        page1_items = [
            {
                "channel_id": {"S": "C123"},
                "thread_ts": {"S": "T1"},
                "timestamp": {"S": str(1000 - i)},
                "role": {"S": "user" if i % 2 == 0 else "assistant"},
                "content": {"S": f"message {i}"},
            }
            for i in range(3)
        ]
        # Page 2: 3 more matching items, no continuation
        page2_items = [
            {
                "channel_id": {"S": "C123"},
                "thread_ts": {"S": "T1"},
                "timestamp": {"S": str(990 - i)},
                "role": {"S": "user" if i % 2 == 0 else "assistant"},
                "content": {"S": f"message page2 {i}"},
            }
            for i in range(3)
        ]

        mock_client.query.side_effect = [
            {"Items": page1_items, "LastEvaluatedKey": {"PK": {"S": "x"}, "SK": {"S": "y"}}},
            {"Items": page2_items},
        ]

        turns = await store.get_history("C123", "T1", limit=5)

        # Should paginate and return 5 (collected 6 across 2 pages, limited to 5)
        assert len(turns) == 5
        assert mock_client.query.call_count == 2

    @pytest.mark.asyncio
    async def test_stops_when_limit_reached(self):
        """Should stop paginating once limit items are collected."""
        from packages.agent.conversation.store import ConversationStore

        mock_client = AsyncMock()
        store = ConversationStore(dynamodb_client=mock_client)

        items = [
            {
                "channel_id": {"S": "C123"},
                "thread_ts": {"S": "T1"},
                "timestamp": {"S": str(1000 - i)},
                "role": {"S": "user"},
                "content": {"S": f"msg {i}"},
            }
            for i in range(10)
        ]

        mock_client.query.return_value = {"Items": items}

        turns = await store.get_history("C123", "T1", limit=5)
        assert len(turns) == 5

    @pytest.mark.asyncio
    async def test_returns_chronological_order(self):
        """Results should be in chronological order (oldest first)."""
        from packages.agent.conversation.store import ConversationStore

        mock_client = AsyncMock()
        store = ConversationStore(dynamodb_client=mock_client)

        # Newest first (scan_index_forward=False)
        items = [
            {
                "channel_id": {"S": "C123"},
                "thread_ts": {"S": "T1"},
                "timestamp": {"S": str(1000 - i)},
                "role": {"S": "user"},
                "content": {"S": f"msg {i}"},
            }
            for i in range(3)
        ]
        mock_client.query.return_value = {"Items": items}

        turns = await store.get_history("C123", "T1", limit=10)

        # Should be chronological (oldest first) — compare numerically
        timestamps = [float(t.timestamp) for t in turns]
        assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
#  R2-2 (MEDIUM): update_with_response fallback triggers on API errors
# ---------------------------------------------------------------------------


class TestBugR2_2_UpdateMessageFallback:
    """Verify update_with_response falls back when Slack returns {ok: false}."""

    @pytest.mark.asyncio
    async def test_fallback_triggers_on_api_error_response(self):
        """When update_message returns {ok: false}, fallback post_message fires."""
        from packages.agent.slack.thread_manager import AgentThreadManager

        mock_store = AsyncMock()
        mock_posting = AsyncMock()

        mock_posting.update_message.return_value = {
            "ok": False,
            "error": "message_not_found",
        }

        manager = AgentThreadManager(
            conversation_store=mock_store,
            posting_handler=mock_posting,
        )

        await manager.update_with_response(
            channel_id="C123",
            message_ts="1234.5678",
            response="Here is your answer",
            thread_ts="1111.0000",
        )

        mock_posting.update_message.assert_called_once()
        # Fallback should fire since {ok: false}
        mock_posting.post_message.assert_called_once_with(
            channel_id="C123",
            message="Here is your answer",
            thread_ts="1111.0000",
        )

    @pytest.mark.asyncio
    async def test_fallback_triggers_on_network_exception(self):
        """Fallback fires when update_message raises an exception."""
        from packages.agent.slack.thread_manager import AgentThreadManager

        mock_store = AsyncMock()
        mock_posting = AsyncMock()

        mock_posting.update_message.side_effect = ConnectionError("network down")

        manager = AgentThreadManager(
            conversation_store=mock_store,
            posting_handler=mock_posting,
        )

        await manager.update_with_response(
            channel_id="C123",
            message_ts="1234.5678",
            response="Here is your answer",
            thread_ts="1111.0000",
        )

        mock_posting.post_message.assert_called_once_with(
            channel_id="C123",
            message="Here is your answer",
            thread_ts="1111.0000",
        )

    @pytest.mark.asyncio
    async def test_no_fallback_on_success(self):
        """When update succeeds, no fallback post."""
        from packages.agent.slack.thread_manager import AgentThreadManager

        mock_store = AsyncMock()
        mock_posting = AsyncMock()
        mock_posting.update_message.return_value = {"ok": True, "ts": "1234.5678"}

        manager = AgentThreadManager(
            conversation_store=mock_store,
            posting_handler=mock_posting,
        )

        await manager.update_with_response(
            channel_id="C123",
            message_ts="1234.5678",
            response="Here is your answer",
            thread_ts="1111.0000",
        )

        mock_posting.update_message.assert_called_once()
        mock_posting.post_message.assert_not_called()


# ---------------------------------------------------------------------------
#  R2-3 (MEDIUM): Protocol signature includes thread_ts
# ---------------------------------------------------------------------------


class TestBugR2_3_ProtocolSignatureMatch:
    """Verify protocol and concrete signatures align for update_with_response."""

    def test_protocol_includes_thread_ts_parameter(self):
        """Protocol now includes thread_ts parameter."""
        from packages.core.typed_di.service_registrations.protocols.agent_protocols import (
            AgentThreadManagerProtocol,
        )

        sig = inspect.signature(AgentThreadManagerProtocol.update_with_response)
        param_names = list(sig.parameters.keys())

        assert "thread_ts" in param_names

    def test_concrete_has_thread_ts_parameter(self):
        """Concrete implementation accepts thread_ts."""
        from packages.agent.slack.thread_manager import AgentThreadManager

        sig = inspect.signature(AgentThreadManager.update_with_response)
        param_names = list(sig.parameters.keys())

        assert "thread_ts" in param_names
        assert sig.parameters["thread_ts"].default is None

    def test_handler_passes_thread_ts_to_update_with_response(self):
        """All handler call sites pass thread_ts."""
        import ast

        with open("packages/agent/slack/handler.py") as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "update_with_response":
                    kwarg_names = [kw.arg for kw in node.keywords]
                    assert (
                        "thread_ts" in kwarg_names
                    ), f"Call at line {node.lineno} missing thread_ts kwarg"


# ---------------------------------------------------------------------------
#  R2-4 (MEDIUM): ChromaDB operations use asyncio.to_thread
# ---------------------------------------------------------------------------


class TestBugR2_4_ChromaDBAsyncWrapping:
    """Verify ChromaDB operations use asyncio.to_thread for non-blocking I/O."""

    def test_add_documents_uses_thread_offloading(self):
        """add_documents wraps synchronous collection.upsert() in to_thread."""
        import ast

        with open("packages/agent/embeddings/vector_store.py") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "add_documents":
                body_source = ast.dump(node)
                assert (
                    "to_thread" in body_source
                ), "add_documents should use asyncio.to_thread for ChromaDB calls"
                break

    def test_query_uses_thread_offloading(self):
        """query wraps synchronous collection.query() in to_thread."""
        import ast

        with open("packages/agent/embeddings/vector_store.py") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "query":
                body_source = ast.dump(node)
                assert (
                    "to_thread" in body_source
                ), "query should use asyncio.to_thread for ChromaDB calls"
                break

    def test_delete_uses_thread_offloading(self):
        """delete_by_channel wraps synchronous collection.delete() in to_thread."""
        import ast

        with open("packages/agent/embeddings/vector_store.py") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "delete_by_channel":
                body_source = ast.dump(node)
                assert "to_thread" in body_source, "delete_by_channel should use asyncio.to_thread"
                break


# ---------------------------------------------------------------------------
#  R2-5 (LOW-MEDIUM): get_agent_thread_ts_set paginates DynamoDB queries
# ---------------------------------------------------------------------------


class TestBugR2_5_ThreadSetPagination:
    """Verify get_agent_thread_ts_set handles DynamoDB pagination."""

    @pytest.mark.asyncio
    async def test_paginates_on_last_evaluated_key(self):
        """When DynamoDB returns LastEvaluatedKey, fetches next page."""
        from packages.agent.conversation.store import ConversationStore

        mock_client = AsyncMock()
        store = ConversationStore(dynamodb_client=mock_client)

        mock_client.query.side_effect = [
            {
                "Items": [{"thread_ts": {"S": "1.0"}}, {"thread_ts": {"S": "2.0"}}],
                "LastEvaluatedKey": {"PK": {"S": "x"}, "SK": {"S": "y"}},
            },
            {
                "Items": [{"thread_ts": {"S": "3.0"}}],
            },
        ]

        result = await store.get_agent_thread_ts_set("C123")

        assert mock_client.query.call_count == 2
        assert result == {"1.0", "2.0", "3.0"}

    @pytest.mark.asyncio
    async def test_single_page_no_continuation(self):
        """Single page without LastEvaluatedKey returns all results."""
        from packages.agent.conversation.store import ConversationStore

        mock_client = AsyncMock()
        store = ConversationStore(dynamodb_client=mock_client)

        mock_client.query.return_value = {
            "Items": [{"thread_ts": {"S": "1.0"}}, {"thread_ts": {"S": "2.0"}}],
        }

        result = await store.get_agent_thread_ts_set("C123")

        assert mock_client.query.call_count == 1
        assert result == {"1.0", "2.0"}


# ---------------------------------------------------------------------------
#  R2-6 (LOW): update_watermark uses update_item to preserve backfill_started_at
# ---------------------------------------------------------------------------


class TestBugR2_6_UpdateWatermarkPreservesStartedAt:
    """Verify update_watermark uses update_item instead of put_item."""

    @pytest.mark.asyncio
    async def test_update_watermark_uses_update_item(self):
        """update_watermark should use update_item (partial) not put_item (overwrite)."""
        from packages.agent.conversation.store import ConversationStore

        mock_client = AsyncMock()
        store = ConversationStore(dynamodb_client=mock_client)

        await store.update_watermark(
            channel_id="C123",
            latest_ts="500.0",
            total_ingested=100,
            backfill_complete=False,
        )

        # Uses update_item (preserves backfill_started_at), not put_item
        mock_client.update_item.assert_called_once()
        mock_client.put_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_watermark_sets_correct_fields(self):
        """update_item expression updates the right fields."""
        from packages.agent.conversation.store import ConversationStore

        mock_client = AsyncMock()
        store = ConversationStore(dynamodb_client=mock_client)

        await store.update_watermark(
            channel_id="C123",
            latest_ts="500.0",
            total_ingested=100,
            backfill_complete=True,
        )

        call_kwargs = mock_client.update_item.call_args[1]
        expr_values = call_kwargs["expression_attribute_values"]

        assert expr_values[":ts"] == {"S": "500.0"}
        assert expr_values[":bc"] == {"BOOL": True}
        assert expr_values[":ti"] == {"N": "100"}
        assert expr_values[":cid"] == {"S": "C123"}


# ---------------------------------------------------------------------------
#  R2-7 (LOW-MEDIUM): RealtimeIngestor includes "source" metadata field
# ---------------------------------------------------------------------------


class TestBugR2_7_RealtimeIngestorSourceMetadata:
    """Verify RealtimeIngestor includes 'source' in document metadata."""

    @pytest.mark.asyncio
    async def test_realtime_metadata_includes_source(self):
        """Realtime ingestor stores documents with source: 'realtime'."""
        from packages.agent.ingestion.realtime_ingestor import RealtimeIngestor

        mock_embeddings = AsyncMock()
        mock_vector_store = AsyncMock()
        mock_conversation_store = AsyncMock()

        mock_embeddings.embed_texts.return_value = [[0.1] * 1536]
        mock_conversation_store.is_agent_thread.return_value = False

        ingestor = RealtimeIngestor(
            embeddings_client=mock_embeddings,
            vector_store=mock_vector_store,
            conversation_store=mock_conversation_store,
            bot_user_id="U_BOT",
        )

        message = {"user": "U_HUMAN", "text": "hello", "ts": "100.0"}
        await ingestor.ingest_message("C123", message)
        await ingestor.flush_all()

        mock_vector_store.add_documents.assert_called_once()
        stored_docs = (
            mock_vector_store.add_documents.call_args[1].get("documents")
            or mock_vector_store.add_documents.call_args[0][0]
        )

        metadata = stored_docs[0]["metadata"]
        assert metadata["source"] == "realtime"

    def test_backfill_ingestor_has_source_metadata(self):
        """Confirm backfill_ingestor includes 'source' for contrast."""
        with open("packages/agent/ingestion/backfill_ingestor.py") as f:
            source = f.read()

        assert '"source": "backfill"' in source or "'source': 'backfill'" in source

    def test_jira_backfill_has_source_metadata(self):
        """Confirm jira_backfill includes 'source' for contrast."""
        with open("packages/agent/ingestion/jira_backfill.py") as f:
            source = f.read()

        assert '"source": "jira"' in source or "'source': 'jira'" in source
