"""Context builder — assembles the LLM context window from retrieved context and conversation history.

Token budget logic is a hard model constraint (not a heuristic). Priority order:
1. System prompt (always)
2. User question (always)
3. Conversation history (most recent turns first)
4. Retrieved context (fill remaining budget, skip what doesn't fit)

No rough truncation ratios — if a document doesn't fit, skip it entirely.
The per-message embedding strategy means individual messages are small enough
that skipping one is low-cost compared to fragmenting it.
"""

from typing import Any, Dict, List

from packages.ai.core.token_utils import count_tokens
from packages.core.constants import MAX_PROCESSABLE_TOKENS
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Reserve tokens for the LLM's response
OUTPUT_TOKEN_RESERVE = 2048
MAX_INPUT_TOKENS = MAX_PROCESSABLE_TOKENS - OUTPUT_TOKEN_RESERVE


class ContextBuilder:
    """Assembles the context window for the agent LLM call."""

    def __init__(self, conversation_store):
        """
        Args:
            conversation_store: ConversationStore for retrieving history
        """
        self._conversation_store = conversation_store

    async def build_context(
        self,
        question: str,
        channel_id: str,
        thread_ts: str,
        retrieved_chunks: List[Dict[str, Any]],
        system_prompt: str,
        max_history_turns: int = 10,
    ) -> List[Dict[str, str]]:
        """Build the LLM message list from system prompt, retrieved context, history, and question.

        Uses a pack-what-fits approach: include everything that fits within
        the model's context window. No proportional allocation or truncation.

        Args:
            question: The user's current question.
            channel_id: The channel ID for conversation history lookup.
            thread_ts: The thread timestamp for history lookup.
            retrieved_chunks: Ranked context from the retriever.
            system_prompt: The agent system prompt.
            max_history_turns: Maximum conversation history turns to include.

        Returns:
            List of message dicts ready for the OpenAI API.
        """
        messages: List[Dict[str, str]] = []

        # 1. System prompt (always included)
        messages.append({"role": "system", "content": system_prompt})
        used_tokens = count_tokens(system_prompt)

        # 2. Reserve space for the user question
        question_tokens = count_tokens(question)
        used_tokens += question_tokens

        # 3. Load conversation history
        history = await self._conversation_store.get_history(
            channel_id=channel_id,
            thread_ts=thread_ts,
            limit=max_history_turns,
        )

        history_messages = []
        for turn in history:
            turn_msg = {"role": turn.role, "content": turn.content}
            turn_tokens = count_tokens(turn.content)
            if used_tokens + turn_tokens > MAX_INPUT_TOKENS:
                logger.warning(
                    "History truncated at %d turns (token budget)", len(history_messages)
                )
                break
            history_messages.append(turn_msg)
            used_tokens += turn_tokens

        # 4. Add retrieved context — pack what fits, skip what doesn't
        remaining_budget = MAX_INPUT_TOKENS - used_tokens
        context_parts = []
        chunks_included = 0

        for chunk in retrieved_chunks:
            chunk_text = chunk["text"]
            chunk_tokens = count_tokens(chunk_text)

            if chunk_tokens > remaining_budget:
                # Per-message documents are small — skip rather than truncate
                continue

            context_parts.append(chunk_text)
            remaining_budget -= chunk_tokens
            chunks_included += 1

        # Assemble context into a single user-role message
        if context_parts:
            context_block = (
                f"You are answering questions in Slack channel <#{channel_id}>.\n\n"
                "Here is relevant context from the channel's message history:\n\n"
                + "\n\n".join(context_parts)
                + "\n\n---\n\n"
            )
            messages.append({"role": "user", "content": context_block})

        # Add conversation history
        messages.extend(history_messages)

        # Add the current question last
        messages.append({"role": "user", "content": question})

        total_tokens = sum(count_tokens(m["content"]) for m in messages)
        logger.info(
            "Context built: %d messages, %d tokens, %d context chunks, %d history turns",
            len(messages),
            total_tokens,
            chunks_included,
            len(history_messages),
        )

        return messages
