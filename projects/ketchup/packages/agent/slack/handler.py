"""Agent Slack handler — universal handler for @Ketchup conversational queries.

The agent is the intelligent router. events.py only intercepts active
maintenance prompts (DynamoDB state machine) before dispatching here.
The LLM understands intent — no regex heuristics needed for JIRA tickets,
status queries, or anything else. Slash commands are handled by a separate endpoint.
"""

import os
import re
from typing import Optional

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def is_agent_enabled() -> bool:
    """Check if the agent feature is enabled."""
    return os.environ.get("KETCHUP_AGENT_ENABLED", "false").lower() == "true"


def strip_bot_mention(text: str, bot_user_id: str) -> str:
    """Remove the bot mention from message text.

    Args:
        text: The raw message text.
        bot_user_id: The bot's Slack user ID.

    Returns:
        Cleaned text without the mention.
    """
    return re.sub(rf"<@{bot_user_id}>", "", text).strip()


class AgentSlackHandler:
    """Handles agent interactions via Slack events.

    Routing strategy: the agent is the universal handler for @Ketchup mentions.
    events.py's handle_app_mention() only intercepts active maintenance prompts
    (a DynamoDB state machine), then routes everything else here.
    The LLM understands intent — no regex heuristics needed.
    """

    def __init__(
        self,
        agent_engine,
        conversation_store,
        thread_manager,
        posting_handler,
        secrets_manager,
        backfill_ingestor=None,
    ):
        """
        Args:
            agent_engine: AgentEngine instance for RAG pipeline.
            conversation_store: ConversationStore for thread tracking.
            thread_manager: AgentThreadManager for thread lifecycle.
            posting_handler: SlackPostingHandler for sending messages.
            secrets_manager: SecretsManager for bot user ID.
            backfill_ingestor: Optional BackfillIngestor for on-demand history indexing.
        """
        self._agent_engine = agent_engine
        self._conversation_store = conversation_store
        self._thread_manager = thread_manager
        self._posting_handler = posting_handler
        self._secrets_manager = secrets_manager
        self._backfill_ingestor = backfill_ingestor

    async def handle_mention(self, event: dict) -> None:
        """Handle an @Ketchup mention routed here by elimination.

        Called from events.py handle_app_mention() AFTER all existing
        handlers have been checked (maintenance, Ketchup markers, etc.).
        No query detection needed — if we're called, it's an agent query.

        Args:
            event: The Slack app_mention event.
        """
        if not is_agent_enabled():
            return

        channel_id = event.get("channel")
        user_id = event.get("user")
        text = event.get("text", "")
        message_ts = event.get("ts")
        thread_ts = event.get("thread_ts")  # None if not in a thread

        bot_user_id = await self._secrets_manager.get_bot_slack_user_id_async()
        question = strip_bot_mention(text, bot_user_id)

        if not question:
            return

        # If mentioned in an existing agent thread, route as follow-up
        if thread_ts:
            is_agent = await self._conversation_store.is_agent_thread(channel_id, thread_ts)
            if is_agent:
                await self._handle_thread_reply(
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    question=question,
                    user_id=user_id,
                )
                return

        # New agent conversation — reply in existing thread or start new one.
        # Use parent thread_ts when mentioned in a thread (Slack requires top-level ts),
        # fall back to message_ts for top-level mentions (creates a new thread).
        conversation_thread_ts = thread_ts or message_ts
        logger.info(
            "Agent conversation start: channel=%s thread_ts=%s message_ts=%s → using=%s",
            channel_id,
            thread_ts,
            message_ts,
            conversation_thread_ts,
        )
        await self._start_conversation(
            channel_id=channel_id,
            thread_ts=conversation_thread_ts,
            question=question,
            user_id=user_id,
        )

    async def handle_thread_reply(self, event: dict) -> None:
        """Handle a reply in an agent conversation thread.

        Called from message event handler when thread_ts matches
        a registered agent thread.

        Args:
            event: The Slack message event.
        """
        if not is_agent_enabled():
            return

        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        user_id = event.get("user")
        text = event.get("text", "")

        if not thread_ts or not text:
            return

        bot_user_id = await self._secrets_manager.get_bot_slack_user_id_async()

        # Strip mention if present
        question = strip_bot_mention(text, bot_user_id)
        if not question:
            return

        await self._handle_thread_reply(
            channel_id=channel_id,
            thread_ts=thread_ts,
            question=question,
            user_id=user_id,
        )

    async def _start_conversation(
        self,
        channel_id: str,
        thread_ts: str,
        question: str,
        user_id: Optional[str],
    ) -> None:
        """Start a new agent conversation thread.

        1. Schedule backfill (fire-and-forget — idempotent, skips if already done)
        2. Register the thread for cross-feature isolation
        3. Post a "thinking" indicator (with first-time notice if backfill pending)
        4. Run RAG pipeline
        5. Update with the response
        """
        # Trigger backfill on first interaction — idempotent (checks watermark)
        is_first_time = False
        if self._backfill_ingestor:
            try:
                await self._backfill_ingestor.schedule_backfill(channel_id)
            except Exception as e:
                logger.warning("Backfill scheduling failed for %s: %s", channel_id, e)

        # Check if this is the first interaction (backfill not yet complete)
        try:
            watermark = await self._conversation_store.get_watermark(channel_id)
            if not watermark or not watermark.backfill_complete:
                is_first_time = True
        except Exception as e:
            logger.debug("Watermark check failed: %s", e)

        # Register thread for isolation
        await self._thread_manager.register_thread(channel_id, thread_ts)

        # Post thinking indicator (with first-time notice if applicable)
        if is_first_time:
            thinking_ts = await self._thread_manager.post_thinking_indicator(
                channel_id,
                thread_ts,
                message=":hourglass_flowing_sand: I'm indexing this channel's history for the first time. This may take a moment — subsequent answers will be much faster.",
            )
            # Wait for backfill to finish so the RAG pipeline has data to work with
            if self._backfill_ingestor:
                await self._backfill_ingestor.wait_for_backfill(channel_id, timeout=120.0)
        else:
            thinking_ts = await self._thread_manager.post_thinking_indicator(channel_id, thread_ts)

        try:
            # Run RAG pipeline
            response = await self._agent_engine.answer(
                question=question,
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
            )

            # Update thinking message with response
            if thinking_ts:
                await self._thread_manager.update_with_response(
                    channel_id, thinking_ts, response, thread_ts=thread_ts
                )
            else:
                # Fallback: post new message
                await self._posting_handler.post_message(
                    channel_id=channel_id,
                    message=response,
                    thread_ts=thread_ts,
                )

        except Exception as e:
            logger.error(
                "Agent error for channel %s thread %s: %s",
                channel_id,
                thread_ts,
                e,
                exc_info=True,
            )
            error_msg = "Sorry, I encountered an error processing your question. Please try again."
            if thinking_ts:
                await self._thread_manager.update_with_response(
                    channel_id, thinking_ts, error_msg, thread_ts=thread_ts
                )
            else:
                await self._posting_handler.post_message(
                    channel_id=channel_id,
                    message=error_msg,
                    thread_ts=thread_ts,
                )

    async def _handle_thread_reply(
        self,
        channel_id: str,
        thread_ts: str,
        question: str,
        user_id: Optional[str],
    ) -> None:
        """Handle a follow-up message in an existing agent thread."""
        # Update thread activity
        await self._conversation_store.update_thread_activity(channel_id, thread_ts)

        # Post thinking indicator
        thinking_ts = await self._thread_manager.post_thinking_indicator(channel_id, thread_ts)

        try:
            response = await self._agent_engine.answer(
                question=question,
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
            )

            if thinking_ts:
                await self._thread_manager.update_with_response(
                    channel_id, thinking_ts, response, thread_ts=thread_ts
                )
            else:
                await self._posting_handler.post_message(
                    channel_id=channel_id,
                    message=response,
                    thread_ts=thread_ts,
                )

        except Exception as e:
            logger.error("Agent thread reply error: %s", e, exc_info=True)
            error_msg = "Sorry, I encountered an error. Please try again."
            if thinking_ts:
                await self._thread_manager.update_with_response(
                    channel_id, thinking_ts, error_msg, thread_ts=thread_ts
                )
