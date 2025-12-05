"""
usage_stats_utils.py

This module provides utility functions for building Block Kit blocks
to display command usage statistics in the Slack home tab.
"""

from typing import Any, Dict, List

from packages.core.logging import setup_logger
from packages.db.operations.command_tracking_operations import get_week_date_range

logger = setup_logger(__name__)


def build_usage_stats_blocks(
    command_stats: Dict[str, int], username: str = "you", days: int = 7
) -> List[Dict[str, Any]]:
    """
    Build Block Kit blocks for displaying command usage statistics.

    Args:
        command_stats: Dictionary mapping command types to their usage counts
        username: Username to display in the stats (default: "you")
        days: Number of days the stats cover (default: 7)

    Returns:
        List of Block Kit blocks for the usage stats section
    """
    blocks = []

    # Add header section
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bar_chart: Command Usage Statistics",
                "emoji": True,
            },
        }
    )

    # Add description section
    # Get current week date range
    week_range = get_week_date_range()

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Showing command usage for *{username}* for the week of *{week_range}*. "
                "This data helps track which commands are most frequently used.",
            },
        }
    )

    # Add divider
    blocks.append({"type": "divider"})

    # If no data, show a message
    if not command_stats:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":warning: No command usage data available for this period.",
                },
            }
        )
        return blocks

    # Calculate total commands
    total_commands = sum(command_stats.values())

    # Add total commands section
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Total Commands Executed:* {total_commands}",
            },
        }
    )

    # Format command stats
    command_details = format_command_stats(command_stats)

    # Add command breakdown section
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Command Breakdown:*\n" + command_details,
            },
        }
    )

    return blocks


def format_command_stats(command_stats: Dict[str, int]) -> str:
    """
    Format command statistics into a readable string with emojis.

    Args:
        command_stats: Dictionary mapping command types to their usage counts

    Returns:
        Formatted string with command stats
    """
    # Define emojis for each command type
    command_emojis = {
        "status": ":traffic_light:",
        "report": ":memo:",
        "analyze": ":mag:",
        "short": ":scissors:",
        "long": ":page_with_curl:",
        "query": ":question:",
        "list": ":clipboard:",
        "archive": ":file_folder:",
        "unknown": ":grey_question:",
    }

    # Sort commands by usage count (descending)
    sorted_commands = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)

    # Format each command with emoji and count
    formatted_lines = []
    for cmd_type, count in sorted_commands:
        # Get emoji for this command type (default to unknown)
        emoji = command_emojis.get(cmd_type.lower(), command_emojis["unknown"])

        # Format command name to be more readable
        readable_name = cmd_type.lower().replace("_", " ").capitalize()

        # Add formatted line
        formatted_lines.append(f"{emoji} *{readable_name}*: {count}")

    # Join lines with newlines
    return "\n".join(formatted_lines)


