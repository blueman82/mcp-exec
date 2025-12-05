"""
slack_message_formatter.py

This module contains the SlackMessageFormatter class, responsible for
cleaning and formatting Slack messages fetched from the API.
"""

import html
import re
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple

from packages.core.logging import setup_logger
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


class SlackMessageFormatter:
    """Handles formatting and cleaning of Slack message data."""

    def __init__(self, user_ops: SlackUserOps):
        """
        Initialize the formatter with necessary dependencies.

        Args:
            user_ops: Instance of SlackUserOps for user ID to name resolution.
        """
        self._user_ops = user_ops
        logger.info("SlackMessageFormatter initialized.")

    def convert_timestamp_to_utc(self, timestamp: str) -> str:
        """
        Convert a Slack timestamp string to a UTC formatted string.

        Args:
            timestamp: Slack timestamp string (e.g., "1625846400.000100")

        Returns:
            UTC formatted string (e.g., "YYYY-MM-DD HH:MM:SS UTC")
        """
        try:
            ts_float = float(timestamp)
            dt_object = datetime.fromtimestamp(ts_float, tz=timezone.utc)
            return dt_object.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, TypeError) as e:
            logger.error("Error converting timestamp '%s': %s", timestamp, e)
            return "Invalid Timestamp"

    async def replace_user_ids_with_names(self, text: str, user_cache: Dict[str, str]) -> str:
        """
        Replace Slack user ID mentions (<@Uxxxxxxx>) with actual usernames.

        Args:
            text: The message text containing potential user mentions.
            user_cache: A dictionary mapping user IDs to usernames.

        Returns:
            Text with user IDs replaced by usernames.
        """

        def replace_mention(match):
            user_id = match.group(1)
            # Use the provided cache, fallback to the original mention if not found
            return f"@{user_cache.get(user_id, match.group(0))}"

        # Use re.sub with the inner function as the replacement
        return re.sub(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", replace_mention, text)

    def clean_text(self, text: str) -> str:
        """
        Clean message text by unescaping HTML entities and removing unwanted patterns.

        Args:
            text: The raw message text.

        Returns:
            The cleaned message text.
        """
        if not text:
            return ""

        # Unescape HTML entities like &amp;, &lt;, &gt;
        cleaned = html.unescape(text)

        # Remove remaining Slack mrkdwn formatting (bold, italics, etc.) - optional
        # cleaned = re.sub(r'[*_`~]', '', cleaned)

        # Remove potential leftover angle brackets from failed links/mentions
        cleaned = cleaned.replace("<", "").replace(">", "")

        # Normalize whitespace (replace multiple spaces/newlines with a single space)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    async def process_message_batch(
        self, messages: List[Dict], user_mentions: Set[str]
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Process a batch of raw messages into formatted strings.

        This combines timestamp conversion, user ID replacement, and text cleaning.
        It now also handles fetching the user cache internally.

        Args:
            messages: List of raw message dictionaries from Slack API.
            user_mentions: Set of user IDs mentioned in the batch and threads.

        Returns:
            A tuple containing:
                - List of formatted message strings.
                - User cache dictionary mapping mentioned user IDs to names.
        """
        processed_messages = []

        # Get user names for all collected user mentions
        user_cache = await self._user_ops.get_user_names(list(user_mentions))

        # Sort messages by timestamp before processing
        # Assuming messages might not be perfectly ordered if threads were fetched separately
        sorted_messages = sorted(messages, key=lambda x: float(x.get("ts", "0")))

        for msg in sorted_messages:
            timestamp = self.convert_timestamp_to_utc(msg.get("ts", "0"))
            user_id = msg.get("user", "Unknown User")
            username = user_cache.get(user_id, user_id)  # Use cache
            text = msg.get("text", "")

            if text:
                # Replace mentions using the fetched cache
                text_with_names = await self.replace_user_ids_with_names(text, user_cache)
                # Clean the text
                cleaned_text = self.clean_text(text_with_names)

                formatted_msg = f"[{timestamp}] {username}: {cleaned_text}"
                processed_messages.append(formatted_msg)

        return processed_messages, user_cache
