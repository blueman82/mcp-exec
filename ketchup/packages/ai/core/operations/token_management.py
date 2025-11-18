"""
token_management.py

Handles token counting, enforcing limits, truncation, notifications,
and potentially cost calculation related aspects for OpenAI interactions.
"""

from typing import Dict, List, Optional

from packages.ai.core.token_utils import (
    count_tokens,
    get_tokenizer,
    tokens_to_words,
)
from packages.core.constants import MAX_PROCESSABLE_TOKENS
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class TokenManager:
    """Manages token limits, truncation, and notifications."""

    def __init__(self):
        """Initializes the TokenManager."""
        # Currently stateless, might add config/dependencies later if needed
        pass

    async def enforce_token_limit(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[str],
        channel_context_id: Optional[str],
        response_url: Optional[str] = None,  # Added for process_large_text
    ) -> List[Dict[str, str]]:
        """
        Check token count, notify user if limit exceeded, and truncate messages if needed.

        Args:
            messages: List of message objects (e.g., from prepare_messages or direct input).
            user_id: The Slack user ID for potential notifications.
            channel_context_id: The relevant channel ID for notifications.
            response_url: Optional Slack response URL for notifications.

        Returns:
            Potentially truncated list of messages.
        """
        # Separate system and user messages for accurate token counting
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        user_messages = [msg for msg in messages if msg.get("role") == "user"]

        # Count tokens separately
        system_text = " ".join(str(msg.get("content", "")) for msg in system_messages)
        user_text = " ".join(str(msg.get("content", "")) for msg in user_messages)

        system_tokens = count_tokens(system_text)
        user_tokens = count_tokens(user_text)
        total_tokens = system_tokens + user_tokens

        logger.info(
            "Token count - System: %s, User: %s, Total: %s (Limit: %s)",
            system_tokens,
            user_tokens,
            total_tokens,
            MAX_PROCESSABLE_TOKENS,
        )

        if total_tokens <= MAX_PROCESSABLE_TOKENS:
            return messages  # No action needed

        # --- Limit Exceeded: Notify and Truncate ---
        logger.warning(
            "Input exceeds token limit (%s > %s), will truncate user content",
            total_tokens,
            MAX_PROCESSABLE_TOKENS,
        )

        # 1. Send Notification (if context available)
        if user_id or channel_context_id or response_url:
            await self._send_truncation_notification(
                total_tokens, user_id, channel_context_id, response_url
            )

        # 2. Truncate Messages (preserving all system messages)
        truncated_messages = self._truncate_messages_preserving_system(
            messages, total_tokens
        )

        return truncated_messages

    async def _send_truncation_notification(
        self,
        total_tokens: int,
        user_id: Optional[str],
        channel_context_id: Optional[str],
        response_url: Optional[str],
    ):
        """Sends a notification to Slack about input truncation."""
        # Lazy import to avoid circular dependency with OpenAIHandler
        from packages.core.typed_di_integration import get_typed_registry
        from packages.core.typed_di.service_registrations.protocols.core_protocols import (
            SlackPostingHandlerProtocol,
        )

        approx_words = tokens_to_words(total_tokens)
        limit_words = tokens_to_words(MAX_PROCESSABLE_TOKENS)
        status_message = (
            f"⚠️ The content provided has approximately {approx_words:,} words, exceeding the processing limit.\n"
            f"Ketchup will proceed using only the last ~{limit_words:,} words. Content beyond this limit will be ignored."
        )

        # Determine the primary notification target
        notify_channel_id = channel_context_id
        notify_user_id = user_id

        # Log attempt
        logger.info(
            "Attempting to send token limit notification (user: %s, channel: %s, response_url: %s)",
            notify_user_id,
            notify_channel_id,
            bool(response_url),
        )

        posting_handler = None
        try:
            registry = get_typed_registry()
            posting_handler = await registry.aget(SlackPostingHandlerProtocol)
            await posting_handler.setup()
            await posting_handler.post_message(
                user_id=notify_user_id,
                channel_id=notify_channel_id,
                message=status_message,
                response_url=response_url,
            )
            logger.info("Token limit notification sent successfully.")
        except Exception as e:
            logger.error(
                "Failed to send token limit notification: %s", str(e), exc_info=True
            )
        finally:
            if posting_handler:
                try:
                    await posting_handler.cleanup()
                except Exception as cleanup_error:
                    logger.error(
                        "Error during posting handler cleanup: %s", str(cleanup_error)
                    )

    def _truncate_messages_preserving_system(
        self,
        messages: List[Dict[str, str]],
        original_total_tokens: int,  # Passed for logging context
    ) -> List[Dict[str, str]]:
        """
        Truncates messages to fit MAX_PROCESSABLE_TOKENS, preserving the system message
        and prioritizing the *end* (most recent) of the user message content.

        Args:
            messages: The original list of messages (usually system + user).
            original_total_tokens: Original token count for logging.

        Returns:
            A new list of messages truncated to fit the token limit.
        """
        logger.info("Original total tokens: %s", original_total_tokens)
        tokenizer_func, decoder_func, is_tiktoken = get_tokenizer()

        # Get ALL system messages, not just the first one
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        user_messages = [msg for msg in messages if msg.get("role") == "user"]

        # Combine all system message content
        system_content = "\n\n".join(
            str(msg.get("content", "")) for msg in system_messages
        )

        # Combine all user message content
        user_content = "\n".join(str(msg.get("content", "")) for msg in user_messages)

        final_messages: List[Dict[str, str]] = []

        system_tokens = count_tokens(system_content)
        available_tokens_for_user = MAX_PROCESSABLE_TOKENS - system_tokens

        if available_tokens_for_user <= 10:
            # Not enough space for meaningful user content, truncate system message only
            logger.warning(
                "Not enough tokens (%s) remaining for user content after system message (%s tokens). Truncating system message to %s tokens.",
                available_tokens_for_user,
                system_tokens,
                MAX_PROCESSABLE_TOKENS,
            )
            # When system messages alone exceed limit, prioritize keeping the last system message
            # (which is usually the most important prompt/instructions)
            if len(system_messages) > 1:
                logger.warning(
                    "Multiple system messages detected. Keeping only the last one (usually the main prompt)."
                )
                # Keep only the last system message
                last_system_msg = system_messages[-1]
                system_content = str(last_system_msg.get("content", ""))

                if is_tiktoken:
                    system_token_ids = tokenizer_func(system_content)
                    if len(system_token_ids) > MAX_PROCESSABLE_TOKENS:
                        truncated_system_ids = system_token_ids[:MAX_PROCESSABLE_TOKENS]
                        truncated_system_content = decoder_func(truncated_system_ids)
                    else:
                        truncated_system_content = system_content
                else:
                    # Fallback: Simple character truncation for system message
                    char_limit = MAX_PROCESSABLE_TOKENS * 4
                    truncated_system_content = system_content[:char_limit]

                final_messages = [
                    {"role": "system", "content": truncated_system_content}
                ]
            else:
                # Single system message case
                if is_tiktoken:
                    system_token_ids = tokenizer_func(system_content)
                    truncated_system_ids = system_token_ids[:MAX_PROCESSABLE_TOKENS]
                    truncated_system_content = decoder_func(truncated_system_ids)
                else:
                    # Fallback: Simple character truncation for system message
                    char_limit = MAX_PROCESSABLE_TOKENS * 4
                    truncated_system_content = system_content[:char_limit]

                final_messages = [
                    {"role": "system", "content": truncated_system_content}
                ]

            new_total = count_tokens(truncated_system_content)
            logger.info("Messages after truncation (system only): %s tokens", new_total)
            return final_messages

        # We have space for user content, truncate it from the beginning (keep the end)
        logger.info(
            "Truncating beginning of user message content to fit %s tokens.",
            available_tokens_for_user,
        )

        if is_tiktoken:
            try:
                user_token_ids = tokenizer_func(user_content)
                if len(user_token_ids) > available_tokens_for_user:
                    # Keep the *last* N tokens
                    truncated_user_ids = user_token_ids[-available_tokens_for_user:]
                    truncated_user_content = decoder_func(truncated_user_ids)
                    logger.info(
                        "Truncated user content using tiktoken (kept end). New user tokens: %d",
                        len(truncated_user_ids),
                    )
                else:
                    # User content fits within the available tokens
                    truncated_user_content = user_content
                    logger.info(
                        "User content fits within available tokens, no truncation needed."
                    )

            except Exception as e:
                logger.error(
                    "tiktoken encoding/decoding failed during reverse truncation: %s. Falling back to line split.",
                    e,
                    exc_info=True,
                )
                # Fall through to line splitting fallback
                is_tiktoken = False  # Force fallback

        if not is_tiktoken:
            # Fallback: Split by lines and keep lines from the end
            logger.warning("Using line splitting fallback for reverse truncation.")
            lines = user_content.splitlines()
            kept_lines: List[str] = []
            current_line_tokens = 0
            for line in reversed(lines):
                line_token_count = count_tokens(line) + 1  # Add 1 for newline approx
                if current_line_tokens + line_token_count <= available_tokens_for_user:
                    kept_lines.insert(0, line)  # Insert at beginning to maintain order
                    current_line_tokens += line_token_count
                else:
                    logger.info("Line limit reached during fallback truncation.")
                    break  # Stop adding older lines
            truncated_user_content = "\n".join(kept_lines)
            logger.info(
                "Truncated user content using fallback (kept end). Approx user tokens: %d",
                current_line_tokens,
            )

        # Construct final messages - preserve ALL system messages separately
        final_messages = system_messages.copy()  # Keep all system messages as-is

        # Add the truncated user message
        if truncated_user_content:
            final_messages.append({"role": "user", "content": truncated_user_content})

        # Log final token count
        final_all_text = system_content + " " + truncated_user_content
        new_total = count_tokens(final_all_text)
        logger.info("Messages after reverse truncation: %s tokens", new_total)

        return final_messages
