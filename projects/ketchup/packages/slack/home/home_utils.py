"""
home_utils.py

This module provides stateless utility functions for the Slack Home tab interface in Ketchup.
It includes logic for building Block Kit blocks, extracting user preferences from Slack payloads,
and saving user preferences to the database.
"""

from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.slack.home.usage_stats_utils import (
    build_admin_command_breakdown_blocks,
    build_admin_export_section,
    build_admin_usage_stats_blocks,
    build_usage_stats_blocks,
)

logger = setup_logger(__name__)


def validate_initial_option(options, initial_option):
    """Ensure initial_option is present in options, else return the first option."""
    if not initial_option:
        return options[0] if options else None
    for opt in options:
        if opt["value"] == initial_option["value"]:
            return initial_option
    return options[0] if options else None


def get_detail_level_display_name(detail_level: str) -> str:
    """Get the display name for a detail level value."""
    detail_map = {
        "high_level": "High-Level Overview",
        "technical_details": "Technical Details",
        "balanced": "Balanced Mix",
    }
    return detail_map.get(detail_level, "Balanced Mix")


def get_time_window_display_name(time_window: str) -> str:
    """Get the display name for a time window value."""
    time_map = {
        "past_2_hours": "Past 2 hours (falls back to latest)",
        "past_24_hours": "Last day (falls back to latest)",
        "all_time": "All Time (Complete channel history)",
        "always_ask": "Always ask me",
    }
    return time_map.get(time_window, "Last day (falls back to latest)")


def get_initial_include_options(include_options: List[str]) -> List[Dict[str, Any]]:
    """Get the initial options for include in summary selection."""
    include_map = {
        "issue_summary": "Issue Root Cause Summary (if available)",
        "action_items": "Action Items (if available)",
        "key_decisions": "Key Decisions (if available)",
        "code_changes": "Relevant Code/Config Changes (if available)",
    }
    return [
        {
            "text": {
                "type": "plain_text",
                "text": include_map.get(option, ""),
                "emoji": True,
            },
            "value": option,
        }
        for option in include_options
        if option in include_map
    ]


