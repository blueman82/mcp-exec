"""
access_request_blocks.py

Build Block Kit components for access requests.
"""

from typing import Any, Dict, List, Optional

from packages.core.time_utils import convert_timestamp_to_utc


class AccessRequestBlocks:
    """Build Block Kit components for access requests."""

    @staticmethod
    def build_unauthorized_message(
        user_id: str,
        show_request_button: bool = True,
        rate_limit_message: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build the unauthorized access message."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔒 Access Required"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "You don't currently have access to Ketchup commands.",
                },
            },
        ]

        if rate_limit_message:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⏱️ *Rate Limit:* {rate_limit_message}",
                    },
                }
            )
        elif show_request_button:
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Request Access"},
                            "action_id": "request_access",
                            "style": "primary",
                            "value": user_id,
                        }
                    ],
                }
            )
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Your request will be sent to the Ketchup team for approval. You'll receive a DM when processed.",
                        }
                    ],
                }
            )
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📧 To request access, please email *org-omeara-all@adobe.com* with your use case.",
                    },
                }
            )

        return blocks

    @staticmethod
    def build_access_request_notification(
        user_id: str,
        user_name: str,
        user_email: str,
        reason: Optional[str],
        request_time: float,
    ) -> List[Dict[str, Any]]:
        """Build the access request notification for approvers."""
        time_str = convert_timestamp_to_utc(request_time)

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔐 New Access Request"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*User:*\n<@{user_id}>"},
                    {"type": "mrkdwn", "text": f"*Name:*\n{user_name}"},
                    {"type": "mrkdwn", "text": f"*Email:*\n{user_email}"},
                    {"type": "mrkdwn", "text": f"*Requested:*\n{time_str}"},
                ],
            },
        ]

        if reason:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Reason for Access:*\n{reason}",
                    },
                }
            )

        blocks.extend(
            [
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve"},
                            "action_id": f"approve_access_{user_id}",
                            "style": "primary",
                            "value": f"{user_id}|{request_time}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject"},
                            "action_id": f"reject_access_{user_id}",
                            "style": "danger",
                            "value": f"{user_id}|{request_time}",
                        },
                    ],
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "⚠️ This request will expire in 24 hours if not actioned.",
                        }
                    ],
                },
            ]
        )

        return blocks

    @staticmethod
    def build_request_processed_blocks(
        original_blocks: List[Dict[str, Any]],
        processed_by: str,
        decision: str,
        decision_time: float,
        rejection_reason: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Update the request notification after processing."""
        # Keep header and user info
        updated_blocks = original_blocks[:2]

        # Add decision info
        time_str = convert_timestamp_to_utc(decision_time)

        if decision == "approved":
            decision_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Approved by* <@{processed_by}> at {time_str}",
                },
            }
        else:
            decision_text = f"❌ *Rejected by* <@{processed_by}> at {time_str}"
            if rejection_reason:
                decision_text += f"\n*Reason:* {rejection_reason}"

            decision_block = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": decision_text},
            }

        updated_blocks.append(decision_block)

        return updated_blocks

    @staticmethod
    def build_rejection_modal() -> Dict[str, Any]:
        """Build the rejection reason modal."""
        return {
            "type": "modal",
            "callback_id": "reject_reason_modal",
            "title": {"type": "plain_text", "text": "Rejection Reason"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "reason_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reason_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter rejection reason...",
                        },
                        "multiline": True,
                    },
                    "label": {"type": "plain_text", "text": "Reason"},
                }
            ],
        }

    @staticmethod
    def build_approval_dm(user_id: str) -> List[Dict[str, Any]]:
        """Build the Ketchup introduction message for newly approved users."""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":wave: Hello <@{user_id}>! Welcome to Ketchup 1.0!",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🍅 Ketchup - AI-Powered CSO Assistant*\nYour assistant for war room summaries and cross-system incident analysis.",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Caveats:*\n• Any AI generated summaries from Ketchup should not be shared directly with customers.\n• This is an internal tool used to help engineers, managers and leaders to catch up with a CSO situation faster.\n• ALL AI generated summaries must be validated for accuracy before any part of it is used in a customer facing statement.\n• Currently, only Adobe Campaign and AJO products are supported for Ketchup use in CSO warrooms.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": '*🏠 Home Tab Settings*\n• Access: Click "Ketchup" in Slack sidebar → "Home" tab\n• Customize: Set product focus, detail level, and time window\n• All settings apply automatically to your summaries and reports',
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Key Commands:*\n\n• *In War Rooms:*\n  `/ketchup status` - Quick incident status\n  `/ketchup report` - Detailed incident report\n  `/ketchup query <question>` - Ask about this war room",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Additional Commands:*\n• `/ketchup list` - View all channels\n• `/ketchup access` - Request channel access\n• `/ketchup archive` - Archive old channels\n\n*Questions? Contact the team!: org-omeara-all@adobe.com <#C08CQN1JCSC|ketchup_feedback>*",
                },
            },
        ]
