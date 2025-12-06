"""
formatters.py

Shared formatting utilities for BlockKit messages.

NOTE: Most shared message formatting logic has moved to
`blockkit_message_utils.py` in the handlers directory.
Only `clean_response_text` and `format_channel_list` remain here
for use by archive/lookup handlers and others.
"""

import re
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.core.time_utils import convert_timestamp_to_utc

logger = setup_logger(__name__)


def format_channel_list(
    title: str, channels: List[Dict[str, Any]], include_archive_time: bool = False
) -> str:
    """
    Format a list of channels for display.

    Args:
        title: The title for the channel list
        channels: List of channel information dictionaries
        include_archive_time: Whether to include archive timestamp

    Returns:
        Formatted channel list as a string
    """
    if not channels:
        return f"*{title}*\n\nNo channels to display."

    result = f"*{title}*\n\n"

    for idx, channel in enumerate(channels, 1):
        channel_id = channel.get("channel_id", "NOT YET AVAILABLE")
        channel_name = channel.get("channel_name", "NOT YET AVAILABLE")
        customer_name = channel.get("customer_name", "NOT YET AVAILABLE")
        jira_ticket = channel.get("jira_ticket", "NOT YET AVAILABLE")

        # Format JIRA ticket - only create link if it's a valid JIRA ID
        formatted_jira_ticket = jira_ticket
        jira_pattern = r"^[A-Z][A-Z0-9]+-\d+$"
        if (
            jira_ticket
            and jira_ticket != "NOT YET AVAILABLE"
            and re.match(jira_pattern, jira_ticket, re.IGNORECASE)
        ):
            formatted_jira_ticket = (
                f"<https://jira.corp.adobe.com/browse/{jira_ticket}|{jira_ticket}>"
            )

        result += (
            f"{idx}. *Channel:* <#{channel_id}|{channel_name}>\n"
            f"   • *Customer:* {customer_name}\n"
            f"   • *Support Ticket:* {formatted_jira_ticket}\n"
            f"   • *Channel ID:* `{channel_id}`\n"
        )

        if include_archive_time and "archived_at" in channel:
            archive_time = convert_timestamp_to_utc(channel["archived_at"])
            result += f"   • *Archived At:* `{archive_time}`\n"

        result += "\n"

    return result


def clean_response_text(response_text: str, query: Optional[str] = None) -> str:
    """
    Clean response text to remove duplicated elements.

    Args:
        response_text: The response text to clean
        query: The query string that was used

    Returns:
        Cleaned response text
    """
    if query:
        query_pattern = re.compile(r"(?i)^(?:query|question):\s*" + re.escape(query) + r"\s*\n+")
        response_text = query_pattern.sub("", response_text)

    response_prefixes = [
        r"^(?:Response|Answer):\s*\n*",
        r"^Here\'s\s+(?:a|the)\s+(?:response|answer)(?:\s+to\s+your\s+(?:query|question))?:\s*\n*",
        r"^(?:I\'ll|Let\s+me)\s+(?:help|assist)\s+(?:you|with\s+that)(?:\.|:)?\s*\n*",
        r"^(?:Based\s+on|According\s+to|From)\s+(?:the|your)\s+(?:question|query|information|details)(?:\.|:)?\s*\n*",
    ]

    for pattern in response_prefixes:
        response_text = re.sub(re.compile(pattern, re.IGNORECASE), "", response_text)

    response_text = response_text.strip()

    return response_text
