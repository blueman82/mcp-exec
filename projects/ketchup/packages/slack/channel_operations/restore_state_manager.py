"""
restore_state_manager.py

Manages the temporary state tracking for channels that were originally archived
and have been temporarily restored by the bot, using DynamoDB for persistence.
"""

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore  # Import the facade

logger = setup_logger(__name__)


class RestoreStateManager:
    """
    Manages the state of channels temporarily unarchived for command execution.
    Tracks which channels were originally archived by the bot to ensure they
    are re-archived, using DynamoDB via DynamoDBStore.
    """

    def __init__(self, dynamodb_store: DynamoDBStore) -> None:
        """
        Initializes the state manager with a DynamoDBStore instance.

        Args:
            dynamodb_store: The DynamoDBStore instance providing access to restore_ops.
        """
        self._db_store = dynamodb_store
        # Access restore_ops through the injected facade
        self._restore_ops = self._db_store.restore_ops
        logger.info("RestoreStateManager initialized with DynamoDBStore.")

    async def store_state(self, channel_id: str) -> bool:
        """
        Marks a channel as having been originally archived by the bot using DynamoDB.

        Args:
            channel_id: The ID of the channel to mark.

        Returns:
            True if the state was successfully stored in DynamoDB, False otherwise.
        """
        logger.info("Attempting to store restore state for channel %s in DynamoDB", channel_id)
        success = await self._restore_ops.set_restore_state(channel_id)
        if success:
            logger.info("Successfully stored restore state for channel %s", channel_id)
        else:
            logger.error("Failed to store restore state for channel %s", channel_id)
        return success

    async def is_rearchive_needed(self, channel_id: str) -> bool:
        """
        Checks DynamoDB if a channel was marked as originally archived by the bot
        and needs re-archiving.

        Args:
            channel_id: The ID of the channel to check.

        Returns:
            True if the channel was marked as originally archived by the bot,
            False otherwise or on error.
        """
        logger.info("Checking DynamoDB for restore state for channel %s", channel_id)
        needed = await self._restore_ops.check_restore_state(channel_id)
        if not needed:
            logger.info(
                "Channel %s restore state not found in DynamoDB or bot did not archive it.",
                channel_id,
            )
        else:
            logger.info(
                "Channel %s restore state FOUND in DynamoDB. Bot needs to re-archive.",
                channel_id,
            )
        return needed

    async def cleanup_state(self, channel_id: str) -> bool:
        """
        Removes the tracking state for a specific channel from DynamoDB.

        Args:
            channel_id: The ID of the channel whose state should be cleaned up.

        Returns:
            True if cleanup was successful or state didn't exist, False on error.
        """
        logger.info(
            "Attempting to clean up restore state for channel %s from DynamoDB",
            channel_id,
        )
        success = await self._restore_ops.clear_restore_state(channel_id)
        if success:
            logger.info("Successfully cleaned up restore state for channel %s", channel_id)
        else:
            logger.error("Failed to clean up restore state for channel %s", channel_id)
        return success
