"""
archive_operations.py

This module contains operations for archived channel management in DynamoDB.
"""

from typing import Optional

from packages.core.logging import setup_logger
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)


class ArchiveOperations(BaseOperations):
    """Operations for archived channel management in DynamoDB."""

    async def update_channel_archived_status(
        self, channel_id: str, archived: bool, archived_at: Optional[int] = None
    ) -> None:
        """
        Update a channel's archived status in DynamoDB.

        Args:
            channel_id: The Slack channel ID
            archived: Whether the channel is archived
            archived_at: Optional timestamp when the channel was archived
        """
        logger.info(
            "Updating archived status for channel %s: archived=%s, archived_at=%s",
            channel_id,
            archived,
            archived_at,
        )

        try:
            key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}

            if archived:
                # Handle archiving case
                if archived_at is not None:
                    # First get the existing item to check for archived_at
                    get_item_response = await self.client.get_item(
                        key=key,
                        table_name=self.table_name,
                    )

                    # Check if item exists and has a non-zero archived_at value
                    existing_item = get_item_response.get("Item", {})
                    existing_archived_at = existing_item.get("archived_at", {}).get(
                        "N", "0"
                    )

                    # Only use the new timestamp if there's no existing non-zero value
                    if existing_archived_at and existing_archived_at != "0":
                        logger.info(
                            "Preserving existing archived_at timestamp: %s",
                            existing_archived_at,
                        )
                        update_expression = (
                            "SET archived = :archived, archived_at = :archived_at"
                        )
                        expression_values = {
                            ":archived": {"BOOL": archived},
                            ":archived_at": {"N": existing_archived_at},
                        }
                    else:
                        # Set both archived status and timestamp with new value
                        update_expression = (
                            "SET archived = :archived, archived_at = :archived_at"
                        )
                        expression_values = {
                            ":archived": {"BOOL": archived},
                            ":archived_at": {"N": str(archived_at)},
                        }
                else:
                    # No archived_at provided, just update archived status
                    update_expression = "SET archived = :archived"
                    expression_values = {
                        ":archived": {"BOOL": archived},
                    }
            else:
                # Handle unarchiving case - set archived to False
                # Preserve archived_at for historical reference
                update_expression = "SET archived = :archived"
                expression_values = {
                    ":archived": {"BOOL": archived},
                }

            # Update the item in DynamoDB
            await self.client.update_item(
                key=key,
                update_expression=update_expression,
                expression_attribute_values=expression_values,
                table_name=self.table_name,
            )
            logger.info(
                "Channel %s archived status updated successfully to %s",
                channel_id,
                "archived" if archived else "unarchived",
            )
        except Exception as e:
            logger.error(
                "Error updating archived status for channel %s: %s", channel_id, str(e)
            )

    async def cleanup(self) -> None:
        """
        Clean up any resources used by this operations instance.

        ArchiveOperations implementation delegates to the parent BaseOperations cleanup.
        """
        logger.info("Cleaning up ArchiveOperations instance")
        await super().cleanup()
