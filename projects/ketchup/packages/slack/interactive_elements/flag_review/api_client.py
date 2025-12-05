"""
api_client.py

Handles external API interactions, HTTP requests, and database operations
for flag review functionality. Provides centralized client management for
Slack API calls, DynamoDB operations, and other external service integrations.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class FlagReviewApiClient:
    """Handles external API interactions and database operations.

    Provides methods for Slack API calls, DynamoDB operations, and HTTP
    client management used in the flag review workflow.
    """

    def __init__(self, dependency_container):
        """Initialize the API client with dependency injection container.

        Args:
            dependency_container: TypedDI container for dependency access.
        """
        self.container = dependency_container

    @property
    def secrets_manager(self):
        """Get secrets manager from dependency container."""
        return self.container.get_secrets_manager()

    @property
    def db_store(self):
        """Get database store from dependency container."""
        return self.container.get_db_store()

    @property
    def posting_handler(self):
        """Get posting handler from dependency container."""
        return self.container.get_posting_handler()

    async def display_modal_via_api(
        self, trigger_id: str, modal_view: Dict[str, Any], modal_type: str
    ) -> bool:
        """Display modal using direct Slack API call.

        Args:
            trigger_id: The Slack trigger ID for opening the modal.
            modal_view: The modal view structure to display.
            modal_type: The type of modal being displayed (for logging).

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        try:
            slack_api_token = await self.secrets_manager.get_slack_api_token_async()

            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            return await self._make_modal_api_request(url, headers, api_payload, modal_type)

        except Exception as e:
            logger.error(f"Error displaying {modal_type} modal: {e}")
            return False

    async def _make_modal_api_request(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        modal_type: str,
    ) -> bool:
        """Make the actual API request to display modal.

        Args:
            url: The Slack API URL to make the request to.
            headers: HTTP headers for the request.
            payload: The request payload containing trigger_id and view.
            modal_type: The type of modal being displayed (for logging).

        Returns:
            True if API request succeeded, False otherwise.
        """
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                logger.info(
                    f"Received response status: {response.status} from Slack API views.open"
                )
                response_data = await response.json()

                if not response_data.get("ok"):
                    error_msg = response_data.get("error", "unknown")
                    logger.error(f"Failed to open {modal_type} modal: {error_msg}")
                    logger.error(f"Full response: {response_data}")
                    logger.error(f"Trigger ID used: {payload.get('trigger_id')}")
                    return False
                else:
                    logger.info(f"{modal_type.capitalize()} modal opened successfully")
                    return True

    async def get_conversation_history(
        self, channel_id: str, message_ts: str, limit: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Get conversation history from Slack API.

        Args:
            channel_id: The channel ID to get history from.
            message_ts: The message timestamp to use as reference.
            limit: Number of messages to retrieve.

        Returns:
            Dictionary containing conversation history or None if failed.
        """
        try:
            result = await self.posting_handler.api_call(
                endpoint="conversations.history",
                payload={
                    "channel": channel_id,
                    "latest": message_ts,
                    "limit": limit,
                    "inclusive": True,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return None

    async def store_command_flag(
        self,
        channel_id: str,
        command_execution_id: str,
        user_id: str,
        user_name: str,
        original_text: str,
        command_type: str,
        original_channel: str,
    ) -> bool:
        """Store command flag information in database.

        Args:
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            user_id: The ID of the user who flagged the command.
            user_name: The name of the user who flagged the command.
            original_text: The original command text that was flagged.
            command_type: The type of command that was flagged.
            original_channel: The original channel where button was clicked.

        Returns:
            True if stored successfully, False otherwise.
        """
        try:
            flag_item = {
                "PK": {"S": f"FEEDBACK#{channel_id}#{command_execution_id}"},
                "SK": {"S": f"FLAG#{user_id}"},
                "user_id": {"S": user_id},
                "user_name": {"S": user_name},
                "original_text": {"S": original_text},
                "command_type": {"S": command_type},
                "status": {"S": "pending"},
                "timestamp": {"S": datetime.now(timezone.utc).isoformat()},
                "original_channel": {"S": original_channel},
                "ttl": {"N": str(int((datetime.now(timezone.utc).timestamp()) + 2592000))},
            }

            await self.db_store.client.put_item(table_name=self.db_store.table_name, item=flag_item)
            return True
        except Exception as e:
            logger.error(f"Error storing command flag: {e}")
            return False

    async def get_command_output(self, command_execution_id: str) -> Optional[str]:
        """Retrieve command output from database.

        Args:
            command_execution_id: The unique command execution ID.

        Returns:
            Command output string if found, None otherwise.
        """
        try:
            timestamp, uuid_part = command_execution_id.split("_")

            result = await self.db_store.client.get_item(
                table_name=self.db_store.table_name,
                key={
                    "PK": {"S": f"COMMAND_OUTPUT#{timestamp}"},
                    "SK": {"S": f"OUTPUT#{uuid_part}"},
                },
            )

            if "Item" in result:
                return result["Item"]["output"]["S"]
            return None
        except Exception as e:
            logger.error(f"Error getting command output: {e}")
            return None

    async def get_feedback_data(self, channel_id: str, message_ts: str) -> Optional[Dict[str, Any]]:
        """Retrieve feedback data for a specific message.

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

    async def update_feedback_status(
        self, channel_id: str, message_ts: str, user_id: str, new_status: str
    ) -> bool:
        """Update feedback status in database.

        Args:
            channel_id: The channel ID where the message was posted.
            message_ts: The timestamp of the message.
            user_id: The user ID who provided the feedback.
            new_status: The new status to set.

        Returns:
            True if updated successfully, False otherwise.
        """
        try:
            await self.db_store.client.update_item(
                table_name=self.db_store.table_name,
                key={
                    "PK": {"S": f"FEEDBACK#{channel_id}#{message_ts}"},
                    "SK": {"S": f"FLAG#{user_id}"},
                },
                update_expression="SET #status = :status, updated_timestamp = :updated_ts",
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={
                    ":status": {"S": new_status},
                    ":updated_ts": {"S": datetime.now(timezone.utc).isoformat()},
                },
            )
            return True
        except Exception as e:
            logger.error(f"Error updating feedback status: {e}")
            return False

    async def store_summary_review(
        self,
        channel_id: str,
        message_ts: str,
        user_id: str,
        user_name: str,
        original_text: str,
        review_reason: str,
        review_type: str = "summary",
    ) -> bool:
        """Store summary review information in database.

        Args:
            channel_id: The channel ID where the message was posted.
            message_ts: The timestamp of the message.
            user_id: The ID of the user who requested the review.
            user_name: The name of the user who requested the review.
            original_text: The original message text.
            review_reason: The reason for requesting the review.
            review_type: The type of review (default: "summary").

        Returns:
            True if stored successfully, False otherwise.
        """
        try:
            flag_item = {
                "PK": {"S": f"FEEDBACK#{channel_id}#{message_ts}"},
                "SK": {"S": f"FLAG#{user_id}"},
                "user_id": {"S": user_id},
                "user_name": {"S": user_name},
                "original_text": {"S": original_text},
                "review_reason": {"S": review_reason},
                "review_type": {"S": review_type},
                "status": {"S": "pending"},
                "timestamp": {"S": datetime.now(timezone.utc).isoformat()},
                "ttl": {"N": str(int((datetime.now(timezone.utc).timestamp()) + 2592000))},
            }

            await self.db_store.client.put_item(table_name=self.db_store.table_name, item=flag_item)
            return True
        except Exception as e:
            logger.error(f"Error storing summary review: {e}")
            return False

    async def update_command_feedback_status(
        self, channel_id: str, command_execution_id: str, user_id: str, new_status: str
    ) -> bool:
        """Update command feedback status in database.

        Args:
            channel_id: The channel ID where the command was executed.
            command_execution_id: The unique command execution ID.
            user_id: The user ID who provided the feedback.
            new_status: The new status to set.

        Returns:
            True if updated successfully, False otherwise.
        """
        try:
            await self.db_store.client.update_item(
                table_name=self.db_store.table_name,
                key={
                    "PK": {"S": f"FEEDBACK#{channel_id}#{command_execution_id}"},
                    "SK": {"S": f"FLAG#{user_id}"},
                },
                update_expression="SET #status = :status, updated_timestamp = :updated_ts",
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={
                    ":status": {"S": new_status},
                    ":updated_ts": {"S": datetime.now(timezone.utc).isoformat()},
                },
            )
            return True
        except Exception as e:
            logger.error(f"Error updating command feedback status: {e}")
            return False
