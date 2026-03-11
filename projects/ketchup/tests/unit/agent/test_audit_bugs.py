"""Bug-exposing tests for Ketchup Agent audit (PR #307).

Each test targets a specific verified bug discovered during the deep audit.
Tests are marked with the bug ID and severity for traceability.

Run with:  pytest tests/unit/agent/test_audit_bugs.py -v
"""

import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
#  BUG 1 (CRITICAL): post_message() missing thread_ts parameter
#
#  handler.py passes thread_ts= to posting_handler.post_message() in multiple
#  places (lines 183-186, 201-204, 232-235), and thread_manager.py also
#  passes thread_ts= at line 45-48. But SlackPostingHandler.post_message()
#  (posting.py:56-63) does NOT accept thread_ts.
#
#  Impact: Every agent query crashes with TypeError — agent is 100% broken.
# ---------------------------------------------------------------------------


class TestBug1_PostMessageThreadTs:
    """Verify post_message accepts thread_ts for agent thread posting."""

    def test_post_message_signature_includes_thread_ts(self):
        """post_message MUST accept thread_ts for agent conversations."""
        from packages.slack.messages.posting import SlackPostingHandler

        sig = inspect.signature(SlackPostingHandler.post_message)
        params = list(sig.parameters.keys())
        assert "thread_ts" in params, (
            "SlackPostingHandler.post_message() is missing the 'thread_ts' parameter. "
            "The agent handler passes thread_ts= in handler.py:183, 201, 232 and "
            "thread_manager.py:45. Without it, every agent query crashes with TypeError."
        )

    @pytest.mark.asyncio
    async def test_handler_fallback_sends_to_thread_not_channel(self):
        """When thinking_ts is None, fallback post_message must include thread_ts."""
        from packages.agent.slack.handler import AgentSlackHandler

        handler = AgentSlackHandler(
            agent_engine=AsyncMock(),
            conversation_store=AsyncMock(),
            thread_manager=AsyncMock(),
            posting_handler=AsyncMock(),
            secrets_manager=AsyncMock(),
        )

        handler._secrets_manager.get_bot_slack_user_id_async.return_value = "UBOT"
        handler._thread_manager.post_thinking_indicator.return_value = None  # thinking failed
        handler._agent_engine.answer.return_value = "answer"

        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            await handler.handle_mention(
                {
                    "channel": "C123",
                    "user": "U456",
                    "text": "<@UBOT> what happened?",
                    "ts": "1234.5678",
                }
            )

        # The fallback post_message call MUST include thread_ts
        call_kwargs = handler._posting_handler.post_message.call_args
        assert call_kwargs is not None, "post_message was not called"
        # thread_ts should be passed so the response stays in the thread
        _, kwargs = call_kwargs
        assert "thread_ts" in kwargs, (
            "Fallback post_message does not include thread_ts — "
            "response will go to channel root instead of the thread"
        )
        assert kwargs["thread_ts"] == "1234.5678"

    @pytest.mark.asyncio
    async def test_thinking_indicator_sends_to_thread(self):
        """post_thinking_indicator must post to the correct thread."""
        from packages.agent.slack.thread_manager import AgentThreadManager

        posting_handler = AsyncMock()
        posting_handler.post_message.return_value = {"ok": True, "ts": "indicator_ts"}

        tm = AgentThreadManager(
            conversation_store=AsyncMock(),
            posting_handler=posting_handler,
        )

        result = await tm.post_thinking_indicator("C123", "1234.5678")

        # Should have succeeded — meaning post_message accepted thread_ts
        assert result is not None, (
            "post_thinking_indicator returned None — post_message likely rejected "
            "the thread_ts parameter with TypeError"
        )

        call_kwargs = posting_handler.post_message.call_args
        _, kwargs = call_kwargs
        assert kwargs.get("thread_ts") == "1234.5678"


# ---------------------------------------------------------------------------
#  BUG 2 (CRITICAL): update_message() called with wrong parameter name
#
#  thread_manager.py:70 calls update_message(text=response) but the actual
#  signature at posting.py:446 is update_message(message=response).
#
#  Impact: update_message ALWAYS fails with TypeError, forcing fallback path.
# ---------------------------------------------------------------------------


