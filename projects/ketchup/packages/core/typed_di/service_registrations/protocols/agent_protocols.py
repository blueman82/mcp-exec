"""
Ketchup Agent Protocol Definitions.

This module contains protocol definitions for the Ketchup Agent feature,
which provides a conversational AI assistant in Slack channels using RAG
(Retrieval-Augmented Generation) over channel message history.

Components:
- Embeddings: Azure OpenAI ada-002 embedding client
- Vector Store: ChromaDB for similarity search
- Conversation Store: DynamoDB for conversation history and thread tracking
- Retriever: Embeds queries and retrieves relevant context chunks
- Context Builder: Assembles LLM context windows
- Agent Engine: Orchestrates the full RAG pipeline
- Ingestor: Real-time and backfill message ingestion
- Slack Handler: Event handling and thread management
- Thread Filter: Cross-feature isolation
"""

from typing import Any, Dict, List, Optional, Protocol, Set, runtime_checkable

__all__ = [
    # Service protocols
    "AgentEmbeddingsClientProtocol",
    "AgentVectorStoreProtocol",
    "AgentConversationStoreProtocol",
    "AgentRetrieverProtocol",
    "AgentContextBuilderProtocol",
    "AgentEngineProtocol",
    "AgentRealtimeIngestorProtocol",
    "AgentBackfillIngestorProtocol",
    "AgentJiraBackfillIngestorProtocol",
    "AgentSlackHandlerProtocol",
    "AgentThreadManagerProtocol",
    "AgentThreadFilterProtocol",
]


# =============================================================================
# Embeddings & Vector Store Protocols
# =============================================================================


@runtime_checkable
class AgentEmbeddingsClientProtocol(Protocol):
    """Protocol for computing text embeddings via Azure OpenAI ada-002."""

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts, returning embedding vectors.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of 1536-dimensional embedding vectors.
        """
        ...

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query text.

        Args:
            query: The query string to embed.

        Returns:
            1536-dimensional embedding vector.
        """
        ...

    async def cleanup(self) -> None:
        """Close HTTP session and release resources."""
        ...