def normalize_user_preferences(prefs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize user preferences for use in prompts.

    Converts underscored values to human-readable format and handles special cases.

    Args:
        prefs: Raw user preferences dictionary

    Returns:
        Normalized preferences with prompt-friendly values
    """
    normalized = prefs.copy()

    # Normalize detail level
    detail_level = prefs.get("detail_level", "balanced")
    if detail_level == "high_level":
        normalized["detail_level"] = "high-level"
    elif detail_level == "technical_details":
        normalized["detail_level"] = "technical"
    else:
        normalized["detail_level"] = "balanced"

    # Normalize time window
    time_window = prefs.get("time_window", "past_24_hours")
    if time_window:
        if time_window == "all_time":
            normalized["time_window"] = "complete channel history"
        else:
            normalized["time_window"] = time_window.replace("_", " ")

    # Normalize product focus
    product_focus = prefs.get("product_focus", ["all_products"])
    if isinstance(product_focus, list):
        product_map = {
            "ajo": "Adobe Journey Optimizer",
            "campaign": "Adobe Campaign",
            "all_products": "all Adobe products",
        }
        normalized_focus = []
        for product in product_focus:
            normalized_focus.append(product_map.get(product, product.replace("_", " ")))
        normalized["product_focus"] = normalized_focus

    return normalized


def build_home_tab_blocks(
    user_prefs: Dict[str, Any],
    first_name: str,
    command_stats: Optional[Dict[str, int]] = None,
    is_admin_user: bool = False,
    admin_stats: Optional[List[tuple]] = None,
    admin_command_breakdown: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build the Block Kit blocks for the Home tab.

    Args:
        user_prefs: The user's preferences
        first_name: The user's first name
        command_stats: Optional personal command usage statistics
        is_admin_user: Whether the user is an admin
        admin_stats: Optional admin-level usage statistics
        admin_command_breakdown: Optional detailed command breakdown by user

    Returns:
        List of Block Kit blocks for the Home tab
    """
    product_map = {
        "ajo": "Adobe Journey Optimizer",
        "campaign": "Adobe Campaign",
        "all_products": "All Products",
    }

    blocks = [
        # Header section
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"👋 Hi {first_name}! Welcome to Ketchup Preferences",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Customize how Ketchup delivers channel summaries specifically for you. Your preferences will be used to personalize all summaries you request.",
            },
        },
        {"type": "divider"},
        # Product focus selection
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Primary Product Focus*\nSelect which Adobe products you're primarily interested in.",
            },
        },
        {
            "type": "actions",
            "block_id": "product_focus_selection",
            "elements": [
                {
                    "type": "static_select",
                    "action_id": "product_focus_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select product",
                        "emoji": True,
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": name,
                                "emoji": True,
                            },
                            "value": val,
                        }
                        for val, name in product_map.items()
                    ],
                    "initial_option": validate_initial_option(
                        [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": name,
                                    "emoji": True,
                                },
                                "value": val,
                            }
                            for val, name in product_map.items()
                        ],
                        {
                            "text": {
                                "type": "plain_text",
                                "text": product_map.get(
                                    user_prefs.get("product_focus", ["all_products"])[0],
                                    product_map["all_products"],
                                ),
                                "emoji": True,
                            },
                            "value": user_prefs.get("product_focus", ["all_products"])[0],
                        },
                    ),
                }
            ],
        },
        {"type": "divider"},
        # Detail level selection
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Preferred Summary Detail Level*\nChoose how detailed you want your summaries to be.",
            },
        },
        {
            "type": "actions",
            "block_id": "detail_level_selection",
            "elements": [
                {
                    "type": "radio_buttons",
                    "action_id": "detail_level_select",
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "High-Level Overview",
                                "emoji": True,
                            },
                            "value": "high_level",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Technical Details",
                                "emoji": True,
                            },
                            "value": "technical_details",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Balanced Mix",
                                "emoji": True,
                            },
                            "value": "balanced",
                        },
                    ],
                    "initial_option": validate_initial_option(
                        [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": get_detail_level_display_name(val),
                                    "emoji": True,
                                },
                                "value": val,
                            }
                            for val in [
                                "high_level",
                                "technical_details",
                                "balanced",
                            ]
                        ],
                        {
                            "text": {
                                "type": "plain_text",
                                "text": get_detail_level_display_name(
                                    user_prefs.get("detail_level", "balanced")
                                ),
                                "emoji": True,
                            },
                            "value": user_prefs.get("detail_level", "balanced"),
                        },
                    ),
                }
            ],
        },
        {"type": "divider"},
        # Time window selection
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Default Summary Time Window*\nSelect your preferred time range for summaries.",
            },
        },
        {
            "type": "actions",
            "block_id": "time_window_selection",
            "elements": [
                {
                    "type": "radio_buttons",
                    "action_id": "time_window_select",
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Past 2 hours (falls back to latest)",
                                "emoji": True,
                            },
                            "value": "past_2_hours",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Last day (falls back to latest)",
                                "emoji": True,
                            },
                            "value": "past_24_hours",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "All Time (Complete channel history)",
                                "emoji": True,
                            },
                            "value": "all_time",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Always ask me",
                                "emoji": True,
                            },
                            "value": "always_ask",
                        },
                    ],
                    "initial_option": validate_initial_option(
                        [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": get_time_window_display_name(val),
                                    "emoji": True,
                                },
                                "value": val,
                            }
                            for val in [
                                "past_2_hours",
                                "past_24_hours",
                                "all_time",
                                "always_ask",
                            ]
                        ],
                        {
                            "text": {
                                "type": "plain_text",
                                "text": get_time_window_display_name(
                                    user_prefs.get("time_window", "past_24_hours")
                                ),
                                "emoji": True,
                            },
                            "value": user_prefs.get("time_window", "past_24_hours"),
                        },
                    ),
                }
            ],
        },
        # Add time window tooltip
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":information_source: If no activity exists in your selected time window, Ketchup will automatically use the most recent information available.",
                }
            ],
        },
        {"type": "divider"},
        # Join notifications enable/disable selection
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Join Channel Notifications*\nReceive a welcome message with channel summary when you join new channels.",
            },
        },
        {
            "type": "actions",
            "block_id": "join_notifications_enabled_selection",
            "elements": [
                {
                    "type": "radio_buttons",
                    "action_id": "join_notifications_enabled_select",
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Enabled - Show me a summary when I join channels",
                                "emoji": True,
                            },
                            "value": "enabled",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Disabled - Don't show notifications",
                                "emoji": True,
                            },
                            "value": "disabled",
                        },
                    ],
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": (
                                "Enabled - Show me a summary when I join channels"
                                if user_prefs.get("join_notifications_enabled", "enabled")
                                == "enabled"
                                else "Disabled - Don't show notifications"
                            ),
                            "emoji": True,
                        },
                        "value": user_prefs.get("join_notifications_enabled", "enabled"),
                    },
                }
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":information_source: When you join eligible channels, Ketchup will send you an ephemeral update in your chosen format.",
                }
            ],
        },
        {"type": "divider"},
        # Support & Feedback section
        {  # --- Feedback & Support header ---
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Support & Feedback*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":book: *Need help?* Check the <https://wiki.corp.adobe.com/display/neolane/Ketchup+How-To|Ketchup How-To Guide> for usage instructions and examples.",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":speech_balloon: *Have feedback or ideas?* Join the <https://adobe.enterprise.slack.com/archives/C08CQN1JCSC|#ketchup-feedback> channel to share your thoughts or report issues.",
            },
        },
        {
            "type": "actions",
            "block_id": "feedback_actions_block",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Report Feedback / Suggest Idea",
                        "emoji": True,
                    },
                    "action_id": "home_open_feedback_modal",
                }
            ],
        },
        {"type": "divider"},  # End Feedback section
    ]

    # -------------------------------
    # Save button
    # -------------------------------
    blocks.extend(
        [
            # Save button
            {
                "type": "actions",
                "block_id": "save_preferences",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Save Preferences",
                            "emoji": True,
                        },
                        "style": "primary",
                        "action_id": "save_preferences_button",
                    }
                ],
            },
            # Footer for save button
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "These preferences will be used to personalize summaries just for you. You can update them any time. :ketchup:",
                    }
                ],
            },
        ]
    )

    # Add divider before optional stats sections if any will be shown
    if command_stats or (is_admin_user and (admin_stats or admin_command_breakdown)):
        blocks.append({"type": "divider"})

    # -------------------------------
    # Optional: Personal usage stats
    # -------------------------------
    if command_stats:
        try:
            blocks.extend(build_usage_stats_blocks(command_stats, first_name))
            # Add a divider to separate from potential admin sections
            if is_admin_user and (admin_stats or admin_command_breakdown):
                blocks.append({"type": "divider"})
        except Exception as e:  # noqa: BLE001 – keep home tab resilient
            logger.error("Error building personal usage stats blocks: %s", str(e))

    # -------------------------------
    # Optional: Admin usage stats
    # -------------------------------
    if is_admin_user and admin_stats:
        try:
            blocks.extend(build_admin_usage_stats_blocks(admin_stats))
            # Add divider between admin sections if there are more to come
            if admin_command_breakdown:
                blocks.append({"type": "divider"})
        except Exception as e:  # noqa: BLE001
            logger.error("Error building admin usage stats blocks: %s", str(e))

    # -------------------------------
    # Optional: Admin command breakdown
    # -------------------------------
    if is_admin_user and admin_command_breakdown:
        try:
            blocks.extend(build_admin_command_breakdown_blocks(admin_command_breakdown))
            # Always add divider before export section
            blocks.append({"type": "divider"})
        except Exception as e:  # noqa: BLE001
            logger.error("Error building admin command breakdown blocks: %s", str(e))

    # -------------------------------
    # Optional: Admin export section
    # -------------------------------
    if is_admin_user:
        try:
            blocks.extend(build_admin_export_section())
        except Exception as e:  # noqa: BLE001
            logger.error("Error building admin export section: %s", str(e))

    return blocks


