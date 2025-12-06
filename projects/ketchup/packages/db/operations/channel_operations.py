"""
channel_operations.py

This module contains operations for channel CRUD in DynamoDB.
"""

import json
import time
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from packages.core.constants import CHANNEL_KEYWORD_TO_PRODUCT
from packages.core.logging import setup_logger
from packages.core.time_utils import convert_days_to_epoch
from packages.db.batch_write_utils import batch_write_items_with_retries
from packages.db.models.channel_metadata import ChannelMetadata
from packages.db.operations.base_operations import BaseOperations
from packages.db.operations.channel_filter_operations import ChannelFilterOperations
from packages.db.operations.channel_query_operations import ChannelQueryOperations

logger = setup_logger(__name__)


class ChannelOperations(BaseOperations):
    """Operations for channel CRUD in DynamoDB."""

    def __init__(self, client, table_name):
        """Initialize ChannelOperations with specialized operation objects."""
        super().__init__(client, table_name)
        self.query_ops = ChannelQueryOperations(client, table_name)
        self.filter_ops = ChannelFilterOperations(client, table_name)

    async def get_all_channel_details(
        self,
        archive_lookup: bool = False,
        days_threshold: Optional[int] = None,
        targeted_lookup: Optional[str] = None,
        list_of_channels: Optional[List[str]] = None,
        product_preference: Optional[str] = None,
        *,
        include_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Get all channel details from DynamoDB.

        This function retrieves channel details from DynamoDB based on the provided parameters.
        It supports targeted lookup, list lookup, and full table scan modes.

        Args:
            archive_lookup: Whether to include archived channels in the results
            days_threshold: Optional number of days to filter archived channels
            targeted_lookup: Optional channel ID for targeted lookup
            list_of_channels: Optional list of channel IDs for list lookup
            product_preference: Optional product name to filter results by
            include_all: If True, returns ALL channels (both active and archived).
                        Bypasses the default archived filter. Keyword-only argument.

        Returns:
            Dictionary of channel details with channel IDs as keys
        """
        start_message = "Starting get_all_channel_details function."
        logger.info(start_message)

        # Log operation type for monitoring
        operation_type = (
            "targeted lookup"
            if targeted_lookup
            else "list lookup" if list_of_channels else "full scan"
        )
        logger.info(
            "Starting get_all_channel_details: %s, archive_lookup=%s, threshold=%s",
            operation_type,
            archive_lookup,
            days_threshold,
        )

        try:
            # Handle single channel targeted lookup
            if targeted_lookup:
                return await self.query_ops._get_targeted_channel(targeted_lookup)

            # Fetch channels based on lookup type
            if list_of_channels:
                channels = await self.query_ops._get_channels_from_list(list_of_channels)
                # Apply product filtering post-fetch for list lookup
                if product_preference and product_preference != "all_products":
                    filtered_channels = {}
                    for ch_id, item in channels.items():
                        # Normalize temporarily to check product field easily
                        normalized_item = self._normalize_item(item)
                        if normalized_item.get("product") == product_preference:
                            filtered_channels[ch_id] = item
                    channels = filtered_channels
                    logger.info(
                        "Filtered channel list by product preference: %s",
                        product_preference,
                    )
            else:
                # Build filter expression for scan
                filter_parts = []
                expr_attr_values = {}

                # Add archive filter if needed
                if archive_lookup:
                    filter_parts.append("archived = :is_archived")
                    expr_attr_values[":is_archived"] = {"BOOL": True}

                    if days_threshold:
                        threshold_epoch = convert_days_to_epoch(days_threshold)
                        logger.info(
                            "Converted %d days to epoch timestamp: %d",
                            days_threshold,
                            threshold_epoch,
                        )
                        filter_parts.append("archived_at >= :threshold_ts")
                        expr_attr_values[":threshold_ts"] = {"N": str(threshold_epoch)}

                # Add product preference filter if needed
                if product_preference and product_preference != "all_products":
                    filter_parts.append("product = :product_pref")
                    expr_attr_values[":product_pref"] = {"S": product_preference}
                    logger.info("Adding product filter to scan: %s", product_preference)

                # Combine filter parts with AND
                filter_expr = " AND ".join(filter_parts) if filter_parts else None

                # Call scan, passing filter parameters if applicable
                channels = await self.query_ops._get_all_channels_scan(
                    filter_expression=filter_expr,
                    expression_attribute_values=expr_attr_values,
                )

            # If scan was performed with filters, post-filtering is likely not needed or redundant
            # If scan was performed *without* filters (archive_lookup=False), we still need to filter out archived ones
            # UNLESS include_all=True, which means caller wants ALL channels (active + archived)
            if (
                not archive_lookup
                and not list_of_channels
                and not targeted_lookup
                and not include_all
            ):
                # Filter out archived channels if a general scan was done
                channels = {
                    ch_id: item
                    for ch_id, item in channels.items()
                    if not item.get("archived", {}).get("BOOL", False)
                }

            # Normalize the raw items before returning
            normalized_channels = {
                ch_id: self._normalize_item(item) for ch_id, item in channels.items()
            }
            return normalized_channels

        except ClientError as e:
            # Use the handle_dynamo_error from query_ops as it's already defined there
            return self.query_ops._handle_dynamo_error(e, operation_type)
        except Exception as e:
            logger.error("Unexpected error during %s: %s", operation_type, str(e))
            return {}

    async def ensure_channels_exist(self, slack_channels: List[Dict[str, Any]]) -> List[str]:
        """
        Ensure all Slack channels exist in DynamoDB, creating missing ones using batch operations.

        Args:
            slack_channels: List of channel objects from Slack API

        Returns:
            List of channel IDs that were newly added (or attempted to be added).
        """
        if not slack_channels:
            logger.info("No Slack channels provided to ensure_channels_exist.")
            return []

        logger.info("Ensuring %d Slack channels exist in DynamoDB", len(slack_channels))

        items_to_create = []
        processed_channel_ids = set()
        added_channels = []
        current_time_epoch = int(time.time())

        try:
            # Get existing channels from DynamoDB (still using scan for simplicity)
            existing_channels = await self.query_ops._get_all_channels_scan()
            existing_channel_ids = set(existing_channels.keys())
            logger.info("Found %d existing channel IDs in DB", len(existing_channel_ids))

            for channel in slack_channels:
                channel_id = channel.get("id")
                channel_name = channel.get("name", "unknown")

                if not channel_id or not isinstance(channel_id, str):
                    logger.warning("Skipping channel with invalid ID: %s", channel)
                    continue

                # Track processed IDs to avoid duplicate processing in this run
                if channel_id in processed_channel_ids:
                    continue
                processed_channel_ids.add(channel_id)

                # Check if channel exists in DynamoDB
                if channel_id not in existing_channel_ids:
                    logger.info(
                        "Channel %s (%s) missing in DB. Preparing for batch creation.",
                        channel_id,
                        channel_name,
                    )
                    # Format item for DynamoDB PutRequest
                    item = {
                        "PK": {"S": f"CHANNEL#{channel_id}"},
                        "SK": {"S": "CSO_DETAILS"},
                        "channel_id": {"S": channel_id},
                        "channel_name": {"S": channel_name},
                        "jira_ticket": {"S": "NOT YET AVAILABLE"},
                        "customer_name": {"S": "NOT YET AVAILABLE"},
                        "archived": {"BOOL": False},
                        "created_at": {"N": str(current_time_epoch)},
                        "archived_at": {"N": "0"},
                        "product": {"S": self.determine_product_type(channel_name)},
                    }
                    items_to_create.append(item)
                    added_channels.append(channel_id)

            # Perform batch write if there are items to create
            if items_to_create:
                logger.info(
                    "Attempting to batch write %d new channel items.",
                    len(items_to_create),
                )
                put_requests = [{"PutRequest": {"Item": item}} for item in items_to_create]
                # Use the shared batch write utility
                success_count, failure_count = await batch_write_items_with_retries(
                    client=self.client,
                    table_name=self.table_name,
                    put_requests=put_requests,
                )
                logger.info(
                    "Batch write for channels complete: %s successful, %s failed",
                    success_count,
                    failure_count,
                )
            else:
                logger.info("No new channels identified for creation.")

        except Exception as e:
            logger.error(
                "Error during ensure_channels_exist operation: %s",
                str(e),
                exc_info=True,
            )
            return []  # Return empty on major error

        logger.info("Finished ensure_channels_exist. Added channels: %s", added_channels)
        return added_channels

    async def get_channel_details(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific channel by ID.

        Delegates to ChannelQueryOperations.get_channel_details.

        Args:
            channel_id: The ID of the channel to retrieve details for

        Returns:
            Dictionary with channel details or None if not found or error occurs
        """
        return await self.query_ops.get_channel_details(channel_id)

    async def store_metadata(self, metadata: ChannelMetadata) -> None:
        """
        Store metadata for a Slack channel in DynamoDB.

        Args:
            metadata: ChannelMetadata object containing all channel information
        """
        logger.info(
            "Starting store_metadata function for channel %s (%s)",
            metadata.channel_id,
            metadata.channel_name,
        )

        # Convert metadata to DynamoDB item
        item = metadata.to_item()

        try:
            # Store in DynamoDB
            await self.client.put_item(item=item, table_name=self.table_name)
            logger.info("Channel metadata stored successfully: %s", metadata.channel_id)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(
                "DynamoDB error during store_metadata: %s - %s",
                error_code,
                error_message,
            )
        except Exception as e:
            logger.error("Unexpected error during store_metadata: %s", str(e))

    async def delete_channel_if_exists(self, channel_id: str) -> bool:
        """
        Delete a channel record from DynamoDB if it exists.

        Args:
            channel_id: The channel ID to delete

        Returns:
            bool: True if channel was deleted or didn't exist, False if an error occurred
        """
        # Log start of operation
        logger.info("Starting delete_channel_if_exists for channel %s.", channel_id)

        try:
            # Check if channel exists
            existing_details = await self.get_channel_details(channel_id)

            if not existing_details:
                logger.info("Channel %s does not exist, nothing to delete.", channel_id)
                return True

            # If it exists, delete it
            key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}
            logger.info("Deleting channel %s from DynamoDB.", channel_id)
            await self.client.delete_item(key=key, table_name=self.table_name)
            logger.info("Channel %s deleted successfully.", channel_id)
            return True

        except Exception as e:
            logger.error("Error deleting channel %s: %s", channel_id, str(e))
            return False

    async def cleanup(self) -> None:
        """
        Clean up any resources used by this operations instance.

        This method ensures proper cleanup of all specialized operations
        instances used by ChannelOperations.
        """
        logger.info("Cleaning up ChannelOperations instance")

        # Clean up the specialized operations instances
        if hasattr(self, "query_ops") and hasattr(self.query_ops, "cleanup"):
            try:
                await self.query_ops.cleanup()
            except Exception as e:
                logger.error("Error cleaning up query_ops: %s", str(e))

        if hasattr(self, "filter_ops") and hasattr(self.filter_ops, "cleanup"):
            try:
                await self.filter_ops.cleanup()
            except Exception as e:
                logger.error("Error cleaning up filter_ops: %s", str(e))

        # Call the parent class cleanup
        await super().cleanup()

    def determine_product_type(self, channel_name: str) -> str:
        """Determine product type based on channel name using CHANNEL_KEYWORD_TO_PRODUCT.

        Args:
            channel_name: The name of the channel

        Returns:
            The product type determined from the channel name
        """
        channel_name_lower = channel_name.lower()

        # Check each keyword in the dictionary
        for keyword, product_type in CHANNEL_KEYWORD_TO_PRODUCT.items():
            if keyword in channel_name_lower:
                return product_type

        # Return unknown if no matching keyword is found
        return "unknown"

    async def update_channel_metadata(
        self,
        channel_id: str,
        customer_name: str,
        jira_ticket: str,
        user_id: str,
    ) -> bool:
        """
        Update customer_name and jira_ticket for a channel in DynamoDB.

        Args:
            channel_id: The Slack channel ID
            customer_name: The new customer name
            jira_ticket: The new JIRA ticket (normalized)
            user_id: The user making the update (for audit logging)

        Returns:
            bool: True if update succeeded, False otherwise
        """
        logger.info(
            "Updating channel metadata for %s: customer_name=%s, jira_ticket=%s, user_id=%s",
            channel_id,
            customer_name,
            jira_ticket,
            user_id,
        )
        try:
            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"CHANNEL#{channel_id}"},
                    "SK": {"S": "CSO_DETAILS"},
                },
                update_expression="SET customer_name = :c, jira_ticket = :j, last_edited_by = :u, last_edited_at = :t",
                expression_attribute_values={
                    ":c": {"S": customer_name},
                    ":j": {"S": jira_ticket},
                    ":u": {"S": user_id},
                    ":t": {"N": str(int(time.time()))},
                },
            )
            logger.info("Channel metadata updated for %s", channel_id)
            return True
        except Exception as e:
            logger.error("Failed to update channel metadata for %s: %s", channel_id, str(e))
            return False

    async def update_channel_fields(self, channel_id: str, updates: Dict[str, Any]) -> bool:
        """
        Generic method to update arbitrary fields on a channel.

        Args:
            channel_id: The channel ID
            updates: Dictionary of field names to values
        """
        logger.info(
            "Updating channel fields for %s: %s",
            channel_id,
            updates,
        )
        try:
            # Build SET expression
            set_parts = []
            expr_values = {}
            expr_names = {}

            for idx, (field, value) in enumerate(updates.items()):
                placeholder = f":val{idx}"
                name_placeholder = f"#{field}"

                set_parts.append(f"{name_placeholder} = {placeholder}")
                expr_names[name_placeholder] = field

                # Convert Python types to DynamoDB types
                if isinstance(value, bool):
                    expr_values[placeholder] = {"BOOL": value}
                elif isinstance(value, (int, float)):
                    expr_values[placeholder] = {"N": str(value)}
                elif isinstance(value, dict):
                    expr_values[placeholder] = {"S": json.dumps(value)}
                else:
                    expr_values[placeholder] = {"S": str(value)}

            update_expr = "SET " + ", ".join(set_parts)

            await self.client.update_item(
                table_name=self.table_name,
                key={"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}},
                update_expression=update_expr,
                expression_attribute_names=expr_names,
                expression_attribute_values=expr_values,
            )
            logger.info("Channel fields updated successfully for %s", channel_id)
            return True
        except Exception as e:
            logger.error(f"Failed to update channel {channel_id}: {e}")
            return False

    async def update_jira_report_status(
        self,
        channel_id: str,
        status: str,
        timestamp: Optional[int] = None,
        retry_count: Optional[int] = None,
    ) -> bool:
        """
        Update the JIRA reporting status for a channel.

        Args:
            channel_id: The channel ID
            status: Status to set (PENDING, PROCESSING, PROCESSED, FAILED, SKIPPED)
            timestamp: Optional timestamp of the reporting attempt
            retry_count: Optional retry count for failed attempts

        Returns:
            True if update was successful, False otherwise
        """
        if not timestamp:
            timestamp = int(time.time())

        try:
            update_expression = (
                "SET jira_report_status = :status, " "jira_report_timestamp = :timestamp"
            )

            expression_values = {
                ":status": {"S": status},
                ":timestamp": {"N": str(timestamp)},
            }

            # Add retry count if provided
            if retry_count is not None:
                update_expression += ", jira_report_retry_count = :retry_count"
                expression_values[":retry_count"] = {"N": str(retry_count)}

            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"CHANNEL#{channel_id}"},
                    "SK": {"S": "CSO_DETAILS"},
                },
                update_expression=update_expression,
                expression_attribute_values=expression_values,
            )
            log_msg = f"Updated JIRA report status for channel {channel_id} to {status}"
            if retry_count is not None:
                log_msg += f" (retry count: {retry_count})"
            logger.info(log_msg)
            return True
        except Exception as e:
            logger.error(f"Failed to update JIRA report status for channel {channel_id}: {str(e)}")
            return False

    async def get_jira_posting_metrics(
        self,
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        """
        Query all channels and aggregate JIRA posting statistics for time period.

        Analyzes JIRA reporter posting status for dashboard metrics.
        Only counts PROCESSED postings that occurred within the time window.
        FAILED/PENDING statuses are counted regardless of age.

        Success is defined as: primary_success OR (primary_invalid AND csopm_success)

        Args:
            start_ts: Start timestamp (Unix epoch)
            end_ts: End timestamp (Unix epoch)

        Returns:
            Dictionary containing:
                - total_channels: Total CSO channels analyzed
                - posted_primary: Channels posted to primary ticket (in time window)
                - posted_csopm: Channels posted to CSOPM ticket (in time window)
                - posted_both: Channels posted to both tickets (in time window)
                - failed_no_ticket: Channels failed due to missing/invalid ticket
                - failed_api_error: Channels failed due to API errors
                - pending: Channels with reports pending
                - processing: Channels currently being processed
                - success_rate: Percentage of successful postings (in time window)
                - channels_needing_attention: List of channel IDs requiring action
        """
        logger.info(f"Starting get_jira_posting_metrics (time window: {start_ts} - {end_ts})")

        try:
            # Get all channels (campaign/ajo only for CSO metrics)
            all_channels = await self.query_ops._get_all_channels_scan()
            normalized_channels = {
                ch_id: self._normalize_item(item) for ch_id, item in all_channels.items()
            }

            # Filter to campaign/ajo channels only (CSO channels)
            cso_channels = {
                ch_id: ch
                for ch_id, ch in normalized_channels.items()
                if ch.get("product") in ["campaign", "ajo"] and not ch.get("archived", False)
            }

            total_channels = len(cso_channels)
            posted_primary = 0
            posted_csopm = 0
            posted_both = 0
            failed_no_ticket = 0
            failed_api_error = 0
            pending = 0
            processing = 0
            channels_needing_attention = []

            for channel_id, channel in cso_channels.items():
                status = channel.get("jira_report_status", "PENDING")
                timestamp = channel.get("jira_report_timestamp", 0)
                primary_invalid = channel.get("jira_report_primary_invalid", False)
                csopm_posted = channel.get("jira_report_csopm_posted", False)
                jira_ticket = channel.get("jira_ticket", "NOT YET AVAILABLE")

                # Count by status
                if status == "PENDING":
                    pending += 1
                    channels_needing_attention.append(channel_id)
                elif status == "PROCESSING":
                    processing += 1
                elif status == "PROCESSED":
                    # Only count if posted within time window
                    if start_ts <= timestamp <= end_ts:
                        # Determine what was posted
                        if not primary_invalid and csopm_posted:
                            posted_both += 1
                            posted_primary += 1
                            posted_csopm += 1
                        elif not primary_invalid:
                            posted_primary += 1
                        elif csopm_posted:
                            posted_csopm += 1
                    # If outside time window, treat as stale/needing update
                    else:
                        pending += 1
                        channels_needing_attention.append(channel_id)
                elif status == "FAILED":
                    # Distinguish failure types
                    if primary_invalid and jira_ticket == "NOT YET AVAILABLE":
                        failed_no_ticket += 1
                    else:
                        failed_api_error += 1
                    channels_needing_attention.append(channel_id)

            # Calculate success rate
            successful = posted_primary + posted_csopm - posted_both
            success_rate = (
                round((successful / total_channels) * 100, 1) if total_channels > 0 else 0.0
            )

            metrics = {
                "total_channels": total_channels,
                "posted_primary": posted_primary,
                "posted_csopm": posted_csopm,
                "posted_both": posted_both,
                "failed_no_ticket": failed_no_ticket,
                "failed_api_error": failed_api_error,
                "pending": pending,
                "processing": processing,
                "success_rate": success_rate,
                "channels_needing_attention": channels_needing_attention,
            }

            logger.info(
                f"JIRA posting metrics: {successful}/{total_channels} "
                f"successful ({success_rate}%)"
            )
            return metrics

        except Exception as e:
            logger.error(f"Error collecting JIRA posting metrics: {e}", exc_info=True)
            return {
                "total_channels": 0,
                "posted_primary": 0,
                "posted_csopm": 0,
                "posted_both": 0,
                "failed_no_ticket": 0,
                "failed_api_error": 0,
                "pending": 0,
                "processing": 0,
                "success_rate": 0.0,
                "channels_needing_attention": [],
            }
