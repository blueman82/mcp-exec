"""Block Kit payload builders for Bravo nudge messages."""

import copy
from typing import Any

GATE_REASON_MAP: dict[str, str] = {
    "G1": "No assignee comment yet",
    "G2": "No update in 4+ hours",
    "G3": "No response within 24 hours",
    "G4": "Unresolved past deadline",
}


def format_trigger_reasons(failed_gates: list[str]) -> str:
    """Join gate codes into user-facing text.

    Args:
        failed_gates: List of gate codes (e.g. ``["G1", "G3"]``).

    Returns:
        Human-readable string with reasons joined by " · ".
    """
    return " · ".join(GATE_REASON_MAP.get(code, code) for code in failed_gates)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _header_block(ticket_key: str) -> dict[str, Any]:
    """Header block with ticket key."""
    return {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"\U0001f514 {ticket_key} needs attention",
            "emoji": True,
        },
    }


def _ticket_info_section(
    *,
    ticket_key: str,
    ticket_url: str,
    jira_status: str,
    summary: str,
) -> dict[str, Any]:
    """Ticket info section with link and status."""
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*Ticket:* <{ticket_url}|{ticket_key}>"},
            {"type": "mrkdwn", "text": f"*Status:* {jira_status}"},
            {"type": "mrkdwn", "text": f"*Summary:* {summary}"},
        ],
    }


def _divider_block() -> dict[str, Any]:
    """Divider block."""
    return {"type": "divider"}


def _llm_summary_section(llm_summary: str) -> dict[str, Any]:
    """Section for LLM-generated summary."""
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*AI Summary:*\n{llm_summary}"},
    }


def _recent_activity_section(recent_activity: str) -> dict[str, Any]:
    """Section for recent activity."""
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Recent Activity:*\n{recent_activity}"},
    }


def _trigger_context(trigger_reason: str) -> dict[str, Any]:
    """Context block showing why the nudge was triggered."""
    return {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"\u26a1 *Why:* {trigger_reason}"},
        ],
    }


def _actions_block(ticket_key: str) -> dict[str, Any]:
    """Action buttons block."""
    return {
        "type": "actions",
        "block_id": f"nudge_actions_{ticket_key}",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "\u2705 Yes, updates coming",
                    "emoji": True,
                },
                "action_id": "nudge_yes_updates",
                "style": "primary",
                "value": ticket_key,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "\U0001f44d No updates needed",
                    "emoji": True,
                },
                "action_id": "nudge_no_updates",
                "value": ticket_key,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "\u23f0 Snooze 1h",
                    "emoji": True,
                },
                "action_id": "nudge_snooze",
                "value": f"{ticket_key}|1h",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "\u23f0 Snooze 4h",
                    "emoji": True,
                },
                "action_id": "nudge_snooze",
                "value": f"{ticket_key}|4h",
            },
        ],
    }


def _replace_actions(
    original_blocks: list[dict[str, Any]], *replacements: dict[str, Any]
) -> list[dict[str, Any]]:
    """Replace actions block(s) with one or more replacement blocks."""
    new_blocks: list[dict[str, Any]] = []
    for block in copy.deepcopy(original_blocks):
        if block.get("type") == "actions":
            new_blocks.extend(replacements)
            continue
        new_blocks.append(block)
    return new_blocks


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------


def build_nudge_blocks(
    *,
    ticket_key: str,
    ticket_url: str,
    jira_status: str,
    summary: str,
    llm_summary: str | None = None,
    recent_activity: str | None = None,
    trigger_reason: str,
) -> list[dict[str, Any]]:
    """Build the full Block Kit payload for a nudge message.

    Args:
        ticket_key: Jira ticket key (e.g. ``"BRAVO-123"``).
        ticket_url: URL linking to the Jira ticket.
        jira_status: Current Jira status label.
        summary: Ticket summary / title.
        llm_summary: Optional LLM-generated summary of the ticket.
        recent_activity: Optional recent activity text.
        trigger_reason: Human-readable reason the nudge was triggered.

    Returns:
        List of Slack Block Kit block dicts.
    """
    blocks: list[dict[str, Any]] = [
        _header_block(ticket_key),
        _ticket_info_section(
            ticket_key=ticket_key,
            ticket_url=ticket_url,
            jira_status=jira_status,
            summary=summary,
        ),
        _divider_block(),
    ]

    if llm_summary is not None:
        blocks.append(_llm_summary_section(llm_summary))

    if recent_activity is not None:
        blocks.append(_recent_activity_section(recent_activity))

    blocks.append(_trigger_context(trigger_reason))
    blocks.append(_divider_block())
    blocks.append(_actions_block(ticket_key))

    return blocks