@runtime_checkable
class AgentVectorStoreProtocol(Protocol):
    """Protocol for vector storage and similarity search via ChromaDB."""

    async def add_documents(
        self, documents: List[Dict[str, Any]], embeddings: List[List[float]]
    ) -> None:
        """Add documents with pre-computed embeddings.

        Args:
            documents: List of dicts with keys: id, text, metadata.
            embeddings: Corresponding embedding vectors.
        """
        ...

    async def query(
        self, query_embedding: List[float], channel_id: Optional[str] = None, top_k: int = 15
    ) -> List[Dict[str, Any]]:
        """Query for similar documents, optionally filtered by channel_id.

        Args:
            query_embedding: The query embedding vector.
            channel_id: Filter results to this channel. None = cross-channel search.
            top_k: Number of results to return.

        Returns:
            List of result dicts with keys: id, text, metadata, distance.
        """
        ...

    async def delete_by_channel(self, channel_id: str) -> None:
        """Delete all documents for a specific channel.

        Args:
            channel_id: The channel whose documents should be deleted.
        """
        ...

    async def get_document_count(self, channel_id: Optional[str] = None) -> int:
        """Get the number of documents, optionally filtered by channel."""
        ...

    async def get_by_time_range(
        self, channel_id: str, since_ts: str, until_ts: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve all documents for a channel within a time range.

        Uses metadata filtering on message_ts (no embedding needed).
        Slack timestamps are epoch strings that sort lexicographically.

        Args:
            channel_id: Filter to this channel.
            since_ts: Earliest message_ts (inclusive).
            until_ts: Latest message_ts (exclusive). None = no upper bound.

        Returns:
            List of dicts with keys: id, text, metadata — sorted chronologically.
        """
        ...

    async def cleanup(self) -> None:
        """Clean up resources."""
        ...


# =============================================================================
# Conversation Store Protocol
# =============================================================================


@runtime_checkable
class AgentConversationStoreProtocol(Protocol):
    """Protocol for DynamoDB conversation history and thread tracking."""

    async def store_turn(self, turn: Any) -> None:
        """Store a conversation turn (user or assistant).

        Args:
            turn: ConversationTurn dataclass instance.
        """
        ...

    async def get_history(self, channel_id: str, thread_ts: str, limit: int = 10) -> list:
        """Get conversation history for a thread.

        Args:
            channel_id: The channel ID.
            thread_ts: The thread timestamp.
            limit: Maximum turns to return.

        Returns:
            List of ConversationTurn objects, chronological order.
        """
        ...

    async def register_thread(self, channel_id: str, thread_ts: str) -> None:
        """Register a new agent conversation thread for isolation.

        Args:
            channel_id: The channel ID.
            thread_ts: The Slack thread timestamp.
        """
        ...

    async def is_agent_thread(self, channel_id: str, thread_ts: str) -> bool:
        """Check if a thread_ts belongs to an agent conversation.

        Args:
            channel_id: The channel ID.
            thread_ts: The thread timestamp to check.

        Returns:
            True if this is a registered agent thread.
        """
        ...

    async def get_agent_thread_ts_set(self, channel_id: str) -> Set[str]:
        """Get all agent thread timestamps for a channel.

        Used for cross-feature isolation filtering.

        Args:
            channel_id: The channel ID.

        Returns:
            Set of thread_ts strings belonging to agent conversations.
        """
        ...

    async def update_thread_activity(self, channel_id: str, thread_ts: str) -> None:
        """Update the last_active_at timestamp for a thread."""
        ...

    async def get_watermark(self, channel_id: str) -> Any:
        """Get the message ingestion watermark for a channel."""
        ...

    async def update_watermark(
        self,
        channel_id: str,
        latest_ts: str,
        total_ingested: int,
        backfill_complete: bool = False,
    ) -> None:
        """Update the message ingestion watermark."""
        ...

    async def increment_watermark(self, channel_id: str, latest_ts: str) -> None:
        """Atomically increment watermark counter and update latest_ts."""
        ...

    async def mark_backfill_started(self, channel_id: str) -> None:
        """Mark that backfill has started for a channel."""
        ...

    async def wipe_channel_data(self, channel_id: str) -> None:
        """Delete all agent data for a channel (on channel_archive)."""
        ...


# =============================================================================
# RAG Pipeline Protocols
# =============================================================================


@runtime_checkable
class AgentRetrieverProtocol(Protocol):
    """Protocol for embedding queries and retrieving relevant context."""

    async def retrieve(
        self, query: str, channel_id: Optional[str] = None, top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context using pure semantic similarity.

        Args:
            query: The user's question.
            channel_id: Filter results to this channel. None = cross-channel search.
            top_k: Number of results to return.

        Returns:
            List of context dicts with keys: id, text, metadata, score.
        """
        ...


@runtime_checkable
class AgentContextBuilderProtocol(Protocol):
    """Protocol for assembling LLM context windows."""

    async def build_context(
        self,
        question: str,
        channel_id: str,
        thread_ts: str,
        retrieved_chunks: List[Dict[str, Any]],
        system_prompt: str,
        max_history_turns: int = 10,
    ) -> List[Dict[str, str]]:
        """Build the LLM message list from context, history, and question.

        Args:
            question: The user's current question.
            channel_id: Channel for history lookup.
            thread_ts: Thread for history lookup.
            retrieved_chunks: Ranked context chunks.
            system_prompt: The agent system prompt.
            max_history_turns: Max history turns to include.

        Returns:
            List of message dicts ready for the OpenAI API.
        """
        ...


@runtime_checkable
class AgentEngineProtocol(Protocol):
    """Protocol for the full RAG pipeline from question to answer."""

    async def answer(
        self,
        question: str,
        channel_id: str,
        thread_ts: str,
        user_id: Optional[str] = None,
    ) -> str:
        """Process a user question through the full RAG pipeline.

        Args:
            question: The user's question text.
            channel_id: The Slack channel ID.
            thread_ts: The conversation thread timestamp.
            user_id: Optional Slack user ID.

        Returns:
            The agent's response text.
        """
        ...


# =============================================================================
# Ingestion Protocols
# =============================================================================


@runtime_checkable
class AgentRealtimeIngestorProtocol(Protocol):
    """Protocol for real-time message ingestion into the vector store."""

    async def ingest_message(self, channel_id: str, message: dict) -> None:
        """Ingest a single message from a Slack event.

        Filters bot/system messages, buffers, and embeds when ready.

        Args:
            channel_id: The channel the message is from.
            message: The Slack message event dict.
        """
        ...

    async def flush_all(self) -> None:
        """Flush all pending message buffers."""
        ...


@runtime_checkable
class AgentBackfillIngestorProtocol(Protocol):
    """Protocol for historical message backfill on bot join."""

    async def schedule_backfill(self, channel_id: str) -> None:
        """Schedule a channel for historical message backfill.

        Args:
            channel_id: The channel to backfill.
        """
        ...


@runtime_checkable
class AgentJiraBackfillIngestorProtocol(Protocol):
    """Protocol for JIRA ticket context backfill into the vector store."""

    async def backfill_jira(self, channel_id: str) -> int:
        """Fetch and index JIRA ticket data for a channel.

        Args:
            channel_id: The channel to backfill JIRA data for.

        Returns:
            Number of documents stored.
        """
        ...


# =============================================================================
# Slack Integration Protocols
# =============================================================================


@runtime_checkable
class AgentSlackHandlerProtocol(Protocol):
    """Protocol for handling agent interactions via Slack events."""

    async def handle_mention(self, event: dict) -> None:
        """Handle an @Ketchup mention that looks like an agent query.

        Args:
            event: The Slack app_mention event.
        """
        ...

    async def handle_thread_reply(self, event: dict) -> None:
        """Handle a reply in an agent conversation thread.

        Args:
            event: The Slack message event.
        """
        ...


@runtime_checkable
class AgentThreadManagerProtocol(Protocol):
    """Protocol for managing agent conversation thread lifecycle."""

    async def register_thread(self, channel_id: str, thread_ts: str) -> None:
        """Register a new agent thread for cross-feature isolation."""
        ...

    async def post_thinking_indicator(self, channel_id: str, thread_ts: str) -> Optional[str]:
        """Post a 'thinking' message, return its ts for later update."""
        ...

    async def update_with_response(
        self, channel_id: str, message_ts: str, response: str, thread_ts: Optional[str] = None
    ) -> None:
        """Replace the thinking message with the actual response."""
        ...


@runtime_checkable
class AgentThreadFilterProtocol(Protocol):
    """Protocol for cross-feature isolation filtering.

    Used by status-updater, /status, /report, /query, and JIRA reporter
    to exclude messages in agent conversation threads.
    """

    async def get_agent_threads(self, channel_id: str) -> Set[str]:
        """Get all agent thread timestamps for a channel (cached)."""
        ...

    def is_agent_thread_message(self, message: dict, agent_threads: Set[str]) -> bool:
        """Check if a message belongs to an agent thread."""
        ...

    def clear_cache(self, channel_id: Optional[str] = None) -> None:
        """Clear the thread lookup cache."""
        ...