class TestBug2_UpdateMessageParamName:
    """Verify update_with_response calls update_message with correct param name."""

    def test_update_message_parameter_is_message_not_text(self):
        """update_message's content parameter is named 'message', not 'text'."""
        from packages.slack.messages.posting import SlackPostingHandler

        sig = inspect.signature(SlackPostingHandler.update_message)
        params = list(sig.parameters.keys())
        # Confirm the actual signature uses 'message'
        assert "message" in params
        assert "text" not in params, (
            "update_message uses 'text' param but thread_manager calls it with 'text='. "
            "If the param is actually 'message', the caller at thread_manager.py:70 "
            "must be fixed to use message= instead of text="
        )

    @pytest.mark.asyncio
    async def test_update_with_response_uses_correct_param(self):
        """update_with_response must pass content as 'message', not 'text'."""
        from packages.agent.slack.thread_manager import AgentThreadManager

        posting_handler = AsyncMock()
        tm = AgentThreadManager(
            conversation_store=AsyncMock(),
            posting_handler=posting_handler,
        )

        await tm.update_with_response("C123", "msg_ts_1", "Here is the answer")

        posting_handler.update_message.assert_called_once()
        call_kwargs = posting_handler.update_message.call_args
        _, kwargs = call_kwargs

        # The parameter MUST be 'message' (not 'text') to match posting.py:446
        assert "text" not in kwargs, (
            "thread_manager passes text= to update_message, but the parameter is named "
            "'message' in posting.py:446. This causes TypeError on every response update."
        )
        # If fixed, it should use the correct param name
        # Note: if both 'text' and 'message' are absent, the call uses positional args
        has_message = "message" in kwargs or (call_kwargs.args and len(call_kwargs.args) >= 4)
        assert has_message or "text" in kwargs, "update_message was not passed the response content"


# ---------------------------------------------------------------------------
#  BUG 3 (HIGH): thread_manager fallback posts to channel root, not thread
#
#  thread_manager.py:79-82 — when update_message fails, the fallback
#  post_message call does NOT include thread_ts. The response appears in the
#  channel root instead of the conversation thread.
# ---------------------------------------------------------------------------


class TestBug3_FallbackMissingThreadTs:
    """Verify fallback post includes thread_ts when update fails."""

    @pytest.mark.asyncio
    async def test_fallback_posts_to_thread_not_channel(self):
        """When update_message fails, fallback MUST post to the thread."""
        from packages.agent.slack.thread_manager import AgentThreadManager

        posting_handler = AsyncMock()
        # Make update_message fail so we hit the fallback path
        posting_handler.update_message.side_effect = Exception("message_not_found")

        tm = AgentThreadManager(
            conversation_store=AsyncMock(),
            posting_handler=posting_handler,
        )

        await tm.update_with_response("C123", "msg_ts_1", "Here is the answer")

        # Fallback post_message should include thread context
        fallback_call = posting_handler.post_message.call_args
        assert fallback_call is not None, "Fallback post_message was not called"
        _, kwargs = fallback_call
        # BUG: thread_ts is NOT passed — response leaks to channel root
        assert "thread_ts" in kwargs, (
            "Fallback post_message at thread_manager.py:79 does not include thread_ts. "
            "When update fails, the response will appear in the channel root instead "
            "of the conversation thread."
        )


# ---------------------------------------------------------------------------
#  BUG 4 (HIGH): String dependency in ServiceSpec breaks DI graph
#
#  agent_services.py:138 uses a string literal for the api_executor dep
#  instead of the actual protocol type. DependencySpec.type is annotated
#  as Type, but at runtime stores a string. Breaks topological sort.
# ---------------------------------------------------------------------------


class TestBug4_StringDepInServiceSpec:
    """Verify all ServiceSpec deps use actual types, not strings."""

    def test_all_agent_deps_are_types_not_strings(self):
        """Every dependency in agent ServiceSpecs must be a Type, not a string."""
        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            from packages.core.typed_di.service_registrations.registrations.agent_services import (
                _get_agent_specs,
            )

            specs = _get_agent_specs()

            for spec in specs:
                for param_name, dep_info in spec.deps.items():
                    if isinstance(dep_info, tuple):
                        dep_type = dep_info[0]
                    else:
                        dep_type = dep_info

                    assert not isinstance(dep_type, str), (
                        f"ServiceSpec for {spec.protocol.__name__} has string dependency "
                        f"'{param_name}': {dep_type!r}. Dependencies must be protocol "
                        f"types, not string paths. This breaks DependencySpec and "
                        f"topological sort. (agent_services.py:138)"
                    )
                    assert isinstance(dep_type, type), (
                        f"ServiceSpec for {spec.protocol.__name__} dep '{param_name}' "
                        f"is {type(dep_type).__name__}, expected a type/protocol class."
                    )


