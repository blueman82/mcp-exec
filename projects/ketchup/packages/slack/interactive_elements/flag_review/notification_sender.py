"""
notification_sender.py

Handles notification sending and formatting for flag review functionality.
Provides specialized methods for creating notification blocks and sending
various types of notifications via direct messages.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class NotificationSender:
    """Handles notification creation and sending for flag reviews."""

    def __init__(self, dependency_container):
        """Initialize the notification sender with dependency injection container.

        Args:
            dependency_container: TypedDI container for dependency access.
        """
        self.container = dependency_container

    @property
    def posting_handler(self):
        """Get posting handler from dependency container."""
        return self.container.get_posting_handler()

    def create_new_flag_notification_blocks(
        self,
        channel_id: str,
        user_id: str,
        user_name: str,
        feedback_text: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Create blocks for new flag notification.

        Args:
            channel_id: The channel ID where the flag was created.
            user_id: The ID of the user who created the flag.
            user_name: The name of the user who created the flag.
            feedback_text: Optional feedback text provided with the flag.

        Returns:
            List of Slack blocks for the notification.
        """
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚩 New Flag for Review"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Channel:*\n<#{channel_id}>"},
                    {"type": "mrkdwn", "text": f"*Flagged by:*\n<@{user_id}>"},
                ],
            },
        ]

        if feedback_text:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Feedback:*\n{feedback_text[:500]}",
                    },
                }
            )

        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in Channel"},
                        "url": f"https://slack.com/app_redirect?channel={channel_id}",
                    }
                ],
            }
        )

        return blocks

    def create_escalation_notification_blocks(
        self, channel_id: str, user_id: str, feedback_text: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Create blocks for escalation notification.

        Args:
            channel_id: The channel ID where the escalation occurred.
            user_id: The ID of the user involved in the escalation.
            feedback_text: Optional feedback text for the escalation.

        Returns:
            List of Slack blocks for the escalation notification.
        """
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "⚠️ Flag Escalated"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This flag has been escalated for urgent review.",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Channel:*\n<#{channel_id}>"},
                    {"type": "mrkdwn", "text": f"*User:*\n<@{user_id}>"},
                ],
            },
        ]

        if feedback_text:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Issue:*\n{feedback_text[:500]}",
                    },
                }
            )

        return blocks

    async def send_dm_error(self, user_id: str, error_message: str) -> None:
        """Send an error message via DM.

        Args:
            user_id: The ID of the user to send the error to.
            error_message: The error message to send.
        """
        try:
            await self.posting_handler.post_message(
                channel_id=user_id,
                message=f"❌ {error_message}",
            )
        except Exception as e:
            logger.error(f"Error sending DM error message: {e}")

    async def send_dm_confirmation(
        self, user_id: str, confirmation_message: str
    ) -> None:
        """Send a confirmation message via DM.

        Args:
            user_id: The ID of the user to send the confirmation to.
            confirmation_message: The confirmation message to send.
        """
        try:
            await self.posting_handler.post_message(
                channel_id=user_id,
                message=f"✅ {confirmation_message}",
            )
        except Exception as e:
            logger.error(f"Error sending DM confirmation: {e}")

    async def show_flag_details_in_dm(self, user_id: str, flag_id: str) -> None:
        """Show flag details in a DM.

        Args:
            user_id: The ID of the user to show details to.
            flag_id: The ID of the flag to show details for.
        """
        # Implementation would retrieve flag details and display them
        logger.info(f"Showing flag details for {flag_id} to user {user_id}")

    async def handle_quick_reply_from_dm(
        self, payload: Dict[str, Any], flag_id: str
    ) -> None:
        """Handle a quick reply action from DM.

        Args:
            payload: The action payload from Slack.
            flag_id: The ID of the flag related to the quick reply.
        """
        # Implementation would handle quick reply functionality
        user_id = payload.get("user", {}).get("id")
        logger.info(f"Processing quick reply for flag {flag_id} from user {user_id}")

    async def send_notification_batch(
        self, notifications: list[Dict[str, Any]]
    ) -> Dict[str, bool]:
        """Send a batch of notifications.

        Args:
            notifications: List of notification configurations.

        Returns:
            Dictionary mapping notification IDs to success status.
        """
        results = {}
        for notification in notifications:
            try:
                user_id = notification.get("user_id")
                message_type = notification.get("type", "info")
                message = notification.get("message")
                
                if message_type == "error":
                    await self.send_dm_error(user_id, message)
                elif message_type == "confirmation":
                    await self.send_dm_confirmation(user_id, message)
                else:
                    await self.posting_handler.post_message(
                        channel_id=user_id,
                        message=message,
                    )
                
                results[notification.get("id", user_id)] = True
            except Exception as e:
                logger.error(f"Error sending notification batch item: {e}")
                results[notification.get("id", user_id)] = False
        
        return results

    def format_notification_timestamp(self, timestamp: Optional[str] = None) -> str:
        """Format a timestamp for notification display.

        Args:
            timestamp: ISO format timestamp string, or None for current time.

        Returns:
            Formatted timestamp string for display.
        """
        if timestamp:
            dt = datetime.fromisoformat(timestamp)
        else:
            dt = datetime.now(timezone.utc)
        
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    def create_notification_footer(self, notification_id: str) -> Dict[str, Any]:
        """Create a standard footer block for notifications.

        Args:
            notification_id: The ID of the notification.

        Returns:
            Slack block for the notification footer.
        """
        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Notification ID: `{notification_id}` | {self.format_notification_timestamp()}",
                }
            ],
        }
