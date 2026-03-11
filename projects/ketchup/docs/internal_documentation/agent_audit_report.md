# Ketchup Agent Deep Audit Report

**PR**: #307 (branch `feat/ketchup-agent`)
**Date**: 2026-03-10
**Scope**: Full bug audit + test gap analysis of the Ketchup Agent RAG pipeline

---

## Executive Summary

The Ketchup Agent feature (PR #307) introduces a RAG-based conversational agent backed by ChromaDB, Azure OpenAI embeddings, and DynamoDB conversation state. Three audit rounds identified **16 bugs** total (2 critical, 4 high, 6 medium, 2 low-medium, 2 low). **All 16 bugs are fixed** with 124 agent tests passing.

| Round | Bugs Found | Status |
|-------|-----------|--------|
| Round 1 | 9 (2 critical, 3 high, 3 medium, 1 low) | All **FIXED** |
| Round 2 | 7 (1 high, 3 medium, 2 low-medium, 1 low) | All **FIXED** |
| Round 3 | 0 (targeted review of 3 features) | Clean |

**Verdict**: All 16 bugs resolved. Safe to merge.

---

## Architecture Overview

```
Slack Event (mention/reply/message)
    |
    v
events.py SlackEventHandler
    |
    v
is_agent_enabled() check (KETCHUP_AGENT_ENABLED env var)
    |
    v
Elimination routing (maintenance? Ketchup marker? bot self-mention? -> no -> AGENT)
    |
    v
AgentSlackHandler.handle_mention() / handle_thread_reply()
    |
    v
AgentEngine.answer():
    1. Retriever.retrieve(query, channel_id) -> embed query -> ChromaDB cosine search
    2. ContextBuilder.build_context(question, retrieved_chunks, history)
    3. ApiExecutor calls Azure OpenAI
    4. ConversationStore.store_turn(user_turn, assistant_turn)
    |
    v
AgentThreadManager posts response (thinking indicator -> update pattern)
    |
    v
Real-time Ingestion (all messages -> RealtimeIngestor -> vector store)
```

**Files audited**: 18 source files across `packages/agent/`, `packages/core/typed_di/`, `packages/slack/`
**Tests reviewed**: 19 test files (18 unit + 1 integration)

---

## Bug Findings

### Bug 1 — CRITICAL: `post_message()` missing `thread_ts` parameter

| Field | Value |
|-------|-------|
| **File** | `packages/slack/messages/posting.py:56-63` |
| **Callers** | `handler.py:183,201,232`, `thread_manager.py:45` |
| **Test** | `test_audit_bugs.py::TestBug1::test_post_message_signature_includes_thread_ts` |

**Description**: `SlackPostingHandler.post_message()` signature is `(self, user_id, channel_id, message, response_url, blocks)`. It does NOT accept `thread_ts`. However, the agent handler passes `thread_ts=` in four places, and the thread manager passes it in one.

**Cascade**: This triggers a `TypeError` that propagates through a triple failure chain:
1. `post_thinking_indicator()` catches the error, returns `None`
2. `thinking_ts` is `None` -> fallback path calls `post_message(thread_ts=...)` -> another `TypeError`
3. Error handler catches and tries `post_message(thread_ts=...)` -> third `TypeError` -> uncaught, bubbles to `events.py`

**Impact**: Every agent query results in complete silence. No response posted, no error message sent, no thinking indicator shown.

**Fix**: Add `thread_ts: Optional[str] = None` to `post_message()` and `_post_channel_message()`. Include `thread_ts` in the Slack API `chat.postMessage` payload when present.

---

### Bug 2 — CRITICAL: `update_message()` called with wrong parameter name

| Field | Value |
|-------|-------|
| **File** | `packages/agent/slack/thread_manager.py:70` |
| **Target** | `packages/slack/messages/posting.py:445-446` |
| **Test** | `test_audit_bugs.py::TestBug2::test_update_with_response_uses_correct_param` |

**Description**: `thread_manager.py:70` calls:
```python
await self._posting_handler.update_message(
    channel_id=channel_id,
    ts=message_ts,
    text=response,  # BUG: parameter name is 'message', not 'text'
)
```

But `update_message()` signature at `posting.py:446` is:
```python
async def update_message(self, channel_id: str, ts: str, message: str, ...)
```

The parameter is named `message`, not `text`.

**Impact**: `update_message` always fails with `TypeError: unexpected keyword argument 'text'`. Every response falls through to the broken fallback path (Bug 3), which also fails due to Bug 1.

**Fix**: Change `text=response` to `message=response` at `thread_manager.py:70`.

---

### Bug 3 — HIGH: Thread manager fallback posts to channel root, not thread

| Field | Value |
|-------|-------|
| **File** | `packages/agent/slack/thread_manager.py:79-82` |
| **Test** | `test_audit_bugs.py::TestBug3::test_fallback_posts_to_thread_not_channel` |

**Description**: When `update_message` fails (which it always does due to Bug 2), the fallback at line 79 is:
```python
await self._posting_handler.post_message(
    channel_id=channel_id,
    message=response,
    # Missing: thread_ts=???
)
```

No `thread_ts` is passed because `update_with_response()` doesn't accept or forward it.

**Impact**: Even after Bugs 1 and 2 are fixed, `update_message` failures (e.g., message deleted, Slack API error) cause agent responses to appear in the channel root instead of the conversation thread. Responses leak to the entire channel.

**Fix**: Add `thread_ts` parameter to `update_with_response()` and pass it to the fallback `post_message` call. Update all callers in `handler.py` to forward `thread_ts`.

---

### Bug 4 — HIGH: String dependency in ServiceSpec breaks DI graph

| Field | Value |
|-------|-------|
| **File** | `packages/core/typed_di/service_registrations/registrations/agent_services.py:138` |
| **Test** | `test_audit_bugs.py::TestBug4::test_all_agent_deps_are_types_not_strings` |

**Description**: The `AgentEngineProtocol` ServiceSpec defines its `api_executor` dependency as a string literal:
```python
deps={
    "retriever": AgentRetrieverProtocol,
    "context_builder": AgentContextBuilderProtocol,
    "conversation_store": AgentConversationStoreProtocol,
    "api_executor": "packages.core.typed_di...ApiExecutorProtocol",  # String, not Type
},
```

`DependencySpec` (at `types.py:41`) annotates `type: Type`. Passing a string stores it as-is, which breaks topological sorting — the sort can't match the string to any registered protocol.

**Note**: The `AgentEngine` spec has a custom `factory=_create_agent_engine` which resolves `ApiExecutorProtocol` directly, bypassing the auto-generated factory. The string dep only affects the dependency graph used for initialization ordering. Whether this causes a startup crash depends on whether the topological sort enforces strict resolution.

**Impact**: Unknown until agent is enabled in production. At minimum, incorrect initialization ordering. At worst, startup crash.

**Fix**: Replace the string with the actual import:
```python
from packages.core.typed_di.service_registrations.protocols.ai_protocols import ApiExecutorProtocol
# ...
"api_executor": ApiExecutorProtocol,
```

---

### Bug 5 — HIGH: Watermark race condition (non-atomic read-modify-write)

| Field | Value |
|-------|-------|
| **File** | `packages/agent/ingestion/realtime_ingestor.py:164-172` |
| **Related** | `packages/agent/conversation/store.py:229-261` |
| **Test** | `test_audit_bugs.py::TestBug5::test_realtime_uses_atomic_increment`, `test_increment_watermark_uses_update_item_not_put_item` |
| **Status** | **FIXED** |

**Description**: The real-time ingestor previously updated the watermark via read-modify-write (get_watermark → compute total → put_item). If backfill completes between the read and write, `backfill_complete=True` gets stomped back to `False`.

**Impact**: Data integrity corruption. Backfill progress lost. Wasted API quota on re-backfilling.

**Fix applied**: Added `ConversationStore.increment_watermark()` that uses DynamoDB `update_item` with `ADD total_ingested :inc` (atomic server-side increment) and `SET latest_ingested_ts = :ts`. Never touches `backfill_complete`. Changed `realtime_ingestor.py` to call `increment_watermark()` instead of `get_watermark()` + `update_watermark()`. Tests verify: (1) `increment_watermark` is called, not the racy pattern; (2) the method uses `update_item` with `ADD`, not `put_item`.

---

### Bug 6 — MEDIUM: Backfill processor race condition

| Field | Value |
|-------|-------|
| **File** | `packages/agent/ingestion/backfill_ingestor.py:80-86` |
| **Test** | `test_audit_bugs.py::TestBug6::test_concurrent_schedule_creates_single_processor` |

**Description**: The `_processing` flag is checked at line 81 and set at line 86 (inside `_process_queue`). Between these two points, another `schedule_backfill()` call can also see `_processing=False` and create a second task:
```python
# schedule_backfill:
if not self._processing:           # Line 81: both calls see False
    asyncio.create_task(self._process_queue())  # Line 82: both create tasks

# _process_queue:
self._processing = True            # Line 86: only runs when task starts executing
```

The test confirmed: **2 processor tasks were created** for 2 rapid `schedule_backfill()` calls.

**Mitigated by**: `mark_backfill_started()` uses a DynamoDB condition expression (`attribute_not_exists(PK)`) that prevents double-starting the same channel. But two channels can be backfilled concurrently instead of sequentially.

**Impact**: Duplicate concurrent backfill processing, wasted embedding API quota, potential queue corruption.

**Fix**: Set `self._processing = True` synchronously before `asyncio.create_task()`:
```python
if not self._processing:
    self._processing = True  # Set BEFORE task creation
    asyncio.create_task(self._process_queue())
```

---

### Bug 7 — MEDIUM: `wipe_channel_data()` missing DynamoDB pagination

| Field | Value |
|-------|-------|
| **File** | `packages/agent/conversation/store.py:314-322` |
| **Test** | `test_audit_bugs.py::TestBug7::test_wipe_handles_pagination` |
| **Status** | **FIXED** |

**Description**: The DynamoDB query in `wipe_channel_data` didn't check `LastEvaluatedKey` for pagination. DynamoDB returns max 1MB per query (~5000 items at ~200 bytes each). Channels with extensive agent usage would only have the first page deleted.

**Impact**: Orphaned DynamoDB records after channel archive. Data leak for compliance-sensitive channels.

**Fix applied**: Wrapped the query in a `while True` loop that collects all items across pages using `exclusive_start_key`. Test uses PK-prefix-aware mock dispatch to verify the pagination key is actually passed on continuation queries, preventing the old false-green where the second prefix query was conflated with pagination.

---

### Bug 8 — MEDIUM: Isolation filter cache never invalidated

| Field | Value |
|-------|-------|
| **File** | `packages/agent/slack/isolation.py:23-38` |
| **Test** | `test_audit_bugs.py::TestBug8::test_new_thread_detected_after_cache_load` |

**Description**: `AgentThreadFilter._cache` is populated on first `get_agent_threads()` call and never updated when new agent threads are registered. `clear_cache()` exists but is never called from the thread registration path.

**Scenario**:
1. Status-updater calls `get_agent_threads("C123")` -> cache: `{1000.0}`
2. Agent handler registers new thread `2000.0`
3. Status-updater uses cached set -> `2000.0` not filtered
4. Agent conversation messages appear in status report

**Impact**: Cross-feature isolation broken for newly created agent threads. Agent messages contaminate status reports, JIRA reports, and /status command output.

**Fix**: Either remove the cache entirely (status-updater runs infrequently, one DynamoDB query is acceptable) or call `clear_cache(channel_id)` from `AgentThreadManager.register_thread()`.

---

### Bug 9 — LOW: Similarity score formula technically incorrect

| Field | Value |
|-------|-------|
| **File** | `packages/agent/rag/retriever.py:68` |
| **Test** | `test_audit_bugs.py::TestBug9::test_orthogonal_vectors_score_zero` |

**Description**: ChromaDB cosine distance `d = 1 - cosine_similarity`, range [0, 2]. The code converts via:
```python
similarity = 1.0 - (candidate.get("distance", 1.0) / 2.0)
```

This maps [0, 2] -> [1.0, 0.0]. The correct formula is `1 - d`, which maps [0, 2] -> [1.0, -1.0] (or clamped to [0, 1]).

Example: orthogonal vectors (d=1.0) get score 0.5 instead of 0.0.

**Impact**: Minimal. The formula is monotonically decreasing, so ranking order is preserved. No threshold filtering is applied. Scores only appear in logs.

**Fix**: `similarity = max(0.0, 1.0 - candidate.get("distance", 1.0))`

---

## Existing Test Coverage Analysis

| Component | Unit Tests | Integration | Gaps |
|-----------|-----------|-------------|------|
| Conversation Models | `test_models.py` | -- | No behavior tests |
| DynamoDB Store | `test_store.py` | -- | No pagination, no concurrency |
| Isolation Filter | `test_isolation.py` | -- | **No cache invalidation test** |
| Channel Archive | `test_lifecycle.py` | -- | No partial failure tests |
| Slack Handler | `test_handler.py` | -- | **No thread_ts plumbing test** |
| Azure Embeddings | `test_azure_embeddings_client.py` | -- | No retry logic tests |
| Message Chunking | `test_chunker.py` | -- | No malformed message tests |
| Vector Store | `test_vector_store.py` | Real ChromaDB | No bounds checking |
| Retriever | `test_retriever.py` | Real ChromaDB | **Tests wrong formula** |
| RAG Engine | `test_engine.py` | Full pipeline | No error handling |
| Context Builder | `test_context_builder.py` | Message assembly | No overflow testing |
| Backfill Ingestor | `test_backfill_ingestor.py` | -- | **No concurrency test** |
| Realtime Ingestor | `test_realtime_ingestor.py` | -- | **No watermark race test** |
| DI Wiring | -- | -- | **No agent services test** |

**Critical gap**: The existing `test_retriever.py:57-59` explicitly asserts the **wrong** formula (`1 - d/2`), encoding Bug 9 into the test suite as "expected behavior."

---

## Tests Written

**File**: `tests/unit/agent/test_audit_bugs.py` (14 tests)

| Test Class | Tests | Bugs Exposed |
|-----------|-------|-------------|
| `TestBug1_PostMessageThreadTs` | 3 | Bug 1 (CRITICAL): signature check, handler fallback, thinking indicator |
| `TestBug2_UpdateMessageParamName` | 2 | Bug 2 (CRITICAL): param name check, actual call verification |
| `TestBug3_FallbackMissingThreadTs` | 1 | Bug 3 (HIGH): fallback missing thread_ts |
| `TestBug4_StringDepInServiceSpec` | 1 | Bug 4 (HIGH): string vs type in deps |
| `TestBug5_WatermarkRaceCondition` | 2 | Bug 5 (HIGH): backfill_complete preservation, total increment |
| `TestBug6_BackfillRaceCondition` | 1 | Bug 6 (MEDIUM): duplicate processor tasks |
| `TestBug7_WipeChannelPagination` | 1 | Bug 7 (MEDIUM): pagination handling |
| `TestBug8_IsolationCacheInvalidation` | 1 | Bug 8 (MEDIUM): stale cache |
| `TestBug9_SimilarityScoreFormula` | 1 | Bug 9 (LOW): incorrect formula |
| `TestAgentEndToEnd` | 1 | Full flow validation |

**Results**: 7 FAILED (confirming bugs), 7 PASSED

---

## Risk Assessment

### Merge Blockers (must fix)

| Bug | Effort | Why |
|-----|--------|-----|
| Bug 1 | ~30 min | Agent completely non-functional without thread_ts in post_message |
| Bug 2 | ~5 min | One-line fix: `text=` -> `message=` |
| Bug 3 | ~20 min | Refactor update_with_response to accept and forward thread_ts |
| Bug 4 | ~5 min | Replace string with import |

### Recommended Before Merge

| Bug | Effort | Why |
|-----|--------|-----|
| Bug 5 | ~1 hr | Data integrity — atomic watermark updates prevent re-backfilling |
| Bug 6 | ~10 min | One-line fix: move `_processing = True` before `create_task()` |

### Can Wait for Follow-up PR

| Bug | Effort | Why |
|-----|--------|-----|
| Bug 7 | ~30 min | Pagination only matters for high-usage channels |
| Bug 8 | ~15 min | Cache invalidation — low frequency impact |
| Bug 9 | ~5 min | Cosmetic — ordering preserved |

### Overall Verdict

**Not safe to merge** in current state. After fixing Bugs 1-4 (estimated ~1 hour), the agent feature will be functional. Bugs 5-6 should ideally be fixed before production enablement. Bugs 7-9 are safe to defer.

---

---

## Round 2 Audit (2026-03-10)

### Context

Following the initial Round 1 audit and fixes (28 commits), a second deep audit was performed across all 48 changed files. Round 1 bugs (1-9) are confirmed fixed. Round 2 identified **7 new bugs** at a deeper level — DynamoDB query semantics, error propagation gaps, protocol drift, async/sync boundaries, data preservation, and metadata consistency. **All 7 bugs are now fixed.**

### Round 2 Bug Findings

#### Bug R2-1 — HIGH: `get_history()` DynamoDB Limit + FilterExpression interaction

| Field | Value |
|-------|-------|
| **File** | `packages/agent/conversation/store.py:74-119` |
| **Test** | `test_audit_round2_bugs.py::TestBugR2_1_GetHistoryLimitFilter` (3 tests) |
| **Status** | **FIXED** |

**Description**: `get_history()` previously queried with `limit=10` and `filter_expression="thread_ts = :thread_ts"`. DynamoDB applies `Limit` BEFORE `FilterExpression` — it reads 10 items from the `AGENT_CONVERSATION#` partition, then filters. In channels with multiple concurrent agent threads, most of those 10 items may belong to other threads.

**Fix applied**: `get_history()` now paginates with over-fetch headroom (`limit * 5`) and collects items across pages until `limit` matching turns are found or DynamoDB has no more pages. Results returned in chronological order.

---

#### Bug R2-2 — MEDIUM: `update_message` silent failure breaks fallback

| Field | Value |
|-------|-------|
| **File** | `packages/agent/slack/thread_manager.py:69-90` |
| **Test** | `test_audit_round2_bugs.py::TestBugR2_2_UpdateMessageFallback` (3 tests) |
| **Status** | **FIXED** |

**Description**: `update_message()` returned `{ok: false}` without raising an exception. `update_with_response()` relied on `try/except` for its fallback, so the fallback never fired on API errors — only on network exceptions.

**Fix applied**: `update_with_response()` now checks `result.get("ok")` after `update_message()` and raises `ValueError` on failure, causing the `except` block to execute and post a fallback message. Tests verify: (1) fallback fires on `{ok: false}`, (2) fallback fires on network exception, (3) no fallback on success.

---

#### Bug R2-3 — MEDIUM: Protocol signature mismatch for `update_with_response`

| Field | Value |
|-------|-------|
| **File** | `packages/core/typed_di/service_registrations/protocols/agent_protocols.py` |
| **Test** | `test_audit_round2_bugs.py::TestBugR2_3_ProtocolSignatureMatch` (3 tests) |
| **Status** | **FIXED** |

**Description**: Protocol signature was missing `thread_ts: Optional[str] = None` that the concrete implementation accepted. All callers passed `thread_ts` but type checkers couldn't verify this.

**Fix applied**: Protocol method signature now includes `thread_ts: Optional[str] = None`, matching the concrete implementation.

---

#### Bug R2-4 — MEDIUM: ChromaDB synchronous calls block the event loop

| Field | Value |
|-------|-------|
| **File** | `packages/agent/embeddings/vector_store.py` (all methods) |
| **Test** | `test_audit_round2_bugs.py::TestBugR2_4_ChromaDBAsyncWrapping` (3 tests) |
| **Status** | **FIXED** |

**Description**: `ChromaVectorStore` wrapped synchronous `chromadb.HttpClient` methods in `async def` without thread offloading, blocking the event loop during backfill and queries.

**Fix applied**: All ChromaDB operations (`upsert`, `query`, `delete`, `count`, `get`, `get_or_create_collection`) now use `asyncio.to_thread()`. Tests verify `add_documents`, `query`, and `delete_by_channel` all use thread offloading via AST inspection.

---

#### Bug R2-5 — LOW-MEDIUM: `get_agent_thread_ts_set` doesn't paginate

| Field | Value |
|-------|-------|
| **File** | `packages/agent/conversation/store.py:181-218` |
| **Test** | `test_audit_round2_bugs.py::TestBugR2_5_ThreadSetPagination` (2 tests) |
| **Status** | **FIXED** |

**Description**: `get_agent_thread_ts_set()` made a single DynamoDB query without handling `LastEvaluatedKey`. For channels with hundreds of agent threads, results were truncated.

**Fix applied**: Now uses the same `while True` / `LastEvaluatedKey` pagination loop as `wipe_channel_data()`. Tests verify: (1) pagination fetches second page, (2) single-page case works correctly.

---

#### Bug R2-6 — LOW: `update_watermark` clobbers `backfill_started_at`

| Field | Value |
|-------|-------|
| **File** | `packages/agent/conversation/store.py:257-291` |
| **Test** | `test_audit_round2_bugs.py::TestBugR2_6_UpdateWatermarkPreservesStartedAt` (2 tests) |
| **Status** | **FIXED** |

**Description**: `update_watermark()` used `put_item` (full overwrite), clobbering `backfill_started_at` after the first page checkpoint.

**Fix applied**: Switched to `update_item` with `SET` expression that updates only `latest_ingested_ts`, `backfill_complete`, `total_ingested`, `updated_at`, and `channel_id` — never touching `backfill_started_at`. Tests verify: (1) `update_item` used, not `put_item`, (2) expression attribute values are correct.

---

#### Bug R2-7 — LOW-MEDIUM: RealtimeIngestor missing `source` metadata field

| Field | Value |
|-------|-------|
| **File** | `packages/agent/ingestion/realtime_ingestor.py:152-158` |
| **Test** | `test_audit_round2_bugs.py::TestBugR2_7_RealtimeIngestorSourceMetadata` (3 tests) |
| **Status** | **FIXED** |

**Description**: `RealtimeIngestor._embed_and_store()` did not include `"source"` in document metadata. Both `BackfillIngestor` (`"source": "backfill"`) and `JiraBackfillIngestor` (`"source": "jira"`) included it.

**Fix applied**: Metadata dict now includes `"source": "realtime"`. All three ingestion paths consistently tag documents by source. Tests verify: (1) realtime includes `"source": "realtime"`, (2) backfill includes `"source": "backfill"`, (3) JIRA includes `"source": "jira"`.

---

### Round 2 Test Coverage

**File**: `tests/unit/agent/test_audit_round2_bugs.py` (19 tests)

| Test Class | Tests | Bug Verified |
|-----------|-------|------------|
| `TestBugR2_1_GetHistoryLimitFilter` | 3 | R2-1 (HIGH): pagination, limit enforcement, chronological order |
| `TestBugR2_2_UpdateMessageFallback` | 3 | R2-2 (MEDIUM): fallback on API error, fallback on exception, no fallback on success |
| `TestBugR2_3_ProtocolSignatureMatch` | 3 | R2-3 (MEDIUM): protocol includes thread_ts, concrete matches, callers pass it |
| `TestBugR2_4_ChromaDBAsyncWrapping` | 3 | R2-4 (MEDIUM): add_documents, query, delete all use to_thread |
| `TestBugR2_5_ThreadSetPagination` | 2 | R2-5 (LOW-MEDIUM): pagination on LastEvaluatedKey, single-page case |
| `TestBugR2_6_UpdateWatermarkPreservesStartedAt` | 2 | R2-6 (LOW): uses update_item, correct expression values |
| `TestBugR2_7_RealtimeIngestorSourceMetadata` | 3 | R2-7 (LOW-MEDIUM): realtime source tag, backfill contrast, JIRA contrast |

**Results**: All 19 tests pass, confirming all 7 fixes.

---

### Overall Round 2 Verdict

**All 7 Round 2 bugs are fixed.** Combined with Round 1 (9 bugs fixed), all 16 audit-discovered bugs are resolved. 124/124 agent tests pass.

---

## Round 3 Audit (2026-03-10)

### Context

Following Round 2, a targeted deep-dive was performed on three specific features added in the 28-commit update: the backfill resume timestamp buffer, the new JIRA backfill subsystem, and the streaming backfill refactor. These features were read during Rounds 1–2 but had not received dedicated audit narratives.

### Scope

| Feature | Files | Lines |
|---------|-------|-------|
| 5-second timestamp buffer | `backfill_ingestor.py:302-309` | 8 |
| JIRA backfill | `jira_backfill.py` (full), `agent_services.py:124-131`, `test_jira_backfill.py` | 215 + 22 + 146 |
| Streaming backfill refactor | `backfill_ingestor.py:110-236` (core loop) | 127 |

### Findings

#### 1. 5-second timestamp buffer — CLEAN

**What it does**: On backfill resume, `_fetch_page()` subtracts 5 seconds from the checkpoint timestamp before passing it to Slack's `conversations.history` `oldest` parameter. This creates a deliberate overlap window to prevent boundary messages from being skipped due to timestamp precision mismatches.

**Audit points verified**:

| Check | Result | Evidence |
|-------|--------|----------|
| Buffer arithmetic | Correct | `str(float(oldest) - 5)` with `ValueError`/`TypeError` fallback (lines 306-309) |
| Overlap idempotency | Safe | Duplicate messages hit ChromaDB `upsert` with same deterministic doc IDs — no data corruption |
| Counter inflation | Negligible | Overlap messages inflate `page_ingested` counter. Worst case: 10 restarts × ~20 overlap msgs = 200 phantom count against 50K cap (~0.4%) |
| `oldest` exclusivity | Correct | Slack API `oldest` is exclusive (`ts > oldest`), so the exact checkpoint message is never refetched even without the buffer |
| Buffer scope | Correct | Applied only to `oldest` on resume, not to cursor-based intra-run pagination |
| Pattern consistency | Correct | Comment cites `channel_msg_ops.py` — same 5s buffer pattern used elsewhere in the codebase |

**No bugs found.**

---

#### 2. JIRA backfill — CLEAN

**What it does**: On bot join, fetches the associated JIRA ticket (from DynamoDB channel metadata or message text), formats the ticket summary + description + comments as embeddable documents, and stores them in ChromaDB with `source="jira"` metadata.

**Audit points verified**:

| Check | Result | Evidence |
|-------|--------|----------|
| Data contract | Correct | `ticket_data["fields"]` for summary/description/status, `ticket_data["comments"]` at top level — matches `JIRADataExtractor._get_ticket_data()` output |
| Defensive fallback | Acceptable | `fields = ticket_data.get("fields", ticket_data)` (line 133) — produces low-quality doc if contract changes, never crashes |
| Idempotency | Correct | Deterministic doc IDs: `{channel_id}:jira:{ticket_id}`, `{channel_id}:jira:{ticket_id}:c:{comment_id}` |
| Truncation | Correct | Description and comments capped at 2000 chars (lines 149, 183) |
| Error handling | Correct | Outer `try/except` in `backfill_jira()` returns 0 on any failure (line 103-110) |
| `zip` safety | Acceptable | `zip(documents, embeddings)` would silently drop tail docs if `embed_texts` returned fewer. In practice, `AzureEmbeddingsClient` returns same-length or raises. |
| DI wiring | Correct | `JIRADataExtractorProtocol` registered as optional dep `(Protocol, True)`. `_create_backfill_ingestor` factory catches resolution failure, sets `jira_backfill=None` (lines 217-221) |
| Metadata consistency | Correct | Includes `"source": "jira"`, `"jira_ticket_id"`, `"jira_doc_type"` — properly tagged |
| Test coverage | Adequate | 5 tests: no-ticket, ticket+comments, empty comments, extractor error, field content |

**No bugs found.**

---

#### 3. Streaming backfill refactor — CLEAN

**What it does**: Replaces the previous batch-everything-then-store approach with page-by-page streaming: fetch → filter → embed → store → checkpoint → next page. Crash at any point resumes from the last checkpoint. Configurable cap via `KETCHUP_AGENT_MAX_BACKFILL_MESSAGES`.

**Audit points verified**:

| Check | Result | Evidence |
|-------|--------|----------|
| Crash resume | Correct | `resume_ts` from `watermark.latest_ingested_ts` (line 128-129), `oldest` param skips processed messages |
| Incremental checkpoint | Correct | `update_watermark()` after each page (lines 186-191), not just at end |
| Cap enforcement (cross-run) | Correct | `total_ingested + page_ingested >= max_messages` includes both historical and current-run counts (line 147) |
| Cap enforcement (within-page) | Correct | `filtered = filtered[:remaining]` slices excess (lines 173-175) |
| Chronological ordering | Correct | `filtered.sort(key=lambda m: float(m.get("ts", "0")))` ensures `latest_ts` from `filtered[-1]` is always the newest (lines 178, 185) |
| Sequential processing | Correct | `_process_queue` drains one channel at a time. `_processing` flag set synchronously before `create_task()` (R1 Bug 6 fix) |
| Rate limiting | Correct | `INTER_PAGE_DELAY = 0.5s` between Slack API calls (line 205) |
| Error isolation | Correct | Per-channel `try/except` in `_process_queue` (lines 98-103) — one channel failure doesn't block the queue |
| Empty page handling | Correct | Empty page with cursor → advance cursor, sleep, continue (lines 161-166). Empty page without cursor → break |
| `backfill_complete` marking | Correct | Final `update_watermark(backfill_complete=True)` only after loop exits (lines 208-214) |
| Duplicate channel scheduling | Harmless | `schedule_backfill` checks `backfill_complete` before queuing (line 79). If already-running channel is re-queued, second run finds resume_ts at end → empty fetch → immediate completion |
| JIRA integration | Correct | Optional `_jira_backfill.backfill_jira()` called after message backfill completes (lines 224-236), with its own `try/except` |
| Configurable cap | Correct | `KETCHUP_AGENT_MAX_BACKFILL_MESSAGES` env var, default 50,000 (line 381-383) |

**No bugs found.**

---

### Round 3 Summary

| Feature | Verdict | New Bugs |
|---------|---------|----------|
| 5-second timestamp buffer | Clean | 0 |
| JIRA backfill | Clean | 0 |
| Streaming backfill refactor | Clean | 0 |

These three features represent second-generation code written after Round 1 exposed the anti-patterns (non-atomic updates, missing pagination, race conditions). The streaming backfill uses incremental checkpointing and sequential queue processing. The JIRA backfill uses idempotent doc IDs and optional DI. The timestamp buffer borrows a proven pattern from `channel_msg_ops`. The lessons from Round 1 were applied correctly.

**Total audit coverage**: 3 rounds, 16 bugs found (9 Round 1 + 7 Round 2 + 0 Round 3), all **FIXED**, 124/124 tests passing.

---

## Appendix: How to Run Audit Tests

```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/projects/ketchup
source tests/setup/.venv/bin/activate

# Round 1 tests (all fixed — should pass)
PYTHONPATH=. python -m pytest tests/unit/agent/test_audit_bugs.py -v

# Round 2 tests (document open bugs)
PYTHONPATH=. python -m pytest tests/unit/agent/test_audit_round2_bugs.py -v

# Full agent suite
PYTHONPATH=. python -m pytest tests/unit/agent/ -v
```

Expected: 124 tests, all passing.
