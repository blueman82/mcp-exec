"""Data models for Ketchup Agent conversations."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConversationTurn:
    """A single turn in an agent conversation."""

    channel_id: str
    thread_ts: str
    timestamp: str  # epoch milliseconds as string
    role: str  # "user" or "assistant"
    content: str
    user_id: Optional[str] = None  # Slack user ID (for user turns)


@dataclass
class AgentThread:
    """Tracks an agent conversation thread for cross-feature isolation."""

    channel_id: str
    thread_ts: str
    created_at: int  # epoch seconds
    last_active_at: int  # epoch seconds
    status: str = "active"  # "active" or "archived"


@dataclass
class MessageWatermark:
    """Tracks message ingestion progress per channel."""

    channel_id: str
    latest_ingested_ts: str  # Slack message timestamp
    backfill_complete: bool = False
    backfill_started_at: Optional[int] = None  # epoch seconds
    total_ingested: int = 0
