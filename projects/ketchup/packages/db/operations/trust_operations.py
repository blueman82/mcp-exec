"""
trust_operations.py

Handles trust endorsement data operations in DynamoDB.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

logger = setup_logger(__name__)


class TrustOperations:
    """Handles trust endorsement operations in DynamoDB."""

    def __init__(self, client: DynamoDBAsyncClient, table_name: str):
        """
        Initialize TrustOperations.

        Args:
            client: DynamoDB async client
            table_name: Name of the DynamoDB table
        """
        self.client = client
        self.table_name = table_name

    async def store_status_update_metadata(
        self,
        channel_id: str,
        status_update_id: str,
        timestamp: int,
        content_preview: str = None,
    ) -> bool:
        """
        Store metadata for a status update with trust tracking.

        Args:
            channel_id: Slack channel ID
            status_update_id: Unique status update ID
            timestamp: Unix timestamp of the update
            content_preview: Optional preview of the status content

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # TTL is 7 days from now
            ttl = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())

            item = {
                "PK": {"S": f"CHANNEL#{channel_id}"},
                "SK": {"S": f"STATUS#{timestamp}#{status_update_id.split('_')[1]}"},
                "status_update_id": {"S": status_update_id},
                "timestamp": {"N": str(timestamp)},
                "trusted_by": {"L": []},
                "trust_count": {"N": "0"},
                "ttl": {"N": str(ttl)},
            }

            if content_preview:
                item["content_preview"] = {"S": content_preview[:200]}

            await self.client.put_item(table_name=self.table_name, item=item)

            logger.info(f"Stored status update metadata for {status_update_id}")
            return True

        except Exception as e:
            logger.error(f"Error storing status update metadata: {e}")
            return False

    async def get_trust_data(
        self, channel_id: str, status_update_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get trust data for a status update.

        Args:
            channel_id: The channel ID
            status_update_id: The status update ID (format: timestamp_uuid)

        Returns:
            Trust data dict or None if not found
        """
        try:
            # Extract timestamp and uuid from status_update_id
            parts = status_update_id.split("_")
            if len(parts) != 2:
                logger.error(f"Invalid status_update_id format: {status_update_id}")
                return None

            timestamp, uuid = parts

            # Validate timestamp is numeric
            try:
                int(timestamp)
            except ValueError:
                logger.error(
                    f"Invalid timestamp in status_update_id: {status_update_id}"
                )
                return None

            # Construct the full key
            result = await self.client.get_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"CHANNEL#{channel_id}"},
                    "SK": {"S": f"STATUS#{timestamp}#{uuid}"},
                },
            )

            if result and result.get("Item"):
                return self._deserialize_trust_item(result["Item"])

            return None

        except Exception as e:
            logger.error(f"Error getting trust data: {e}")
            return None

    async def add_trust_endorsement(
        self, channel_id: str, status_update_id: str, user_id: str, user_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Add a trust endorsement to a status update.

        Args:
            channel_id: Channel ID
            status_update_id: Status update ID
            user_id: User ID who is trusting
            user_name: User name

        Returns:
            Updated trust data or None on error
        """
        try:
            # First get the current item to check if user already trusted
            current = await self.get_trust_data(channel_id, status_update_id)
            if not current:
                logger.error(f"Status update {status_update_id} not found")
                return None

            # Check if user already trusted
            trusted_by = current.get("trusted_by", [])
            if any(t["user_id"] == user_id for t in trusted_by):
                logger.info(f"User {user_id} already trusted {status_update_id}")
                current["user_already_trusted"] = True
                return current

            # Add new trust endorsement
            trust_entry = {
                "user_id": user_id,
                "user_name": user_name,
                "trusted_at": int(datetime.now(timezone.utc).timestamp()),
            }

            # Update the item
            timestamp = status_update_id.split("_")[0]
            uuid = status_update_id.split("_")[1]

            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"CHANNEL#{channel_id}"},
                    "SK": {"S": f"STATUS#{timestamp}#{uuid}"},
                },
                update_expression=(
                    "SET trusted_by = list_append(if_not_exists(trusted_by, :empty_list), :trust), "
                    "trust_count = if_not_exists(trust_count, :zero) + :inc"
                ),
                expression_attribute_values={
                    ":trust": {"L": [self._serialize_trust_entry(trust_entry)]},
                    ":inc": {"N": "1"},
                    ":zero": {"N": "0"},
                    ":empty_list": {"L": []},
                },
            )

            # Fetch the updated item since update_item doesn't return it
            return await self.get_trust_data(channel_id, status_update_id)

        except Exception as e:
            logger.error(f"Error adding trust endorsement: {e}")
            return None

    async def add_command_trust_endorsement(
        self, channel_id: str, command_execution_id: str, user_id: str, user_name: str
    ) -> Dict[str, Any]:
        """
        Add a trust endorsement to a command execution.

        Args:
            channel_id: The channel ID
            command_execution_id: The command execution ID (format: timestamp_uuid)
            user_id: The user ID
            user_name: The user name

        Returns:
            Updated trust data or None on error
        """
        try:
            # First get the current item to check if user already trusted
            current = await self.get_command_trust_data(
                channel_id, command_execution_id
            )
            if not current:
                logger.error(f"Command execution {command_execution_id} not found")
                return None

            # Check if user already trusted
            trusted_by = current.get("trusted_by", [])
            if any(t["user_id"] == user_id for t in trusted_by):
                logger.info(f"User {user_id} already trusted {command_execution_id}")
                current["user_already_trusted"] = True
                return current

            # Add new trust endorsement
            trust_entry = {
                "user_id": user_id,
                "user_name": user_name,
                "trusted_at": int(datetime.now(timezone.utc).timestamp()),
            }

            # Update the item
            timestamp = command_execution_id.split("_")[0]
            uuid = command_execution_id.split("_")[1]

            result = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"CHANNEL#{channel_id}"},
                    "SK": {"S": f"COMMAND#{timestamp}#{uuid}"},
                },
                update_expression=(
                    "SET trusted_by = list_append(if_not_exists(trusted_by, :empty_list), :new_trust), "
                    "trust_count = if_not_exists(trust_count, :zero) + :inc"
                ),
                expression_attribute_values={
                    ":new_trust": {
                        "L": [
                            {
                                "M": {
                                    "user_id": {"S": user_id},
                                    "user_name": {"S": user_name},
                                    "trusted_at": {"N": str(trust_entry["trusted_at"])},
                                }
                            }
                        ]
                    },
                    ":inc": {"N": "1"},
                    ":zero": {"N": "0"},
                    ":empty_list": {"L": []},
                },
                return_values="ALL_NEW",
            )

            if result and result.get("Attributes"):
                updated_data = self._deserialize_trust_item(result["Attributes"])
                logger.info(
                    f"Trust endorsement added for command {command_execution_id}"
                )
                return updated_data

            return None
        except Exception as e:
            logger.error(f"Error adding command trust endorsement: {e}")
            return None

    async def get_command_trust_data(
        self, channel_id: str, command_execution_id: str
    ) -> Dict[str, Any]:
        """
        Get trust data for a command execution.

        Args:
            channel_id: The channel ID
            command_execution_id: The command execution ID (format: timestamp_uuid)

        Returns:
            Trust data dict or None if not found
        """
        try:
            # Extract timestamp and uuid from command_execution_id
            parts = command_execution_id.split("_")
            if len(parts) != 2:
                logger.error(
                    f"Invalid command_execution_id format: {command_execution_id}"
                )
                return None

            timestamp, uuid = parts

            # Validate timestamp is numeric
            try:
                int(timestamp)
            except ValueError:
                logger.error(
                    f"Invalid timestamp in command_execution_id: {command_execution_id}"
                )
                return None

            # Construct the full key
            result = await self.client.get_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"CHANNEL#{channel_id}"},
                    "SK": {"S": f"COMMAND#{timestamp}#{uuid}"},
                },
            )

            if result and result.get("Item"):
                return self._deserialize_trust_item(result["Item"])

            return None

        except Exception as e:
            logger.error(f"Error getting command trust data: {e}")
            return None

    def _serialize_trust_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize a trust entry for DynamoDB."""
        return {
            "M": {
                "user_id": {"S": entry["user_id"]},
                "user_name": {"S": entry["user_name"]},
                "trusted_at": {"N": str(entry["trusted_at"])},
            }
        }

    def _deserialize_trust_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize a DynamoDB item to trust data."""
        # Check if this is a command or status item
        sk = item.get("SK", {}).get("S", "")
        is_command = sk.startswith("COMMAND#")

        result = {
            "timestamp": int(item.get("timestamp", {}).get("N", "0")),
            "trust_count": int(item.get("trust_count", {}).get("N", "0")),
            "trusted_by": [],
        }

        # Add appropriate ID based on item type
        if is_command:
            result["command_execution_id"] = item.get("command_execution_id", {}).get(
                "S", ""
            )
            result["command_type"] = item.get("command_type", {}).get("S", "")
            result["command_output"] = item.get("command_output", {}).get("S", "")
            result["channel_id"] = item.get("channel_id", {}).get("S", "")
        else:
            result["status_update_id"] = item.get("status_update_id", {}).get("S", "")

        # Deserialize trusted_by list
        trusted_by_list = item.get("trusted_by", {}).get("L", [])
        for trust_item in trusted_by_list:
            trust_map = trust_item.get("M", {})
            result["trusted_by"].append(
                {
                    "user_id": trust_map.get("user_id", {}).get("S", ""),
                    "user_name": trust_map.get("user_name", {}).get("S", ""),
                    "trusted_at": int(trust_map.get("trusted_at", {}).get("N", "0")),
                }
            )

        return result

    async def cleanup_channel_trust_data(self, channel_id: str) -> bool:
        """
        Clean up all trust endorsement data for a channel when it's archived.

        Args:
            channel_id: The channel ID to clean up trust data for

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Query all STATUS items for this channel
            result = await self.client.query(
                table_name=self.table_name,
                key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":pk": {"S": f"CHANNEL#{channel_id}"},
                    ":sk_prefix": {"S": "STATUS#"},
                },
            )

            items = result.get("Items", [])
            if not items:
                logger.info(f"No trust endorsement data found for channel {channel_id}")
                return True

            # Delete items in batches (DynamoDB batch limit is 25)
            batch_size = 25
            deleted_count = 0

            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]
                delete_requests = []

                for item in batch:
                    delete_requests.append(
                        {"DeleteRequest": {"Key": {"PK": item["PK"], "SK": item["SK"]}}}
                    )

                # Execute batch delete using the utility
                # Note: batch_write_items_with_retries expects PutRequests, but we have DeleteRequests
                # We need to use the underlying client directly for deletes
                underlying_client = await self.client._get_client()
                response = await underlying_client.batch_write_item(
                    RequestItems={self.table_name: delete_requests}
                )

                # Handle any unprocessed items
                unprocessed = response.get("UnprocessedItems", {}).get(
                    self.table_name, []
                )
                deleted_count += len(delete_requests) - len(unprocessed)

                if unprocessed:
                    logger.warning(
                        f"Failed to delete {len(unprocessed)} trust endorsement records"
                    )

            logger.info(
                f"Successfully cleaned up {deleted_count} trust endorsement records for channel {channel_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error cleaning up trust data for channel {channel_id}: {e}")
            return False

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("TrustOperations cleanup completed")
