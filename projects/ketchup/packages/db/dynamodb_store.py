"""
dynamodb_store.py

This module contains the DynamoDBStore class for interacting with DynamoDB.
It acts as a facade for specialized operation classes.
"""

import time
from typing import Any, Dict, List, Optional

import orjson

from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.models.channel_metadata import ChannelMetadata
from packages.db.operations.archive_operations import ArchiveOperations
from packages.db.operations.channel_operations import ChannelOperations
from packages.db.operations.feedback_operations import FeedbackOperations
from packages.db.operations.restore_state_operations import RestoreStateOperations
from packages.db.operations.trust_operations import TrustOperations

logger = setup_logger(__name__)


class DynamoDBStore:
    """
    Service for interacting with DynamoDB for storage operations related to channels.
    This class acts as a facade for specialized operation classes, using an injected async client.
    """

    def __init__(self, client: DynamoDBAsyncClient, table_name: str):
        """
        Initialize the DynamoDBStore with an injected async client.

        Args:
            client: An initialized DynamoDBAsyncClient instance.
            table_name: The DynamoDB table name.
        """
        # Store injected client and table name
        self.client = client
        self.table_name = table_name

        # Initialize specialized operation classes, passing the injected client
        self.channel_ops = ChannelOperations(self.client, self.table_name)
        self.archive_ops = ArchiveOperations(self.client, self.table_name)
        self.feedback_ops = FeedbackOperations(self.client, self.table_name)
        self.restore_ops = RestoreStateOperations(self.client, self.table_name)
        self.trust_ops = TrustOperations(self.client, self.table_name)

    async def get_all_channel_details(
        self,
        archive_lookup: bool = False,
        days_threshold: Optional[int] = None,
        targeted_lookup: Optional[str] = None,
        list_of_channels: Optional[List[str]] = None,
        product_preference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get all channel details from DynamoDB.

        Delegates to ChannelOperations.get_all_channel_details.

        Args:
            archive_lookup: Whether to include archived channels in the results
            days_threshold: Optional number of days to filter archived channels
            targeted_lookup: Optional channel ID for targeted lookup
            list_of_channels: Optional list of channel IDs for list lookup
            product_preference: Optional product name to filter results by

        Returns:
            Dictionary of channel details with channel IDs as keys
        """
        return await self.channel_ops.get_all_channel_details(
            archive_lookup=archive_lookup,
            days_threshold=days_threshold,
            targeted_lookup=targeted_lookup,
            list_of_channels=list_of_channels,
            product_preference=product_preference,
        )

    async def get_channel_details(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific channel by ID.

        Delegates to ChannelOperations.get_channel_details.

        Args:
            channel_id: The ID of the channel to retrieve details for

        Returns:
            Dictionary with channel details or None if not found or error occurs
        """
        return await self.channel_ops.get_channel_details(channel_id)

    async def store_metadata(self, metadata: ChannelMetadata) -> None:
        """
        Store metadata for a Slack channel in DynamoDB.

        Delegates to ChannelOperations.store_metadata.

        Args:
            metadata: ChannelMetadata object containing all channel information
        """
        await self.channel_ops.store_metadata(metadata)

    async def update_channel_archived_status(
        self, channel_id: str, archived: bool, archived_at: Optional[int] = None
    ) -> None:
        """
        Update a channel's archived status in DynamoDB.

        Delegates to ArchiveOperations.update_channel_archived_status.

        Args:
            channel_id: The Slack channel ID
            archived: Whether the channel is archived
            archived_at: Optional timestamp when the channel was archived
        """
        await self.archive_ops.update_channel_archived_status(channel_id, archived, archived_at)

    async def store_feedback(self, feedback_item: Dict[str, Any]) -> bool:
        """
        Store feedback item in DynamoDB.

        Delegates to FeedbackOperations.store_feedback.

        Args:
            feedback_item: Dictionary containing feedback information

        Returns:
            bool: True if successful, False otherwise
        """
        return await self.feedback_ops.store_feedback(feedback_item)

    async def delete_channel_if_exists(self, channel_id: str) -> bool:
        """
        Delete a channel record from DynamoDB if it exists.

        Delegates to ChannelOperations.delete_channel_if_exists.

        Args:
            channel_id: The channel ID to delete

        Returns:
            bool: True if channel was deleted or didn't exist, False if an error occurred
        """
        return await self.channel_ops.delete_channel_if_exists(channel_id)

    async def ensure_channels_exist(self, slack_channels: List[Dict[str, Any]]) -> List[str]:
        """
        Ensure all Slack channels exist in DynamoDB.

        Args:
            slack_channels: List of channel objects from Slack API

        Returns:
            List of channel IDs that were newly added
        """
        return await self.channel_ops.ensure_channels_exist(slack_channels)

    async def cleanup(self) -> None:
        """Clean up resources used by the store and its operations."""
        logger.info("Cleaning up DynamoDB Store")
        # Cleanup internal Ops instances first
        await self.channel_ops.cleanup()
        await self.archive_ops.cleanup()
        await self.feedback_ops.cleanup()
        await self.trust_ops.cleanup()

        # Cleanup the injected client (responsibility of the factory/caller)
        # Do NOT call self.client.cleanup() here, as it's shared.
        logger.info("DynamoDB Store internal cleanup finished.")

    async def check_if_temporary_unarchive(self, channel_id: str) -> bool:
        """
        Check if a channel has the 'temp_unarchive_expiry' attribute, indicating
        it was temporarily unarchived.

        Args:
            channel_id: The ID of the channel to check.

        Returns:
            bool: True if the attribute exists, False otherwise.
        """
        logger.info("Checking temporary unarchive status for channel %s", channel_id)
        try:
            # Delegate the check to the RestoreStateOperations which handles this specific SK
            return await self.restore_ops.check_if_temporary_unarchive(channel_id)
        except Exception as e:
            logger.error(
                "Error checking temporary unarchive status via RestoreStateOperations for %s: %s",
                channel_id,
                str(e),
            )
            return False  # Assume not temporary on error

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
        return await self.channel_ops.update_channel_metadata(
            channel_id=channel_id,
            customer_name=customer_name,
            jira_ticket=jira_ticket,
            user_id=user_id,
        )

    async def update_channel_fields(self, channel_id: str, updates: Dict[str, Any]) -> bool:
        """
        Generic method to update arbitrary fields on a channel.

        Args:
            channel_id: The channel ID
            updates: Dictionary of field names to values

        Returns:
            bool: True if update succeeded, False otherwise
        """
        return await self.channel_ops.update_channel_fields(channel_id=channel_id, updates=updates)

    async def get_channel_details_consistent(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific channel by ID using strongly consistent read.

        This method is specifically for operations that need to avoid race conditions,
        such as archive/unarchive operations. It ensures the most recent data is returned.

        Args:
            channel_id: The ID of the channel to retrieve details for

        Returns:
            Dictionary with channel details or None if not found or error occurs
        """
        return await self.channel_ops.query_ops.get_channel_details_consistent(channel_id)

    async def is_duplicate_event(self, team_id: str, user_id: str, timestamp: str) -> bool:
        """
        Check if an event is a duplicate using atomic conditional put.
        Returns True if duplicate (already exists), False if new.

        Args:
            team_id: The Slack team ID
            user_id: The Slack user ID
            timestamp: The event timestamp

        Returns:
            bool: True if this is a duplicate event, False if it's new
        """
        pk = f"EVENT#{team_id}#{user_id}#{timestamp}"
        ttl = int(time.time() + 60)  # 60 second TTL

        try:
            # Try to create the item - will fail if it already exists
            await self.client.put_item(
                table_name=self.table_name,
                item={"PK": {"S": pk}, "SK": {"S": "DEDUP"}, "ttl": {"N": str(ttl)}},
                condition_expression="attribute_not_exists(PK)",
            )
            # Successfully created - not a duplicate
            return False
        except Exception as e:
            if "ConditionalCheckFailedException" in str(e):
                # Item already exists - this is a duplicate
                logger.info(f"Duplicate event detected: {pk}")
                return True
            else:
                # Unexpected error - log and allow processing to continue
                logger.error(f"Error checking duplicate event: {e}")
                return False

    async def store_maintenance_cache(
        self, date: str, data: List[Dict], ttl_seconds: int = 86400
    ) -> bool:
        """
        Store maintenance data cache in DynamoDB.

        Args:
            date: Date in YYYY-MM-DD format
            data: List of maintenance records
            ttl_seconds: Time-to-live in seconds (default: 24 hours)

        Returns:
            True if successful, False otherwise
        """
        try:
            item = {
                "PK": {"S": f"MAINTENANCE#{date}"},
                "SK": {"S": "CACHE"},
                "maintenance_data": {"S": orjson.dumps(data).decode("utf-8")},
                "fetched_at": {"N": str(int(time.time()))},
                "ttl": {"N": str(int(time.time()) + ttl_seconds)},
            }

            await self.client.put_item(item=item, table_name=self.table_name)

            logger.info(f"Stored maintenance cache for date: {date}")
            return True

        except Exception as e:
            logger.error(f"Failed to store maintenance cache: {e}")
            return False

    async def get_maintenance_cache(self, date: str) -> Optional[List[Dict]]:
        """
        Retrieve maintenance data cache from DynamoDB.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            List of maintenance records, or None if not found/expired
        """
        try:
            response = await self.client.get_item(
                key={"PK": {"S": f"MAINTENANCE#{date}"}, "SK": {"S": "CACHE"}},
                table_name=self.table_name,
                consistent_read=True,
            )

            if "Item" not in response:
                logger.info(f"No maintenance cache found for date: {date}")
                return None

            item = response["Item"]

            # Check if expired (TTL)
            ttl = int(item.get("ttl", {}).get("N", "0"))
            if ttl > 0 and int(time.time()) > ttl:
                logger.info(f"Maintenance cache expired for date: {date}")
                return None

            # Parse and return data
            data_json = item.get("maintenance_data", {}).get("S", "[]")
            return orjson.loads(data_json)

        except Exception as e:
            logger.error(f"Failed to get maintenance cache: {e}")
            return None

    # Trust operations are handled through trust_ops which accesses the client directly
    # No need for generic query_items or update_item methods without GSI

    # ==================== Maintenance Prompt State Methods ====================

    async def put_maintenance_prompt(
        self, channel_id: str, prompt_ts: str, attempt: int, jira_ticket: Optional[str] = None
    ) -> bool:
        """
        Store maintenance prompt state so any container can see it.

        Args:
            channel_id: Slack channel ID
            prompt_ts: Timestamp of the prompt message
            attempt: Current attempt number (1-3)
            jira_ticket: JIRA ticket if reply was received

        Returns:
            True if stored successfully
        """
        item = {
            "PK": {"S": f"MAINTENANCE_PROMPT#{channel_id}"},
            "SK": {"S": "ACTIVE"},
            "prompt_ts": {"S": prompt_ts},
            "attempt": {"N": str(attempt)},
            "started_at": {"N": str(int(time.time()))},
            "expires_at": {"N": str(int(time.time() + 120))},  # 2 minute timeout
        }

        if jira_ticket:
            item["jira_ticket"] = {"S": jira_ticket}

        try:
            await self.client.put_item(item=item, table_name=self.table_name)
            return True
        except Exception as e:
            logger.error(f"Failed to store maintenance prompt for {channel_id}: {e}")
            return False

    async def get_maintenance_prompt(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get active maintenance prompt state for a channel.

        Args:
            channel_id: Slack channel ID

        Returns:
            Prompt state dict or None if no active prompt
        """
        try:
            result = await self.client.get_item(
                key={"PK": {"S": f"MAINTENANCE_PROMPT#{channel_id}"}, "SK": {"S": "ACTIVE"}},
                table_name=self.table_name,
            )

            item = result.get("Item")
            if not item:
                return None

            # Check if expired (extract value from DynamoDB format)
            expires_at = int(item.get("expires_at", {}).get("N", 0))
            if expires_at < time.time():
                # Expired - delete it
                await self.delete_maintenance_prompt(channel_id)
                return None

            # Convert DynamoDB format to simple dict
            simple_item = {
                "prompt_ts": item.get("prompt_ts", {}).get("S"),
                "attempt": int(item.get("attempt", {}).get("N", 0)),
                "started_at": int(item.get("started_at", {}).get("N", 0)),
                "expires_at": expires_at,
            }

            if "jira_ticket" in item:
                simple_item["jira_ticket"] = item["jira_ticket"].get("S")

            return simple_item

        except Exception as e:
            logger.error(f"Failed to get maintenance prompt for {channel_id}: {e}")
            return None

    async def delete_maintenance_prompt(self, channel_id: str) -> bool:
        """
        Delete maintenance prompt state.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if deleted successfully
        """
        try:
            await self.client.delete_item(
                key={"PK": {"S": f"MAINTENANCE_PROMPT#{channel_id}"}, "SK": {"S": "ACTIVE"}},
                table_name=self.table_name,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete maintenance prompt for {channel_id}: {e}")
            return False

    async def store_maintenance_reply(self, channel_id: str, jira_ticket: str) -> bool:
        """
        Store JIRA ticket reply so the waiting container can retrieve it.

        Args:
            channel_id: Slack channel ID
            jira_ticket: The JIRA ticket number

        Returns:
            True if stored successfully
        """
        # Update the existing prompt with the ticket
        try:
            prompt = await self.get_maintenance_prompt(channel_id)
            if prompt:
                # Convert back to DynamoDB format for update
                item = {
                    "PK": {"S": f"MAINTENANCE_PROMPT#{channel_id}"},
                    "SK": {"S": "ACTIVE"},
                    "prompt_ts": {"S": prompt["prompt_ts"]},
                    "attempt": {"N": str(prompt["attempt"])},
                    "started_at": {"N": str(prompt["started_at"])},
                    "expires_at": {"N": str(prompt["expires_at"])},
                    "jira_ticket": {"S": jira_ticket},
                    "replied_at": {"N": str(int(time.time()))},
                }
                await self.client.put_item(item=item, table_name=self.table_name)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to store maintenance reply for {channel_id}: {e}")
            return False

    async def increment_monthly_counter(
        self, counter_name: str, month_key: str, increment: int = 1
    ) -> bool:
        """
        Atomically increment a monthly metrics counter in METRICS_SUMMARY record.

        Uses DynamoDB ADD operation for thread-safe atomic increments.
        Creates the counter if it doesn't exist.

        Args:
            counter_name: Counter type (e.g., 'auto_status_posts', 'war_room_sent')
            month_key: Month identifier in YYYY_MM format (e.g., '2025_10')
            increment: Amount to increment by (default: 1)

        Returns:
            True if increment succeeded

        Example:
            await db_store.increment_monthly_counter(
                'auto_status_posts', '2025_10', 1
            )
            # Creates/increments: auto_status_posts_2025_10
        """
        field_name = f"{counter_name}_{month_key}"

        try:
            await self.client.update_item(
                table_name=self.table_name,
                key={"PK": {"S": "METRICS_SUMMARY"}, "SK": {"S": "AGGREGATES"}},
                update_expression="ADD #field :inc",
                expression_attribute_names={"#field": field_name},
                expression_attribute_values={":inc": {"N": str(increment)}},
            )
            logger.debug(f"Incremented {field_name} by {increment}")
            return True
        except Exception as e:
            logger.error(f"Failed to increment {field_name}: {e}")
            return False

    async def get_monthly_aggregates(self, month_keys: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Retrieve monthly aggregate metrics for specified months.

        Fetches the METRICS_SUMMARY record and extracts counters for
        the requested month keys.

        Args:
            month_keys: List of month identifiers in YYYY_MM format
                       (e.g., ['2025_09', '2025_10'])

        Returns:
            Dictionary mapping month keys to their metrics:
            {
                '2025_10': {
                    'auto_status_posts': 45,
                    'war_room_sent': 450,
                    'war_room_success': 445,
                    'war_room_failed': 5,
                    'war_room_unique_users': 128
                },
                '2025_09': {...}
            }

        Example:
            aggregates = await db_store.get_monthly_aggregates(
                ['2025_09', '2025_10']
            )
            sept_posts = aggregates['2025_09']['auto_status_posts']
        """
        try:
            response = await self.client.get_item(
                table_name=self.table_name,
                key={"PK": {"S": "METRICS_SUMMARY"}, "SK": {"S": "AGGREGATES"}},
            )

            if not response or "Item" not in response:
                logger.warning("METRICS_SUMMARY record not found")
                return {month_key: {} for month_key in month_keys}

            item = response["Item"]

            # Extract metrics for requested months
            result = {}
            for month_key in month_keys:
                month_metrics = {}

                # Counter prefixes to look for
                counter_prefixes = [
                    "auto_status_posts",
                    "war_room_sent",
                    "war_room_success",
                    "war_room_failed",
                    "war_room_unique_users",
                ]

                for prefix in counter_prefixes:
                    field_name = f"{prefix}_{month_key}"
                    if field_name in item:
                        # Extract number value from DynamoDB format
                        value = item[field_name].get("N", "0")
                        month_metrics[prefix] = int(value)
                    else:
                        month_metrics[prefix] = 0

                result[month_key] = month_metrics

            logger.debug(f"Retrieved aggregates for {len(month_keys)} months")
            return result

        except Exception as e:
            logger.error(f"Failed to get monthly aggregates: {e}")
            return {month_key: {} for month_key in month_keys}
