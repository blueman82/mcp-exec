"""Tests for Block Kit payload builders."""

import copy

import pytest

from bravo.services.blocks import (
    build_acknowledged_blocks,
    build_collect_pat_modal,
    build_fix_error_blocks,
    build_fix_now_modal,
    build_fix_submitted_blocks,
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
    assert "nudge_fix_now" in ids
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
    assert "nudge_fix_now" in ids
    assert "nudge_yes_updates" in ids
    assert "nudge_no_updates" in ids
    assert "nudge_snooze_1h" in ids
    assert "nudge_snooze_4h" in ids
    assert len(ids) == 5


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
    assert "nudge_fix_now" in ids
    assert "nudge_yes_updates" in ids
    assert "nudge_no_updates" in ids
    assert "nudge_snooze_1h" in ids
    assert "nudge_snooze_4h" in ids
    assert len(ids) == 5


# ---------------------------------------------------------------------------
# Fix now button properties
# ---------------------------------------------------------------------------


def test_build_nudge_blocks_fix_now_is_first_action() -> None:
    blocks = _build_default_blocks()
    ids = _action_ids(blocks)
    assert ids[0] == "nudge_fix_now"


def test_build_nudge_blocks_fix_now_is_primary() -> None:
    blocks = _build_default_blocks()
    for block in blocks:
        if block.get("type") == "actions":
            fix_btn = block["elements"][0]
            assert fix_btn["action_id"] == "nudge_fix_now"
            assert fix_btn.get("style") == "primary"
            break


# ---------------------------------------------------------------------------
# build_fix_now_modal
# ---------------------------------------------------------------------------


def test_build_fix_now_modal_all_fields_missing() -> None:
    modal = build_fix_now_modal(
        ticket_key="BRAVO-42",
        current_fields={"summary": "test", "description": "", "priority": "", "components": []},
    )
    assert modal["callback_id"] == "fix_now_modal"
    assert modal["private_metadata"] == "BRAVO-42"
    block_ids = [b["block_id"] for b in modal["blocks"]]
    assert "fix_description" in block_ids
    assert "fix_priority" in block_ids
    assert "fix_components" in block_ids
    assert len(modal["blocks"]) == 3


def test_build_fix_now_modal_partial_missing() -> None:
    modal = build_fix_now_modal(
        ticket_key="BRAVO-42",
        current_fields={
            "summary": "test",
            "description": "",
            "priority": "Major",
            "components": ["Backend"],
        },
    )
    assert len(modal["blocks"]) == 1
    assert modal["blocks"][0]["block_id"] == "fix_description"


def test_build_fix_now_modal_no_fields_missing() -> None:
    modal = build_fix_now_modal(
        ticket_key="BRAVO-42",
        current_fields={
            "summary": "test",
            "description": "A description",
            "priority": "Major",
            "components": ["Backend"],
        },
    )
    assert modal["blocks"] == []


def test_build_fix_now_modal_title_truncated() -> None:
    modal = build_fix_now_modal(
        ticket_key="CPGNCX-123456789012345",
        current_fields={"summary": "", "description": "", "priority": "", "components": []},
    )
    title = modal["title"]["text"]
    assert len(title) <= 24


def test_build_fix_now_modal_priority_has_options() -> None:
    modal = build_fix_now_modal(
        ticket_key="BRAVO-42",
        current_fields={"summary": "test", "description": "ok", "priority": "", "components": ["X"]},
    )
    assert len(modal["blocks"]) == 1
    element = modal["blocks"][0]["element"]
    assert element["type"] == "static_select"
    option_values = [o["value"] for o in element["options"]]
    assert "Blocker" in option_values
    assert "Minor" in option_values


# ---------------------------------------------------------------------------
# build_fix_submitted_blocks
# ---------------------------------------------------------------------------


def test_build_fix_submitted_blocks_replaces_actions() -> None:
    original = _build_default_blocks()
    result = build_fix_submitted_blocks(
        original_blocks=original,
        fields_updated=["description", "priority"],
    )
    block_types = [b["type"] for b in result]
    assert "actions" not in block_types
    context_texts = []
    for block in result:
        if block.get("type") == "context":
            for el in block.get("elements", []):
                context_texts.append(el.get("text", ""))
    assert any("Fix now" in t for t in context_texts)
    assert any("description" in t for t in context_texts)


def test_build_fix_submitted_blocks_does_not_mutate_original() -> None:
    original = _build_default_blocks()
    original_snapshot = copy.deepcopy(original)
    build_fix_submitted_blocks(
        original_blocks=original,
        fields_updated=["components"],
    )
    assert original == original_snapshot


# ---------------------------------------------------------------------------
# build_fix_error_blocks
# ---------------------------------------------------------------------------


def test_build_fix_error_blocks_replaces_actions() -> None:
    original = _build_default_blocks()
    result = build_fix_error_blocks(
        original_blocks=original,
        ticket_key="BRAVO-42",
        error_message="Could not update BRAVO-42",
    )
    # Original 5-button actions block should be gone; a new actions block
    # with restored buttons should exist after the error context.
    action_blocks = [b for b in result if b.get("type") == "actions"]
    assert len(action_blocks) == 1
    # The restored actions block should have 5 buttons (all original buttons)
    assert len(action_blocks[0]["elements"]) == 5


def test_build_fix_error_blocks_shows_error_text() -> None:
    original = _build_default_blocks()
    result = build_fix_error_blocks(
        original_blocks=original,
        ticket_key="BRAVO-42",
        error_message="Jira update timed out for BRAVO-42",
    )
    context_texts = []
    for block in result:
        if block.get("type") == "context":
            for el in block.get("elements", []):
                context_texts.append(el.get("text", ""))
    assert any("Jira update timed out for BRAVO-42" in t for t in context_texts)


def test_build_fix_error_blocks_restores_action_buttons() -> None:
    original = _build_default_blocks()
    result = build_fix_error_blocks(
        original_blocks=original,
        ticket_key="BRAVO-42",
        error_message="Could not update BRAVO-42",
    )
    ids = _action_ids(result)
    assert "nudge_fix_now" in ids
    assert "nudge_yes_updates" in ids
    assert "nudge_no_updates" in ids
    assert "nudge_snooze_1h" in ids
    assert "nudge_snooze_4h" in ids


# ---------------------------------------------------------------------------
# build_collect_pat_modal
# ---------------------------------------------------------------------------


def test_build_collect_pat_modal_structure() -> None:
    modal = build_collect_pat_modal()
    assert modal["callback_id"] == "collect_pat_modal"
    assert modal["title"]["text"] == "Connect Jira"
    assert modal["submit"]["text"] == "Save PAT"
    assert modal["close"]["text"] == "Cancel"
    assert modal["private_metadata"] == ""


def test_build_collect_pat_modal_has_pat_input() -> None:
    modal = build_collect_pat_modal()
    input_blocks = [b for b in modal["blocks"] if b.get("type") == "input"]
    assert len(input_blocks) == 1
    assert input_blocks[0]["block_id"] == "pat_input_block"
    assert input_blocks[0]["element"]["action_id"] == "pat_value"
    assert input_blocks[0]["element"]["type"] == "plain_text_input"


def test_build_collect_pat_modal_has_jira_link() -> None:
    modal = build_collect_pat_modal()
    section = modal["blocks"][0]
    assert section["type"] == "section"
    text = section["text"]["text"]
    assert "jira.corp.adobe.com" in text
    assert "personal-access-tokens" in text
