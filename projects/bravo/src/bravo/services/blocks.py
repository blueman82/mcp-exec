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
                    "text": "\U0001f527 Fix now",
                    "emoji": True,
                },
                "action_id": "nudge_fix_now",
                "style": "primary",
                "value": ticket_key,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "\u2705 Yes, updates coming",
                    "emoji": True,
                },
                "action_id": "nudge_yes_updates",
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
                "action_id": "nudge_snooze_1h",
                "value": f"{ticket_key}|1h",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "\u23f0 Snooze 4h",
                    "emoji": True,
                },
                "action_id": "nudge_snooze_4h",
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
            and "Snoozed until" in elements[0].get("text", "")
        ):
            new_blocks.append(restored_actions)
            skip_next_actions = True
            continue

        if skip_next_actions and block.get("type") == "actions":
            skip_next_actions = False
            continue

        new_blocks.append(block)
    return new_blocks


_JIRA_BASE_URL = "https://jira.corp.adobe.com"


def build_collect_pat_modal() -> dict[str, Any]:
    """Build a Slack modal for collecting a user's Jira PAT.

    Returns:
        Slack view payload suitable for ``views.open()``.
        Caller sets ``private_metadata`` before opening.
    """
    pat_url = (
        f"{_JIRA_BASE_URL}/secure/ViewProfile.jspa"
        "?selectedTab=com.atlassian.pats.pats-plugin"
        ":jira-user-personal-access-tokens"
    )
    return {
        "type": "modal",
        "callback_id": "collect_pat_modal",
        "private_metadata": "",
        "title": {"type": "plain_text", "text": "Connect Jira"},
        "submit": {"type": "plain_text", "text": "Save PAT"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "To update Jira on your behalf, Bravo needs your "
                        "Personal Access Token (PAT).\n\n"
                        f"<{pat_url}|Generate a PAT in Jira>"
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "pat_input_block",
                "label": {"type": "plain_text", "text": "Jira PAT"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "pat_value",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Paste your Personal Access Token",
                    },
                },
            },
        ],
    }


_JIRA_PRIORITIES: list[str] = [
    "Blocker",
    "Critical",
    "Major",
    "Normal",
    "Minor",
    "Trivial",
]


def build_fix_now_modal(
    *,
    ticket_key: str,
    current_fields: dict[str, Any],
) -> dict[str, Any]:
    """Build a Slack modal view for fixing missing Jira fields.

    Only fields that are empty/missing in *current_fields* generate
    an input block.  Returns a modal with an empty ``blocks`` list
    when nothing is missing.

    Args:
        ticket_key: Jira ticket key (carried via ``private_metadata``).
        current_fields: Dict with keys ``description``, ``priority``,
            ``components`` holding the ticket's current values.

    Returns:
        Slack view payload suitable for ``views.open()``.
    """
    input_blocks: list[dict[str, Any]] = []

    if not current_fields.get("description"):
        input_blocks.append(
            {
                "type": "input",
                "block_id": "fix_description",
                "label": {
                    "type": "plain_text",
                    "text": "Description",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe the issue or request\u2026",
                    },
                },
            }
        )

    if not current_fields.get("priority"):
        input_blocks.append(
            {
                "type": "input",
                "block_id": "fix_priority",
                "label": {
                    "type": "plain_text",
                    "text": "Priority",
                },
                "element": {
                    "type": "static_select",
                    "action_id": "priority_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select priority",
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": p},
                            "value": p,
                        }
                        for p in _JIRA_PRIORITIES
                    ],
                },
            }
        )

    if not current_fields.get("components"):
        input_blocks.append(
            {
                "type": "input",
                "block_id": "fix_components",
                "label": {
                    "type": "plain_text",
                    "text": "Components",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "components_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Comma-separated, e.g. Backend, API",
                    },
                },
            }
        )

    # Truncate title to Slack's 24-char limit for modal titles.
    title_text = f"Fix {ticket_key}"
    if len(title_text) > 24:
        title_text = title_text[:24]

    return {
        "type": "modal",
        "callback_id": "fix_now_modal",
        "private_metadata": ticket_key,
        "title": {"type": "plain_text", "text": title_text},
        "submit": {"type": "plain_text", "text": "Update Jira"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": input_blocks,
    }


def build_comment_modal(
    ticket_key: str,
    success_message: str,
) -> dict[str, Any]:
    """Build a modal for writing a Jira comment after PAT validation.

    Combines a success banner with a free-text input for the engineer's
    comment. Uses ``comment_modal`` callback_id so the submission routes
    to ``_handle_comment_submission``.

    Args:
        ticket_key: Jira ticket key (carried via ``private_metadata``).
        success_message: Success banner text shown above the input.

    Returns:
        Slack view payload suitable for ``response_action: "update"``.
    """
    title_text = f"Comment on {ticket_key}"
    if len(title_text) > 24:
        title_text = title_text[:24]

    return {
        "type": "modal",
        "callback_id": "comment_modal",
        "private_metadata": "",
        "title": {"type": "plain_text", "text": title_text},
        "submit": {"type": "plain_text", "text": "Post Comment"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"\u2705 {success_message}",
                },
            },
            {
                "type": "input",
                "block_id": "comment_input_block",
                "label": {"type": "plain_text", "text": "Your comment"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "comment_value",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe your update or progress\u2026",
                    },
                },
            },
        ],
    }


