"""Message Updater Module.

Handles message updates, content transformation, and coordination for flag review operations.
Provides functionality for updating original messages, review messages, and managing state changes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from packages.core.logging import setup_logger
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class MessageUpdater:
    """Handles message updates, content transformation, and coordination."""

    def __init__(self, posting_handler: SlackPostingHandler):
        """Initialize the message updater.

        Args:
            posting_handler: Handler for posting messages to Slack.
        """
        self.posting_handler = posting_handler

    async def update_original_message(
        self, channel_id: str, message_ts: str, user_id: str
    ) -> None:
        """Update the original message to show it's been flagged.

        Args:
            channel_id: The channel ID containing the message.
            message_ts: The timestamp of the message to update.
            user_id: The ID of the user who flagged the message.
        """
        try:
            # Get current message using api_call
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
                logger.error(
                    f"Could not find message {message_ts} in channel {channel_id}"
                )
                return

            message = result["messages"][0]
            blocks = message.get("blocks", [])

            # Add flag indicator
            flag_display = f"⚠️ Flagged for review by <@{user_id}>"
            updated_blocks = self.update_flag_display_in_blocks(blocks, flag_display)

            # Update message
            await self.posting_handler.update_message(
                channel_id=channel_id,
                ts=message_ts,
                message="Status update flagged for review",
                blocks=updated_blocks,
            )

        except Exception as e:
            logger.error(f"Error updating original message: {e}")

    async def update_acknowledged_message(
        self, channel_id: str, message_ts: str, admin_id: str, user_id: str
    ) -> None:
        """Update message after admin acknowledgment.

        Args:
            channel_id: The channel ID containing the message.
            message_ts: The timestamp of the message to update.
            admin_id: The ID of the admin who acknowledged the feedback.
            user_id: The ID of the user who flagged the message.
        """
        try:
            # Get current message using api_call
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
                return

            message = result["messages"][0]
            blocks = message.get("blocks", [])

            # Update display
            flag_display = (
                f"✅ Reviewed: Feedback from <@{user_id}> acknowledged by <@{admin_id}>"
            )
            updated_blocks = self.update_flag_display_in_blocks(blocks, flag_display)

            # Update message
            await self.posting_handler.update_message(
                channel_id=channel_id,
                ts=message_ts,
                message="Status update flagged for review",
                blocks=updated_blocks,
            )

        except Exception as e:
            logger.error(f"Error updating acknowledged message: {e}")

    def update_flag_display_in_blocks(
        self, blocks: List[Dict[str, Any]], flag_display: str
    ) -> List[Dict[str, Any]]:
        """Update flag display in message blocks.

        Args:
            blocks: List of existing message blocks.
            flag_display: The new flag display text to show.

        Returns:
            Updated list of message blocks with flag display.
        """
        updated_blocks = []
        flag_updated = False

        for block in blocks:
            # Check if this is an existing flag display block
            if block.get("type") == "section" and block.get("text", {}).get(
                "text", ""
            ).startswith(("⚠️ Flagged", "✅ Reviewed")):
                # Replace with new display
                if flag_display and not flag_updated:
                    updated_blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": flag_display},
                        }
                    )
                    flag_updated = True
            else:
                updated_blocks.append(block)

        # If no existing flag block found, add before buttons
        if not flag_updated and flag_display:
            # Find where to insert (before actions block)
            insert_index = len(updated_blocks)
            for i, block in enumerate(updated_blocks):
                if block.get("type") == "actions":
                    insert_index = i
                    break

            updated_blocks.insert(
                insert_index,
                {"type": "section", "text": {"type": "mrkdwn", "text": flag_display}},
            )

        return updated_blocks

    async def update_review_message(
        self, payload: Dict[str, Any], admin_id: str
    ) -> None:
        """Update the review channel message after acknowledgment.

        Args:
            payload: The interaction payload from Slack.
            admin_id: The ID of the admin who acknowledged the feedback.
        """
        try:
            # Get current blocks
            blocks = payload.get("message", {}).get("blocks", [])

            # Add acknowledgment context with HH:MM time format
            ack_time = datetime.now(timezone.utc).strftime("%H:%M")
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"✅ Acknowledged by <@{admin_id}> at {ack_time}",
                        }
                    ],
                }
            )

            # Remove acknowledge button, add Mark as Completed button, keep reply button
            for block in blocks:
                if block.get("type") == "actions":
                    # Extract button value from any existing button for reuse
                    button_value = None
                    for element in block.get("elements", []):
                        if element.get("value"):
                            button_value = element["value"]
                            break

                    # Filter out acknowledge buttons, keep reply button
                    filtered_elements = [
                        element
                        for element in block.get("elements", [])
                        if element.get("action_id") not in [
                            "acknowledge_feedback",
                            "acknowledge_command_feedback"
                        ]
                    ]

                    # Add Mark as Completed button at the beginning if we have the value
                    if button_value:
                        mark_completed_button = {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Mark as Completed"},
                            "action_id": "mark_review_completed",
                            "value": button_value,
                            "style": "primary",
                        }
                        filtered_elements.insert(0, mark_completed_button)

                    block["elements"] = filtered_elements

            # Update message
            await self.posting_handler.update_message(
                channel_id=payload.get("channel", {}).get("id"),
                ts=payload.get("message", {}).get("ts"),
                message="✅ Acknowledged",
                blocks=blocks,
            )

        except Exception as e:
            logger.error(f"Error updating review message: {e}")

    async def update_review_message_with_reply(
        self, payload: Dict[str, Any], admin_id: str
    ) -> None:
        """Update the review channel message after reply is sent.

        Args:
            payload: The interaction payload from Slack.
            admin_id: The ID of the admin who sent the reply.
        """
        try:
            # Get current blocks
            blocks = payload.get("message", {}).get("blocks", [])

            # Add reply context with HH:MM time format
            reply_time = datetime.now(timezone.utc).strftime("%H:%M")
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"💬 Reply sent by <@{admin_id}> at {reply_time}",
                        }
                    ],
                }
            )

            # Remove action buttons
            blocks = [b for b in blocks if b.get("type") != "actions"]

            # Update message
            await self.posting_handler.update_message(
                channel_id=payload.get("channel", {}).get("id"),
                ts=payload.get("message", {}).get("ts"),
                message="💬 Reply sent",
                blocks=blocks,
            )

        except Exception as e:
            logger.error(f"Error updating review message with reply: {e}")

    async def update_review_message_completed(
        self, payload: Dict[str, Any], admin_id: str
    ) -> None:
        """Update the review channel message when marked as completed.

        Args:
            payload: The interaction payload from Slack.
            admin_id: The ID of the admin who marked it complete.
        """
        try:
            # Get current blocks
            blocks = payload.get("message", {}).get("blocks", [])

            # Apply strikethrough to the first section block (title)
            for block in blocks:
                if block.get("type") == "section" and block.get("text", {}).get("type") == "mrkdwn":
                    text = block["text"]["text"]
                    # Apply strikethrough to title line only if not already applied
                    if "Flagged for Review" in text and not text.startswith("~"):
                        # Split into lines, apply strikethrough only to first line (title)
                        lines = text.split("\n")
                        if lines:
                            # Apply strikethrough to title line only, add REVIEW COMPLETED suffix
                            lines[0] = f"~{lines[0]}~ - *REVIEW COMPLETED*"
                            # Reconstruct with checkmark
                            block["text"]["text"] = f"✅ {'\n'.join(lines)}"
                    break

            # Add completion context with HH:MM UTC time format
            completed_time = datetime.now(timezone.utc).strftime("%H:%M")
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"✅ Review completed by <@{admin_id}> at {completed_time} UTC",
                        }
                    ],
                }
            )

            # Remove all action buttons
            blocks = [b for b in blocks if b.get("type") != "actions"]

            # Update message
            await self.posting_handler.update_message(
                channel_id=payload.get("channel", {}).get("id"),
                ts=payload.get("message", {}).get("ts"),
                message="✅ Review Completed",
                blocks=blocks,
            )

        except Exception as e:
            logger.error(f"Error updating review message as completed: {e}")

    async def check_message_exists(self, channel_id: str, message_ts: str) -> bool:
        """Check if the original message still exists in the channel.

        Args:
            channel_id: The channel ID to check.
            message_ts: The timestamp of the message to check.

        Returns:
            True if message exists, False otherwise.
        """
        try:
            result = await self.posting_handler.api_call(
                endpoint="conversations.history",
                payload={
                    "channel": channel_id,
                    "latest": message_ts,
                    "limit": 1,
                    "inclusive": True,
                },
            )

            messages = result.get("messages", [])
            if messages and messages[0].get("ts") == message_ts:
                return True
            else:
                logger.info(
                    f"Message {message_ts} no longer exists in channel {channel_id}"
                )
                return False

        except Exception as e:
            logger.error(f"Error checking if message exists: {e}")
            # Assume it doesn't exist if we can't check
            return False

    async def update_review_message_orphaned(
        self, payload: Dict[str, Any], admin_id: str, channel_id: str
    ) -> None:
        """Update the review channel message when original message no longer exists.

        Args:
            payload: The interaction payload from Slack.
            admin_id: The ID of the admin acknowledging the feedback.
            channel_id: The channel ID where the original message was posted.
        """
        try:
            # Get current blocks
            blocks = payload.get("message", {}).get("blocks", [])

            # Add warning about orphaned message
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚠️ *Original message no longer exists* - likely replaced by a newer status update",
                    },
                }
            )

            # Add acknowledgment context with HH:MM time format
            ack_time = datetime.now(timezone.utc).strftime("%H:%M")
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"✅ Acknowledged by <@{admin_id}> at {ack_time} (feedback recorded)",
                        }
                    ],
                }
            )

            # Remove acknowledge button, add Mark as Completed button, keep reply button
            for block in blocks:
                if block.get("type") == "actions":
                    # Extract button value from any existing button for reuse
                    button_value = None
                    for element in block.get("elements", []):
                        if element.get("value"):
                            button_value = element["value"]
                            break

                    # Filter out acknowledge buttons, keep reply button
                    filtered_elements = [
                        element
                        for element in block.get("elements", [])
                        if element.get("action_id") not in [
                            "acknowledge_feedback",
                            "acknowledge_command_feedback"
                        ]
                    ]

                    # Add Mark as Completed button at the beginning if we have the value
                    if button_value:
                        mark_completed_button = {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Mark as Completed"},
                            "action_id": "mark_review_completed",
                            "value": button_value,
                            "style": "primary",
                        }
                        filtered_elements.insert(0, mark_completed_button)

                    block["elements"] = filtered_elements

            # Update message
            await self.posting_handler.update_message(
                channel_id=payload.get("channel", {}).get("id"),
                ts=payload.get("message", {}).get("ts"),
                message="✅ Acknowledged (original message replaced)",
                blocks=blocks,
            )

            # Also send ephemeral message to admin
            await self.posting_handler.post_message(
                channel_id=payload.get("channel", {}).get("id"),
                user_id=admin_id,
                message=f"ℹ️ Note: The original message in <#{channel_id}> has been "
                         "replaced by a newer status update, but your acknowledgment "
                         "has been recorded.",
            )

        except Exception as e:
            logger.error(f"Error updating orphaned review message: {e}")