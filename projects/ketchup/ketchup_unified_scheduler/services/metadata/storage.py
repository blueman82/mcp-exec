"""
storage.py

This module contains the MetadataStorage class that handles
data persistence for channel metadata.
"""

from typing import Dict, List

from packages.core.constants import DYNAMODB_TABLE_NAME
from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.models.channel_metadata import ChannelMetadata


class MetadataStorage:
    """Handles storage and retrieval of channel metadata."""

    def __init__(self, dynamodb_store=None):
        """Initialize with DynamoDB store dependency.

        Args:
            dynamodb_store: DynamoDB operations client
        """
        self.logger = setup_logger(__name__)
        if dynamodb_store is not None:
            self.dynamodb_store = dynamodb_store
        else:
            client = DynamoDBAsyncClient()
            self.dynamodb_store = DynamoDBStore(client=client, table_name=DYNAMODB_TABLE_NAME)

    async def scan_for_incomplete_metadata(self) -> List[str]:
        """
        Scan for channels with missing or incomplete metadata.

        Returns:
            List of channel IDs with incomplete metadata
        """
        self.logger.info("Scanning for channels with incomplete metadata")

        try:
            # Fetch all channel details from DynamoDB
            all_channels = await self.dynamodb_store.get_all_channel_details()

            # Filter channels with incomplete metadata
            incomplete_channels = []
            for channel_id, details in all_channels.items():
                customer_name = details.get("customer_name", "NOT YET AVAILABLE")
                jira_ticket = details.get("jira_ticket", "NOT YET AVAILABLE")

                if customer_name == "NOT YET AVAILABLE" or jira_ticket == "NOT YET AVAILABLE":
                    if not details.get("archived", False):  # Skip archived channels
                        incomplete_channels.append(channel_id)

            self.logger.info(
                "Found %d channels with incomplete metadata out of %d total channels",
                len(incomplete_channels),
                len(all_channels),
            )

            return incomplete_channels

        except Exception as e:
            self.logger.error("Error scanning for incomplete metadata: %s", str(e), exc_info=True)
            return []

    async def needs_metadata_update(self, channel_id: str) -> bool:
        """
        Check if a channel needs metadata update.

        Args:
            channel_id: The Slack channel ID to check

        Returns:
            bool: True if channel needs metadata update
        """
        try:
            channel_details = await self.dynamodb_store.get_channel_details(channel_id)

            if not channel_details:
                self.logger.warning("Channel %s not found in DynamoDB", channel_id)
                return False

            customer_name = channel_details.get("customer_name", "NOT YET AVAILABLE")
            jira_ticket = channel_details.get("jira_ticket", "NOT YET AVAILABLE")

            return customer_name == "NOT YET AVAILABLE" or jira_ticket == "NOT YET AVAILABLE"
        except Exception as e:
            self.logger.error(
                "Error checking if channel %s needs update: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            # Default to False on error to avoid unnecessary processing
            return False

    async def store_extracted_metadata(self, channel_id: str, metadata: Dict[str, str]) -> bool:
        """
        Store extracted metadata in DynamoDB.

        Args:
            channel_id: Slack channel ID
            metadata: Dict with extracted customer_name and jira_ticket

        Returns:
            bool: True if storage was successful
        """
        try:
            # Get existing channel metadata
            channel_details = await self.dynamodb_store.get_channel_details(channel_id)

            if not channel_details:
                self.logger.warning("Channel %s not found in DynamoDB", channel_id)
                return False

            # Only update if the new value is not 'NOT YET AVAILABLE', otherwise keep the existing value
            new_customer_name = metadata.get("customer_name", "NOT YET AVAILABLE")
            current_customer_name = channel_details.get("customer_name", "NOT YET AVAILABLE")

            # Reject values that look like raw JSON (bug: AI sometimes returns JSON blob)
            if new_customer_name and new_customer_name.lstrip().startswith("{"):
                self.logger.warning(
                    "Rejecting JSON-like customer_name for channel %s: %.80s",
                    channel_id,
                    new_customer_name,
                )
                new_customer_name = "NOT YET AVAILABLE"

            if new_customer_name == "NOT YET AVAILABLE":
                customer_name_to_store = current_customer_name
            else:
                customer_name_to_store = new_customer_name

            new_jira_ticket = metadata.get("jira_ticket", "NOT YET AVAILABLE")
            current_jira_ticket = channel_details.get("jira_ticket", "NOT YET AVAILABLE")
            if new_jira_ticket == "NOT YET AVAILABLE":
                jira_ticket_to_store = current_jira_ticket
            else:
                jira_ticket_to_store = new_jira_ticket

            # Check if metadata actually changed
            if (
                customer_name_to_store == current_customer_name
                and jira_ticket_to_store == current_jira_ticket
            ):
                self.logger.info(
                    "No changes to metadata for channel %s, skipping update", channel_id
                )
                return True

            # Create updated metadata model
            updated_metadata = ChannelMetadata(
                channel_id=channel_id,
                channel_name=channel_details.get("channel_name", "NOT YET AVAILABLE"),
                custom_fields={
                    "customer_name": customer_name_to_store,
                    "jira_ticket": jira_ticket_to_store,
                    "archived": channel_details.get("archived", False),
                    "created_at": channel_details.get("created_at", 0),
                    "archived_at": channel_details.get("archived_at", 0),
                    "product": channel_details.get("product", "Unknown"),
                },
            )

            # Store the updated metadata
            await self.dynamodb_store.store_metadata(updated_metadata)

            self.logger.info(
                "Updated metadata stored for channel %s: %s, %s",
                channel_id,
                customer_name_to_store,
                jira_ticket_to_store,
            )

            return True

        except Exception as e:
            self.logger.error(
                "Failed to store metadata for channel %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return False

    async def cleanup(self) -> None:
        """Clean up storage resources.

        NOTE: dynamodb_store is an injected dependency from TypedDI.
        Do NOT cleanup injected dependencies as they may be shared
        across multiple services in the unified scheduler.
        """
        # Previously called dynamodb_store.cleanup() which closed the shared
        # DynamoDB session, breaking other tasks running concurrently.
        # Injected dependencies should be managed by the DI container, not here.
        pass