def build_nudge_fallback_text(
    *,
    ticket_key: str,
    summary: str,
    trigger_reason: str,
) -> str:
    """Build plain-text fallback for a nudge message.

    Args:
        ticket_key: Jira ticket key.
        summary: Ticket summary / title.
        trigger_reason: Human-readable trigger reason.

    Returns:
        Plain-text string suitable for Slack ``text`` field.
    """
    return f"\U0001f514 {ticket_key} needs attention: {summary} \u2014 {trigger_reason}"


def build_snoozed_blocks(
    *,
    original_blocks: list[dict[str, Any]],
    snoozed_until_text: str,
    ticket_key: str,
) -> list[dict[str, Any]]:
    """Replace the actions block with a snooze notice and unsnooze button.

    Args:
        original_blocks: The original nudge Block Kit payload.
        snoozed_until_text: Human-readable snooze expiry (e.g. ``"3:00 PM"``).
        ticket_key: Jira ticket key for the unsnooze button value.

    Returns:
        New list of blocks with the actions block replaced.
    """
    snooze_context: dict[str, Any] = {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"\u23f8\ufe0f Snoozed until {snoozed_until_text}",
            },
        ],
    }
    unsnooze_actions: dict[str, Any] = {
        "type": "actions",
        "block_id": f"nudge_actions_{ticket_key}",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "\u25b6\ufe0f Unsnooze",
                    "emoji": True,
                },
                "action_id": "nudge_unsnooze",
                "value": ticket_key,
            },
        ],
    }
    return _replace_actions(original_blocks, snooze_context, unsnooze_actions)


def build_acknowledged_blocks(
    *, original_blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace the actions block with an acknowledgement notice.

    Args:
        original_blocks: The original nudge Block Kit payload.

    Returns:
        New list of blocks with the actions block replaced.
    """
    ack_context: dict[str, Any] = {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "\U0001f44d Got it \u2014 will check back in 4 hours",
            },
        ],
    }
    return _replace_actions(original_blocks, ack_context)


def build_yes_updates_blocks(
    *, original_blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace the actions block with a prompt to reply in thread.

    Args:
        original_blocks: The original nudge Block Kit payload.

    Returns:
        New list of blocks with the actions block replaced.
    """
    reply_context: dict[str, Any] = {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": "\u2705 Reply in this thread with your update"},
        ],
    }
    return _replace_actions(original_blocks, reply_context)


def build_unsnoozed_blocks(
    *,
    original_blocks: list[dict[str, Any]],
    ticket_key: str,
) -> list[dict[str, Any]]:
    """Replace snoozed context and unsnooze actions with the original actions block.

    Args:
        original_blocks: The snoozed Block Kit payload.
        ticket_key: Jira ticket key for rebuilding the actions block.

    Returns:
        New list of blocks with snoozed blocks replaced by action buttons.
    """
    restored_actions = _actions_block(ticket_key)

    new_blocks: list[dict[str, Any]] = []
    skip_next_actions = False
    for block in copy.deepcopy(original_blocks):
        # The snoozed state has a context block (snooze notice) immediately
        # followed by an actions block (unsnooze button). Detect the snooze
        # context and flag so we also skip the subsequent actions block.
        elements = block.get("elements", [])
        if (
            block.get("type") == "context"
            and elements
            and isinstance(elements[0], dict)
            and "\u23f8" in elements[0].get("text", "")
        ):
            new_blocks.append(restored_actions)
            skip_next_actions = True
            continue

        if skip_next_actions and block.get("type") == "actions":
            skip_next_actions = False
            continue

        new_blocks.append(block)
    return new_blocks
