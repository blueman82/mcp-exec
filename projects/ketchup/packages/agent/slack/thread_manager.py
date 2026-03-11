"""Agent thread manager — handles thread lifecycle and typing indicators."""

from typing import Optional

from packages.core.logging import setup_logger

logger = setup_logger(__name__)

THINKING_MESSAGE = ":hourglass_flowing_sand: Thinking..."


class AgentThreadManager:
    """Manages agent conversation thread lifecycle."""

    def __init__(self, conversation_store, posting_handler):
        """
        Args:
            conversation_store: ConversationStore for thread registration.
            posting_handler: SlackPostingHandler for Slack API calls.
        """
        self._conversation_store = conversation_store
        self._posting_handler = posting_handler

    async def register_thread(self, channel_id: str, thread_ts: str) -> None:
        """Register a new agent thread for cross-feature isolation.

        Args:
            channel_id: The channel ID.
            thread_ts: The thread timestamp.
        """
        await self._conversation_store.register_thread(channel_id, thread_ts)
        logger.info("Registered agent thread %s in channel %s", thread_ts, channel_id)

    async def post_thinking_indicator(
        self, channel_id: str, thread_ts: str, message: Optional[str] = None
    ) -> Optional[str]:
        """Post a 'thinking' message in the thread.

        Args:
            channel_id: The channel ID.
            thread_ts: The thread timestamp to reply in.
            message: Optional custom message (defaults to THINKING_MESSAGE).

        Returns:
            The timestamp of the thinking message (for later update), or None on failure.
        """
        try:
            result = await self._posting_handler.post_message(
                channel_id=channel_id,
                message=message or THINKING_MESSAGE,
                thread_ts=thread_ts,
            )
            if not result or not isinstance(result, dict):
                return None

            posted_ts = result.get("ts")

            # Verify Slack actually threaded the message. If response lacks
            # message.thread_ts, Slack silently posted top-level — delete and retry.
            actual_thread_ts = result.get("message", {}).get("thread_ts")
            if posted_ts and not actual_thread_ts:
                logger.warning(
                    "Thinking indicator posted top-level (ts=%s) despite thread_ts=%s — deleting and retrying",
                    posted_ts,
                    thread_ts,
                )
                await self._posting_handler.delete_message(channel_id, posted_ts)
                retry = await self._posting_handler.post_message(
                    channel_id=channel_id,
                    message=message or THINKING_MESSAGE,
                    thread_ts=thread_ts,
                )
                if retry and isinstance(retry, dict):
                    return retry.get("ts")
                return None

            return posted_ts
        except Exception as e:
            logger.warning("Failed to post thinking indicator: %s", e)
            return None

    async def update_with_response(
        self, channel_id: str, message_ts: str, response: str, thread_ts: Optional[str] = None
    ) -> None:
        """Update the thinking message with the actual response.

        Args:
            channel_id: The channel ID.
            message_ts: The timestamp of the thinking message to update.
            response: The response text to replace the thinking message with.
            thread_ts: The parent thread timestamp (for fallback posting).
        """
        try:
            result = await self._posting_handler.update_message(
                channel_id=channel_id,
                ts=message_ts,
                message=response,
            )
            # update_message returns a dict — check ok flag since it doesn't raise on failure
            if not result or not result.get("ok"):
                error = result.get("error", "unknown") if result else "no response"
                raise ValueError(f"Slack chat.update failed: {error}")
        except Exception as e:
            logger.warning(
                "Failed to update message %s, posting new message: %s",
                message_ts,
                e,
            )
            # Fallback: post a new message if update fails
            await self._posting_handler.post_message(
                channel_id=channel_id,
                message=response,
                thread_ts=thread_ts,
            )
