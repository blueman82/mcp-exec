"""Slack Block Kit message formatters.

This module provides functions to format messages using Slack's Block Kit API.
Includes formatters for final SPL queries with dual explanations, clarifying
questions with interactive buttons, and uncertainty messages.

Privacy Note:
    - NEVER log the content of blocks/messages
    - Only log metadata (thread_id, block count, etc.)
"""

from typing import Any


def format_final_query(
    plain_explanation: str, spl_query: str, technical_explanation: str
) -> list[dict[str, Any]]:
    """Format final SPL query with dual explanations.

    Creates a Slack Block Kit message with:
    - Plain language explanation for non-technical users
    - SPL query in code block (no language identifier to prevent copy issues)
    - Technical details for experts
    - Session complete notification for transparency

    Args:
        plain_explanation: Plain language explanation for non-technical users
        spl_query: The SPL query string
        technical_explanation: Technical details for experts

    Returns:
        List of Slack Block Kit block dicts

    Example:
        >>> blocks = format_final_query(
        ...     "This finds email bounces in last 24 hours",
        ...     "index=campaign_prod failureType=* earliest=-24h",
        ...     "Uses campaign_prod index, failureType field"
        ... )
        >>> len(blocks)
        5
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Plain Language:*\n{plain_explanation}",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```\n{spl_query}\n```"},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"_Technical: {technical_explanation}_"}],
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "✓ Session complete - all data cleared. Start a new thread for another query.",
                }
            ],
        },
    ]


def format_clarifying_question(question: str, options: list[str]) -> list[dict[str, Any]]:
    """Format clarifying question with numbered options.

    Creates a message with numbered options that users can reply to.
    This avoids Slack's 75-char button text limit.

    Args:
        question: The clarifying question to ask
        options: List of option strings

    Returns:
        List of Slack Block Kit block dicts

    Example:
        >>> blocks = format_clarifying_question(
        ...     "Which log type?",
        ...     ["eventlog_momentum", "mta_log"]
        ... )
        >>> "1." in blocks[1]["text"]["text"]
        True
    """
    # Build numbered options list
    options_text = "\n".join([f"*{i+1}.* {opt}" for i, opt in enumerate(options)])

    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{question}*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": options_text}},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_Reply with a number (1, 2, etc.) or describe what you need._",
                }
            ],
        },
    ]

    return blocks


def format_uncertainty_message(missing_info: str) -> list[dict[str, Any]]:
    """Format honest uncertainty message.

    When the agent lacks sufficient information to answer confidently,
    this creates a message that:
    - Clearly states what information is missing
    - Suggests user provide more details
    - Maintains honest communication (no hallucination)

    Args:
        missing_info: Description of what information is missing

    Returns:
        List of Slack Block Kit block dicts

    Example:
        >>> blocks = format_uncertainty_message("log retention period")
        >>> "⚠️" in blocks[0]["text"]["text"]
        True
        >>> "log retention period" in blocks[0]["text"]["text"]
        True
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ I don't have enough information about: *{missing_info}*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Could you provide more details or rephrase your question?",
            },
        },
    ]
