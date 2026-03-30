"""
home_utils.py

Covers:
- extract_preferences_from_state: Extracts user preferences from Slack view payload
- validate_initial_option: Validates initial option selection for Block Kit
- get_detail_level_display_name: Maps detail level keys to display names
- get_time_window_display_name: Maps time window keys to display names
- get_initial_include_options: Filters valid include_in_summary options
- build_home_tab_blocks: Generates Block Kit blocks for the Home tab

Edge Cases Covered:
- Missing or unknown values in preferences
- Empty options or initial values
- Unknown keys for display name functions
- Filtering out invalid include_in_summary options
- Block Kit structure validation

Expected Outcomes:
- Functions return correct values for valid and invalid input
- Block Kit blocks contain required sections (header, actions, context)
- All logic branches and error cases are covered
"""

from packages.slack.home.home_utils import (
    build_home_tab_blocks,
    extract_preferences_from_state,
    get_detail_level_display_name,
    get_initial_include_options,
    get_time_window_display_name,
    validate_initial_option,
)


def test_extract_preferences_from_state_default():
    """Test extraction of preferences from a standard Slack view payload."""
    payload = {
        "view": {
            "state": {
                "values": {
                    "product_focus_selection": {
                        "product_focus_select": {"selected_option": {"value": "ajo"}}
                    },
                    "detail_level_selection": {
                        "detail_level_select": {"selected_option": {"value": "technical_details"}}
                    },
                    "time_window_selection": {
                        "time_window_select": {"selected_option": {"value": "past_2_hours"}}
                    },
                }
            }
        }
    }
    prefs = extract_preferences_from_state(payload)
    assert prefs["product_focus"] == ["ajo"]
    assert prefs["detail_level"] == "technical_details"
    assert prefs["time_window"] == "past_2_hours"
    assert prefs["join_notifications_enabled"] == "enabled"


def test_extract_preferences_join_notifications_enabled():
    """Test extraction of join notifications enabled preference."""
    payload = {
        "view": {
            "state": {
                "values": {
                    "product_focus_selection": {
                        "product_focus_select": {"selected_option": {"value": "all_products"}}
                    },
                    "detail_level_selection": {
                        "detail_level_select": {"selected_option": {"value": "balanced"}}
                    },
                    "time_window_selection": {
                        "time_window_select": {"selected_option": {"value": "past_24_hours"}}
                    },
                    "join_notifications_enabled_selection": {
                        "join_notifications_enabled_select": {
                            "selected_option": {"value": "disabled"}
                        }
                    },
                }
            }
        }
    }
    prefs = extract_preferences_from_state(payload)
    assert prefs["join_notifications_enabled"] == "disabled"


def test_extract_preferences_join_notifications_enabled_missing():
    """Test extraction falls back to enabled when join notifications preference is missing."""
    payload = {
        "view": {
            "state": {
                "values": {
                    "product_focus_selection": {
                        "product_focus_select": {"selected_option": {"value": "all_products"}}
                    },
                    "detail_level_selection": {
                        "detail_level_select": {"selected_option": {"value": "balanced"}}
                    },
                    "time_window_selection": {
                        "time_window_select": {"selected_option": {"value": "past_24_hours"}}
                    },
                }
            }
        }
    }
    prefs = extract_preferences_from_state(payload)
    assert prefs["join_notifications_enabled"] == "enabled"


def test_validate_initial_option():
    """Test that validate_initial_option returns the correct initial or fallback option."""
    options = [
        {"value": "a"},
        {"value": "b"},
    ]
    initial = {"value": "b"}
    assert validate_initial_option(options, initial) == initial
    assert validate_initial_option(options, {"value": "c"}) == options[0]
    assert validate_initial_option([], None) is None


def test_get_detail_level_display_name():
    """Test mapping of detail level keys to display names, including unknown key fallback."""
    assert get_detail_level_display_name("high_level").startswith("High-Level")
    assert get_detail_level_display_name("technical_details").startswith("Technical")
    assert get_detail_level_display_name("balanced").startswith("Balanced")
    assert get_detail_level_display_name("unknown") == "Balanced Mix"


def test_get_time_window_display_name():
    """Test mapping of time window keys to display names, including unknown key fallback."""
    assert get_time_window_display_name("past_2_hours") == "Past 2 hours (falls back to latest)"
    assert get_time_window_display_name("past_24_hours") == "Last day (falls back to latest)"
    assert get_time_window_display_name("since_last_summary") == "Last day (falls back to latest)"
    assert get_time_window_display_name("unknown") == "Last day (falls back to latest)"


def test_get_initial_include_options():
    """Test filtering of valid include_in_summary options from input list."""
    opts = get_initial_include_options(["issue_summary", "action_items", "unknown"])
    assert any(o["value"] == "issue_summary" for o in opts)
    assert any(o["value"] == "action_items" for o in opts)
    assert all(o["value"] != "unknown" for o in opts)


def test_build_home_tab_blocks():
    """Test that build_home_tab_blocks returns a valid block kit structure for preferences."""
    prefs = {
        "role": "technical_user",
        "product_focus": ["all_products"],
        "detail_level": "balanced",
        "time_window": "past_24_hours",
        "include_in_summary": "issue_summary",  # Pass a single value, not a list
    }
    first_name = "TestUser"
    blocks = build_home_tab_blocks(prefs, first_name)
    assert isinstance(blocks, list)

    # Find the header and check for personalized greeting
    header_block = next((b for b in blocks if b["type"] == "header"), None)
    assert header_block is not None
    assert header_block["text"]["type"] == "plain_text", "Header blocks must use plain_text type"
    assert f"Hi {first_name}!" in header_block["text"]["text"]

    # Check for intro section without how-to link
    intro_section = blocks[1]  # Second block should be the intro section
    assert intro_section["type"] == "section"
    assert "Customize how Ketchup delivers" in intro_section["text"]["text"]
    assert "Ketchup How-To" not in intro_section["text"]["text"]

    # Check for Support & Feedback section
    support_section_index = next(
        (
            i
            for i, b in enumerate(blocks)
            if b["type"] == "section" and "Support & Feedback" in b["text"]["text"]
        ),
        None,
    )
    assert support_section_index is not None

    # Check for feedback button
    feedback_actions_block = next(
        (b for b in blocks if b.get("block_id") == "feedback_actions_block"),
        None,
    )
    assert feedback_actions_block is not None
    assert feedback_actions_block["type"] == "actions"
    assert any(
        e["action_id"] == "home_open_feedback_modal" for e in feedback_actions_block["elements"]
    )

    # Basic structure checks
    assert any(b["type"] == "actions" for b in blocks)
    assert any(b["type"] == "context" for b in blocks)