def build_admin_usage_stats_blocks(
    top_users: List[tuple], days: int = 7, limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Build Block Kit blocks for displaying admin-level usage statistics.

    Args:
        top_users: List of (user_id, user_name, command_count) tuples
        days: Number of days the stats cover (default: 7)
        limit: Maximum number of users to display (default: 5)

    Returns:
        List of Block Kit blocks for the admin usage stats section
    """
    blocks = []

    # Add header section
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":chart_with_upwards_trend: Team Usage Statistics",
                "emoji": True,
            },
        }
    )

    # Add description section
    # Get current week date range
    week_range = get_week_date_range()

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Showing team command usage for the week of *{week_range}*. "
                f"This data helps track overall bot usage across the team.\n"
                f"_Showing top {limit} users. Use 'Export to CSV' to see all users._",
            },
        }
    )

    # Add divider
    blocks.append({"type": "divider"})

    # If no data, show a message
    if not top_users:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":warning: No team usage data available for this period.",
                },
            }
        )
        return blocks

    # Format top users list (excluding Gary Harrison)
    top_users_formatted = []
    rank = 1
    for user_id, user_name, count in top_users[: limit * 2]:  # Get extra in case we filter some out
        # Skip Gary Harrison
        if user_id == "W7MGASQ2K":
            continue

        if rank > limit:
            break
        # Add medal emoji for top 3
        if rank == 1:
            medal = ":first_place_medal: "
        elif rank == 2:
            medal = ":second_place_medal: "
        elif rank == 3:
            medal = ":third_place_medal: "
        else:
            medal = ""

        top_users_formatted.append(f"{medal}*{user_name}*: {count} commands")
        rank += 1

    # Add top users section
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Top Users:*\n" + "\n".join(top_users_formatted),
            },
        }
    )

    return blocks


def build_admin_command_breakdown_blocks(
    user_command_breakdown: Dict[str, Dict[str, Any]], days: int = 7
) -> List[Dict[str, Any]]:
    """
    Build Block Kit blocks for displaying detailed command breakdown by user.

    Args:
        user_command_breakdown: Dictionary mapping user_id to {user_name, commands: {command_type: count}}
        days: Number of days the stats cover (default: 7)

    Returns:
        List of Block Kit blocks for the admin command breakdown section
    """
    blocks = []

    # Add header section
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bar_chart: Command Breakdown by User",
                "emoji": True,
            },
        }
    )

    # Add description section
    # Get current week date range
    week_range = get_week_date_range()

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Detailed command usage per user for the week of *{week_range}*.\n"
                f"_Showing top 5 users. Use 'Export to CSV' to see all users._",
            },
        }
    )

    # Add divider
    blocks.append({"type": "divider"})

    # If no data, show a message
    if not user_command_breakdown:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":warning: No detailed command data available for this period.",
                },
            }
        )
        return blocks

    # Build breakdown text for all users (excluding Gary Harrison)
    breakdown_lines = []
    for user_id, user_data in user_command_breakdown.items():
        # Skip Gary Harrison
        if user_id == "W7MGASQ2K":
            continue
        user_name = user_data.get("user_name", "unknown")
        commands = user_data.get("commands", {})

        # Add user header
        breakdown_lines.append(f"*{user_name}*")

        # Add each command for this user
        for cmd_type, count in commands.items():
            breakdown_lines.append(f"  • {cmd_type}: {count}")

        # Add spacing between users
        breakdown_lines.append("")

    # Remove trailing empty line
    if breakdown_lines and breakdown_lines[-1] == "":
        breakdown_lines.pop()

    # Split into chunks if too long (Slack has a 3000 char limit per text block)
    breakdown_text = "\n".join(breakdown_lines)

    # If text is too long, split into multiple sections
    if len(breakdown_text) > 2500:
        # Split by users to avoid breaking in the middle of a user's data
        current_chunk = []
        current_length = 0

        i = 0
        while i < len(breakdown_lines):
            # Find the next user section (starts with bold text)
            if breakdown_lines[i].startswith("*") and i > 0:
                # Check if adding this user would exceed limit
                user_section = []
                j = i
                while j < len(breakdown_lines) and not (
                    j > i and breakdown_lines[j].startswith("*")
                ):
                    user_section.append(breakdown_lines[j])
                    j += 1

                section_text = "\n".join(user_section)
                if current_length + len(section_text) > 2500 and current_chunk:
                    # Add current chunk as a block
                    blocks.append(
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "\n".join(current_chunk),
                            },
                        }
                    )
                    current_chunk = user_section
                    current_length = len(section_text)
                else:
                    current_chunk.extend(user_section)
                    current_length += len(section_text)
                i = j
            else:
                current_chunk.append(breakdown_lines[i])
                current_length += len(breakdown_lines[i])
                i += 1

        # Add final chunk
        if current_chunk:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join(current_chunk),
                    },
                }
            )
    else:
        # Add single section with all breakdown data
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": breakdown_text,
                },
            }
        )

    return blocks


def build_admin_export_section() -> List[Dict[str, Any]]:
    """
    Build export section for admin users.
    """
    blocks = []

    # Export section
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*📊 Export Usage Data*\nDownload a comprehensive CSV report of team command usage with trends.",
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Export to CSV", "emoji": True},
                "action_id": "export_usage_csv",
                "style": "primary",
            },
        }
    )

    return blocks


def build_trend_summary_block(trends_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build trend summary blocks for the home tab.
    """
    blocks = []

    total_trend = trends_data.get("trends", {}).get("total_usage", {})
    current = total_trend.get("current", 0)
    delta = total_trend.get("delta", 0)
    percent = total_trend.get("percent", 0)

    # Get week date ranges
    current_week_range = get_week_date_range()
    from packages.db.operations.command_tracking_operations import (
        get_previous_week_timestamps,
    )

    previous_week_range = get_week_date_range(get_previous_week_timestamps()[0])

    # Trend indicator
    if delta > 0:
        trend_text = f"📈 Up {percent:.1f}% from last week"
    elif delta < 0:
        trend_text = f"📉 Down {abs(percent):.1f}% from last week"
    else:
        trend_text = "→ Same as last week"

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Weekly Trend*\n{current} total commands this week ({current_week_range})\n{trend_text} ({previous_week_range})",
            },
        }
    )

    return blocks
