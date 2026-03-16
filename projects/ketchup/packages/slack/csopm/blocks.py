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
    - csopm_stop_reminders: Stop ketchup reminders for this ticket
    - csopm_enable_reminders: Re-enable ketchup reminders for this ticket
    - csopm_view_jira: Link to view ticket in JIRA
    """

    # Action ID prefixes for CSOPM buttons
    ACTION_ACKNOWLEDGE = "csopm_acknowledge"
    ACTION_CREATE_FOLLOWUP = "csopm_create_followup"
    ACTION_STOP_REMINDERS = "csopm_stop_reminders"
    ACTION_ENABLE_REMINDERS = "csopm_enable_reminders"
    ACTION_VIEW_JIRA = "csopm_view_jira"
    ACTION_SNOOZE = "csopm_snooze"
    ACTION_UNSNOOZE = "csopm_unsnooze"
    ACTION_CLOSE_TICKET = "csopm_close_ticket"
    ACTION_MARK_COMPLETE = "csopm_mark_complete"
    ACTION_REASSIGN = "csopm_reassign"

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
                    "text": "New CSOPM Ticket Assigned",
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
                            "text": "Acknowledge",
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
                            "text": "Reassign",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_REASSIGN,
                        "value": action_value,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Create Follow-up",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_CREATE_FOLLOWUP,
                        "value": action_value,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Mark Complete",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_MARK_COMPLETE,
                        "value": action_value,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Stop Reminders",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_STOP_REMINDERS,
                        "value": action_value,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in JIRA",
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
        emoji = ":warning:" if ping_count >= 2 else ":bell:"
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
                            "text": "Warning: This ticket will be escalated after 3 unanswered pings",
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
                            "text": "Acknowledge",
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
                            "text": "View in JIRA",
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
    def _build_open_followups_section(
        cls,
        open_followups: List[Dict[str, str]],
    ) -> Optional[Dict[str, Any]]:
        """Build a context block section for open follow-up tickets.

        Args:
            open_followups: List of dicts with 'key' and 'status' for open followups.
                Format: [{'key': 'CAMP-123', 'status': 'In Progress'}, ...]

        Returns:
            Context block dict if there are open followups, None otherwise.
        """
        if not open_followups:
            return None

        # Format: :warning: Open follow-up tickets:
        # • CAMP-123 (In Progress)
        # • CPGNTT-456 (Open)
        followup_lines = []
        for followup in open_followups[:5]:  # Limit to 5 to avoid overly long messages
            key = followup.get("key", "Unknown")
            status = followup.get("status", "Unknown")
            jira_url = f"{JIRA_BASE_URL}/{key}"
            followup_lines.append(f"• <{jira_url}|{key}> ({status})")

        if len(open_followups) > 5:
            followup_lines.append(f"• _... and {len(open_followups) - 5} more_")

        text = ":warning: *Open follow-up tickets:*\n" + "\n".join(followup_lines)

        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": text,
                }
            ],
        }

    @classmethod
    def build_closure_reminder(
        cls,
        ticket: CSOPMTicket,
        days_old: int,
        ping_count: int,
        has_open_linked: bool = False,
        open_followups: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for a closure reminder notification.

        Creates a reminder DM with:
        - Header indicating closure reminder
        - Ticket details with age information
        - Open follow-up tickets section (for transparency)
        - Action buttons for closure actions

        Args:
            ticket: The CSOPMTicket requiring closure attention.
            days_old: Number of days since ticket creation.
            ping_count: Current ping count for this reminder.
            has_open_linked: Whether ticket has open linked tickets (via JIRA links).
            open_followups: List of open followup tickets with their statuses.
                Format: [{'key': 'CAMP-123', 'status': 'In Progress'}, ...]
                Shown to provide visibility into open followups.

        Returns:
            List of Block Kit block dictionaries.
        """
        blocks: List[Dict[str, Any]] = []

        # Header block
        emoji = ":warning:" if ping_count >= 2 else ":clipboard:"
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

        # Open follow-up tickets section (for transparency)
        if open_followups:
            followups_block = cls._build_open_followups_section(open_followups)
            if followups_block:
                blocks.append(followups_block)

        # Warning for open linked tickets (general JIRA links, not tracked followups)
        # Only show this if has_open_linked but no specific followups listed
        if has_open_linked and not open_followups:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": ":information_source: This ticket has open linked tickets. Please review before closing.",
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
                            "text": ":alarm_clock: This ticket will be escalated after 3 unanswered pings",
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
                    "text": "Close Ticket",
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
                    "text": "Snooze 7 Days",
                    "emoji": True,
                },
                "action_id": cls.ACTION_SNOOZE,
                "value": action_value,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View in JIRA",
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
            "acknowledged": ":white_check_mark:",
            "done": ":white_check_mark:",
            "snoozed": ":clock3:",
            "closed": ":lock:",
            "reminders_stopped": ":no_bell:",
            "reminders_enabled": ":bell:",
        }
        emoji = action_emoji.get(action_type, ":white_check_mark:")

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

    # Action IDs for modal interactions (triggers modal update)
    ACTION_PROJECT_SELECT = "csopm_project_select"
    ACTION_ISSUETYPE_SELECT = "csopm_issuetype_select"

    @classmethod
    def build_create_followup_modal(
        cls,
        ticket: CSOPMTicket,
        projects: List[Dict[str, Any]] = None,
        issue_types: List[Dict[str, Any]] = None,
        selected_project_key: Optional[str] = None,
        pat_expiry_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build a modal view for creating a follow-up ticket.

        Creates a modal with:
        - Project selector (dynamic from JIRA)
        - Issue type selector (dynamic from JIRA, updates on project selection)
        - Summary input
        - Description input (pre-filled with parent reference)

        Args:
            ticket: The parent CSOPMTicket to create follow-up for.
            projects: Optional list of JIRA projects for dropdown.
                Each project dict should have 'key' and 'name' fields.
            issue_types: Optional list of JIRA issue types for dropdown.
                Each issue type dict should have 'id' and 'name' fields.
            selected_project_key: Currently selected project key for initial selection.
                Issue types are fetched dynamically when project changes.
            pat_expiry_minutes: Minutes until stored PAT expires, or None if no PAT stored.

        Returns:
            Modal view dictionary for views.open API.
        """
        import json

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

        # Add PAT blocks (reusable helper)
        blocks.extend(cls._build_pat_blocks(pat_expiry_minutes))

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
                # Find initial option if selected_project_key is provided
                initial_option = None
                if selected_project_key:
                    for opt in project_options:
                        if opt["value"] == selected_project_key:
                            initial_option = opt
                            break

                element = {
                    "type": "static_select",
                    "action_id": cls.ACTION_PROJECT_SELECT,
                    "placeholder": {"type": "plain_text", "text": "Select a project"},
                    "options": project_options[:100],
                }
                if initial_option:
                    element["initial_option"] = initial_option

                blocks.append(
                    {
                        "type": "input",
                        "block_id": "project_block",
                        "dispatch_action": True,
                        "label": {"type": "plain_text", "text": "Project"},
                        "element": element,
                    }
                )
        else:
            blocks.append(
                {
                    "type": "input",
                    "block_id": "project_block",
                    "label": {"type": "plain_text", "text": "Project Key"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "project_input",
                        "initial_value": "CSOPM",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter project key (e.g., CSOPM)",
                        },
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
                        "dispatch_action": True,  # Triggers field metadata fetch on selection
                        "label": {"type": "plain_text", "text": "Issue Type"},
                        "element": {
                            "type": "static_select",
                            "action_id": cls.ACTION_ISSUETYPE_SELECT,
                            "placeholder": {"type": "plain_text", "text": "Select issue type"},
                            "options": issue_type_options[:100],
                        },
                    }
                )
        else:
            blocks.append(
                {
                    "type": "input",
                    "block_id": "issue_type_block",
                    "label": {"type": "plain_text", "text": "Issue Type"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "issue_type_input",
                        "initial_value": "Task",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter issue type (e.g., Task, Bug)",
                        },
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

        # Add info context about optional fields
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":information_source: For additional fields (priority, labels, etc.), edit the ticket in JIRA after creation.",
                    }
                ],
            }
        )

        # Build private_metadata with ticket key for modal submission
        metadata = {
            "ticket_key": ticket.key,
            "ticket_summary": ticket.summary[:100] if ticket.summary else "",
        }
        metadata_str = json.dumps(metadata)

        return {
            "type": "modal",
            "callback_id": "csopm_create_followup_modal",
            "private_metadata": metadata_str,
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
    def build_followup_confirmation(
        cls,
        new_ticket_key: str,
        parent_ticket_key: str,
        jira_url: str,
    ) -> List[Dict[str, Any]]:
        """Build confirmation blocks for a successfully created follow-up ticket.

        Includes a button to create another follow-up for the same parent.

        Args:
            new_ticket_key: The key of the newly created ticket.
            parent_ticket_key: The key of the parent CSOPM ticket.
            jira_url: Full URL to the new ticket in JIRA.

        Returns:
            List of Block Kit blocks for the confirmation message.
        """
        parent_url = f"{JIRA_BASE_URL}/{parent_ticket_key}"
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":white_check_mark: Follow-up ticket *<{jira_url}|{new_ticket_key}>* created!\n"
                        f"Linked to parent ticket *<{parent_url}|{parent_ticket_key}>*"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Create Another Follow-up",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_CREATE_FOLLOWUP,
                        "value": parent_ticket_key,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in JIRA",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_VIEW_JIRA,
                        "value": new_ticket_key,
                        "url": jira_url,
                    },
                ],
            },
        ]

    @classmethod
    def build_status_transition_modal(
        cls,
        ticket_key: str,
        target_status: str,
        field_metadata: List[Dict[str, Any]],
        ticket_summary: Optional[str] = None,
        pat_expiry_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build a modal for transitioning a ticket to a new status.

        Creates a modal with:
        - Info about the transition
        - PAT input/status (required for transition)
        - Dynamic fields required for the transition
        - Optional comment field

        Args:
            ticket_key: The JIRA ticket key (e.g., "CSOPM-12345")
            target_status: The target status name (e.g., "Complete", "Closed")
            field_metadata: List of field metadata for the transition.
            ticket_summary: Optional ticket summary for display.
            pat_expiry_minutes: Minutes until stored PAT expires, or None if no PAT stored.

        Returns:
            Modal view dictionary for views.open API.
        """
        import json

        jira_url = f"{JIRA_BASE_URL}/{ticket_key}"

        # Build blocks list
        blocks: List[Dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Transitioning *<{jira_url}|{ticket_key}>* to *{target_status}*",
                },
            },
        ]

        # Add ticket summary if provided
        if ticket_summary:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Summary:* {ticket_summary[:200]}",
                        }
                    ],
                }
            )

        blocks.append({"type": "divider"})

        # Add PAT blocks (reusable helper)
        blocks.extend(cls._build_pat_blocks(pat_expiry_minutes))

        # Add dynamic fields from transition metadata
        if field_metadata:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Required fields for {target_status}:*",
                    },
                }
            )
            dynamic_blocks = cls.build_dynamic_fields_blocks(
                field_metadata, required_only=False, force_required=True
            )
            blocks.extend(dynamic_blocks)

        # Add optional comment field
        blocks.append(
            {
                "type": "input",
                "block_id": "comment_block",
                "label": {
                    "type": "plain_text",
                    "text": "Comment (optional)",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "comment_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Add a comment to the ticket",
                    },
                },
                "optional": True,
            }
        )

        # Build private_metadata
        metadata = {
            "ticket_key": ticket_key,
            "target_status": target_status,
            "ticket_summary": ticket_summary[:100] if ticket_summary else "",
        }
        metadata_str = json.dumps(metadata)

        # Determine modal title based on target status
        title_text = (
            f"Mark {target_status}" if target_status == "Complete" else f"{target_status} Ticket"
        )

        return {
            "type": "modal",
            "callback_id": "csopm_status_transition_modal",
            "private_metadata": metadata_str,
            "title": {
                "type": "plain_text",
                "text": title_text[:24],  # Slack title max 24 chars
            },
            "submit": {
                "type": "plain_text",
                "text": "Submit",
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
            },
            "blocks": blocks,
        }

    @classmethod
    def build_transition_confirmation(
        cls,
        ticket_key: str,
        new_status: str,
    ) -> List[Dict[str, Any]]:
        """Build confirmation blocks for a successful status transition.

        Args:
            ticket_key: The JIRA ticket key.
            new_status: The new status the ticket transitioned to.

        Returns:
            List of Block Kit blocks for the confirmation message.
        """
        jira_url = f"{JIRA_BASE_URL}/{ticket_key}"
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":white_check_mark: *<{jira_url}|{ticket_key}>* "
                        f"transitioned to *{new_status}*"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in JIRA",
                            "emoji": True,
                        },
                        "action_id": cls.ACTION_VIEW_JIRA,
                        "value": ticket_key,
                        "url": jira_url,
                    },
                ],
            },
        ]

    # Fields that are auto-filled and should not be shown in modal
    SKIP_FIELDS = {"project", "issuetype", "reporter", "attachment", "issuelinks"}

    @classmethod
    def _build_pat_blocks(
        cls,
        pat_expiry_minutes: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Build PAT input/status blocks for modals.

        Returns either:
        - A status section with Edit button (if PAT stored)
        - An input field with Save button (if no PAT)

        Args:
            pat_expiry_minutes: Minutes until stored PAT expires, or None if no PAT stored.

        Returns:
            List of block dictionaries for PAT handling.
        """
        blocks: List[Dict[str, Any]] = []

        if pat_expiry_minutes:
            # User has a stored PAT - show status with Edit button only
            blocks.append(
                {
                    "type": "section",
                    "block_id": "pat_status_block",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: *JIRA PAT stored* (expires in {pat_expiry_minutes} min)",
                    },
                    "accessory": {
                        "type": "button",
                        "action_id": "csopm_edit_pat",
                        "text": {
                            "type": "plain_text",
                            "text": "Edit",
                        },
                    },
                }
            )
        else:
            # No stored PAT (or expired) - show input field with Save button
            # PAT is REQUIRED - no tickets without it
            blocks.append(
                {
                    "type": "input",
                    "block_id": "pat_block",
                    "label": {
                        "type": "plain_text",
                        "text": "JIRA Personal Access Token",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "pat_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter your JIRA PAT",
                        },
                    },
                    "hint": {
                        "type": "plain_text",
                        "text": "Required. Get one at jira.corp.adobe.com > Profile > Personal Access Tokens",
                    },
                    "optional": False,
                }
            )
            # Add Save button after PAT input
            blocks.append(
                {
                    "type": "actions",
                    "block_id": "pat_save_block",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "csopm_save_pat",
                            "text": {
                                "type": "plain_text",
                                "text": "Save PAT",
                            },
                            "style": "primary",
                        }
                    ],
                }
            )

        return blocks

    @classmethod
    def build_dynamic_field_block(
        cls,
        field: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Build a Slack input block for a JIRA field based on its metadata.

        Args:
            field: Field metadata from get_issuetype_metadata response.
                Expected keys: fieldId, name, required, schema, allowedValues

        Returns:
            Slack block dict or None if field should be skipped.
        """
        field_id = field.get("fieldId", "")
        field_name = field.get("name", field_id)
        required = field.get("required", False)
        schema = field.get("schema", {})
        allowed_values = field.get("allowedValues")
        schema_type = schema.get("type", "string")

        # Skip system fields that are auto-filled
        if field_id.lower() in cls.SKIP_FIELDS:
            return None

        # Skip summary and description - they're already in the modal
        if field_id in ("summary", "description"):
            return None

        block_id = f"dynamic_{field_id}_block"
        action_id = f"dynamic_{field_id}_input"

        # Handle fields with allowed values (dropdowns)
        if allowed_values and isinstance(allowed_values, list) and len(allowed_values) > 0:
            options = []
            for val in allowed_values[:100]:  # Slack limit
                if isinstance(val, dict):
                    # Most JIRA fields use {id, name} or {value, name} format
                    opt_value = str(val.get("id", val.get("value", val.get("name", ""))))
                    opt_name = val.get("name", val.get("value", opt_value))
                    if opt_value and opt_name:
                        options.append(
                            {
                                "text": {"type": "plain_text", "text": str(opt_name)[:75]},
                                "value": str(opt_value),
                            }
                        )
                elif isinstance(val, str):
                    options.append(
                        {
                            "text": {"type": "plain_text", "text": val[:75]},
                            "value": val,
                        }
                    )

            if options:
                return {
                    "type": "input",
                    "block_id": block_id,
                    "label": {"type": "plain_text", "text": field_name[:24]},
                    "element": {
                        "type": "static_select",
                        "action_id": action_id,
                        "placeholder": {"type": "plain_text", "text": f"Select {field_name}"[:150]},
                        "options": options,
                    },
                    "optional": not required,
                }

        # Handle user picker fields
        if schema_type == "user":
            return {
                "type": "input",
                "block_id": block_id,
                "label": {"type": "plain_text", "text": field_name[:24]},
                "element": {
                    "type": "plain_text_input",
                    "action_id": action_id,
                    "placeholder": {"type": "plain_text", "text": f"Enter {field_name} username"},
                },
                "optional": not required,
            }

        # Handle array types (multi-select or text)
        if schema_type == "array":
            return {
                "type": "input",
                "block_id": block_id,
                "label": {"type": "plain_text", "text": field_name[:24]},
                "element": {
                    "type": "plain_text_input",
                    "action_id": action_id,
                    "placeholder": {
                        "type": "plain_text",
                        "text": f"Enter {field_name} (comma-separated)",
                    },
                },
                "optional": not required,
            }

        # Default: text input
        return {
            "type": "input",
            "block_id": block_id,
            "label": {"type": "plain_text", "text": field_name[:24]},
            "element": {
                "type": "plain_text_input",
                "action_id": action_id,
                "placeholder": {"type": "plain_text", "text": f"Enter {field_name}"},
            },
            "optional": not required,
        }

    @classmethod
    def build_dynamic_fields_blocks(
        cls,
        field_metadata: List[Dict[str, Any]],
        required_only: bool = True,
        force_required: bool = False,
    ) -> List[Dict[str, Any]]:
        """Build Slack input blocks for dynamic JIRA fields.

        Args:
            field_metadata: List of field metadata from get_issuetype_metadata.
            required_only: If True, only include required fields.
            force_required: If True, all fields are marked as required regardless
                of JIRA metadata. Used for transition modals where all shown
                fields must be filled.

        Returns:
            List of Slack block dicts for dynamic fields.
        """
        blocks = []

        for field in field_metadata:
            # Filter by required if needed
            if required_only and not field.get("required", False):
                continue

            block = cls.build_dynamic_field_block(field, force_required=force_required)
            if block:
                blocks.append(block)

        return blocks

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
