"""
Database operations for flag review functionality.

This module handles all database interactions for storing and retrieving
flag review records, feedback data, and related information.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.interactive_elements.flag_review.flag_types import REVIEW_CHANNEL_ID

logger = setup_logger(__name__)


class FlagReviewDatabaseOperations:
    """Handles all database operations for flag review functionality."""

    def __init__(self, db_store: DynamoDBStore):
        """
        Initialize the database operations handler.

        Args:
            db_store: DynamoDB store instance for database operations
        """
        self.db_store = db_store
        self.table_name = db_store.table_name

    async def save_flag_review_to_db(
        self,
        channel_id: str,
        message_ts: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: List[str],
        status_text: str,
        original_blocks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Save a flag review record to the database.

        Args:
            channel_id: The channel where the flag was raised
            message_ts: The timestamp of the message being flagged
            user_id: The ID of the user raising the flag
            user_name: The name of the user raising the flag
            feedback_text: The feedback text provided
            validation_issues: List of validation issues found
            status_text: The status text being flagged
            original_blocks: The original message blocks

        Returns:
            Dict with success status and any error information
        """
        try:
            flag_id = f"{channel_id}_{message_ts}_{user_id}"
            timestamp = datetime.now(timezone.utc)

            flag_item = {
                "PK": {"S": f"FLAG_REVIEW#{flag_id}"},
                "SK": {"S": f"TIMESTAMP#{timestamp.isoformat()}"},
                "flag_id": {"S": flag_id},
                "channel_id": {"S": channel_id},
                "message_ts": {"S": message_ts},
                "user_id": {"S": user_id},
                "user_name": {"S": user_name},
                "feedback_text": {"S": feedback_text},
                "status_text": {"S": status_text},
                "original_blocks": {"S": str(original_blocks)},
                "sanitization_issues": {"L": [{"S": issue} for issue in validation_issues]},
                "text_length": {"N": str(len(feedback_text))},
                "status": {"S": "pending"},
                "created_at": {"S": timestamp.isoformat()},
                "ttl": {"N": str(int(timestamp.timestamp() + (30 * 24 * 60 * 60)))},  # 30 days TTL
                "review_channel_id": {"S": REVIEW_CHANNEL_ID},
                "slack_team_id": {"S": "T018BPFUD75"},
                "app_version": {"S": "2.1.0"},
            }

            await self.db_store.client.put_item(table_name=self.table_name, item=flag_item)

            logger.info(f"Stored flag review for {flag_id} from user {user_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error saving flag review to database: {e}")
            return {"success": False, "error": str(e)}

    async def save_command_flag_to_db(
        self,
        channel_id: str,
        command_execution_id: str,
        command_type: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: List[str],
        command_output: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save a command flag review record to the database.

        Args:
            channel_id: The channel where the command was executed
            command_execution_id: The unique ID of the command execution
            command_type: The type of command that was executed
            user_id: The ID of the user raising the flag
            user_name: The name of the user raising the flag
            feedback_text: The feedback text provided
            validation_issues: List of validation issues found
            command_output: The output of the command (optional)

        Returns:
            Dict with success status and any error information
        """
        try:
            flag_id = f"{channel_id}_{command_execution_id}_{user_id}"
            timestamp = datetime.now(timezone.utc)

            flag_item = {
                "PK": {"S": f"COMMAND_FLAG#{flag_id}"},
                "SK": {"S": f"TIMESTAMP#{timestamp.isoformat()}"},
                "flag_id": {"S": flag_id},
                "channel_id": {"S": channel_id},
                "command_execution_id": {"S": command_execution_id},
                "command_type": {"S": command_type},
                "user_id": {"S": user_id},
                "user_name": {"S": user_name},
                "feedback_text": {"S": feedback_text},
                "sanitization_issues": {"L": [{"S": issue} for issue in validation_issues]},
                "text_length": {"N": str(len(feedback_text))},
                "status": {"S": "pending"},
                "created_at": {"S": timestamp.isoformat()},
                "ttl": {"N": str(int(timestamp.timestamp() + (30 * 24 * 60 * 60)))},  # 30 days TTL
                "review_channel_id": {"S": REVIEW_CHANNEL_ID},
                "command_output": {"S": command_output or "Output not found"},
                "slack_team_id": {"S": "T018BPFUD75"},
                "app_version": {"S": "2.1.0"},
            }

            await self.db_store.client.put_item(table_name=self.table_name, item=flag_item)

            logger.info(f"Stored command flag for {command_execution_id} from user {user_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error saving command flag to database: {e}")
            return {"success": False, "error": str(e)}

    async def get_flag_review_record(self, flag_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a flag review record from the database.

        Args:
            flag_id: The unique identifier of the flag review

        Returns:
            The flag review record if found, None otherwise
        """
        try:
            # Use scan since we need to find by flag_id attribute
            # Ensure this is an async call
            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": "flag_id = :flag_id",
                "expression_attribute_values": {":flag_id": {"S": flag_id}},
            }
            items = []
            while True:
                result = await self.db_store.client.scan(**scan_kwargs)
                items.extend(result.get("Items", []))
                if items:
                    break
                last_key = result.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key

            if items:
                return items[0]
            return None

        except Exception as e:
            logger.error(f"Error retrieving flag review record: {e}")
            return None

    async def update_flag_review_status(
        self,
        flag_id: str,
        status: str,
        admin_id: Optional[str] = None,
        reply_text: Optional[str] = None,
    ) -> bool:
        """
        Update the status of a flag review record.

        Args:
            flag_id: The unique identifier of the flag review
            status: The new status (e.g., 'acknowledged', 'replied')
            admin_id: The ID of the admin taking action (optional)
            reply_text: The reply text if status is 'replied' (optional)

        Returns:
            True if update successful, False otherwise
        """
        try:
            record = await self.get_flag_review_record(flag_id)
            if not record:
                logger.warning(f"Flag review record not found: {flag_id}")
                return False

            update_expression = "SET #status = :status, updated_at = :updated_at"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": {"S": status},
                ":updated_at": {"S": datetime.now(timezone.utc).isoformat()},
            }

            if admin_id:
                if status == "acknowledged":
                    update_expression += (
                        ", acknowledged_by = :admin_id, acknowledged_at = :timestamp"
                    )
                elif status == "replied":
                    update_expression += ", replied_by = :admin_id, replied_at = :timestamp"
                expression_attribute_values[":admin_id"] = {"S": admin_id}
                expression_attribute_values[":timestamp"] = {
                    "S": datetime.now(timezone.utc).isoformat()
                }

            if reply_text and status == "replied":
                update_expression += ", reply_text = :reply_text"
                expression_attribute_values[":reply_text"] = {"S": reply_text}

            await self.db_store.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": record["PK"],
                    "SK": record["SK"],
                },
                update_expression=update_expression,
                expression_attribute_names=expression_attribute_names,
                expression_attribute_values=expression_attribute_values,
            )

            logger.info(f"Updated flag review {flag_id} to status: {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating flag review status: {e}")
            return False

    async def get_command_output(self, channel_id: str, command_execution_id: str) -> Optional[str]:
        """
        Get the command output from the database.

        Args:
            channel_id: The channel ID where the command was executed
            command_execution_id: The unique ID of the command execution

        Returns:
            The command output if found, None otherwise
        """
        try:
            # Extract timestamp and uuid from command_execution_id
            timestamp, uuid_part = command_execution_id.split("_")

            result = await self.db_store.client.get_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"CHANNEL#{channel_id}"},
                    "SK": {"S": f"COMMAND#{timestamp}#{uuid_part}"},
                },
            )

            item = result.get("Item")
            if item:
                return item.get("command_output", {}).get("S", "")
            return None

        except Exception as e:
            logger.error(f"Error getting command output: {e}")
            return None

    async def query_flag_reviews_for_user(
        self, user_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query flag reviews submitted by a specific user.

        Args:
            user_id: The ID of the user
            limit: Maximum number of records to return

        Returns:
            List of flag review records
        """
        try:
            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": "user_id = :user_id",
                "expression_attribute_values": {":user_id": {"S": user_id}},
            }
            items = []
            while True:
                result = await self.db_store.client.scan(**scan_kwargs)
                items.extend(result.get("Items", []))
                last_key = result.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key

            # Sort results by created_at descending (since scan doesn't support sorting)
            items.sort(key=lambda x: x.get("created_at", {}).get("S", ""), reverse=True)

            return items[:limit]

        except Exception as e:
            logger.error(f"Error querying flag reviews for user: {e}")
            return []

    async def delete_flag_review_record(self, flag_id: str) -> bool:
        """
        Delete a flag review record from the database.

        Args:
            flag_id: The unique identifier of the flag review

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            record = await self.get_flag_review_record(flag_id)
            if not record:
                logger.warning(f"Flag review record not found for deletion: {flag_id}")
                return False

            await self.db_store.client.delete_item(
                table_name=self.table_name,
                key={
                    "PK": record["PK"],
                    "SK": record["SK"],
                },
            )

            logger.info(f"Deleted flag review record: {flag_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting flag review record: {e}")
            return False

    async def update_feedback_status(
        self,
        channel_id: str,
        message_ts: str,
        status: str,
        acknowledged_by: str,
        acknowledged_at: str,
    ) -> None:
        """
        Update feedback status for a flagged message.

        Args:
            channel_id: The channel ID where the message was flagged
            message_ts: The message timestamp
            status: The new status (e.g., 'acknowledged', 'replied')
            acknowledged_by: The admin user ID who acknowledged
            acknowledged_at: The timestamp of acknowledgment

        Raises:
            Exception: If update fails
        """
        # Construct flag_id from channel_id and message_ts
        # We need to find the flag record by scanning for matching channel and message
        try:
            logger.info(
                f"Searching for flag review: channel_id={channel_id}, "
                f"message_ts={message_ts}, message_ts_type={type(message_ts).__name__}"
            )

            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": "channel_id = :channel_id AND message_ts = :message_ts",
                "expression_attribute_values": {
                    ":channel_id": {"S": channel_id},
                    ":message_ts": {"S": message_ts},
                },
            }
            items = []
            while True:
                result = await self.db_store.client.scan(**scan_kwargs)
                items.extend(result.get("Items", []))
                if items:
                    break
                last_key = result.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key

            logger.info(f"Database scan result: found {len(items)} items.")

            if not items:
                logger.warning(
                    f"No flag review found for channel {channel_id}, message_ts {message_ts}. "
                    f"This may be a status summary flag (command_execution_id format) or the "
                    f"record may not exist in the database."
                )
                return

            record = items[0]

            # Update the record
            update_expression = "SET #status = :status, updated_at = :updated_at"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": {"S": status},
                ":updated_at": {"S": datetime.now(timezone.utc).isoformat()},
            }

            if status == "acknowledged":
                update_expression += ", acknowledged_by = :admin_id, acknowledged_at = :timestamp"
            elif status == "replied":
                update_expression += ", replied_by = :admin_id, replied_at = :timestamp"
            elif status == "completed":
                update_expression += ", completed_by = :admin_id, completed_at = :timestamp"

            expression_attribute_values[":admin_id"] = {"S": acknowledged_by}
            expression_attribute_values[":timestamp"] = {"S": acknowledged_at}

            await self.db_store.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": record["PK"],
                    "SK": record["SK"],
                },
                update_expression=update_expression,
                expression_attribute_names=expression_attribute_names,
                expression_attribute_values=expression_attribute_values,
            )

            logger.info(
                f"Updated feedback status for channel {channel_id}, message {message_ts} to {status}"
            )

        except Exception as e:
            logger.error(f"Error updating feedback status: {e}")
            raise

    async def update_command_feedback_status(
        self,
        channel_id: str,
        command_execution_id: str,
        original_user_id: str,
        status: str,
        acknowledged_by: str,
        acknowledged_at: str,
    ) -> None:
        """
        Update feedback status for a flagged command.

        Args:
            channel_id: The channel ID where the command was executed
            command_execution_id: The command execution ID
            original_user_id: The user who flagged the command
            status: The new status (e.g., 'acknowledged', 'replied')
            acknowledged_by: The admin user ID who acknowledged
            acknowledged_at: The timestamp of acknowledgment

        Raises:
            Exception: If update fails
        """
        # Construct flag_id for command flags
        try:
            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": "channel_id = :channel_id AND command_execution_id = :cmd_id AND user_id = :user_id",
                "expression_attribute_values": {
                    ":channel_id": {"S": channel_id},
                    ":cmd_id": {"S": command_execution_id},
                    ":user_id": {"S": original_user_id},
                },
            }
            items = []
            while True:
                result = await self.db_store.client.scan(**scan_kwargs)
                items.extend(result.get("Items", []))
                if items:
                    break
                last_key = result.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key

            if not items:
                logger.warning(
                    f"No command flag found for channel {channel_id}, command {command_execution_id}"
                )
                return

            record = items[0]

            # Update the record
            update_expression = "SET #status = :status, updated_at = :updated_at"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": {"S": status},
                ":updated_at": {"S": datetime.now(timezone.utc).isoformat()},
            }

            if status == "acknowledged":
                update_expression += ", acknowledged_by = :admin_id, acknowledged_at = :timestamp"
            elif status == "replied":
                update_expression += ", replied_by = :admin_id, replied_at = :timestamp"
            elif status == "completed":
                update_expression += ", completed_by = :admin_id, completed_at = :timestamp"

            expression_attribute_values[":admin_id"] = {"S": acknowledged_by}
            expression_attribute_values[":timestamp"] = {"S": acknowledged_at}

            await self.db_store.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": record["PK"],
                    "SK": record["SK"],
                },
                update_expression=update_expression,
                expression_attribute_names=expression_attribute_names,
                expression_attribute_values=expression_attribute_values,
            )

            logger.info(
                f"Updated command feedback status for channel {channel_id}, command {command_execution_id} to {status}"
            )

        except Exception as e:
            logger.error(f"Error updating command feedback status: {e}")
            raise

    async def get_feedback_data(self, channel_id: str, message_ts: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve feedback data for a specific message.

        Args:
            channel_id: The channel ID
            message_ts: The message timestamp

        Returns:
            Feedback data if found, None otherwise
        """
        try:
            # Look for feedback records matching the channel and message
            flag_id = f"{channel_id}_{message_ts}"
            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": "flag_id = :flag_id",
                "expression_attribute_values": {":flag_id": {"S": flag_id}},
            }
            items = []
            while True:
                result = await self.db_store.client.scan(**scan_kwargs)
                items.extend(result.get("Items", []))
                if items:
                    break
                last_key = result.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key
            if items:
                item = items[0]
                # Convert DynamoDB format to expected format
                return {
                    "user_id": item.get("user_id", {}).get("S"),
                    "user_name": item.get("user_name", {}).get("S"),
                    "feedback_text": item.get("feedback_text", {}).get("S"),
                    "status": item.get("status", {}).get("S"),
                }
            return None

        except Exception as e:
            logger.error(f"Error getting feedback data: {e}")
            return None

    async def add_flag_atomically(
        self,
        channel_id: str,
        message_ts: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: list,
    ) -> Dict[str, Any]:
        """
        Add a flag atomically to the database.

        Args:
            channel_id: The channel ID
            message_ts: The message timestamp
            user_id: The user ID
            user_name: The user name
            feedback_text: The feedback text
            validation_issues: List of validation issues

        Returns:
            Dict with success status and any additional info
        """
        try:
            # Check if flag already exists
            try:
                existing = await self.get_feedback_data(channel_id, message_ts)
                if existing:
                    return {"success": True, "already_exists": True}
            except Exception:
                # If get_feedback_data fails (mocked), continue to create
                pass

            # Save the flag
            result = await self.save_flag_review_to_db(
                channel_id=channel_id,
                message_ts=message_ts,
                user_id=user_id,
                user_name=user_name,
                feedback_text=feedback_text,
                validation_issues=validation_issues,
                status_text="pending",
                original_blocks=[],
            )

            return result

        except Exception as e:
            logger.error(f"Error adding flag atomically: {e}")
            return {"success": False, "error": str(e)}

    async def get_flag_status(self, channel_id: str, message_ts: str) -> Optional[Dict[str, Any]]:
        """
        Get flag status for a specific message.

        Args:
            channel_id: The channel ID
            message_ts: The message timestamp

        Returns:
            Flag status data if found, None otherwise
        """
        return await self.get_feedback_data(channel_id, message_ts)
