"""
Direct message handling for flag review functionality.

This module handles sending direct messages to users for
acknowledgments, replies, and notifications related to flag reviews.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class FlagReviewDMHandler:
    """Handles direct message operations for flag review functionality."""

    def __init__(self, posting_handler: SlackPostingHandler):
        """
        Initialize the DM handler.

        Args:
            posting_handler: Handler for posting messages to Slack
        """
        self.posting_handler = posting_handler

    async def send_dm_to_requester(
        self,
        user_id: str,
        dm_type: str,
        admin_name: str,
        channel_id: str,
        message_ts: Optional[str] = None,
        reply_text: Optional[str] = None,
        command_execution_id: Optional[str] = None,
        message_exists: bool = True,
    ) -> bool:
        """
        Send a DM to the user who submitted feedback.

        Args:
            user_id: ID of the user to send DM to
            dm_type: Type of DM ('acknowledgment', 'reply')
            admin_name: Name of the admin taking action
            channel_id: Channel where the original feedback was submitted
            message_ts: Timestamp of the original message (optional)
            reply_text: Reply text for 'reply' type DMs (optional)
            command_execution_id: ID for command-related DMs (optional)

        Returns:
            True if DM sent successfully, False otherwise
        """
        try:
            if dm_type == "acknowledgment":
                blocks = self._create_acknowledgment_blocks(
                    admin_name=admin_name,
                    channel_id=channel_id,
                    is_command=bool(command_execution_id),
                )
                message = "Your feedback has been acknowledged."
            elif dm_type == "reply":
                blocks = self._create_reply_blocks(
                    admin_name=admin_name,
                    channel_id=channel_id,
                    message_ts=message_ts,
                    reply_text=reply_text or "Thank you for your feedback.",
                    is_command=bool(command_execution_id),
                    message_exists=message_exists,
                )
                message = "Ketchup team response to your feedback"
            else:
                logger.error(f"Unknown DM type: {dm_type}")
                return False

            # Send DM (user_id serves as channel_id for DMs)
            result = await self.posting_handler.post_message(
                channel_id=user_id,
                message=message,
                blocks=blocks,
            )

            if result and result.get("ok"):
                logger.info(f"Successfully sent {dm_type} DM to user {user_id}")
                return True
            else:
                logger.error(f"Failed to send {dm_type} DM: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending DM to requester: {e}")
            return False

    async def send_dm_to_reviewer(
        self,
        reviewer_id: str,
        notification_type: str,
        channel_id: str,
        user_id: str,
        user_name: str,
        feedback_text: Optional[str] = None,
    ) -> bool:
        """
        Send a notification DM to a reviewer/admin.

        Args:
            reviewer_id: ID of the reviewer to notify
            notification_type: Type of notification ('new_flag', 'escalation')
            channel_id: Channel where the flag was raised
            user_id: ID of the user who raised the flag
            user_name: Name of the user who raised the flag
            feedback_text: The feedback text (optional)

        Returns:
            True if DM sent successfully, False otherwise
        """
        try:
            if notification_type == "new_flag":
                blocks = self._create_new_flag_notification_blocks(
                    channel_id=channel_id,
                    user_id=user_id,
                    user_name=user_name,
                    feedback_text=feedback_text,
                )
                message = "New flag for review"
            elif notification_type == "escalation":
                blocks = self._create_escalation_notification_blocks(
                    channel_id=channel_id,
                    user_id=user_id,
                    feedback_text=feedback_text,
                )
                message = "Flag escalated for urgent review"
            else:
                logger.error(f"Unknown notification type: {notification_type}")
                return False

            # Send DM to reviewer
            result = await self.posting_handler.post_message(
                channel_id=reviewer_id,
                message=message,
                blocks=blocks,
            )

            if result and result.get("ok"):
                logger.info(f"Successfully sent {notification_type} notification to {reviewer_id}")
                return True
            else:
                logger.error(f"Failed to send notification: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending DM to reviewer: {e}")
            return False

    async def handle_dm_action(self, payload: Dict[str, Any], action_type: str) -> bool:
        """
        Handle actions initiated from DM buttons.

        Args:
            payload: The interaction payload from Slack
            action_type: Type of action to handle

        Returns:
            True if handled successfully, False otherwise
        """
        try:
            user_id = payload.get("user", {}).get("id")
            action = payload.get("actions", [{}])[0]
            action_value = action.get("value")

            if action_type == "view_flag":
                # Handle viewing the flag details
                await self._show_flag_details_in_dm(user_id, action_value)
            elif action_type == "quick_reply":
                # Handle quick reply from DM
                await self._handle_quick_reply_from_dm(payload, action_value)
            else:
                logger.warning(f"Unknown DM action type: {action_type}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error handling DM action: {e}")
            return False

    async def process_dm_response(
        self, user_id: str, response_text: str, context: Dict[str, Any]
    ) -> bool:
        """
        Process a response sent via DM.

        Args:
            user_id: ID of the user sending the response
            response_text: The response text
            context: Context information about the original flag

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            # Extract context information
            flag_id = context.get("flag_id")
            # original_channel = context.get("channel_id")  # Reserved for future use

            # Validate the response
            if not response_text or len(response_text.strip()) < 1:
                await self._send_dm_error(user_id, "Response cannot be empty.")
                return False

            # Process the response based on context
            logger.info(f"Processing DM response from {user_id} for flag {flag_id}")

            # Send confirmation
            await self._send_dm_confirmation(user_id, "Your response has been recorded.")

            return True

        except Exception as e:
            logger.error(f"Error processing DM response: {e}")
            return False

    def _create_acknowledgment_blocks(
        self, admin_name: str, channel_id: str, is_command: bool = False
    ) -> list:
        """Create blocks for acknowledgment DM."""
        title = "✅ Command Feedback Acknowledged" if is_command else "✅ Feedback Acknowledged"
        text = (
            f"Thank you for your feedback on the command in <#{channel_id}>."
            if is_command
            else f"Thank you for your feedback on the status update in <#{channel_id}>."
        )

        return [
            {"type": "header", "text": {"type": "plain_text", "text": title}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{text} Your feedback has been acknowledged by the team.",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Acknowledged by:* {admin_name}\n"
                    f"*Time:* {datetime.now(timezone.utc).strftime('%H:%M')} UTC",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "If you need to follow up, please contact the team "
                        "org-omeara-all@adobe.com or create a new feedback.",
                    }
                ],
            },
        ]

    def _create_reply_blocks(
        self,
        admin_name: str,
        channel_id: str,
        message_ts: Optional[str],
        reply_text: str,
        is_command: bool = False,
        message_exists: bool = True,
    ) -> list:
        """Create blocks for reply DM."""
        header_text = "🎯 Command Team Response" if is_command else "🎯 Ketchup Team Response"
        intro_text = (
            f"Thank you for your feedback on the command in <#{channel_id}>."
            if is_command
            else f"Thank you for your feedback on the status update in <#{channel_id}>."
        )

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": header_text}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{intro_text} Here's our response:",
                },
            },
            {"type": "section", "text": {"type": "plain_text", "text": reply_text}},
        ]

        # Add link to original message only if it exists and message_ts is available
        if message_ts and message_exists:
            link = f"https://adobe.enterprise.slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"From: {admin_name} | <{link}|View original message>",
                        }
                    ],
                }
            )
        else:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"From: {admin_name}"}],
                }
            )

        return blocks

    async def _show_flag_details_in_dm(self, user_id: str, flag_id: str) -> None:
        """Show flag details in a DM."""
        # Implementation would retrieve flag details and display them
        logger.info(f"Showing flag details for {flag_id} to user {user_id}")

    async def _handle_quick_reply_from_dm(self, payload: Dict[str, Any], flag_id: str) -> None:
        """Handle a quick reply action from DM."""
        # Implementation would handle quick reply functionality
        logger.info(f"Handling quick reply for flag {flag_id}")
