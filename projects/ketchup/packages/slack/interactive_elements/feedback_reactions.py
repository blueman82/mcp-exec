"""
feedback_reactions.py

This module processes feedback reactions from Slack messages using a dedicated handler class.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from packages.core.local_metrics import MetricsStorage
from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class FeedbackReactionsHandler:
    """Handles processing of user feedback reactions (thumbs up/down)."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        dynamodb_store: DynamoDBStore,
        # MetricsStorage service for feedback telemetry
        metrics: MetricsStorage,
    ):
        """
        Initializes the FeedbackReactionsHandler.

        Args:
            posting_handler: Handler for posting messages to Slack.
            dynamodb_store: Handler for interacting with DynamoDB.
            metrics: Handler for publishing metrics to local storage.
        """
        self._posting_handler = posting_handler
        self._dynamodb_store = dynamodb_store
        self._metrics = metrics
        logger.info("FeedbackReactionsHandler initialized.")

    def _generate_command_execution_id(self) -> str:
        """Generate a unique ID for this command execution."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        unique_suffix = str(uuid.uuid4())[:8]  # 8 chars
        return f"{timestamp}_{unique_suffix}"

    async def _store_command_execution_context(
        self,
        command_execution_id: str,
        channel_id: str,
        command_type: str,
        command_output: str,
    ) -> None:
        """Store command execution context for later retrieval."""
        try:
            # Extract timestamp and uuid from command_execution_id
            timestamp, uuid_part = command_execution_id.split("_")

            # Store in format: CHANNEL#{channel_id} / COMMAND#{timestamp}#{uuid}
            sk_value = f"COMMAND#{timestamp}#{uuid_part}"
            command_item = {
                "PK": {"S": f"CHANNEL#{channel_id}"},
                "SK": {"S": sk_value},
                "command_execution_id": {"S": command_execution_id},
                "command_type": {"S": command_type},
                "command_output": {"S": command_output},
                "channel_id": {"S": channel_id},
                "timestamp": {
                    "N": str(timestamp)
                },  # Convert to string for DynamoDB Number type
                "created_at": {"S": datetime.now(timezone.utc).isoformat()},
                "trusted_by": {"L": []},  # Initialize empty trust list
                "trust_count": {"N": "0"},
            }

            logger.info(
                f"Storing command execution {command_execution_id} with PK: CHANNEL#{channel_id}, SK: {sk_value}"
            )

            await self._dynamodb_store.client.put_item(
                table_name=self._dynamodb_store.table_name, item=command_item
            )

            logger.info(f"Stored command execution context: {command_execution_id}")

        except Exception as e:
            logger.error(f"Error storing command execution context: {e}")

    async def _get_command_execution_context(
        self, command_execution_id: str, channel_id: str = None
    ) -> Dict[str, Any]:
        """Retrieve command execution context."""
        try:
            # Extract timestamp and uuid from command_execution_id
            timestamp, uuid_part = command_execution_id.split("_")

            # If channel_id is provided, use it for efficient lookup
            if channel_id:
                response = await self._dynamodb_store.client.get_item(
                    table_name=self._dynamodb_store.table_name,
                    key={
                        "PK": {"S": f"CHANNEL#{channel_id}"},
                        "SK": {"S": f"COMMAND#{timestamp}#{uuid_part}"},
                    },
                )

                if "Item" in response:
                    item = response["Item"]
                    return {
                        "command_execution_id": item.get(
                            "command_execution_id", {}
                        ).get("S", ""),
                        "command_type": item.get("command_type", {}).get("S", ""),
                        "command_output": item.get("command_output", {}).get("S", ""),
                        "channel_id": item.get("channel_id", {}).get("S", ""),
                    }
            else:
                # Without channel_id, we need to scan (less efficient)
                # This is a fallback for backward compatibility
                logger.warning(
                    f"No channel_id provided for command lookup: {command_execution_id}"
                )
                return {
                    "command_execution_id": command_execution_id,
                    "command_type": "unknown",
                    "command_output": "Content not available",
                    "channel_id": "unknown",
                }

        except Exception as e:
            logger.error(f"Error retrieving command execution context: {e}")
            return {}

    def map_reaction_to_rating(self, reaction: str) -> int:
        """
        Map a Slack reaction string to a numeric rating.

        Args:
            reaction: Slack reaction identifier (e.g., "trust_status_update" or "flag_status_review")

        Returns:
            1 for trust, -1 for flag, or 0 if unrecognized
        """
        try:
            if reaction == "trust_status_update":
                return 1
            elif reaction == "flag_status_review":
                return -1
            else:
                logger.warning("Unrecognized feedback reaction action_id: %s", reaction)
                return 0
        except Exception as e:
            logger.error("Error mapping reaction '%s': %s", reaction, str(e))
            return 0

    async def build_feedback_blocks(
        self, channel_id: str, summary_type: str, command_output: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Build Slack interactive buttons for trust/flag actions.

        Args:
            channel_id: The channel ID to attach feedback to
            summary_type: The type of summary for feedback context (short, long, query, etc.)
            command_output: The actual command output content for storage

        Returns:
            List of Block Kit blocks for trust/flag buttons
        """
        try:
            # Generate unique ID for this command execution
            command_execution_id = self._generate_command_execution_id()

            # Store command execution context for later retrieval
            await self._store_command_execution_context(
                command_execution_id=command_execution_id,
                channel_id=channel_id,
                command_type=summary_type,
                command_output=command_output,
            )

            # Trust button value: command_execution_id
            trust_value = command_execution_id

            # Flag button value: channel_id|command_execution_id|command_type
            flag_value = f"{channel_id}|{command_execution_id}|{summary_type}"

            # Construct the Block Kit JSON structure directly
            # Explicitly type hint the list for mypy
            feedback_blocks: List[Dict[str, Any]] = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Please rate the summary (ID: {channel_id}):",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "style": "primary",
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✓ Trust this summary",
                            },
                            "value": trust_value,
                            "action_id": "trust_status_update",
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🚩 Flag for review",
                            },
                            "value": flag_value,
                            "action_id": "flag_status_review",
                        },
                    ],
                },
                # Context block removed as per previous logic
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Generated by Ketchup. :ketchup:\n"
                            ":warning: *Attention* :warning:\n"
                            "This auto-generated summary is based on Slack discussions.\n"
                            "Please review and validate every detail carefully before using it for CFS,\n"
                            "ticketing, or any formal communication",
                        },
                    ],
                },
            ]
            logger.info(
                "Created feedback blocks for channel %s with type %s",
                channel_id,
                summary_type,
            )
            return feedback_blocks
        except Exception as e:
            error_message = (
                f"Error creating feedback blocks for channel {channel_id}: {e}"
            )
            logger.error(error_message)
            return []

    async def acknowledge_reaction(
        self,
        response_url: str,
        rating: str,
    ) -> bool:
        """
        Sends an ephemeral acknowledgment message using the response_url.

        Args:
            response_url: The response URL from the original interaction.
            rating: The feedback rating ('positive' or 'negative').

        Returns:
            True if acknowledgment was sent successfully, False otherwise.
        """
        logger.info("Sending acknowledgment via response_url...")
        icon = "✓" if rating == "positive" else "🚩"
        message_text = "Trust recorded" if rating == "positive" else "Flag recorded"
        ack_blocks = [
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"{icon} {message_text}"}],
            }
        ]

        try:
            # Use the injected posting handler
            response = await self._posting_handler._post_response_url(
                response_url=response_url,
                message=message_text,
                blocks=ack_blocks,
            )
            success = isinstance(response, dict) and response.get("ok", False)
            if success:
                logger.info(
                    "Feedback acknowledgment sent successfully via response_url."
                )
            else:
                logger.error(
                    "Failed to send feedback acknowledgment via response_url: %s",
                    response,
                )
            return success
        except Exception as e:
            logger.error(
                "Exception sending feedback acknowledgment via response_url: %s",
                e,
                exc_info=True,
            )
            return False

    async def publish_feedback_metric(self, summary_type: str, rating: int) -> bool:
        """
        Publish feedback metrics to local storage using the injected handler.

        Args:
            summary_type: The type of summary (e.g., short, long, query)
            rating: Numeric rating (1 for positive, -1 for negative)

        Returns:
            True if metric published successfully, False otherwise
        """
        # Use the injected metrics storage instance
        metric_name = "UserFeedbackRating"
        dimensions = [
            {"Name": "SummaryType", "Value": summary_type},
            {"Name": "RatingValue", "Value": str(rating)},
        ]
        try:
            # Use the injected handler
            success = await self._metrics.put_metric(
                name=metric_name, value=rating, dimensions=dimensions
            )
            if success:
                logger.info(
                    "Published feedback metric '%s' with rating %d for type '%s'",
                    metric_name,
                    rating,
                    summary_type,
                )
            else:
                logger.warning(
                    "Failed to publish feedback metric for type '%s'", summary_type
                )
            return success
        except Exception as e:
            logger.error("Error publishing feedback metric: %s", str(e))
            return False

    async def process_feedback_reaction(
        self,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Process a feedback reaction interaction payload.

        Args:
            payload: The interaction payload dictionary from Slack.

        Returns:
            True if processing was successful, False otherwise.
        """
        if not payload or "actions" not in payload or not payload["actions"]:
            logger.error("Invalid or missing payload/actions for feedback processing.")
            return False

        try:
            action = payload["actions"][0]
            action_id = action.get("action_id")
            response_url = payload.get("response_url")
            user_id = payload.get("user", {}).get("id")
            value_parts = action.get("value", "").split("|")

            # Check response_url specifically before using it
            if not response_url:
                logger.error(
                    "Missing response_url in feedback payload. Cannot acknowledge."
                )
                # We might still be able to store feedback/metrics if other data is present,
                # but acknowledgement isn't possible.
                # Consider returning False or continuing without acknowledgement.
                # For now, let's return False as ack is important UX.
                return False

            if not all([action_id, user_id]) or len(value_parts) != 3:
                logger.error(
                    "Missing required fields (excluding response_url check) or invalid value format in feedback payload: action_id=%s, user_id=%s, value_parts=%s",
                    action_id,
                    user_id,
                    value_parts,
                )
                # Attempt to notify user if possible
                await self.acknowledge_reaction(response_url, "error")
                return False

            channel_id, summary_type, _ = value_parts  # Extracted for context/logging

            logger.info(
                "Processing feedback reaction: user=%s, channel=%s, type=%s, action=%s",
                user_id,
                channel_id,
                summary_type,
                action_id,
            )

            rating_value = self.map_reaction_to_rating(action_id)
            if rating_value == 0:
                logger.warning("Could not map action_id '%s' to a rating.", action_id)
                await self.acknowledge_reaction(
                    response_url, "error"
                )  # Safe to call now
                return False

            # Note: This method is no longer used since trust/flag actions are routed
            # directly to their respective handlers. This is kept for backward compatibility.
            logger.info(
                "Feedback reaction processed but no longer stored - routed to trust/flag handlers"
            )

            # Just acknowledge the reaction
            rating_str = "positive" if rating_value == 1 else "negative"
            ack_sent = await self.acknowledge_reaction(response_url, rating_str)
            if not ack_sent:
                logger.warning("Acknowledgment sending failed.")

            return True

        except Exception as e:
            logger.error(
                "Unexpected error processing feedback reaction: %s", e, exc_info=True
            )
            # Attempt to send generic error acknowledgment if possible
            response_url_in_except = payload.get("response_url")
            if response_url_in_except:
                try:
                    await self.acknowledge_reaction(response_url_in_except, "error")
                except Exception as ack_err:
                    logger.error(
                        "Failed to send error acknowledgment during exception handling: %s",
                        ack_err,
                    )
            return False