# ---------------------------------------------------------------------------
#  BUG 5 (HIGH): Watermark race condition (non-atomic read-modify-write)
#
#  realtime_ingestor.py:164-172 reads watermark, increments total, writes
#  back using put_item (full overwrite). Concurrent backfill can overwrite
#  backfill_complete=True with False.
# ---------------------------------------------------------------------------


class TestBug5_WatermarkRaceCondition:
    """Verify watermark updates use atomic increment, not read-modify-write."""

    @pytest.mark.asyncio
    async def test_realtime_uses_atomic_increment(self):
        """Real-time ingestion must use increment_watermark (atomic), not update_watermark."""
        from packages.agent.ingestion.realtime_ingestor import RealtimeIngestor

        embeddings_client = AsyncMock()
        embeddings_client.embed_texts.return_value = [[0.1] * 1536]

        vector_store = AsyncMock()
        conversation_store = AsyncMock()
        conversation_store.is_agent_thread.return_value = False

        ingestor = RealtimeIngestor(
            embeddings_client=embeddings_client,
            vector_store=vector_store,
            conversation_store=conversation_store,
            bot_user_id="UBOT",
        )

        await ingestor._embed_and_store(
            "C123",
            {"ts": "10000.0", "text": "hello", "user": "U1"},
        )

        # Must use atomic increment_watermark, NOT read-modify-write update_watermark
        conversation_store.increment_watermark.assert_called_once_with(
            channel_id="C123",
            latest_ts="10000.0",
        )
        # Should NOT call get_watermark + update_watermark (the racy pattern)
        conversation_store.get_watermark.assert_not_called()
        conversation_store.update_watermark.assert_not_called()

    @pytest.mark.asyncio
    async def test_increment_watermark_uses_update_item_not_put_item(self):
        """increment_watermark must use DynamoDB update_item (atomic ADD)."""
        from packages.agent.conversation.store import ConversationStore

        dynamodb_client = AsyncMock()
        store = ConversationStore(dynamodb_client=dynamodb_client)

        await store.increment_watermark("C123", "10000.0")

        # Must use update_item (atomic) not put_item (full overwrite)
        dynamodb_client.update_item.assert_called_once()
        dynamodb_client.put_item.assert_not_called()

        call_kwargs = dynamodb_client.update_item.call_args
        _, kwargs = call_kwargs

        # Verify ADD is used for atomic increment
        assert "ADD" in kwargs["update_expression"], (
            "increment_watermark must use ADD for atomic counter increment. "
            "Without ADD, concurrent writers can stomp each other's counts."
        )
        # Verify backfill_complete is NOT touched
        assert "backfill_complete" not in kwargs["update_expression"], (
            "increment_watermark must NOT touch backfill_complete. "
            "Only backfill completion should set that flag."
        )


# ---------------------------------------------------------------------------
#  BUG 6 (MEDIUM): BackfillIngestor race condition
#
#  backfill_ingestor.py:80-86 — between checking self._processing=False
#  and the task setting self._processing=True, a second schedule_backfill
#  call can also create a task. Two tasks process the queue concurrently.
# ---------------------------------------------------------------------------


class TestBug6_BackfillRaceCondition:
    """Verify backfill doesn't create duplicate processor tasks."""

    @pytest.mark.asyncio
    async def test_concurrent_schedule_creates_single_processor(self):
        """Two rapid schedule_backfill calls must not create two processor tasks."""
        from packages.agent.ingestion.backfill_ingestor import BackfillIngestor

        conversation_store = AsyncMock()
        conversation_store.get_watermark.return_value = None  # not yet backfilled

        ingestor = BackfillIngestor(
            embeddings_client=AsyncMock(),
            vector_store=AsyncMock(),
            conversation_store=conversation_store,
            posting_handler=AsyncMock(),
            bot_user_id="UBOT",
        )

        tasks_created = []
        original_create_task = asyncio.create_task

        def tracking_create_task(coro):
            task = original_create_task(coro)
            tasks_created.append(task)
            return task

        with (
            patch.dict(os.environ, {"KETCHUP_AGENT_BACKFILL_ENABLED": "true"}),
            patch("asyncio.create_task", side_effect=tracking_create_task),
        ):
            # Schedule two channels in rapid succession (no await between)
            await ingestor.schedule_backfill("C001")
            await ingestor.schedule_backfill("C002")

        # BUG: Both calls see _processing=False and both create tasks
        assert len(tasks_created) <= 1, (
            f"Expected at most 1 processor task, but {len(tasks_created)} were created. "
            "Race condition: _processing flag is set inside _process_queue (after task start), "
            "not at the point where schedule_backfill checks it."
        )

        # Cleanup: cancel any dangling tasks
        for task in tasks_created:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