def extract_preferences_from_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract preferences from the payload state (view.state.values).

    Args:
        payload: The block_actions payload from Slack

    Returns:
        Dict containing the user's preferences
    """
    state = (
        payload.get("view", {}).get("state", {}).get("values", {}) if payload.get("view") else {}
    )
    if not state:
        state = payload.get("state", {}).get("values", {})

    def get_selected_option(block, action_id, multi=False):
        if block and action_id in block:
            action = block[action_id]
            if multi:
                return [opt["value"] for opt in action.get("selected_options", [])]
            else:
                return action.get("selected_option", {}).get("value")
        return None

    product_focus = get_selected_option(
        state.get("product_focus_selection"), "product_focus_select", multi=False
    )
    if product_focus:
        product_focus = [product_focus]
    else:
        product_focus = ["all_products"]

    detail_level = (
        get_selected_option(state.get("detail_level_selection"), "detail_level_select")
        or "balanced"
    )
    time_window = (
        get_selected_option(state.get("time_window_selection"), "time_window_select")
        or "past_24_hours"
    )
    join_notifications_enabled = (
        get_selected_option(
            state.get("join_notifications_enabled_selection"),
            "join_notifications_enabled_select",
        )
        or "enabled"
    )

    return {
        "product_focus": product_focus,
        "detail_level": detail_level,
        "time_window": time_window,
        "join_notifications_enabled": join_notifications_enabled,
    }


async def save_user_preferences(
    user_id: str,
    payload: Dict[str, Any],
    user_store,
    slack_user_ops,
    slack_client,
) -> bool:
    """Save a user's preferences to the database.

    Args:
        user_id: The Slack user ID
        payload: The block_actions payload from Slack
        user_store: Store for user preference data
        slack_user_ops: SlackUserOps for fetching user info
        slack_client: SlackAsyncClient for Slack API interactions

    Returns:
        bool: True if the preferences were saved successfully, False otherwise
    """
    try:
        preferences = extract_preferences_from_state(payload)
        logger.info(f"Extracted preferences from UI state: {preferences}")
        await slack_user_ops.get_user_names([user_id])
        success = await user_store.store_user_preferences(user_id, preferences)
        if success is not False:
            trigger_id = payload.get("trigger_id")
            user_data = await user_store.get_user(user_id)
            real_name = user_data.get("real_name", "there") if user_data else "there"
            if trigger_id:
                await open_success_modal(trigger_id, real_name, slack_client)
            return True
        logger.warning(
            f"Failed to store preferences for user {user_id} according to user_store.store_user_preferences."
        )
        return False
    except Exception as e:
        logger.error("Error saving user preferences: %s", str(e), exc_info=True)
        return False


async def open_success_modal(trigger_id: str, real_name: str, slack_client) -> bool:
    """Open a success modal to confirm preferences update, personalized with the user's first name.

    Args:
        trigger_id: The trigger ID provided by Slack to open the modal
        real_name: The user's real name (full name)
        slack_client: SlackAsyncClient for Slack API interactions

    Returns:
        bool: True if the modal was opened successfully, False otherwise
    """
    try:
        first_name = real_name.split()[0] if real_name else "there"
        payload = {
            "trigger_id": trigger_id,
            "view": {
                "type": "modal",
                "callback_id": "preferences_saved",
                "title": {
                    "type": "plain_text",
                    "text": "Preferences Saved",
                    "emoji": True,
                },
                "close": {"type": "plain_text", "text": "Close", "emoji": True},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *Thank you {first_name}, your preferences are now saved!*",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "Your preferences will be used to personalize your summaries. You can update them any time from the Home tab.",
                            }
                        ],
                    },
                ],
            },
        }
        data = await slack_client.api_call("views.open", payload)
        if not data.get("ok"):
            logger.error("Failed to open success modal: %s", data.get("error"))
            return False
        logger.info("Successfully opened success modal")
        return True
    except Exception as e:
        logger.error("Error opening success modal: %s", str(e))
        return False
