"""Cross-feature isolation — filters agent thread messages from other features."""

from typing import Optional, Set

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class AgentThreadFilter:
    """Provides agent thread filtering for cross-feature isolation.

    Used by status-updater, /status, /report, /query, and JIRA reporter
    to exclude messages that belong to agent conversation threads.
    """

    def __init__(self, conversation_store):
        """
        Args:
            conversation_store: ConversationStore for thread lookups.
        """
        self._conversation_store = conversation_store
        self._cache: dict[str, Set[str]] = {}  # channel_id -> thread_ts set

    async def get_agent_threads(self, channel_id: str) -> Set[str]:
        """Get all agent thread timestamps for a channel.

        Always fetches fresh data because new threads can be registered
        at any time by the agent handler.

        Args:
            channel_id: The channel to look up.

        Returns:
            Set of thread_ts strings belonging to agent conversations.
        """
        threads = await self._conversation_store.get_agent_thread_ts_set(channel_id)
        self._cache[channel_id] = threads
        return threads

    def is_agent_thread_message(
        self,
        message: dict,
        agent_threads: Set[str],
    ) -> bool:
        """Check if a message belongs to an agent thread.

        Args:
            message: Slack message dict.
            agent_threads: Set of known agent thread_ts values.

        Returns:
            True if the message should be filtered out.
        """
        thread_ts = message.get("thread_ts")
        if not thread_ts:
            return False
        return thread_ts in agent_threads

    def clear_cache(self, channel_id: Optional[str] = None) -> None:
        """Clear the thread cache.

        Args:
            channel_id: If provided, only clear cache for this channel.
        """
        if channel_id:
            self._cache.pop(channel_id, None)
        else:
            self._cache.clear()