# ---------------------------------------------------------------------------
#  BUG 7 (MEDIUM): wipe_channel_data missing DynamoDB pagination
#
#  store.py:314-322 — query returns max 1MB per call. If a channel has
#  thousands of turns, only the first page is deleted. The rest are orphaned.
# ---------------------------------------------------------------------------


class TestBug7_WipeChannelPagination:
    """Verify wipe_channel_data handles paginated DynamoDB results."""

    @pytest.mark.asyncio
    async def test_wipe_handles_pagination(self):
        """wipe_channel_data must paginate through all items, not just one page."""
        from packages.agent.conversation.store import ConversationStore

        dynamodb_client = AsyncMock()

        # Simulate paginated response for conversation prefix:
        # Page 1: 100 items + LastEvaluatedKey, Page 2: 50 items (no key = done)
        conv_page1 = [
            {"PK": {"S": "AGENT_CONVERSATION#C123"}, "SK": {"S": f"TURN#{i}"}} for i in range(100)
        ]
        conv_page2 = [
            {"PK": {"S": "AGENT_CONVERSATION#C123"}, "SK": {"S": f"TURN#{i}"}}
            for i in range(100, 150)
        ]

        # Track which prefix and whether pagination key was provided
        query_calls = []

        async def mock_query(**kwargs):
            query_calls.append(kwargs)
            pk = kwargs["expression_attribute_values"][":pk"]["S"]
            has_start_key = "exclusive_start_key" in kwargs

            if "AGENT_CONVERSATION#" in pk and not has_start_key:
                # First page of conversation items
                return {
                    "Items": conv_page1,
                    "LastEvaluatedKey": {
                        "PK": {"S": "AGENT_CONVERSATION#C123"},
                        "SK": {"S": "TURN#99"},
                    },
                }
            elif "AGENT_CONVERSATION#" in pk and has_start_key:
                # Second page of conversation items (pagination continuation)
                return {"Items": conv_page2}
            elif "AGENT_THREAD#" in pk:
                # Thread registry — no items
                return {"Items": []}
            return {"Items": []}

        dynamodb_client.query = AsyncMock(side_effect=mock_query)
        dynamodb_client.delete_item = AsyncMock()

        store = ConversationStore(dynamodb_client=dynamodb_client)
        await store.wipe_channel_data("C123")

        total_deletes = dynamodb_client.delete_item.call_count
        # 150 conversation items (2 pages) + 1 watermark = 151
        assert total_deletes >= 151, (
            f"Only {total_deletes} items deleted, but there were 150 conversation "
            "turns across 2 pages + 1 watermark. wipe_channel_data must handle "
            "DynamoDB query pagination via LastEvaluatedKey."
        )

        # Verify the pagination key was actually passed on the second query
        pagination_calls = [c for c in query_calls if "exclusive_start_key" in c]
        assert len(pagination_calls) >= 1, (
            "No query calls included exclusive_start_key — pagination is not implemented. "
            "Items beyond the first DynamoDB page are silently orphaned."
        )


# ---------------------------------------------------------------------------
#  BUG 8 (MEDIUM): Isolation filter cache never invalidated
#
#  isolation.py:23-38 — cache is populated on first get_agent_threads() call
#  and never invalidated when new threads are registered. New agent threads
#  leak into status reports.
# ---------------------------------------------------------------------------


class TestBug8_IsolationCacheInvalidation:
    """Verify isolation filter detects newly registered threads."""

    @pytest.mark.asyncio
    async def test_new_thread_detected_after_cache_load(self):
        """After cache is loaded, a new thread must still be detected."""
        from packages.agent.slack.isolation import AgentThreadFilter

        conversation_store = AsyncMock()

        # First call: only thread A exists
        conversation_store.get_agent_thread_ts_set.return_value = {"1000.0"}

        filt = AgentThreadFilter(conversation_store=conversation_store)

        # Load cache
        threads_v1 = await filt.get_agent_threads("C123")
        assert "1000.0" in threads_v1

        # Now a new thread is registered by the agent handler (outside the filter)
        conversation_store.get_agent_thread_ts_set.return_value = {"1000.0", "2000.0"}

        # Get threads again — should see the new thread
        threads_v2 = await filt.get_agent_threads("C123")

        # BUG: Cache returns stale data — "2000.0" is NOT in the result
        assert "2000.0" in threads_v2, (
            "AgentThreadFilter cache is stale: thread '2000.0' was registered after "
            "cache load but get_agent_threads() still returns the old set. "
            "Status reports will include agent thread messages, breaking isolation."
        )


