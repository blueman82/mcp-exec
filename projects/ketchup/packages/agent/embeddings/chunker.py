"""Message formatter for creating embeddable documents from Slack messages.

Per-message embedding strategy: each message becomes its own document with
author and timestamp context embedded in the text. No sliding windows,
no overlap parameters, no author grouping heuristics.

This gives maximum retrieval granularity — the vector store returns
individual messages, and the LLM reasons about relevance and recency
from the timestamp context included in each document.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class MessageDocument:
    """A single message prepared for embedding."""

    channel_id: str
    doc_id: str
    text: str
    message_ts: str
    user_id: str
    has_thread_replies: bool = False


def format_messages(
    messages: List[dict],
    channel_id: str,
) -> List[MessageDocument]:
    """Create one embeddable document per message.

    Each document's text includes the author and timestamp so the
    embedding model captures conversational context. The vector store
    handles similarity search; the LLM handles temporal reasoning.

    Args:
        messages: List of Slack message dicts (must have 'ts', 'user', 'text').
        channel_id: The channel these messages belong to.

    Returns:
        List of MessageDocument objects ready for embedding.
    """
    if not messages:
        return []

    documents = []
    for msg in messages:
        ts = msg.get("ts", "")
        user = msg.get("user", "unknown")
        text = msg.get("text", "").strip()

        if not text:
            continue

        has_threads = bool(msg.get("thread_ts") and msg.get("reply_count"))
        doc_id = f"{channel_id}:{ts}"

        # Convert Slack epoch to readable UTC for context
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            readable_ts = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError, OSError):
            readable_ts = ts

        # Include author and timestamp in text for richer embeddings
        doc_text = f"[{readable_ts}] <@{user}>: {text}"

        documents.append(
            MessageDocument(
                channel_id=channel_id,
                doc_id=doc_id,
                text=doc_text,
                message_ts=ts,
                user_id=user,
                has_thread_replies=has_threads,
            )
        )

    logger.info(
        "Formatted %d messages into %d documents for channel %s",
        len(messages),
        len(documents),
        channel_id,
    )
    return documents
