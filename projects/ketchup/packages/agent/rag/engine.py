"""Agent engine — orchestrates the full RAG pipeline from question to answer.

Single-pass retrieval: query → embed → top-K from ChromaDB → build context → LLM.
No re-ranking step, no hybrid scoring. The LLM evaluates relevance from the
context it receives, including timestamps for temporal reasoning.
"""

import os
import re
import time
from typing import Optional

from packages.core.config.feature_flags import FeatureFlags
from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Default configuration (overridable via env vars)
DEFAULT_TOP_K = 20
DEFAULT_MAX_HISTORY = 10
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_MAX_TOKENS = 2048


class AgentEngine:
    """Orchestrates the full RAG pipeline: retrieve → build context → call LLM."""

    def __init__(
        self,
        retriever,
        context_builder,
        conversation_store,
        api_executor,
        system_prompt: str,
    ):
        """
        Args:
            retriever: Retriever instance for embedding queries and searching.
            context_builder: ContextBuilder instance for assembling context.
            conversation_store: ConversationStore for persisting turns.
            api_executor: ApiExecutor instance for Azure OpenAI calls.
            system_prompt: The agent's system prompt text.
        """
        self._retriever = retriever
        self._context_builder = context_builder
        self._conversation_store = conversation_store
        self._api_executor = api_executor
        self._system_prompt = system_prompt

        # Load config from env
        self._top_k = int(os.environ.get("KETCHUP_AGENT_TOP_K", str(DEFAULT_TOP_K)))
        self._max_history = int(
            os.environ.get("KETCHUP_AGENT_MAX_HISTORY_TURNS", str(DEFAULT_MAX_HISTORY))
        )
        self._temperature = float(
            os.environ.get("KETCHUP_AGENT_TEMPERATURE", str(DEFAULT_TEMPERATURE))
        )
        self._max_tokens = int(os.environ.get("KETCHUP_AGENT_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))

    async def answer(
        self,
        question: str,
        channel_id: str,
        thread_ts: str,
        user_id: Optional[str] = None,
    ) -> str:
        """Process a user question through the full RAG pipeline.

        Pipeline:
        1. Retrieve relevant context (single-pass cosine similarity)
        2. Build LLM context window (system prompt + context + history + question)
        3. Call Azure OpenAI
        4. Store conversation turns (user + assistant) in DynamoDB
        5. Return the response text

        Args:
            question: The user's question text.
            channel_id: The Slack channel ID.
            thread_ts: The conversation thread timestamp.
            user_id: Optional Slack user ID of the questioner.

        Returns:
            The agent's response text.
        """
        start_time = time.time()

        # Step 1: Retrieve relevant context
        logger.info(
            "Agent query in channel %s: retrieving context (top_k=%d)",
            channel_id,
            self._top_k,
        )
        chunks = await self._retriever.retrieve(
            query=question,
            channel_id=channel_id,
            top_k=self._top_k,
        )

        # Step 2: Build context window
        # Append JSON response instruction when structured output is enabled
        system_prompt = self._system_prompt
        if FeatureFlags.is_structured_json_output_enabled():
            system_prompt += (
                "\n\nIMPORTANT: Return your response as JSON with this exact structure:\n"
                '{"response_text": "your complete formatted response here using Slack mrkdwn"}\n'
            )

        messages = await self._context_builder.build_context(
            question=question,
            channel_id=channel_id,
            thread_ts=thread_ts,
            retrieved_chunks=chunks,
            system_prompt=system_prompt,
            max_history_turns=self._max_history,
        )

        # Step 3: Build payload and call LLM
        payload = {
            "messages": messages,
            "max_completion_tokens": self._max_tokens,
            "temperature": self._temperature,
            "top_p": 0.9,
        }

        # Enable JSON mode when feature flag is on (matches ApiExecutor.prepare_payload)
        if FeatureFlags.is_structured_json_output_enabled():
            payload["response_format"] = {"type": "json_object"}

        response_data = await self._api_executor.execute_request(
            payload=payload,
            channel_info=None,  # No re-archiving for agent queries
            user_id=user_id,
            incoming_channel=channel_id,
        )

        # Extract response text
        response_text = ""
        choices = response_data.get("choices", [])
        if choices:
            response_text = choices[0].get("message", {}).get("content", "")

        # Extract from JSON wrapper when structured output is enabled
        if response_text and FeatureFlags.is_structured_json_output_enabled():
            from packages.ai.core.json_response import safe_extract_response_text

            response_text = safe_extract_response_text(response_text, fallback=response_text)

        if not response_text:
            response_text = (
                "I wasn't able to generate a response. Please try rephrasing your question."
            )

        # Step 4: Store conversation turns
        timestamp_ms = str(int(time.time() * 1000))

        from packages.agent.conversation.models import ConversationTurn

        user_turn = ConversationTurn(
            channel_id=channel_id,
            thread_ts=thread_ts,
            timestamp=timestamp_ms,
            role="user",
            content=question,
            user_id=user_id,
        )
        await self._conversation_store.store_turn(user_turn)

        # Store assistant turn (slightly later timestamp)
        assistant_turn = ConversationTurn(
            channel_id=channel_id,
            thread_ts=thread_ts,
            timestamp=str(int(timestamp_ms) + 1),
            role="assistant",
            content=response_text,
        )
        await self._conversation_store.store_turn(assistant_turn)

        elapsed = time.time() - start_time
        logger.info(
            "Agent answered in %.2fs for channel %s (chunks=%d, history_msgs=%d)",
            elapsed,
            channel_id,
            len(chunks),
            len(messages) - 2,  # minus system + question
        )

        return _linkify_jira_tickets(response_text)


# Valid JIRA project prefixes used across Ketchup
_JIRA_PREFIXES = "|".join(VALID_JIRA_PROJECTS)
_JIRA_TICKET_RE = re.compile(rf"(?<!\|)(?<!browse/)(?<!/)\b((?:{_JIRA_PREFIXES})-\d+)\b(?![^<]*>)")
_JIRA_BASE_URL = "https://jira.corp.adobe.com/browse"


def _linkify_jira_tickets(text: str) -> str:
    """Convert plain JIRA ticket references to clickable Slack mrkdwn links.

    Skips tickets already inside <url|label> links.
    """
    return _JIRA_TICKET_RE.sub(rf"<{_JIRA_BASE_URL}/\1|\1>", text)
