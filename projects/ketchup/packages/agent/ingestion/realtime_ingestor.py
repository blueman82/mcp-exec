"""Real-time message ingestor — processes incoming Slack messages for the agent index.

Uses an async queue for immediate per-message embedding. No buffer
accumulation, no flush thresholds, no timeout heuristics. Each message
flows through: receive → queue → embed → store. Natural backpressure
from the queue prevents overload.
"""

import asyncio
import time
from typing import Optional

from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# System subtypes to skip (consistent with channel_msg_ops.py)
FILTERED_SYSTEM_SUBTYPES = {
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "channel_archive",
    "channel_unarchive",
    "pinned_item",
    "unpinned_item",
    "bot_add",
    "bot_remove",
}


class RealtimeIngestor:
    """Ingests individual Slack messages into the agent's vector store.

    Each message is queued and embedded individually — no buffering,
    no chunking windows. The async queue provides natural backpressure.
    """

    def __init__(
        self,
        embeddings_client,
        vector_store,
        conversation_store,
        bot_user_id: str,
    ):
        """
        Args:
            embeddings_client: AzureEmbeddingsClient for computing embeddings.
            vector_store: ChromaVectorStore for storing documents.
            conversation_store: ConversationStore for watermark and thread checks.
            bot_user_id: The bot's Slack user ID for message filtering.
        """
        self._embeddings_client = embeddings_client
        self._vector_store = vector_store
        self._conversation_store = conversation_store
        self._bot_user_id = bot_user_id

        self._queue: asyncio.Queue = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task] = None

    def _ensure_processor_running(self) -> None:
        """Start the queue processor if not already running."""
        if self._processor_task is None or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_queue())

    async def ingest_message(self, channel_id: str, message: dict) -> None:
        """Ingest a single message from a Slack event.

        Filters out bot messages, system messages, and agent thread messages,
        then queues the message for immediate embedding.

        Args:
            channel_id: The channel the message is from.
            message: The Slack message event dict.
        """
        # Filter: bot's own messages
        if message.get("user") == self._bot_user_id:
            return

        # Filter: any bot messages
        if message.get("bot_id"):
            return

        # Filter: system subtypes
        subtype = message.get("subtype", "")
        if subtype in FILTERED_SYSTEM_SUBTYPES:
            return

        # Filter: agent thread messages (don't index our own conversations)
        thread_ts = message.get("thread_ts")
        if thread_ts:
            is_agent = await self._conversation_store.is_agent_thread(channel_id, thread_ts)
            if is_agent:
                return

        # Filter: messages mentioning the bot (agent questions — not channel history)
        text = message.get("text", "")
        if f"<@{self._bot_user_id}>" in text:
            return

        # Filter: slash commands
        if text.startswith("/ketchup"):
            return

        # Queue for immediate embedding
        await self._queue.put((channel_id, message))
        self._ensure_processor_running()

    async def flush_all(self) -> None:
        """Wait for all queued messages to be processed."""
        if not self._queue.empty():
            await self._queue.join()

    async def _process_queue(self) -> None:
        """Process queued messages — embed and store each one individually."""
        while True:
            try:
                channel_id, message = await asyncio.wait_for(self._queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                # No messages for 60s — stop processor, will restart on next ingest
                logger.debug("Ingestor queue idle, stopping processor")
                return

            try:
                await self._embed_and_store(channel_id, message)
            except Exception as e:
                logger.error(
                    "Failed to embed message in channel %s: %s",
                    channel_id,
                    e,
                    exc_info=True,
                )
            finally:
                self._queue.task_done()

    async def _embed_and_store(self, channel_id: str, message: dict) -> None:
        """Embed a single message and store it in the vector store."""
        from packages.agent.embeddings.chunker import format_messages

        documents = format_messages([message], channel_id)
        if not documents:
            return

        doc = documents[0]

        # Embed the message text
        embeddings = await self._embeddings_client.embed_texts([doc.text])

        # Store in vector store
        await self._vector_store.add_documents(
            documents=[
                {
                    "id": doc.doc_id,
                    "text": doc.text,
                    "metadata": {
                        "channel_id": doc.channel_id,
                        "message_ts": float(doc.message_ts),
                        "user_id": doc.user_id,
                        "has_thread_replies": doc.has_thread_replies,
                        "ingested_at": int(time.time()),
                        "source": "realtime",
                    },
                }
            ],
            embeddings=embeddings,
        )

        # Update watermark atomically — no read-modify-write race
        await self._conversation_store.increment_watermark(
            channel_id=channel_id,
            latest_ts=message.get("ts", "0"),
        )
