"""
Utility functions for formatting and enhancing Slack Block Kit messages.

This module provides shared logic for formatting messages, creating Slack blocks, and enhancing text-only fallbacks.
Use these helpers to keep Block Kit handler code DRY and maintainable.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from packages.core.logging import setup_logger
from packages.core.time_utils import convert_timestamp_to_utc
from packages.slack.formatters.utils import enhance_structured_text, normalize_text

logger = setup_logger(__name__)


def create_context_tooltip_block():
    """
    Create a Slack context block with a tooltip message.

    Returns:
        Slack context block with tooltip message
    """
    return {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": ":information_source: Only *Customer* and *Support Ticket* are editable. Channel ID cannot be changed.",
            }
        ],
    }


def format_message_header_with_channel_details(
    title: str,
    channel_detail: Optional[Dict[str, Any]] = None,
    query: Optional[str] = None,
) -> str:
    """
    Format the header part of a message, including title, channel details, and query.

    Args:
        title: Message title
        channel_detail: Optional channel details to include
        query: Optional query to include

    Returns:
        Formatted header string
    """
    message_start = f"*{title}*\n\n"
    if channel_detail:
        jira_ticket = channel_detail.get("jira_ticket", "NOT YET AVAILABLE")
        formatted_jira_ticket = jira_ticket
        jira_pattern = r"^[A-Z][A-Z0-9]+-\d+$"
        if jira_ticket and jira_ticket != "NOT YET AVAILABLE" and isinstance(jira_ticket, str):
            if re.match(jira_pattern, jira_ticket, re.IGNORECASE):
                formatted_jira_ticket = (
                    f"<https://jira.corp.adobe.com/browse/{jira_ticket}|{jira_ticket}>"
                )
            else:
                formatted_jira_ticket = jira_ticket
        message_start += (
            f"*Customer Name:*\n{channel_detail.get('customer_name', 'NOT YET AVAILABLE')}\n\n"
            f"*Support Ticket:*\n{formatted_jira_ticket}\n\n"
            f"*Channel Name:*\n<#{channel_detail.get('channel_id', 'NOT YET AVAILABLE')}|{channel_detail.get('channel_name', 'NOT YET AVAILABLE')}>\n\n"
            f"*Channel ID:*\n`{channel_detail.get('channel_id', 'NOT YET AVAILABLE')}`\n\n"
        )
    if query:
        message_start += f"*Query:*\n`{query}`\n\n"
    return message_start


def format_message_body_with_response(
    content: str,
    query: Optional[str] = None,
) -> str:
    """
    Format the body part of a message, including the response label and content.

    Args:
        content: Main message content
        query: Optional query to determine if response label is needed

    Returns:
        Formatted body string
    """
    content_text = normalize_text(content)
    response_label = "*Response:*\n" if query is not None else ""
    return response_label + content_text + "\n\n"


def create_message_blocks(message: str) -> List[Dict[str, Any]]:
    """
    Create Slack blocks for message content, splitting long messages.

    Args:
        message: The formatted message string

    Returns:
        List of Slack block objects
    """
    max_chars = 3000  # Slack's limit for section text
    blocks = []
    start = 0
    while start < len(message):
        # Find the best split point (prefer newlines) before max_chars
        end = start + max_chars
        if end < len(message):
            # Look backwards from max_chars for a newline
            split_point = message.rfind("\n", start, end)
            if split_point == -1 or split_point <= start:
                split_point = end
            else:
                split_point += 1
        else:
            split_point = len(message)

        block_text = message[start:split_point].strip()
        if block_text:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": block_text},
                }
            )
        start = split_point

    if not blocks and message.strip():
        logger.warning(
            "Message splitting resulted in no blocks, adding original message truncated."
        )
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message[:max_chars]},
            }
        )
    elif not blocks:
        logger.warning("Original message was effectively empty, resulted in no blocks.")

    max_blocks = 50
    if len(blocks) > max_blocks:
        logger.warning("Message resulted in %d blocks, truncating to %d.", len(blocks), max_blocks)
        truncation_block: Dict[str, Any] = {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":warning: *Message truncated due to length limits.*",
                }
            ],
        }
        blocks = blocks[: max_blocks - 1] + [truncation_block]

    return blocks


def enhance_message_for_fallback(message: str) -> str:
    """
    Enhance a message for text-only fallback display.

    When Block Kit messages fail to send, this function enhances
    the plain text for better readability in a text-only context.

    Args:
        message: Original formatted message

    Returns:
        Enhanced message optimized for text-only display
    """
    enhanced_message = enhance_structured_text(message)
    return enhanced_message


def format_channel_list_block(
    idx: int,
    channel: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Format a section and actions block for a channel summary with an Edit button.

    Args:
        idx: The index of the channel in the list (1-based)
        channel: Channel metadata dict

    Returns:
        Tuple of (section block, actions block)
    """
    channel_id = channel.get("channel_id", "NOT AVAILABLE")
    channel_name = channel.get("channel_name", "NOT YET AVAILABLE")
    customer_name = channel.get("customer_name", "NOT YET AVAILABLE")
    jira_ticket = channel.get("jira_ticket", "NOT YET AVAILABLE")
    archived_at = channel.get("archived_at")
    # Format JIRA ticket as clickable link if valid
    formatted_jira_ticket = jira_ticket
    jira_pattern = r"^[A-Z][A-Z0-9]+-\d+$"
    if jira_ticket and jira_ticket != "NOT YET AVAILABLE" and isinstance(jira_ticket, str):
        if re.match(jira_pattern, jira_ticket, re.IGNORECASE):
            formatted_jira_ticket = (
                f"<https://jira.corp.adobe.com/browse/{jira_ticket}|{jira_ticket}>"
            )
        else:
            formatted_jira_ticket = jira_ticket
    section_text = (
        f"{idx}. *Channel:* <#{channel_id}|{channel_name}>\n"
        f"*Customer:* {customer_name}\n"
        f"*Support Ticket:* {formatted_jira_ticket}\n"
        f"*Channel ID:* `{channel_id}`\n"
    )
    if archived_at:
        archived_str = convert_timestamp_to_utc(archived_at)
        section_text += f"*Archived:* `{archived_str}`"
    section_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": section_text},
    }
    actions_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Edit Customer/Ticket"},
                "action_id": "edit_channel_metadata",
                "value": json.dumps(
                    {
                        "channel_id": channel_id,
                        "customer_name": customer_name,
                        "jira_ticket": jira_ticket,
                    }
                ),
            }
        ],
    }
    return section_block, actions_block