def build_pat_error_modal(ticket_key: str) -> dict[str, Any]:
    """Build an error modal shown when PAT validation fails.

    Reuses ``collect_pat_modal`` callback_id so a retry goes through
    the existing PAT collection handler.

    Args:
        ticket_key: Jira ticket key (informational context).

    Returns:
        Slack view payload suitable for ``response_action: "update"``.
    """
    pat_url = (
        f"{_JIRA_BASE_URL}/secure/ViewProfile.jspa"
        "?selectedTab=com.atlassian.pats.pats-plugin"
        ":jira-user-personal-access-tokens"
    )
    return {
        "type": "modal",
        "callback_id": "collect_pat_modal",
        "private_metadata": "",
        "title": {"type": "plain_text", "text": "Connect Jira"},
        "submit": {"type": "plain_text", "text": "Retry"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "\u26a0\ufe0f *PAT validation failed*\n\n"
                        "The token you entered could not authenticate with Jira. "
                        "Please check that:\n"
                        "\u2022 The token is not expired\n"
                        "\u2022 It was copied completely (no extra spaces)\n"
                        "\u2022 It has the required permissions\n\n"
                        f"<{pat_url}|Generate a new PAT in Jira>"
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "pat_input_block",
                "label": {"type": "plain_text", "text": "Jira PAT"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "pat_value",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Paste your Personal Access Token",
                    },
                },
            },
        ],
    }


def build_reeval_result_blocks(
    *,
    original_blocks: list[dict[str, Any]],
    passed: bool,
    trigger_reason: str,
) -> list[dict[str, Any]]:
    """Replace the Why + actions blocks with a re-evaluation result.

    Preserves the header, ticket info, and first divider from the original
    nudge, then replaces everything after with the re-eval result as a
    prominent section block.

    Args:
        original_blocks: The current nudge Block Kit payload.
        passed: Whether all checks passed.
        trigger_reason: Human-readable reasons (for failed re-eval).

    Returns:
        New list of blocks with re-eval result.
    """
    # Keep blocks up to and including the first divider after ticket info
    kept: list[dict[str, Any]] = []
    divider_count = 0
    for block in copy.deepcopy(original_blocks):
        kept.append(block)
        if block.get("type") == "divider":
            divider_count += 1
            if divider_count >= 1:
                break

    if passed:
        result_section: dict[str, Any] = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "\u2705 *Re-evaluation \u2014 all checks passed!*\n\n"
                    "Your update resolved all issues. No further action needed."
                ),
            },
        }
    else:
        result_section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"\u26a0\ufe0f *Re-evaluation \u2014 still needs attention*\n\n"
                    f"{trigger_reason}"
                ),
            },
        }

    comment_context: dict[str, Any] = {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": "\u2709\ufe0f Your comment was posted to Jira"},
        ],
    }

    kept.append(result_section)
    kept.append(_divider_block())
    kept.append(comment_context)
    return kept


def build_fix_error_blocks(
    *,
    original_blocks: list[dict[str, Any]],
    ticket_key: str,
    error_message: str,
) -> list[dict[str, Any]]:
    """Replace the actions block with an error notice and restored action buttons.

    Allows the user to retry after a Jira update failure.

    Args:
        original_blocks: The original nudge Block Kit payload.
        ticket_key: Jira ticket key for rebuilding the actions block.
        error_message: User-facing error description.

    Returns:
        New list of blocks with the actions block replaced.
    """
    error_context: dict[str, Any] = {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"\u26a0\ufe0f {error_message}"},
        ],
    }
    restored_actions = _actions_block(ticket_key)
    return _replace_actions(original_blocks, error_context, restored_actions)


def build_fix_submitted_blocks(
    *,
    original_blocks: list[dict[str, Any]],
    fields_updated: list[str],
) -> list[dict[str, Any]]:
    """Replace the actions block with a fix-submitted confirmation.

    Args:
        original_blocks: The original nudge Block Kit payload.
        fields_updated: List of field names that were updated.

    Returns:
        New list of blocks with the actions block replaced.
    """
    field_list = ", ".join(fields_updated) if fields_updated else "fields"
    fix_context: dict[str, Any] = {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"\U0001f527 Updated via Fix now: {field_list}",
            },
        ],
    }
    return _replace_actions(original_blocks, fix_context)
