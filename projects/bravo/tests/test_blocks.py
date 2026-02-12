"""Tests for Block Kit payload builders."""

import copy

import pytest

from bravo.services.blocks import (
    build_acknowledged_blocks,
    build_nudge_blocks,
    build_nudge_fallback_text,
    build_snoozed_blocks,
    build_unsnoozed_blocks,
    build_yes_updates_blocks,
    format_trigger_reasons,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_KWARGS: dict = {
    "ticket_key": "BRAVO-42",
    "ticket_url": "https://jira.example.com/browse/BRAVO-42",
    "jira_status": "In Progress",
    "summary": "Fix login timeout",
    "trigger_reason": "No assignee comment yet",
}


def _build_default_blocks() -> list[dict]:
    """Return nudge blocks built with SAMPLE_KWARGS (no optional fields)."""
    return build_nudge_blocks(**SAMPLE_KWARGS)


def _action_ids(blocks: list[dict]) -> list[str]:
    """Extract action_id values from the actions block."""
    for block in blocks:
        if block.get("type") == "actions":
            return [el["action_id"] for el in block["elements"]]
    return []


# ---------------------------------------------------------------------------
# format_trigger_reasons
# ---------------------------------------------------------------------------


def test_format_trigger_reasons_single_gate() -> None:
    result = format_trigger_reasons(["G1"])
    assert result == "No assignee comment yet"


def test_format_trigger_reasons_multiple_gates() -> None:
    result = format_trigger_reasons(["G1", "G3"])
    assert result == "No assignee comment yet \u00b7 No response within 24 hours"


def test_format_trigger_reasons_unknown_code_passed_through() -> None:
    result = format_trigger_reasons(["G1", "X9"])
    assert "No assignee comment yet" in result
    assert "X9" in result
    assert " \u00b7 " in result


def test_format_trigger_reasons_empty_list() -> None:
    result = format_trigger_reasons([])
    assert result == ""


# ---------------------------------------------------------------------------
# build_nudge_blocks
# ---------------------------------------------------------------------------


def test_build_nudge_blocks_required_args_only() -> None:
    blocks = _build_default_blocks()
    assert isinstance(blocks, list)
    assert all(isinstance(b, dict) for b in blocks)
    assert len(blocks) == 6
    assert blocks[0]["type"] == "header"
    assert blocks[-1]["type"] == "actions"


def test_build_nudge_blocks_with_llm_summary() -> None:
    blocks = build_nudge_blocks(**SAMPLE_KWARGS, llm_summary="AI says hello")
    assert len(blocks) == 7


def test_build_nudge_blocks_with_llm_summary_and_recent_activity() -> None:
    blocks = build_nudge_blocks(
        **SAMPLE_KWARGS,
        llm_summary="AI says hello",
        recent_activity="User commented 2h ago",
    )
    assert len(blocks) == 8


def test_build_nudge_blocks_ticket_key_in_header() -> None:
    blocks = _build_default_blocks()
    header_text = blocks[0]["text"]["text"]
    assert "BRAVO-42" in header_text


def test_build_nudge_blocks_ticket_url_in_info_section() -> None:
    blocks = _build_default_blocks()
    info_block = blocks[1]
    field_texts = [f["text"] for f in info_block["fields"]]
    assert any(SAMPLE_KWARGS["ticket_url"] in t for t in field_texts)


def test_build_nudge_blocks_action_button_ids() -> None:
    blocks = _build_default_blocks()
    ids = _action_ids(blocks)
    assert "nudge_yes_updates" in ids
    assert "nudge_no_updates" in ids
    assert "nudge_snooze_1h" in ids
    assert "nudge_snooze_4h" in ids


# ---------------------------------------------------------------------------
# build_nudge_fallback_text
# ---------------------------------------------------------------------------


def test_build_nudge_fallback_text_contains_fields() -> None:
    text = build_nudge_fallback_text(
        ticket_key="BRAVO-42",
        summary="Fix login timeout",
        trigger_reason="No assignee comment yet",
    )
    assert isinstance(text, str)
    assert "BRAVO-42" in text
    assert "Fix login timeout" in text
    assert "No assignee comment yet" in text


# ---------------------------------------------------------------------------
# build_snoozed_blocks
# ---------------------------------------------------------------------------


def test_build_snoozed_blocks_replaces_actions() -> None:
    original = _build_default_blocks()
    snoozed = build_snoozed_blocks(
        original_blocks=original,
        snoozed_until_text="3:00 PM",
        ticket_key="BRAVO-42",
    )
    # No block should have 4 action buttons
    for block in snoozed:
        if block.get("type") == "actions":
            assert len(block["elements"]) != 4


def test_build_snoozed_blocks_has_snooze_context() -> None:
    original = _build_default_blocks()
    snoozed = build_snoozed_blocks(
        original_blocks=original,
        snoozed_until_text="3:00 PM",
        ticket_key="BRAVO-42",
    )
    context_texts = []
    for block in snoozed:
        if block.get("type") == "context":
            for el in block.get("elements", []):
                context_texts.append(el.get("text", ""))
    assert any("Snoozed until" in t for t in context_texts)


def test_build_snoozed_blocks_has_unsnooze_button() -> None:
    original = _build_default_blocks()
    snoozed = build_snoozed_blocks(
        original_blocks=original,
        snoozed_until_text="3:00 PM",
        ticket_key="BRAVO-42",
    )
    ids = _action_ids(snoozed)
    assert "nudge_unsnooze" in ids


def test_build_snoozed_blocks_does_not_mutate_original() -> None:
    original = _build_default_blocks()
    original_snapshot = copy.deepcopy(original)
    build_snoozed_blocks(
        original_blocks=original,
        snoozed_until_text="3:00 PM",
        ticket_key="BRAVO-42",
    )
    assert original == original_snapshot


# ---------------------------------------------------------------------------
# build_acknowledged_blocks
# ---------------------------------------------------------------------------


def test_build_acknowledged_blocks_replaces_actions() -> None:
    original = _build_default_blocks()
    acked = build_acknowledged_blocks(original_blocks=original)
    # Actions block should be gone
    block_types = [b["type"] for b in acked]
    assert "actions" not in block_types
    # Context block with "Got it" should be present
    context_texts = []
    for block in acked:
        if block.get("type") == "context":
            for el in block.get("elements", []):
                context_texts.append(el.get("text", ""))
    assert any("Got it" in t for t in context_texts)


def test_build_acknowledged_blocks_does_not_mutate_original() -> None:
    original = _build_default_blocks()
    original_snapshot = copy.deepcopy(original)
    build_acknowledged_blocks(original_blocks=original)
    assert original == original_snapshot


# ---------------------------------------------------------------------------
# build_yes_updates_blocks
# ---------------------------------------------------------------------------


def test_build_yes_updates_blocks_replaces_actions() -> None:
    original = _build_default_blocks()
    result = build_yes_updates_blocks(original_blocks=original)
    block_types = [b["type"] for b in result]
    assert "actions" not in block_types
    context_texts = []
    for block in result:
        if block.get("type") == "context":
            for el in block.get("elements", []):
                context_texts.append(el.get("text", ""))
    assert any("Reply in this thread" in t for t in context_texts)


def test_build_yes_updates_blocks_does_not_mutate_original() -> None:
    original = _build_default_blocks()
    original_snapshot = copy.deepcopy(original)
    build_yes_updates_blocks(original_blocks=original)
    assert original == original_snapshot


# ---------------------------------------------------------------------------
# build_unsnoozed_blocks
# ---------------------------------------------------------------------------


def test_build_unsnoozed_blocks_restores_action_buttons() -> None:
    original = _build_default_blocks()
    snoozed = build_snoozed_blocks(
        original_blocks=original,
        snoozed_until_text="3:00 PM",
        ticket_key="BRAVO-42",
    )
    unsnoozed = build_unsnoozed_blocks(
        original_blocks=snoozed,
        ticket_key="BRAVO-42",
    )
    ids = _action_ids(unsnoozed)
    assert "nudge_yes_updates" in ids
    assert "nudge_no_updates" in ids
    assert "nudge_snooze_1h" in ids
    assert "nudge_snooze_4h" in ids
    assert len(ids) == 4


def test_build_unsnoozed_blocks_removes_snooze_context() -> None:
    original = _build_default_blocks()
    snoozed = build_snoozed_blocks(
        original_blocks=original,
        snoozed_until_text="3:00 PM",
        ticket_key="BRAVO-42",
    )
    unsnoozed = build_unsnoozed_blocks(
        original_blocks=snoozed,
        ticket_key="BRAVO-42",
    )
    for block in unsnoozed:
        if block.get("type") == "context":
            for el in block.get("elements", []):
                assert "Snoozed until" not in el.get("text", "")


def test_build_unsnoozed_blocks_handles_slack_emoji_shortcodes() -> None:
    """Slack converts Unicode emoji to shortcodes in round-tripped blocks."""
    original = _build_default_blocks()
    snoozed = build_snoozed_blocks(
        original_blocks=original,
        snoozed_until_text="3:00 PM",
        ticket_key="BRAVO-42",
    )
    # Simulate Slack replacing Unicode ⏸️ with :double_vertical_bar:
    for block in snoozed:
        if block.get("type") == "context":
            for el in block.get("elements", []):
                el["text"] = el["text"].replace("\u23f8\ufe0f", ":double_vertical_bar:")
    unsnoozed = build_unsnoozed_blocks(
        original_blocks=snoozed,
        ticket_key="BRAVO-42",
    )
    ids = _action_ids(unsnoozed)
    assert "nudge_yes_updates" in ids
    assert "nudge_no_updates" in ids
    assert "nudge_snooze_1h" in ids
    assert "nudge_snooze_4h" in ids
    assert len(ids) == 4
