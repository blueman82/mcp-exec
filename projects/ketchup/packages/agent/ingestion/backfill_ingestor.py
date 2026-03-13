"""Backfill ingestor — fetches and indexes all historical messages for a channel.

Streams page-by-page: each page is fetched, filtered, embedded, stored, and
checkpointed before moving to the next. Crash at any point resumes from the
last checkpoint (watermark.latest_ingested_ts), not from zero.

Configurable message cap via KETCHUP_AGENT_MAX_BACKFILL_MESSAGES (default 50000).
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from packages.agent.embeddings.chunker import format_messages
from packages.agent.ingestion.realtime_ingestor import FILTERED_SYSTEM_SUBTYPES
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Hard constraints (API rate limits, not heuristics)
MESSAGES_PER_PAGE = 200
EMBEDDING_BATCH_SIZE = 16
MAX_CONCURRENT_EMBEDDINGS = 2
INTER_PAGE_DELAY = 0.5  # seconds between pagination requests (Slack rate limit)
DEFAULT_MAX_BACKFILL_MESSAGES = 50_000


class BackfillIngestor:
    """Backfills historical messages for a channel into the vector store.

    Streams page-by-page with incremental checkpointing. On restart after
    a crash, resumes from the watermark's latest_ingested_ts rather than
    re-processing the entire channel.
    """

    def __init__(
        self,
        embeddings_client: Any,
        vector_store: Any,
        conversation_store: Any,
        posting_handler: Any,
        bot_user_id: str,
        jira_backfill_ingestor: Any | None = None,
    ) -> None:
        self._embeddings_client = embeddings_client
        self._vector_store = vector_store
        self._conversation_store = conversation_store
        self._posting_handler = posting_handler
        self._bot_user_id = bot_user_id
        self._jira_backfill = jira_backfill_ingestor
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_EMBEDDINGS)

        # Queue for sequential backfill processing
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing = False

        # Completion events — allows callers to await backfill for a channel
        self._completion_events: dict[str, asyncio.Event] = {}

    async def schedule_backfill(self, channel_id: str) -> None:
        """Schedule a channel for backfill processing.

        Checks if backfill is already complete before scheduling.
        """
        if not self._is_backfill_enabled():
            logger.info("Agent backfill disabled, skipping channel %s", channel_id)
            return

        watermark = await self._conversation_store.get_watermark(channel_id)
        if watermark and watermark.backfill_complete:
            logger.info("Channel %s already backfilled, skipping", channel_id)
            return

        logger.info("Scheduling backfill for channel %s", channel_id)

        # Create completion event before queuing so callers can await it
        if channel_id not in self._completion_events:
            self._completion_events[channel_id] = asyncio.Event()

        await self._queue.put(channel_id)

        # Set flag synchronously before creating task (Bug 6 fix)
        if not self._processing:
            self._processing = True
            asyncio.create_task(self._process_queue())

    async def wait_for_backfill(self, channel_id: str, timeout: float = 120.0) -> bool:
        """Wait for a channel's backfill to complete.

        Returns True if backfill completed within timeout, False otherwise.
        """
        watermark = await self._conversation_store.get_watermark(channel_id)
        if watermark and watermark.backfill_complete:
            return True

        event = self._completion_events.get(channel_id)
        if not event:
            return False

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(
                "Backfill wait timed out for %s after %.0fs",
                channel_id,
                timeout,
            )
            return False

    async def _process_queue(self) -> None:
        try:
            while not self._queue.empty():
                channel_id = await self._queue.get()
                try:
                    await self._backfill_channel(channel_id)
                except Exception as e:
                    logger.error(
                        "Backfill failed for channel %s: %s",
                        channel_id,
                        e,
                        exc_info=True,
                    )
                finally:
                    # Signal completion (success or failure) so waiters unblock
                    event = self._completion_events.pop(channel_id, None)
                    if event:
                        event.set()
                    self._queue.task_done()
        finally:
            self._processing = False

    async def _backfill_channel(self, channel_id: str) -> None:
        """Execute streaming backfill for a single channel.

        Streams page-by-page: fetch → filter → embed → store → checkpoint.
        Resumes from watermark on restart. Stops at message cap.
        """
        max_messages = self._get_max_backfill_messages()
        logger.info(
            "Starting backfill for channel %s (cap: %d messages)",
            channel_id,
            max_messages,
        )

        watermark = await self._conversation_store.get_watermark(channel_id)
        resume_ts: str | None = None
        total_ingested = 0

        if watermark and watermark.latest_ingested_ts != "0":
            resume_ts = watermark.latest_ingested_ts
            total_ingested = watermark.total_ingested or 0
            logger.info(
                "Resuming backfill for %s from ts=%s (%d already ingested)",
                channel_id,
                resume_ts,
                total_ingested,
            )
        else:
            await self._conversation_store.mark_backfill_started(channel_id)

        cursor: str | None = None
        page_count = 0
        page_ingested = 0
        latest_ts = resume_ts or "0"

        while True:
            # Check message cap (total across all runs)
            if total_ingested + page_ingested >= max_messages:
                logger.info(
                    "Backfill cap reached for %s: %d messages (limit: %d)",
                    channel_id,
                    total_ingested + page_ingested,
                    max_messages,
                )
                break

            messages, next_cursor = await self._fetch_page(
                channel_id,
                cursor,
                oldest=resume_ts,
            )

            if not messages:
                if not next_cursor:
                    break
                cursor = next_cursor
                await asyncio.sleep(INTER_PAGE_DELAY)
                continue

            filtered = self._filter_messages(messages)
            page_count += 1

            # Fetch thread replies for messages with replies
            thread_budget = max_messages - (total_ingested + page_ingested + len(filtered))
            thread_replies = await self._collect_thread_replies(
                channel_id,
                messages,
                thread_budget,
            )

            # Deduplicate by ts — broadcast replies appear in both history and threads
            all_messages = list({m.get("ts", ""): m for m in filtered + thread_replies}.values())

            if all_messages:
                # Enforce cap within page
                remaining = max_messages - (total_ingested + page_ingested)
                all_messages = all_messages[:remaining]

                # Sort chronologically within page
                all_messages.sort(key=lambda m: float(m.get("ts", "0")))

                stored = await self._embed_and_store_page(all_messages, channel_id)
                page_ingested += stored

                # Checkpoint: update watermark after each page
                latest_ts = all_messages[-1].get("ts", "0")
                await self._conversation_store.update_watermark(
                    channel_id=channel_id,
                    latest_ts=latest_ts,
                    total_ingested=total_ingested + page_ingested,
                    backfill_complete=False,
                )

            logger.info(
                "Backfill page %d for %s: %d raw, %d filtered, %d thread replies, %d stored this run",
                page_count,
                channel_id,
                len(messages),
                len(filtered),
                len(thread_replies),
                page_ingested,
            )

            if not next_cursor:
                break
            cursor = next_cursor
            await asyncio.sleep(INTER_PAGE_DELAY)

        # Mark complete
        final_total = total_ingested + page_ingested
        await self._conversation_store.update_watermark(
            channel_id=channel_id,
            latest_ts=latest_ts,
            total_ingested=final_total,
            backfill_complete=True,
        )

        logger.info(
            "Backfill complete for %s: %d messages this run, %d total",
            channel_id,
            page_ingested,
            final_total,
        )

        # JIRA backfill: fetch and embed ticket data for this channel
        if self._jira_backfill:
            try:
                jira_docs = await self._jira_backfill.backfill_jira(channel_id)
                if jira_docs:
                    logger.info(
                        "JIRA backfill added %d documents for %s",
                        jira_docs,
                        channel_id,
                    )
            except Exception as e:
                logger.error(
                    "JIRA backfill failed for %s: %s",
                    channel_id,
                    e,
                    exc_info=True,
                )

    async def _collect_thread_replies(
        self,
        channel_id: str,
        messages: list[dict],
        budget: int,
    ) -> list[dict]:
        """Fetch and filter thread replies for messages with reply_count > 0.

        Args:
            channel_id: The channel ID.
            messages: Raw messages from the current page.
            budget: Maximum number of thread replies to collect.

        Returns:
            Filtered thread reply messages within budget.
        """
        thread_parents = [m for m in messages if m.get("reply_count")]
        collected: list[dict] = []

        for parent in thread_parents:
            remaining = budget - len(collected)
            if remaining <= 0:
                break

            replies = await self._fetch_thread_replies(channel_id, parent["ts"])
            # Exclude parent (already in top-level messages) and apply filters
            replies = self._filter_messages([r for r in replies if r.get("ts") != parent["ts"]])
            collected.extend(replies[:remaining])
            await asyncio.sleep(INTER_PAGE_DELAY)

        return collected

    async def _embed_and_store_page(
        self,
        messages: list[dict],
        channel_id: str,
    ) -> int:
        """Embed and store a page of filtered messages.

        Returns:
            Number of documents stored.
        """
        documents = format_messages(messages, channel_id)
        if not documents:
            return 0

        total_stored = 0
        for i in range(0, len(documents), EMBEDDING_BATCH_SIZE):
            batch = documents[i : i + EMBEDDING_BATCH_SIZE]
            texts = [d.text for d in batch]

            async with self._semaphore:
                embeddings = await self._embeddings_client.embed_texts(texts)

            store_docs = [
                {
                    "id": doc.doc_id,
                    "text": doc.text,
                    "metadata": {
                        "channel_id": doc.channel_id,
                        "message_ts": float(doc.message_ts),
                        "user_id": doc.user_id,
                        "has_thread_replies": doc.has_thread_replies,
                        "ingested_at": int(time.time()),
                        "source": "backfill",
                    },
                }
                for doc in batch
            ]

            await self._vector_store.add_documents(store_docs, embeddings)
            total_stored += len(store_docs)

        return total_stored

    async def _slack_paginated_get(
        self,
        endpoint: str,
        params: dict[str, str],
    ) -> tuple[list[dict], str | None]:
        """Make a single paginated GET to a Slack API endpoint.

        Returns:
            Tuple of (messages list, next cursor or None).
        """
        try:
            response = await self._posting_handler.api_get(endpoint, params)
        except Exception as e:
            logger.error(
                "Error calling %s for %s: %s",
                endpoint,
                params.get("channel", "?"),
                e,
                exc_info=True,
            )
            return [], None

        if not response or not response.get("ok"):
            error = response.get("error", "unknown") if response else "no response"
            logger.warning(
                "%s failed for %s: %s",
                endpoint,
                params.get("channel", "?"),
                error,
            )
            return [], None

        messages = response.get("messages", [])
        next_cursor = response.get("response_metadata", {}).get("next_cursor", "") or None
        return messages, next_cursor

    async def _fetch_page(
        self,
        channel_id: str,
        cursor: str | None = None,
        oldest: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Fetch a page of messages from conversations.history."""
        # Apply 5-second buffer to oldest timestamp (Slack precision mismatches)
        oldest_buffered = oldest
        if oldest and oldest != "0":
            try:
                oldest_buffered = str(float(oldest) - 5)
            except (ValueError, TypeError):
                oldest_buffered = oldest

        params: dict[str, str] = {
            "channel": channel_id,
            "limit": str(MESSAGES_PER_PAGE),
            "include_all_metadata": "false",
        }
        if cursor:
            params["cursor"] = cursor
        if oldest_buffered:
            params["oldest"] = oldest_buffered

        return await self._slack_paginated_get("conversations.history", params)

    async def _fetch_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> list[dict]:
        """Fetch all replies in a thread via conversations.replies."""
        all_replies: list[dict] = []
        cursor: str | None = None

        while True:
            params: dict[str, str] = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": str(MESSAGES_PER_PAGE),
            }
            if cursor:
                params["cursor"] = cursor

            messages, next_cursor = await self._slack_paginated_get(
                "conversations.replies",
                params,
            )
            all_replies.extend(messages)

            if not next_cursor:
                break
            cursor = next_cursor

        return all_replies

    def _filter_messages(self, messages: list[dict]) -> list[dict]:
        """Filter out bot messages, system messages, and slash commands."""
        bot_mention = f"<@{self._bot_user_id}>"
        return [
            msg
            for msg in messages
            if msg.get("user") != self._bot_user_id
            and not msg.get("bot_id")
            and msg.get("subtype", "") not in FILTERED_SYSTEM_SUBTYPES
            and not msg.get("text", "").startswith("/ketchup")
            and bot_mention not in msg.get("text", "")
        ]

    @staticmethod
    def _is_backfill_enabled() -> bool:
        return os.environ.get("KETCHUP_AGENT_BACKFILL_ENABLED", "false").lower() == "true"

    @staticmethod
    def _get_max_backfill_messages() -> int:
        return int(
            os.environ.get(
                "KETCHUP_AGENT_MAX_BACKFILL_MESSAGES", str(DEFAULT_MAX_BACKFILL_MESSAGES)
            )
        )
