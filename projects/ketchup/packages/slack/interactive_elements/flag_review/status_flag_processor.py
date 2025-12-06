"""Status Flag Processor Module.

Handles flag status processing and validation for AI-generated summaries.
Provides functionality for creating, storing, and managing status flags.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.interactive_elements.flag_review.flag_types import REVIEW_CHANNEL_ID
from packages.slack.interactive_elements.flag_review.message_updater import MessageUpdater
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class StatusFlagProcessor:
    """Handles flag status processing and validation."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        db_store: DynamoDBStore,
        secrets_manager=None,
    ):
        """Initialize the status flag processor.

        Args:
            posting_handler: Handler for posting messages to Slack.
            db_store: DynamoDB store for data persistence.
            secrets_manager: Secrets manager for API tokens (optional for backward compatibility).
        """
        self.posting_handler = posting_handler
        self.db_store = db_store
        self.secrets_manager = secrets_manager
        self.message_updater = MessageUpdater(posting_handler)

    async def handle_flag_button_click(self, payload: Dict[str, Any]) -> bool:
        """Handle the flag for review button click for status updates."""
        try:
            action = payload.get("actions", [{}])[0]
            value = action.get("value", "")
            trigger_id = payload.get("trigger_id")

            # Extract info from button value: "{channel_id}|{message_ts}|{status_update_id}"
            parts = value.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid flag button value format: {value}")
                return False

            channel_id, message_ts, status_update_id = parts[0], parts[1], parts[2]

            # Check if already flagged
            existing_flag = await self.get_feedback_data(channel_id, message_ts)
            if existing_flag and existing_flag.get("status") == "pending":
                logger.warning(f"Message {channel_id}_{message_ts} already flagged")
                await self._show_already_flagged_modal(trigger_id)
                return False

            # Display feedback modal
            await self._show_feedback_modal(trigger_id, channel_id, message_ts, status_update_id)
            return True

        except Exception as e:
            logger.error(f"Error handling flag button click: {e}")
            return False

    async def handle_flag_submission(self, payload: Dict[str, Any]) -> bool:
        """Handle the flag review modal submission for status updates.

        Args:
            payload: The view_submission payload from Slack containing the modal data.

        Returns:
            True if submission was processed successfully, False otherwise.
        """
        try:
            # Extract user information
            user_id = payload.get("user", {}).get("id")
            user_name = payload.get("user", {}).get("name", "unknown")

            # Extract feedback text from modal input
            values = payload.get("view", {}).get("state", {}).get("values", {})
            feedback_text = (
                values.get("feedback_block", {}).get("feedback_input", {}).get("value", "")
            )

            # Extract metadata from private_metadata
            private_metadata = payload.get("view", {}).get("private_metadata", "")
            parts = private_metadata.split("|")
            if len(parts) < 3:
                logger.error(f"Invalid private_metadata format: {private_metadata}")
                return False

            channel_id, message_ts, status_update_id = parts[0], parts[1], parts[2]

            # Validate feedback
            validation_result = await self.validate_feedback(
                text=feedback_text, user_id=user_id, channel_id=channel_id
            )
            if not validation_result["valid"]:
                logger.warning(f"Invalid feedback: {validation_result['issues']}")

            # Store flag in database
            flag_result = await self.add_flag(
                channel_id,
                message_ts,
                user_id,
                user_name,
                feedback_text,
                validation_result.get("issues", []),
            )
            if not flag_result["success"]:
                logger.error(f"Failed to store flag: {flag_result.get('error')}")
                return False

            # Post to review channel
            await self.post_to_review_channel(
                channel_id,
                message_ts,
                user_id,
                user_name,
                feedback_text,
                validation_result.get("issues", []),
                status_update_id,
            )

            # Update original message to show it's been flagged
            await self.message_updater.update_original_message(
                channel_id=channel_id,
                message_ts=message_ts,
                user_id=user_id,
            )

            logger.info(f"Flag submission processed successfully for {channel_id}/{message_ts}")
            return True

        except Exception as e:
            logger.error(f"Error handling flag submission: {e}", exc_info=True)
            return False

    async def validate_feedback(self, text: str, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Validate feedback text for potential issues."""
        issues = []
        if len(text) < 10:
            issues.append("Feedback too short")
        elif len(text) > 3000:
            issues.append("Feedback exceeds maximum length")
        # Check for potential security issues
        suspicious_patterns = ["<script", "javascript:", "onclick=", "onerror="]
        for pattern in suspicious_patterns:
            if pattern.lower() in text.lower():
                issues.append("Contains potentially unsafe content")
                break
        # Check for spam patterns
        if text.count("http") > 5:
            issues.append("Contains too many URLs")
        return {"valid": len(issues) == 0, "issues": issues, "sanitized_text": text}

    async def add_flag(
        self,
        channel_id: str,
        message_ts: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: List[str],
    ) -> Dict[str, Any]:
        """Add a flag to the database.

        Args:
            channel_id: The channel ID where the flag was created.
            message_ts: The timestamp of the message being flagged.
            user_id: The ID of the user creating the flag.
            user_name: The username of the user creating the flag.
            feedback_text: The user's feedback text.
            validation_issues: List of validation issues found in the feedback.

        Returns:
            Dictionary with 'success' boolean and optional 'error' message.
        """
        try:
            # Check if flag already exists (singleton pattern)
            existing_flag = await self.get_feedback_data(channel_id, message_ts)
            if existing_flag:
                logger.info(f"Flag already exists for {channel_id}/{message_ts}")
                return {"success": True, "already_exists": True}

            # Store flag in DynamoDB
            flag_item = {
                "PK": {"S": f"FEEDBACK#{channel_id}#{message_ts}"},
                "SK": {"S": f"FLAG#{user_id}"},  # Singleton per message
                "feedback_type": {"S": "flag"},
                "channel_id": {"S": channel_id},
                "message_ts": {"S": message_ts},
                "user_id": {"S": user_id},
                "user_name": {"S": user_name},
                "original_text": {"S": feedback_text},
                "sanitized_text": {"S": feedback_text},  # Could add sanitization
                "sanitization_issues": {"L": [{"S": issue} for issue in validation_issues]},
                "text_length": {"N": str(len(feedback_text))},
                "status": {"S": "pending"},
                "created_at": {"S": datetime.now(timezone.utc).isoformat()},
                "ttl": {
                    "N": str(int((datetime.now(timezone.utc).timestamp()) + (30 * 24 * 60 * 60)))
                },
                "review_channel_id": {"S": REVIEW_CHANNEL_ID},
                "slack_team_id": {"S": "T018BPFUD75"},
                "app_version": {"S": "2.1.0"},
            }

            await self.db_store.client.put_item(table_name=self.db_store.table_name, item=flag_item)

            logger.info(f"Stored flag for message {message_ts} from user {user_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error adding flag: {e}")
            return {"success": False, "error": str(e)}

    async def post_to_review_channel(
        self,
        channel_id: str,
        message_ts: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: List[str],
        status_update_id: str,
    ) -> None:
        """Post feedback to the review channel.

        Args:
            channel_id: The channel ID where the feedback originated.
            message_ts: The timestamp of the message being flagged.
            user_id: The ID of the user who provided feedback.
            user_name: The username of the user who provided feedback.
            feedback_text: The user's feedback text.
            validation_issues: List of validation issues found in the feedback.
            status_update_id: The status update ID being flagged.
        """
        try:
            # Get original summary from trust data
            original_summary = await self.get_original_summary(channel_id, status_update_id)

            # Create message blocks for the review channel
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Status Update Flagged for Review*\n"
                        f"Reported by: <@{user_id}>\n"
                        f"Channel: <#{channel_id}>\n"
                        f"Message: https://slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Feedback:*\n{feedback_text}",
                    },
                },
            ]

            # Only add original summary if we found one (skip "Summary not found" messages)
            if original_summary and original_summary != "Summary not found":
                blocks.extend(
                    [
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Original Summary:*\n{original_summary[:500]}{'...' if len(original_summary) > 500 else ''}",
                            },
                        },
                    ]
                )

            # Add validation warnings if any
            if validation_issues:
                blocks.append(
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"⚠️ Validation warnings: {', '.join(validation_issues)}",
                            }
                        ],
                    }
                )

            # Add action buttons for acknowledge and reply
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Acknowledge Review"},
                            "action_id": "acknowledge_feedback",
                            "value": f"{channel_id}|{message_ts}|{user_id}",
                            "style": "primary",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "💬 Reply"},
                            "action_id": "reply_to_feedback",
                            "value": f"{channel_id}|{message_ts}|{user_id}",
                        },
                    ],
                }
            )

            # Post and store result
            await self.post_summary_review_and_store(
                blocks=blocks,
                channel_id=channel_id,
                message_ts=message_ts,
            )

        except Exception as e:
            logger.error(f"Error posting to review channel: {e}", exc_info=True)

    async def get_original_summary(self, channel_id: str, status_update_id: str) -> str:
        """Get original summary from trust data.

        Args:
            channel_id: The channel ID where the status update was posted.
            status_update_id: The unique status update ID.

        Returns:
            The original summary text if found, default message otherwise.
        """
        original_summary = "Summary not found"
        if status_update_id:
            trust_data = await self.db_store.trust_ops.get_trust_data(channel_id, status_update_id)
            if trust_data:
                original_summary = trust_data.get("content_preview", original_summary)
        return original_summary

    async def post_summary_review_and_store(
        self,
        blocks: List[Dict[str, Any]],
        channel_id: str,
        message_ts: str,
    ) -> None:
        """Post summary review message and store result timestamp.

        Args:
            blocks: List of block dictionaries for the review message.
            channel_id: The channel ID where the original message was posted.
            message_ts: The timestamp of the original message being reviewed.
        """
        try:
            result = await self.posting_handler.post_message(
                channel_id=REVIEW_CHANNEL_ID,
                blocks=blocks,
                message="Summary flagged for review",
            )

            # Store review message timestamp for later updates
            if result and result.get("ts"):
                await self.update_feedback_review_ts(
                    channel_id=channel_id, message_ts=message_ts, review_ts=result["ts"]
                )

        except Exception as e:
            logger.error(f"Error posting summary review message: {e}")

    async def get_feedback_data(self, channel_id: str, message_ts: str) -> Optional[Dict[str, Any]]:
        """Get feedback data for a message.

        Args:
            channel_id: The channel ID where the message was posted.
            message_ts: The timestamp of the message.

        Returns:
            Dictionary containing feedback data if found, None otherwise.
        """
        try:
            # Query for feedback items
            result = await self.db_store.client.query(
                table_name=self.db_store.table_name,
                key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":pk": {"S": f"FEEDBACK#{channel_id}#{message_ts}"},
                    ":sk_prefix": {"S": "FLAG#"},
                },
            )

            items = result.get("Items", [])
            if items:
                # Return first item (should only be one due to singleton flag)
                item = items[0]
                return {
                    "user_id": item.get("user_id", {}).get("S", ""),
                    "user_name": item.get("user_name", {}).get("S", ""),
                    "feedback_text": item.get("original_text", {}).get("S", ""),
                    "status": item.get("status", {}).get("S", "pending"),
                }

            return None

        except Exception as e:
            logger.error(f"Error getting feedback data: {e}")
            return None

    async def update_feedback_review_ts(
        self, channel_id: str, message_ts: str, review_ts: str
    ) -> None:
        """Store the review message timestamp.

        Args:
            channel_id: The channel ID where the original message was posted.
            message_ts: The timestamp of the original message.
            review_ts: The timestamp of the review message.
        """
        try:
            feedback_data = await self.get_feedback_data(channel_id, message_ts)
            if not feedback_data:
                return

            user_id = feedback_data["user_id"]

            await self.db_store.client.update_item(
                table_name=self.db_store.table_name,
                key={
                    "PK": {"S": f"FEEDBACK#{channel_id}#{message_ts}"},
                    "SK": {"S": f"FLAG#{user_id}"},
                },
                update_expression="SET review_message_ts = :ts",
                expression_attribute_values={":ts": {"S": review_ts}},
            )

        except Exception as e:
            logger.error(f"Error updating review message timestamp: {e}")

    async def _show_feedback_modal(
        self, trigger_id: str, channel_id: str, message_ts: str, status_update_id: str
    ) -> bool:
        """Display feedback modal for user to enter their feedback.

        Args:
            trigger_id: Slack trigger ID for opening the modal.
            channel_id: The channel ID where the message exists.
            message_ts: The timestamp of the message being flagged.
            status_update_id: The status update ID being flagged.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        if not self.secrets_manager:
            logger.error("No secrets_manager available to display modal")
            return False

        try:
            # Create modal view
            modal_view = {
                "type": "modal",
                "callback_id": "flag_review_modal",
                "private_metadata": f"{channel_id}|{message_ts}|{status_update_id}",
                "title": {"type": "plain_text", "text": "Flag for Review"},
                "submit": {"type": "plain_text", "text": "Send"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Please describe what's wrong with this status update:",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "feedback_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "feedback_input",
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "The summary is incorrect because...",
                            },
                            "min_length": 10,
                            "max_length": 3000,
                        },
                        "label": {"type": "plain_text", "text": "Your feedback"},
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "Your feedback will be sent to the Ketchup team for review.",
                            }
                        ],
                    },
                ],
            }

            # Display modal via Slack API
            slack_api_token = await self.secrets_manager.get_slack_api_token_async()
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }
            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error(f"Failed to open feedback modal: {error_msg}")
                        return False

            logger.info("Feedback modal opened successfully")
            return True

        except Exception as e:
            logger.error(f"Error showing feedback modal: {e}")
            return False

    async def _show_already_flagged_modal(self, trigger_id: str) -> bool:
        """Display error modal when message is already flagged.

        Args:
            trigger_id: Slack trigger ID for opening the modal.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        if not self.secrets_manager:
            logger.error("No secrets_manager available to display modal")
            return False

        try:
            # Create error modal view
            modal_view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": "Already Flagged"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "⚠️ This status update has already been flagged for review.\n\nYou cannot flag it again until the review is complete.",
                        },
                    }
                ],
            }

            # Display modal via Slack API
            slack_api_token = await self.secrets_manager.get_slack_api_token_async()
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }
            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error(f"Failed to open already-flagged modal: {error_msg}")
                        return False

            logger.info("Already-flagged modal opened successfully")
            return True

        except Exception as e:
            logger.error(f"Error showing already-flagged modal: {e}")
            return False
