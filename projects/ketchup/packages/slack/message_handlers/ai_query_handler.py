"""
ai_query_handler.py

This module contains the AI query message handler for processing
AI-related queries from Slack messages in various contexts.
"""

import re
from typing import Optional, Tuple

from packages.core.constants import (
    SLACK_CHANNEL_ID_REGEX,
    SLACK_CHANNEL_MENTION_REGEX,
)
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class AIQueryMessageHandler:
    """
    Handler for AI query messages that need to extract channel information
    from message text in various formats.
    """

    def _extract_channel_from_message(self, message_text: str) -> Optional[str]:
        """
        Extract channel reference from message text.

        Handles both standard channel names and Slack channel mention formats:
        - Standard: #channel-name
        - Slack mention: <#CHANNEL_ID|channel-name>

        Args:
            message_text: The message text to extract channel from

        Returns:
            The extracted channel reference (ID, mention, or name) or None if not found
        """
        if not message_text:
            return None

        # First check for Slack channel mentions: <#CHANNEL_ID|channel-name>
        mention_match = SLACK_CHANNEL_MENTION_REGEX.search(message_text)
        if mention_match:
            # Return the full mention format
            return mention_match.group(0)

        # Then check for standard channel names: #channel-name
        # Updated regex pattern to handle both formats properly
        channel_name_pattern = re.compile(r"(^|\s)#([a-z0-9][a-z0-9_-]{0,80})")
        name_match = channel_name_pattern.search(message_text)
        if name_match:
            # Return the channel name with #
            return f"#{name_match.group(2)}"

        # Check for direct channel IDs without # prefix
        id_match = SLACK_CHANNEL_ID_REGEX.search(message_text)
        if id_match:
            return id_match.group(0)

        return None

    def extract_channel_info(self, message_text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract channel information and determine the format type.

        Args:
            message_text: The message text to extract channel from

        Returns:
            Tuple of (channel_reference, format_type) where format_type is one of:
            'mention', 'name', 'id', or None
        """
        channel_ref = self._extract_channel_from_message(message_text)

        if not channel_ref:
            return None, None

        # Determine format type
        if SLACK_CHANNEL_MENTION_REGEX.match(channel_ref):
            return channel_ref, 'mention'
        elif channel_ref.startswith('#'):
            return channel_ref, 'name'
        elif SLACK_CHANNEL_ID_REGEX.match(channel_ref):
            return channel_ref, 'id'
        else:
            return channel_ref, 'unknown'