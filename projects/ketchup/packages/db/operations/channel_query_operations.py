"""
channel_query_operations.py

This module contains query operations for channels in DynamoDB.
"""

from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from packages.core.constants import MAX_BATCH_SIZE  # Import batch size constant
from packages.core.logging import setup_logger
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)


class ChannelQueryOperations(BaseOperations):
    """Query operations for channels in DynamoDB."""

    async def cleanup(self) -> None:
        """
        Clean up any resources used by this operations instance.

        This includes releasing any connections, caches, or other resources
        held by this instance.
        """
        logger.info("Cleaning up ChannelQueryOperations resources")
        await super().cleanup()

    async def _get_targeted_channel(self, channel_id: str) -> Dict[str, Any]:
        """
        Get details for a single channel by ID.

        Args:
            channel_id: The ID of the channel to retrieve

        Returns:
            Dictionary with channel details or empty dict if not found
        """
        logger.info("Performing targeted lookup for channel: %s", channel_id)

        key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}
        response = await self.client.get_item(key=key, table_name=self.table_name)

        item = response.get("Item")
        if not item:
            logger.info("No channel found for ID: %s", channel_id)
            return {}

        # Return formatted channel details
        normalized = self._normalize_item(item)
        return {
            channel_id: {
                "customer_name": normalized.get("customer_name", "NOT YET AVAILABLE"),
                "jira_ticket": normalized.get("jira_ticket", "NOT YET AVAILABLE"),
                "channel_name": normalized.get("channel_name", "NOT YET AVAILABLE"),
                "channel_id": channel_id,
            }
        }

    async def get_channel_details(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific channel by ID.

        This is a convenience method that provides direct access to a single channel's details.
        It returns None if the channel doesn't exist or if an error occurs during retrieval.

        Args:
            channel_id: The ID of the channel to retrieve details for

        Returns:
            Dictionary with channel details or None if not found or error occurs
        """
        logger.info("Starting get_channel_details for channel: %s", channel_id)

        try:
            # Get the item from DynamoDB
            key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}
            response = await self.client.get_item(key=key, table_name=self.table_name)

            # If no data was found, return None
            if not response.get("Item"):
                logger.info("No channel found for ID: %s", channel_id)
                return None

            # Extract and normalize the channel details from DynamoDB format
            item = response.get("Item", {})
            return self._normalize_item(item)

        except Exception as e:
            error_message = f"Error retrieving channel {channel_id}: {str(e)}"
            logger.error(error_message)
            return None

    async def get_channel_details_consistent(
        self, channel_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific channel by ID using strongly consistent read.

        This method is specifically for operations that need to avoid race conditions,
        such as archive/unarchive operations. It ensures the most recent data is returned.

        Args:
            channel_id: The ID of the channel to retrieve details for

        Returns:
            Dictionary with channel details or None if not found or error occurs
        """
        logger.info(
            "Starting get_channel_details_consistent for channel: %s", channel_id
        )

        try:
            # Get the item from DynamoDB with consistent read
            key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}
            response = await self.client.get_item(
                key=key, table_name=self.table_name, consistent_read=True
            )

            # If no data was found, return None
            if not response.get("Item"):
                logger.info("No channel found for ID: %s", channel_id)
                return None

            # Extract and normalize the channel details from DynamoDB format
            item = response.get("Item", {})
            return self._normalize_item(item)

        except Exception as e:
            error_message = (
                f"Error retrieving channel {channel_id} with consistent read: {str(e)}"
            )
            logger.error(error_message)
            return None

    async def _get_channels_from_list(self, channel_ids: List[str]) -> Dict[str, Any]:
        """
        Get details for multiple channels from a list of IDs using batch_get_item.

        Args:
            channel_ids: List of channel IDs to retrieve (duplicates are handled)

        Returns:
            Dictionary of channel details keyed by channel ID, containing raw DynamoDB items.
        """
        if not channel_ids:
            logger.info("Empty channel list provided to _get_channels_from_list")
            return {}

        # Remove duplicates and potential None/empty values
        unique_channel_ids = list(
            set(ch_id for ch_id in channel_ids if ch_id and isinstance(ch_id, str))
        )
        if not unique_channel_ids:
            logger.info("Channel list contains no valid IDs")
            return {}

        logger.info(
            "Fetching details for %s unique channels using batch_get_item",
            len(unique_channel_ids),
        )
        channels = {}
        keys_to_process = [
            {"PK": {"S": f"CHANNEL#{ch_id}"}, "SK": {"S": "CSO_DETAILS"}}
            for ch_id in unique_channel_ids
        ]

        while keys_to_process:
            # Take a batch of keys up to the DynamoDB limit
            current_batch_keys = keys_to_process[:MAX_BATCH_SIZE]
            keys_to_process = keys_to_process[MAX_BATCH_SIZE:]

            request_items = {self.table_name: {"Keys": current_batch_keys}}

            try:
                logger.info(
                    "Calling batch_get_item for %s keys", len(current_batch_keys)
                )
                # Get the underlying client to call batch_get_item
                underlying_client = await self.client._get_client()
                response = await underlying_client.batch_get_item(
                    RequestItems=request_items
                )

                # Process successfully retrieved items
                items = response.get("Responses", {}).get(self.table_name, [])
                for item in items:
                    # Extract channel_id from the PK
                    pk_value = item.get("PK", {}).get("S", "")
                    if pk_value.startswith("CHANNEL#"):
                        channel_id = pk_value.split("#", 1)[1]
                        channels[channel_id] = item
                    else:
                        logger.warning("Found item with unexpected PK format: %s", item)

                # Handle unprocessed keys
                unprocessed_keys = (
                    response.get("UnprocessedKeys", {})
                    .get(self.table_name, {})
                    .get("Keys", [])
                )
                if unprocessed_keys:
                    logger.warning(
                        "%s keys were unprocessed by batch_get_item. Adding back to process list.",
                        len(unprocessed_keys),
                    )
                    # Add unprocessed keys back to the list for the next iteration (simple retry)
                    keys_to_process.extend(unprocessed_keys)

            except ClientError as e:
                # Log the specific DynamoDB error but continue if possible to process other batches
                self._handle_dynamo_error(
                    e, "batch_get_item in _get_channels_from_list"
                )
                # Decide if we should stop entirely or just skip this batch
                # For now, we log and continue with potentially remaining keys_to_process
                logger.error("Skipping failed batch, attempting remaining keys if any.")
            except Exception as e:
                # Catch broader exceptions
                logger.error(
                    "Unexpected error during batch_get_item in _get_channels_from_list: %s",
                    str(e),
                    exc_info=True,
                )
                logger.error(
                    "Stopping further batch processing due to unexpected error."
                )
                keys_to_process = []  # Stop processing further batches

        logger.info(
            "Finished fetching channels. Retrieved details for %s channels.",
            len(channels),
        )
        return channels

    async def _get_all_channels_scan(
        self,
        filter_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get channel details using a table scan, optionally applying filters.

        Args:
            filter_expression: Optional DynamoDB filter expression string.
            expression_attribute_values: Optional dict for filter expression values.
            expression_attribute_names: Optional dict for filter expression names.

        Returns:
            Dictionary of channel details keyed by channel ID
        """
        logger.info(
            "Performing full table scan%s",
            " with filter" if filter_expression else "",
        )
        if filter_expression:
            logger.info("Filter expression: %s", filter_expression)
            logger.info("Filter values: %s", expression_attribute_values)

        all_items = []
        last_evaluated_key = None
        while True:
            try:
                scan_params = {
                    "table_name": self.table_name,
                    "exclusive_start_key": last_evaluated_key,
                }

                if filter_expression:
                    scan_params["filter_expression"] = filter_expression
                    scan_params["expression_attribute_values"] = (
                        expression_attribute_values
                    )
                    if expression_attribute_names:
                        scan_params["expression_attribute_names"] = (
                            expression_attribute_names
                        )

                response = await self.client.scan(**scan_params)
                items = response.get("Items", [])
                logger.info("Retrieved %d items in current scan page", len(items))
                all_items.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
                logger.info("Scanning next page...")
            except ClientError as e:
                self._handle_dynamo_error(e, "scan in _get_all_channels_scan")
                logger.error("Stopping scan due to DynamoDB error.")
                return {}  # Return empty on error
            except Exception as e:
                logger.error(
                    "Unexpected error during scan in _get_all_channels_scan: %s",
                    str(e),
                    exc_info=True,
                )
                return {}  # Return empty on error

        logger.info("Total items retrieved from scan: %d", len(all_items))

        # Map channel IDs to items, filtering for CSO_DETAILS
        # Note: The primary SK filter is still needed even if FilterExpression is used,
        # as FilterExpression applies AFTER the scan reads items.
        channels = {
            item.get("PK", {}).get("S", "").replace("CHANNEL#", ""): item
            for item in all_items
            if item.get("SK", {}).get("S") == "CSO_DETAILS"
        }

        logger.info("Final number of channels after filtering: %d", len(channels))
        return channels

    def _handle_dynamo_error(
        self, error: ClientError, operation_type: str
    ) -> Dict[str, Any]:
        """
        Handle DynamoDB specific errors.

        Args:
            error: The ClientError exception
            operation_type: Type of operation that failed

        Returns:
            Empty dictionary (failure case)
        """
        error_code = error.response["Error"]["Code"]
        error_message = error.response["Error"]["Message"]
        logger.error(
            "DynamoDB error during %s: %s - %s",
            operation_type,
            error_code,
            error_message,
        )
        return {}

    async def get_all_active_channels(self) -> List[Dict[str, Any]]:
        """Get all non-archived channels for auto-status updates."""
        try:
            all_items = []
            last_evaluated_key = None

            # Handle pagination to get all channels
            while True:
                # Build scan parameters
                scan_params = {
                    "table_name": self.table_name,
                    "filter_expression": "SK = :sk AND (attribute_not_exists(archived) OR archived = :not_archived)",
                    "expression_attribute_values": {
                        ":sk": {"S": "CSO_DETAILS"},
                        ":not_archived": {"BOOL": False},
                    },
                }

                # Add exclusive_start_key for pagination if present
                if last_evaluated_key:
                    scan_params["exclusive_start_key"] = last_evaluated_key

                # Perform scan
                response = await self.client.scan(**scan_params)

                # Collect items from this page
                items = response.get("Items", [])
                all_items.extend(items)

                # Check for more pages
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break

                logger.info(
                    f"Scanning next page for active channels, retrieved {len(all_items)} so far"
                )

            logger.info(f"Total active channels retrieved: {len(all_items)}")
            # Normalize all collected items
            return [self._normalize_item(item) for item in all_items]
        except Exception as e:
            logger.error(f"Error getting active channels: {e}")
            return []
