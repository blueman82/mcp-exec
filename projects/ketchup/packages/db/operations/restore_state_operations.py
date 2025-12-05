"""
restore_state_operations.py

Handles DynamoDB operations related to tracking temporary channel restore state.
"""

import time

from botocore.exceptions import ClientError

from packages.core.constants import DYNAMODB_SK_RESTORE_STATE, RESTORE_STATE_TTL_SECONDS
from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

logger = setup_logger(__name__)


class RestoreStateOperations:
    """
    Manages DynamoDB operations for tracking channels temporarily unarchived by the bot.
    Uses a specific Sort Key (SK="RESTORE_STATE") within the main channel table.

    TL;DR: Persistently tracks channels temporarily unarchived by the bot using
           DynamoDB items (PK=CHANNEL#id, SK=RESTORE_STATE) to ensure correct
           re-archiving logic, avoiding interference with manually unarchived channels.
           TTL manages item cleanup.
    """

    def __init__(self, client: DynamoDBAsyncClient, table_name: str):
        """
        Initialize RestoreStateOperations.

        Args:
            client: The DynamoDBAsyncClient instance.
            table_name: The name of the DynamoDB table.
        """
        self._client = client
        self._table_name = table_name
        self._sk = DYNAMODB_SK_RESTORE_STATE
        logger.info(
            "RestoreStateOperations initialized for table %s with SK %s",
            self._table_name,
            self._sk,
        )

    def _get_key(self, channel_id: str) -> dict:
        """Helper function to create the DynamoDB key."""
        return {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": self._sk}}

    async def set_restore_state(self, channel_id: str) -> bool:
        """
        Mark a channel as temporarily unarchived by the bot in DynamoDB.

        Creates an item with PK="CHANNEL#<channel_id>" and SK="RESTORE_STATE",
        including a TTL attribute (`temp_unarchive_expiry`).

        Args:
            channel_id: The ID of the channel to mark.

        Returns:
            True if successful, False otherwise.
        """
        key = self._get_key(channel_id)
        # Calculate expiry timestamp
        current_time = int(time.time())
        expiry_ts = current_time + RESTORE_STATE_TTL_SECONDS

        item_to_put = {
            **key,
            "tracked": {"BOOL": True},  # Keep existing flag if needed
            "temp_unarchive_expiry": {"N": str(expiry_ts)},  # Add TTL attribute
        }

        logger.info(
            "Setting restore state for channel %s with expiry %s, item: %s",
            channel_id,
            expiry_ts,
            item_to_put,
        )
        try:
            await self._client.put_item(table_name=self._table_name, item=item_to_put)
            logger.info(
                "Successfully set restore state for channel %s with expiry %s.",
                channel_id,
                expiry_ts,
            )
            return True
        except ClientError as e:
            logger.error(
                "Failed to set restore state for channel %s: %s",
                channel_id,
                e.response["Error"]["Message"],
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error setting restore state for channel %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return False

    async def check_restore_state(self, channel_id: str) -> bool:
        """
        Check if a channel is marked as temporarily unarchived by the bot in DynamoDB.

        Uses ConsistentRead=True to avoid race condition where member_joined event
        fires immediately after unarchive but before eventual consistency propagates.

        Args:
            channel_id: The ID of the channel to check.

        Returns:
            True if the restore state item exists, False otherwise.
        """
        key = self._get_key(channel_id)
        logger.info("Checking restore state for channel %s", channel_id)
        try:
            response = await self._client.get_item(
                table_name=self._table_name, key=key, consistent_read=True
            )
            item_exists = "Item" in response
            logger.info("Restore state check for channel %s: %s", channel_id, item_exists)
            return item_exists
        except ClientError as e:
            logger.error(
                "Failed to check restore state for channel %s: %s",
                channel_id,
                e.response["Error"]["Message"],
                exc_info=True,
            )
            return False  # Assume state doesn't exist on error
        except Exception as e:
            logger.error(
                "Unexpected error checking restore state for channel %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return False  # Assume state doesn't exist on error

    async def check_if_temporary_unarchive(self, channel_id: str) -> bool:
        """
        Check specifically for the presence of the temp_unarchive_expiry attribute,
        which indicates a temporary unarchive state.

        Uses ConsistentRead=True to avoid race condition.

        Args:
            channel_id: The ID of the channel to check.

        Returns:
            True if the restore state item exists AND has the temp_unarchive_expiry attribute,
            False otherwise.
        """
        key = self._get_key(channel_id)
        logger.info("Checking for temporary unarchive attribute for channel %s", channel_id)
        try:
            response = await self._client.get_item(
                table_name=self._table_name, key=key, consistent_read=True
            )
            item = response.get("Item")
            if item and "temp_unarchive_expiry" in item:
                logger.info("Temporary unarchive attribute found for channel %s.", channel_id)
                return True
            else:
                logger.info(
                    "Temporary unarchive attribute NOT found for channel %s (Item: %s).",
                    channel_id,
                    item,
                )
                return False
        except ClientError as e:
            logger.error(
                "Failed to check temporary unarchive attribute for channel %s: %s",
                channel_id,
                e.response["Error"]["Message"],
                exc_info=True,
            )
            return False  # Assume not temporary on error
        except Exception as e:
            logger.error(
                "Unexpected error checking temporary unarchive attribute for channel %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return False  # Assume not temporary on error

    async def clear_restore_state(self, channel_id: str) -> bool:
        """
        Remove the temporary restore state marker for a channel from DynamoDB.

        Args:
            channel_id: The ID of the channel whose state should be cleared.

        Returns:
            True if successful or item didn't exist, False on error.
        """
        key = self._get_key(channel_id)
        logger.info("Clearing restore state for channel %s", channel_id)
        try:
            await self._client.delete_item(
                table_name=self._table_name, key=key
            )  # delete_item doesn't error if item not found
            logger.info("Successfully cleared restore state for channel %s.", channel_id)
            return True
        except ClientError as e:
            logger.error(
                "Failed to clear restore state for channel %s: %s",
                channel_id,
                e.response["Error"]["Message"],
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error clearing restore state for channel %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return False
