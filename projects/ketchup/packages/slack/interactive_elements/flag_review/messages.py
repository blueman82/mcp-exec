"""
Message handling for flag review functionality.

This module handles posting, updating, and formatting messages
related to flag reviews, feedback, and admin responses.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.slack.interactive_elements.flag_review.flag_types import REVIEW_CHANNEL_ID
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class FlagReviewMessageHandler:
    """Handles message operations for flag review functionality."""

    def __init__(self, posting_handler: SlackPostingHandler):
        """
        Initialize the message handler.

        Args:
            posting_handler: Handler for posting messages to Slack
        """
        self.posting_handler = posting_handler

    async def post_flag_message(
        self,
        channel_id: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: List[str],
        message_ts: Optional[str] = None,
        status_text: Optional[str] = None,
    ) -> Optional[str]:
        """
        Post a flag review message to the review channel.

        Args:
            channel_id: Channel where the flag was raised
            user_id: ID of the user who flagged
            user_name: Name of the user who flagged
            feedback_text: The feedback provided
            validation_issues: Any validation issues found
            message_ts: Timestamp of the original message (optional)
            status_text: The status text being flagged (optional)

        Returns:
            Message timestamp if posted successfully, None otherwise
        """
        try:
            # Format time as HH:MM
            flag_time = datetime.now(timezone.utc)
            time_str = flag_time.strftime("%H:%M")

            blocks = self._create_flag_review_blocks(
                channel_id=channel_id,
                user_id=user_id,
                user_name=user_name,
                feedback_text=feedback_text,
                validation_issues=validation_issues,
                time_str=time_str,
                message_ts=message_ts,
                status_text=status_text,
            )

            # Post to review channel
            result = await self.posting_handler.post_message(
                channel_id=REVIEW_CHANNEL_ID,
                message="New flag for review",
                blocks=blocks,
            )

            if result.get("ok"):
                return result.get("ts")
            return None

        except Exception as e:
            logger.error(f"Error posting flag message: {e}")
            return None

    async def update_existing_message(
        self,
        channel_id: str,
        message_ts: str,
        update_type: str,
        user_id: Optional[str] = None,
        admin_id: Optional[str] = None,
    ) -> bool:
        """
        Update an existing message with flag status.

        Args:
            channel_id: Channel containing the message
            message_ts: Timestamp of the message to update
            update_type: Type of update ('flagged', 'acknowledged', 'replied')
            user_id: ID of the user who flagged (for 'flagged' type)
            admin_id: ID of the admin who took action (for other types)

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get current message
            result = await self.posting_handler.api_call(
                endpoint="conversations.history",
                payload={
                    "channel": channel_id,
                    "latest": message_ts,
                    "limit": 1,
                    "inclusive": True,
                },
            )

            if not result.get("messages"):
                logger.error(f"Could not find message {message_ts} in channel {channel_id}")
                return False

            message = result["messages"][0]
            blocks = message.get("blocks", [])

            # Create appropriate flag display
            if update_type == "flagged":
                flag_display = f"⚠️ Flagged for review by <@{user_id}>"
            elif update_type == "acknowledged":
                flag_display = f"✅ Acknowledged by <@{admin_id}>"
            elif update_type == "replied":
                flag_display = f"💬 Reply sent by <@{admin_id}>"
            else:
                flag_display = "⚠️ Flagged for review"

            updated_blocks = self._update_flag_display_in_blocks(blocks, flag_display)

            # Update message
            update_result = await self.posting_handler.update_message(
                channel_id=channel_id,
                ts=message_ts,
                message="Status update flagged for review",
                blocks=updated_blocks,
            )

            return update_result.get("ok", False)

        except Exception as e:
            logger.error(f"Error updating existing message: {e}")
            return False

    async def send_confirmation_message(
        self,
        response_url: str,
        confirmation_type: str,
        user_id: Optional[str] = None,
        additional_text: Optional[str] = None,
    ) -> bool:
        """
        Send a confirmation message to the user.

        Args:
            response_url: Slack response URL
            confirmation_type: Type of confirmation ('submitted', 'acknowledged', 'replied')
            user_id: User ID for mentions (optional)
            additional_text: Additional text to include (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if confirmation_type == "submitted":
                message = "✅ Thank you! Your feedback has been submitted for review."
            elif confirmation_type == "acknowledged":
                message = f"✅ Feedback acknowledged. <@{user_id}> has been notified."
            elif confirmation_type == "replied":
                message = f"✅ Reply sent to <@{user_id}>."
            else:
                message = "✅ Action completed successfully."

            if additional_text:
                message += f"\n{additional_text}"

            await self.posting_handler.post_message(
                response_url=response_url,
                message=message,
                replace_original=False,
            )
            return True

        except Exception as e:
            logger.error(f"Error sending confirmation message: {e}")
            return False

    def _create_flag_review_blocks(
        self,
        channel_id: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: List[str],
        time_str: str,
        message_ts: Optional[str] = None,
        status_text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Create message blocks for flag review.

        Args:
            channel_id: Channel ID
            user_id: User ID
            user_name: User name
            feedback_text: Feedback text
            validation_issues: Validation issues
            time_str: Time string
            message_ts: Message timestamp (optional)
            status_text: Status text (optional)

        Returns:
            List of message blocks
        """
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Status Flagged for Review"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Channel:*\n<#{channel_id}>"},
                    {"type": "mrkdwn", "text": f"*Flagged by:*\n<@{user_id}>"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{time_str}"},
                ],
            },
        ]

        # Add message link if available
        if message_ts:
            link = f"https://adobe.enterprise.slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"
            blocks[1]["fields"].insert(1, {"type": "mrkdwn", "text": f"*Message:*\n<{link}|View>"})

        # Add status text if available
        if status_text:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Status Text:*\n```{status_text[:500]}```",
                    },
                }
            )

        # Add feedback
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Feedback:*\n{feedback_text}"},
            }
        )

        # Add validation issues if any
        if validation_issues:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"⚠️ Validation notes: {', '.join(validation_issues)}",
                        }
                    ],
                }
            )

        # Add action buttons
        if message_ts:
            # Include user_id in both button values for precise flag lookup
            acknowledge_value = f"{channel_id}|{message_ts}|{user_id}"
            reply_value = f"{channel_id}|{message_ts}|{user_id}"
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Acknowledge"},
                            "style": "primary",
                            "action_id": "acknowledge_feedback",
                            "value": acknowledge_value,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "💬 Reply"},
                            "action_id": "reply_to_feedback",
                            "value": reply_value,
                        },
                    ],
                }
            )

        return blocks

    def _update_flag_display_in_blocks(
        self, blocks: List[Dict[str, Any]], flag_display: str
    ) -> List[Dict[str, Any]]:
        """
        Update blocks to include flag display.

        Args:
            blocks: Original message blocks
            flag_display: Flag display text to add

        Returns:
            Updated blocks
        """
        # Find or create context block for flag display
        context_block_index = -1
        for i, block in enumerate(blocks):
            if block.get("type") == "context" and any(
                "Flagged" in str(element.get("text", "")) for element in block.get("elements", [])
            ):
                context_block_index = i
                break

        if context_block_index >= 0:
            # Update existing context block
            blocks[context_block_index] = {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": flag_display}],
            }
        else:
            # Add new context block at the end
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": flag_display}],
                }
            )

        return blocks
