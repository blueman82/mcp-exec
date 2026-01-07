"""
CSOPM Notification Block Kit Builders.

This module provides Block Kit message builders for CSOPM notifications,
following the established patterns in packages/slack/blockkits/handlers/.

Block Kit Structure for Assignment DMs:
1. Header - Ticket assignment notification
2. Section - Ticket details (key, summary, status)
3. Actions - Interactive buttons (Acknowledge, Create Follow-up, Done, View in JIRA)
4. Context - Additional info (assigned timestamp)

Action IDs use the 'csopm_' prefix to route through payload_processor.py.

Architectural Note:
This is the first Block Kit builder for CSOPM notifications. It establishes
patterns for how notification messages are structured and how button actions
are identified. Future CSOPM-related Block Kit builders should follow this pattern.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import CSOPMTicket

logger = setup_logger(__name__)


# JIRA base URL for ticket links
JIRA_BASE_URL = "https://jira.corp.adobe.com/browse"


class CSOPMNotificationBlocks:
    """Block Kit message builder for CSOPM notifications.

    Creates structured Slack Block Kit messages for:
    - New ticket assignment notifications
    - RCA reminder notifications
    - Closure reminder notifications
    - Acknowledgment confirmation messages

    All action buttons use the 'csopm_' prefix for routing:
    - csopm_acknowledge: Mark ticket as acknowledged
    - csopm_create_followup: Open modal to create follow-up ticket
    - csopm_done: Mark ticket as done/closed
    - csopm_view_jira: Link to view ticket in JIRA
    """

    # Action ID prefixes for CSOPM buttons
    ACTION_ACKNOWLEDGE = "csopm_acknowledge"
    ACTION_CREATE_FOLLOWUP = "csopm_create_followup"
    ACTION_DONE = "csopm_done"
    ACTION_VIEW_JIRA = "csopm_view_jira"
    ACTION_SNOOZE = "csopm_snooze"
    ACTION_CLOSE_TICKET = "csopm_close_ticket"

    @classmethod
    def build_assignment_notification(
        cls,
        ticket: CSOPMTicket,
        exigence_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for a new ticket assignment notification.

        Creates a DM notification with:
        - Header indicating new assignment
        - Ticket details section
        - Action buttons for user interaction

        Args:
            ticket: The CSOPMTicket that was assigned.
            exigence_id: Optional Exigence event ID if linked.

        Returns:
            List of Block Kit block dictionaries.
        """
        blocks: List[Dict[str, Any]] = []

        # Header block
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎫 New CSOPM Ticket Assigned",
                    "emoji": True,
                },
            }
        )

        # Ticket details section
        jira_url = f"{JIRA_BASE_URL}/{ticket.key}"
        details_text = (
            f"*<{jira_url}|{ticket.key}>*\n"
            f"*Summary:* {ticket.summary}\n"
            f"*Status:* {ticket.status}"
        )

        if exigence_id or ticket.exigence_id:
            event_id = exigence_id or ticket.exigence_id
            details_text += f"\n*Exigence ID:* {event_id}"

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": details_text,
                },
            }
        )

        # Divider before actions
        blocks.append({"type": "divider"})

        # Action buttons
        action_value = ticket.key  # Pass ticket key as value for all actions
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Acknowledge",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_ACKNOWLEDGE,
                        "value": action_value,
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "➕ Create Follow-up",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_CREATE_FOLLOWUP,
                        "value": action_value,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✔️ Done",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_DONE,
                        "value": action_value,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔗 View in JIRA",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_VIEW_JIRA,
                        "value": action_value,
                        "url": jira_url,
                    },
                ],
            }
        )

        # Context block with timestamp
        now = datetime.now(timezone.utc)
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Assigned at {now.strftime('%Y-%m-%d %H:%M')} UTC",
                    }
                ],
            }
        )

        return blocks

    @classmethod
    def build_rca_reminder(
        cls,
        ticket: CSOPMTicket,
        days_old: int,
        ping_count: int,
    ) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for an RCA reminder notification.

        Creates a reminder DM with:
        - Header indicating RCA reminder
        - Ticket details with age information
        - Action buttons for acknowledgment

        Args:
            ticket: The CSOPMTicket requiring RCA attention.
            days_old: Number of days since ticket creation.
            ping_count: Current ping count for this reminder.

        Returns:
            List of Block Kit block dictionaries.
        """
        blocks: List[Dict[str, Any]] = []

        # Header block
        emoji = "⚠️" if ping_count >= 2 else "🔔"
        header_text = f"RCA Reminder (Ping {ping_count}/3)"

        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {header_text}",
                    "emoji": True,
                },
            }
        )

        # Ticket details section
        jira_url = f"{JIRA_BASE_URL}/{ticket.key}"
        details_text = (
            f"*<{jira_url}|{ticket.key}>* needs RCA attention\n\n"
            f"*Summary:* {ticket.summary}\n"
            f"*Status:* {ticket.status}\n"
            f"*Age:* {days_old} days old"
        )

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": details_text,
                },
            }
        )

        # Warning for high ping count
        if ping_count >= 2:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "⚠️ This ticket will be escalated after 3 unanswered pings",
                        }
                    ],
                }
            )

        # Divider before actions
        blocks.append({"type": "divider"})

        # Action buttons
        action_value = ticket.key
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Acknowledge",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_ACKNOWLEDGE,
                        "value": action_value,
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔗 View in JIRA",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_VIEW_JIRA,
                        "value": action_value,
                        "url": jira_url,
                    },
                ],
            }
        )

        return blocks

    @classmethod
    def build_closure_reminder(
        cls,
        ticket: CSOPMTicket,
        days_old: int,
        ping_count: int,
        has_open_linked: bool = False,
    ) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for a closure reminder notification.

        Creates a reminder DM with:
        - Header indicating closure reminder
        - Ticket details with age information
        - Action buttons for closure actions

        Args:
            ticket: The CSOPMTicket requiring closure attention.
            days_old: Number of days since ticket creation.
            ping_count: Current ping count for this reminder.
            has_open_linked: Whether ticket has open linked tickets.

        Returns:
            List of Block Kit block dictionaries.
        """
        blocks: List[Dict[str, Any]] = []

        # Header block
        emoji = "⚠️" if ping_count >= 2 else "📋"
        header_text = f"Closure Reminder (Ping {ping_count}/3)"

        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {header_text}",
                    "emoji": True,
                },
            }
        )

        # Ticket details section
        jira_url = f"{JIRA_BASE_URL}/{ticket.key}"
        details_text = (
            f"*<{jira_url}|{ticket.key}>* is {days_old} days old\n\n"
            f"*Summary:* {ticket.summary}\n"
            f"*Status:* {ticket.status}\n"
            f"Please review and close if work is complete."
        )

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": details_text,
                },
            }
        )

        # Warning for open linked tickets
        if has_open_linked:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "ℹ️ This ticket has open linked tickets. Please review before closing.",
                        }
                    ],
                }
            )

        # Warning for high ping count
        if ping_count >= 2:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "⚠️ This ticket will be escalated after 3 unanswered pings",
                        }
                    ],
                }
            )

        # Divider before actions
        blocks.append({"type": "divider"})

        # Action buttons
        action_value = ticket.key
        action_elements = [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "✅ Close Ticket",
                    "emoji": True,
                },
                "action_id": cls.ACTION_CLOSE_TICKET,
                "value": action_value,
                "style": "primary",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "⏰ Snooze 7 Days",
                    "emoji": True,
                },
                "action_id": cls.ACTION_SNOOZE,
                "value": action_value,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "🔗 View in JIRA",
                    "emoji": True,
                },
                "action_id": cls.ACTION_VIEW_JIRA,
                "value": action_value,
                "url": jira_url,
            },
        ]

        blocks.append({"type": "actions", "elements": action_elements})

        return blocks

    @classmethod
    def build_acknowledgment_confirmation(
        cls,
        ticket_key: str,
        action_type: str = "acknowledged",
    ) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for an acknowledgment confirmation.

        Creates a simple confirmation message after a button action.

        Args:
            ticket_key: The JIRA ticket key that was acknowledged.
            action_type: Type of action ("acknowledged", "done", "snoozed", "closed").

        Returns:
            List of Block Kit block dictionaries.
        """
        action_emoji = {
            "acknowledged": "✅",
            "done": "✔️",
            "snoozed": "⏰",
            "closed": "🔒",
        }
        emoji = action_emoji.get(action_type, "✅")

        action_text = {
            "acknowledged": "acknowledged",
            "done": "marked as done",
            "snoozed": "snoozed for 7 days",
            "closed": "closed",
        }
        text = action_text.get(action_type, action_type)

        jira_url = f"{JIRA_BASE_URL}/{ticket_key}"
        now = datetime.now(timezone.utc)

        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *<{jira_url}|{ticket_key}>* has been {text}.",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Updated at {now.strftime('%Y-%m-%d %H:%M')} UTC",
                    }
                ],
            },
        ]

    @classmethod
    def build_create_followup_modal(
        cls,
        ticket: CSOPMTicket,
        projects: List[Dict[str, Any]] = None,
        issue_types: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a modal view for creating a follow-up ticket.

        Creates a modal with:
        - Project selector (dynamic from JIRA)
        - Issue type selector (dynamic from JIRA)
        - Summary input
        - Description input (pre-filled with parent reference)

        Args:
            ticket: The parent CSOPMTicket to create follow-up for.
            projects: Optional list of JIRA projects for dropdown.
                Each project dict should have 'key' and 'name' fields.
            issue_types: Optional list of JIRA issue types for dropdown.
                Each issue type dict should have 'id' and 'name' fields.

        Returns:
            Modal view dictionary for views.open API.
        """
        jira_url = f"{JIRA_BASE_URL}/{ticket.key}"

        # Build blocks list
        blocks: List[Dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Creating follow-up for *<{jira_url}|{ticket.key}>*",
                },
            },
        ]

        # Add project selector if projects are provided
        if projects:
            project_options = [
                {
                    "text": {"type": "plain_text", "text": f"{p['key']} - {p['name']}"[:75]},
                    "value": p["key"],
                }
                for p in projects
                if p.get("key") and p.get("name")
            ]
            if project_options:
                blocks.append(
                    {
                        "type": "input",
                        "block_id": "project_block",
                        "label": {"type": "plain_text", "text": "Project"},
                        "element": {
                            "type": "static_select",
                            "action_id": "project_input",
                            "placeholder": {"type": "plain_text", "text": "Select a project"},
                            "options": project_options[:100],  # Slack limit is 100 options
                        },
                    }
                )
        else:
            # Fallback to text input if no projects provided
            blocks.append(
                {
                    "type": "input",
                    "block_id": "project_block",
                    "label": {"type": "plain_text", "text": "Project Key"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "project_input",
                        "initial_value": "CSOPM",
                        "placeholder": {"type": "plain_text", "text": "Enter project key (e.g., CSOPM)"},
                    },
                }
            )

        # Add issue type selector if issue types are provided
        if issue_types:
            issue_type_options = [
                {
                    "text": {"type": "plain_text", "text": it["name"][:75]},
                    "value": it.get("id", it["name"]),
                }
                for it in issue_types
                if it.get("name")
            ]
            if issue_type_options:
                blocks.append(
                    {
                        "type": "input",
                        "block_id": "issue_type_block",
                        "label": {"type": "plain_text", "text": "Issue Type"},
                        "element": {
                            "type": "static_select",
                            "action_id": "issue_type_input",
                            "placeholder": {"type": "plain_text", "text": "Select issue type"},
                            "options": issue_type_options[:100],  # Slack limit is 100 options
                        },
                    }
                )
        else:
            # Fallback to text input if no issue types provided
            blocks.append(
                {
                    "type": "input",
                    "block_id": "issue_type_block",
                    "label": {"type": "plain_text", "text": "Issue Type"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "issue_type_input",
                        "initial_value": "Task",
                        "placeholder": {"type": "plain_text", "text": "Enter issue type (e.g., Task, Bug)"},
                    },
                }
            )

        # Add summary input
        blocks.append(
            {
                "type": "input",
                "block_id": "summary_block",
                "label": {
                    "type": "plain_text",
                    "text": "Summary",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "summary_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter follow-up summary",
                    },
                },
            }
        )

        # Add description input
        blocks.append(
            {
                "type": "input",
                "block_id": "description_block",
                "label": {
                    "type": "plain_text",
                    "text": "Description",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description_input",
                    "multiline": True,
                    "initial_value": f"Follow-up ticket for {ticket.key}.\n\nParent: {jira_url}",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter description",
                    },
                },
                "optional": True,
            }
        )

        return {
            "type": "modal",
            "callback_id": "csopm_create_followup_modal",
            "private_metadata": ticket.key,  # Pass parent ticket key
            "title": {
                "type": "plain_text",
                "text": "Create Follow-up",
            },
            "submit": {
                "type": "plain_text",
                "text": "Create",
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
            },
            "blocks": blocks,
        }

    @classmethod
    def get_fallback_text(
        cls,
        notification_type: str,
        ticket_key: str,
    ) -> str:
        """Get fallback text for notifications (used when blocks can't be displayed).

        Args:
            notification_type: Type of notification ("assignment", "rca", "closure").
            ticket_key: The JIRA ticket key.

        Returns:
            Plain text fallback message.
        """
        jira_url = f"{JIRA_BASE_URL}/{ticket_key}"

        fallback_text = {
            "assignment": f"New CSOPM ticket assigned: {ticket_key} - {jira_url}",
            "rca": f"RCA reminder for CSOPM ticket: {ticket_key} - {jira_url}",
            "closure": f"Closure reminder for CSOPM ticket: {ticket_key} - {jira_url}",
        }

        return fallback_text.get(
            notification_type,
            f"CSOPM notification for {ticket_key} - {jira_url}",
        )