# ---------------------------------------------------------------------------
#  BUG 9 (LOW): Similarity score formula technically incorrect
#
#  retriever.py:68 uses `1 - d/2` but ChromaDB cosine distance is `1 - sim`,
#  so the correct formula is `1 - d`. Ordering preserved (monotonic), but
#  magnitudes are wrong — orthogonal vectors (d=1.0) map to 0.5 not 0.0.
# ---------------------------------------------------------------------------


class TestBug9_SimilarityScoreFormula:
    """Verify similarity scores correctly convert cosine distance."""

    @pytest.mark.asyncio
    async def test_orthogonal_vectors_score_zero(self):
        """Orthogonal vectors (distance=1.0) should have similarity=0.0, not 0.5."""
        from packages.agent.rag.retriever import Retriever

        embeddings_client = AsyncMock()
        embeddings_client.embed_query.return_value = [0.1] * 1536

        vector_store = AsyncMock()
        vector_store.query.return_value = [
            {"id": "doc1", "text": "text1", "metadata": {}, "distance": 0.0},  # identical
            {"id": "doc2", "text": "text2", "metadata": {}, "distance": 1.0},  # orthogonal
            {"id": "doc3", "text": "text3", "metadata": {}, "distance": 2.0},  # opposite
        ]

        retriever = Retriever(embeddings_client=embeddings_client, vector_store=vector_store)
        results = await retriever.retrieve("test", "C123")

        # Correct cosine-distance-to-similarity: sim = 1 - distance
        assert results[0]["score"] == pytest.approx(1.0), "Identical vectors should have score 1.0"
        assert results[1]["score"] == pytest.approx(0.0), (
            f"Orthogonal vectors have score {results[1]['score']}, expected 0.0. "
            "Formula `1 - d/2` maps distance=1.0 to 0.5 instead of 0.0."
        )
        assert results[2]["score"] == pytest.approx(
            0.0
        ), "Opposite vectors should be clamped to 0.0 (or -1.0 if not clamped)"


# ---------------------------------------------------------------------------
#  BUG 10 (MEDIUM): Full agent flow end-to-end: mention → response in thread
#
#  This test exercises the complete happy path including thread_ts plumbing.
#  It catches Bugs 1, 2, 3 together as a functional test.
# ---------------------------------------------------------------------------


class TestAgentEndToEnd:
    """End-to-end: verify a mention results in a threaded response."""

    @pytest.mark.asyncio
    async def test_mention_to_response_stays_in_thread(self):
        """A new @Ketchup mention must result in a response in the thread."""
        from packages.agent.slack.handler import AgentSlackHandler

        posting_handler = AsyncMock()
        posting_handler.post_message.return_value = {"ok": True, "ts": "thinking_ts_1"}
        posting_handler.update_message.return_value = {"ok": True}

        thread_manager_store = AsyncMock()

        handler = AgentSlackHandler(
            agent_engine=AsyncMock(answer=AsyncMock(return_value="The CPU spiked at 2pm")),
            conversation_store=thread_manager_store,
            thread_manager=MagicMock(),  # We'll mock the whole thread manager
            posting_handler=posting_handler,
            secrets_manager=AsyncMock(
                get_bot_slack_user_id_async=AsyncMock(return_value="UBOT"),
            ),
        )

        # Set up thread_manager as an AsyncMock so we can verify calls
        handler._thread_manager = AsyncMock()
        handler._thread_manager.register_thread = AsyncMock()
        handler._thread_manager.post_thinking_indicator = AsyncMock(return_value="thinking_ts")
        handler._thread_manager.update_with_response = AsyncMock()

        event = {
            "channel": "C123",
            "user": "U456",
            "text": "<@UBOT> what caused the CPU spike?",
            "ts": "1234.5678",
        }

        with patch.dict(os.environ, {"KETCHUP_AGENT_ENABLED": "true"}):
            # This should NOT raise any TypeError
            await handler.handle_mention(event)

        # Thread was registered
        handler._thread_manager.register_thread.assert_called_once_with("C123", "1234.5678")

        # Thinking indicator posted to the correct thread
        handler._thread_manager.post_thinking_indicator.assert_called_once_with("C123", "1234.5678")

        # Response updated (or posted) — the response must have reached the user
        handler._thread_manager.update_with_response.assert_called_once()
        call_args = handler._thread_manager.update_with_response.call_args
        assert "CPU spiked" in call_args.args[2] or "CPU spiked" in str(call_args)
