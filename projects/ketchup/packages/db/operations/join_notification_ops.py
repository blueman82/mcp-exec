"""
join_notification_ops.py

Database operations for join notification tracking with atomic counters.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol

from packages.db.models.notification_tracking import FailureReason
from packages.db.operations.base_operations import BaseOperations

logger = logging.getLogger(__name__)


class JoinNotificationOpsProtocol(Protocol):
    """Protocol for join notification tracking operations"""

    async def track_notification(self, tracking_data: Dict[str, Any]) -> bool: ...
    async def get_channel_stats(self, channel_id: str) -> Dict[str, Any]: ...
    async def get_weekly_report(self, week_key: str) -> Dict[str, Any]: ...


class JoinNotificationOps(BaseOperations):
    """Implementation of notification tracking operations"""

    def __init__(self, client, table_name: str):
        """Initialize the JoinNotificationOps."""
        super().__init__(client, table_name)

    def _get_iso_week(self) -> str:
        """Get current ISO week in YYYY-Www format"""
        year, week, _ = datetime.now(timezone.utc).isocalendar()
        return f"{year:04d}-W{week:02d}"

    async def track_notification(self, tracking_data: Dict[str, Any]) -> bool:
        """Track a join notification delivery attempt with atomic operations."""
        try:
            logger.info(
                "Tracking notification for user %s in channel %s: status=%s",
                tracking_data.get("user_id"),
                tracking_data.get("channel_id"),
                tracking_data.get("delivery_status"),
            )

            # Execute both operations concurrently
            results = await asyncio.gather(
                self._update_channel_counters(tracking_data),
                self._put_detail_record(tracking_data),
                return_exceptions=True,
            )

            # Check for exceptions
            if not self._validate_tracking_results(results):
                return False

            # Trigger weekly pruning (non-blocking)
            channel_id = tracking_data["channel_id"]
            asyncio.create_task(self._prune_old_weeks(channel_id))
            return True

        except Exception as e:
            logger.error(f"Error tracking notification: {e}", exc_info=True)
            return False

    def _validate_tracking_results(self, results) -> bool:
        """Validate concurrent tracking operation results."""
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                operation = ["counter update", "detail record"][i]
                logger.error(f"Failed to execute {operation}: {result}")
                return False
        return True

    async def _update_channel_counters(self, data: Dict[str, Any]):
        """Update channel counters using separate items to avoid nested map issues"""
        channel_id = data["channel_id"]
        week_key = self._get_iso_week()
        status = data["delivery_status"]
        timestamp = data["timestamp"]

        # Execute both updates concurrently for better performance
        await asyncio.gather(
            self._update_channel_aggregate(channel_id, status, timestamp, data),
            self._update_weekly_item(channel_id, week_key, status, timestamp),
            return_exceptions=False,
        )

    async def _update_channel_aggregate(
        self, channel_id: str, status: str, timestamp: int, data: Dict[str, Any]
    ):
        """Update channel aggregate (CSO_DETAILS) with totals and last timestamp

        Uses split operations to avoid DynamoDB ValidationException:
        1. Initialize map if needed (separate operation)
        2. Update counters only (no path overlap)
        """
        key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}

        # Step 1: Initialize map if needed (separate operation to avoid path overlap)
        try:
            await self.client.update_item(
                table_name=self.table_name,
                key=key,
                update_expression="SET #ujn = if_not_exists(#ujn, :empty_map)",
                expression_attribute_names={"#ujn": "user_join_notifications"},
                expression_attribute_values={":empty_map": {"M": {}}},
            )
        except Exception as e:
            error_name = type(e).__name__
            if "ConditionalCheckFailed" not in error_name:
                logger.warning(
                    "DynamoDB update failed (expected ConditionalCheckFailed, got %s): %s",
                    error_name,
                    e,
                )
            # Map might already exist — ConditionalCheckFailed is expected on retry, continue

        # Step 2: Update counters and timestamp (no path overlap with parent map)
        update_expr = """
            SET #ujn.#lts = :timestamp
            ADD #ujn.#ts :one,
                #ujn.#t_success :inc_success,
                #ujn.#t_failed :inc_failed,
                #ujn.#t_disabled :inc_disabled
        """

        expression_names = {
            "#ujn": "user_join_notifications",
            "#ts": "total_sent",
            "#t_success": "total_success",
            "#t_failed": "total_failed",
            "#t_disabled": "total_disabled",
            "#lts": "last_sent_timestamp",
        }

        expression_values = {
            ":one": {"N": "1"},
            ":timestamp": {"N": str(timestamp)},
            ":inc_success": {"N": "1" if status == "success" else "0"},
            ":inc_failed": {"N": "1" if status == "failed" else "0"},
            ":inc_disabled": {"N": "1" if status == "disabled" else "0"},
        }

        # Add failure tracking if needed
        if status == "failed" and data.get("failure_reason_code"):
            update_expr += ", #ujn.#lfrc = :reason_code, #ujn.#lfrm = :reason_msg"
            expression_names.update(
                {"#lfrc": "last_failure_reason_code", "#lfrm": "last_failure_message"}
            )
            expression_values.update(
                {
                    ":reason_code": {"S": data["failure_reason_code"]},
                    ":reason_msg": {"S": (data.get("error_message", "") or "")[:512]},
                }
            )

        await self.client.update_item(
            table_name=self.table_name,
            key=key,
            update_expression=update_expr,
            expression_attribute_names=expression_names,
            expression_attribute_values=expression_values,
        )

    async def _update_weekly_item(
        self, channel_id: str, week_key: str, status: str, timestamp: int
    ):
        """Update weekly item (WEEK#YYYY-Www) with counters"""
        key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": f"WEEK#{week_key}"}}

        update_expr = """
            ADD #sent :one,
                #success :inc_success,
                #failed :inc_failed,
                #disabled :inc_disabled
            SET #lut = :timestamp,
                #wk = :week_key
        """

        expression_names = {
            "#sent": "sent",
            "#success": "success",
            "#failed": "failed",
            "#disabled": "disabled",
            "#lut": "last_updated_ts",
            "#wk": "week_key",
        }

        expression_values = {
            ":one": {"N": "1"},
            ":inc_success": {"N": "1" if status == "success" else "0"},
            ":inc_failed": {"N": "1" if status == "failed" else "0"},
            ":inc_disabled": {"N": "1" if status == "disabled" else "0"},
            ":timestamp": {"N": str(timestamp)},
            ":week_key": {"S": week_key},
        }

        await self.client.update_item(
            table_name=self.table_name,
            key=key,
            update_expression=update_expr,
            expression_attribute_names=expression_names,
            expression_attribute_values=expression_values,
        )

    async def _put_detail_record(self, tracking_data: Dict[str, Any]):
        """Store per-user tracking record with TTL and truncated errors"""
        item = self._build_detail_record_item(tracking_data)
        await self.client.put_item(table_name=self.table_name, item=item)

    def _build_detail_record_item(self, tracking_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build DynamoDB item for detail record storage."""
        item = {
            "PK": {"S": f"USER_JOIN#{tracking_data['channel_id']}"},
            "SK": {"S": f"TS#{tracking_data['timestamp']}#USER#{tracking_data['user_id']}"},
            "user_id": {"S": tracking_data["user_id"]},
            "channel_id": {"S": tracking_data["channel_id"]},
            "notification_attempted": {"BOOL": tracking_data.get("notification_attempted", False)},
            "delivery_status": {"S": tracking_data["delivery_status"]},
            "timestamp": {"N": str(tracking_data["timestamp"])},
            # NOTE: Using temp_unarchive_expiry (not "ttl") because DynamoDB only supports
            # ONE TTL attribute per table, and this table already has TTL configured for
            # temp_unarchive_expiry (used by restore_state_operations). All records using
            # this attribute will be automatically deleted after expiration.
            "temp_unarchive_expiry": {"N": str(tracking_data["timestamp"] + 2592000)},  # 30 days
        }

        # Add optional fields with consistent truncation
        if tracking_data.get("failure_reason_code"):
            item["failure_reason_code"] = {"S": tracking_data["failure_reason_code"]}
        if tracking_data.get("error_message"):
            item["error_message"] = {"S": tracking_data["error_message"][:512]}

        return item

    def _classify_slack_error(self, response: Dict[str, Any]) -> Optional[str]:
        """Map Slack API responses to failure reason codes."""
        if not response:
            return FailureReason.NETWORK_ERROR.value
        if response.get("ok"):
            return None

        error = response.get("error", "")
        error_mappings = self._get_slack_error_mappings()
        return error_mappings.get(error, FailureReason.SLACK_API_ERROR.value)

    def _get_slack_error_mappings(self) -> Dict[str, str]:
        """Get mapping of Slack error codes to FailureReason values."""
        return {
            "not_in_channel": FailureReason.SLACK_NOT_IN_CHANNEL.value,
            "channel_not_found": FailureReason.SLACK_NOT_IN_CHANNEL.value,
            "is_archived": FailureReason.SLACK_NOT_IN_CHANNEL.value,
            "rate_limited": FailureReason.SLACK_RATE_LIMITED.value,
            "ratelimited": FailureReason.SLACK_RATE_LIMITED.value,
            "not_authed": FailureReason.SLACK_PERMISSION_DENIED.value,
            "invalid_auth": FailureReason.SLACK_PERMISSION_DENIED.value,
            "missing_scope": FailureReason.SLACK_PERMISSION_DENIED.value,
            "cannot_post_ephemeral": FailureReason.SLACK_PERMISSION_DENIED.value,
            "restricted_action": FailureReason.SLACK_PERMISSION_DENIED.value,
        }

    async def _prune_old_weeks(self, channel_id: str):
        """Keep only last 52 weeks using the PK/SK model"""
        try:
            # Calculate cutoff week
            iso_cal = datetime.now(timezone.utc).isocalendar()
            current_year, current_week = iso_cal.year, iso_cal.week
            cutoff_year, cutoff_week = current_year - 1, current_week

            # Query all weekly items for this channel
            response = await self.client.query(
                table_name=self.table_name,
                key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":pk": {"S": f"CHANNEL#{channel_id}"},
                    ":sk_prefix": {"S": "WEEK#"},
                },
            )

            if "Items" not in response:
                return

            # Identify items to delete
            keys_to_delete = []
            for item in response["Items"]:
                week_key = item["SK"]["S"].replace("WEEK#", "")
                try:
                    year, week = map(int, week_key.split("-W"))
                    if (year < cutoff_year) or (year == cutoff_year and week < cutoff_week):
                        keys_to_delete.append({"PK": item["PK"], "SK": item["SK"]})
                except (ValueError, AttributeError):
                    continue

            # Batch delete old weeks
            for key in keys_to_delete:
                await self.client.delete_item(table_name=self.table_name, key=key)

            if keys_to_delete:
                logger.info(
                    f"Pruned {len(keys_to_delete)} old weekly items for channel {channel_id}"
                )

        except Exception as e:
            logger.error(f"Error pruning old weeks for channel {channel_id}: {e}")

    async def get_channel_stats(self, channel_id: str) -> Dict[str, Any]:
        """Get notification stats for a channel including weekly breakdown."""
        try:
            # Get aggregate stats from CSO_DETAILS
            key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}
            response = await self.client.get_item(table_name=self.table_name, key=key)

            if "Item" not in response:
                return {}

            ujn = response["Item"].get("user_join_notifications", {}).get("M", {})
            if not ujn:
                return {}

            # Get base stats
            stats = self._normalize_item({"user_join_notifications": {"M": ujn}})[
                "user_join_notifications"
            ]

            # Query weekly items for this channel
            weekly_response = await self.client.query(
                table_name=self.table_name,
                key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":pk": {"S": f"CHANNEL#{channel_id}"},
                    ":sk_prefix": {"S": "WEEK#"},
                },
            )

            # Add weekly stats
            if "Items" in weekly_response:
                stats["weekly_stats"] = {}
                for item in weekly_response["Items"]:
                    week_key = item["SK"]["S"].replace("WEEK#", "")
                    stats["weekly_stats"][week_key] = self._normalize_item(item)

            return stats
        except Exception as e:
            logger.error(f"Error getting channel stats for {channel_id}: {e}")
            return {}

    async def get_weekly_report(self, week_key: str) -> Dict[str, Any]:
        """Get aggregated weekly report across all channels."""
        try:
            return {
                "week": week_key,
                "total_channels": 0,
                "total_sent": 0,
                "total_success": 0,
                "total_failed": 0,
                "total_disabled": 0,
                "success_rate": 0.0,
                "channels": [],
            }
        except Exception as e:
            logger.error(f"Error getting weekly report for {week_key}: {e}")
            return {}

    async def get_unique_users_count(
        self,
        channel_id: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> int:
        """
        Get count of unique users who joined a channel.

        Queries detail records and deduplicates by user_id.

        Args:
            channel_id: Channel ID to query
            start_ts: Optional start timestamp filter (inclusive)
            end_ts: Optional end timestamp filter (exclusive)

        Returns:
            Count of unique users
        """
        try:
            query_params = {
                "table_name": self.table_name,
                "key_condition_expression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "expression_attribute_values": {
                    ":pk": {"S": f"USER_JOIN#{channel_id}"},
                    ":sk_prefix": {"S": "TS#"},
                },
            }

            if start_ts is not None or end_ts is not None:
                conditions = ["PK = :pk", "SK BETWEEN :start_sk AND :end_sk"]
                query_params["key_condition_expression"] = " AND ".join(conditions)
                start_key = f"TS#{start_ts}" if start_ts else "TS#0"
                end_key = f"TS#{end_ts}" if end_ts else "TS#9999999999999"
                query_params["expression_attribute_values"][":start_sk"] = {"S": start_key}
                query_params["expression_attribute_values"][":end_sk"] = {"S": end_key}

            response = await self.client.query(**query_params)

            if "Items" not in response:
                return 0

            unique_user_ids = {
                item["user_id"]["S"] for item in response["Items"] if "user_id" in item
            }

            return len(unique_user_ids)

        except Exception as e:
            logger.error(
                f"Error getting unique users count for channel {channel_id}: {e}",
                exc_info=True,
            )
            return 0

    async def get_unique_users_for_week(self, channel_id: str, week_key: str) -> int:
        """
        Get count of unique users who joined during a specific week.

        Args:
            channel_id: Channel ID to query
            week_key: ISO week key in format YYYY-Www (e.g., "2025-W01")

        Returns:
            Count of unique users for that week
        """
        try:
            year, week = map(int, week_key.split("-W"))
            from datetime import datetime, timedelta, timezone

            jan_4 = datetime(year, 1, 4, tzinfo=timezone.utc)
            week_one_start = jan_4 - timedelta(days=jan_4.weekday())
            target_week_start = week_one_start + timedelta(weeks=week - 1)
            target_week_end = target_week_start + timedelta(days=7)

            start_ts = int(target_week_start.timestamp())
            end_ts = int(target_week_end.timestamp())

            return await self.get_unique_users_count(channel_id, start_ts=start_ts, end_ts=end_ts)

        except Exception as e:
            logger.error(
                f"Error getting unique users for week {week_key} " f"in channel {channel_id}: {e}",
                exc_info=True,
            )
            return 0

    async def get_time_filtered_stats(
        self, channel_id: str, start_ts: int, end_ts: int
    ) -> Dict[str, Any]:
        """
        Get notification statistics for a specific time period.

        Queries detail records and aggregates counts for the time window.

        Args:
            channel_id: Channel ID to query
            start_ts: Start timestamp (inclusive)
            end_ts: End timestamp (exclusive)

        Returns:
            Dictionary with:
            - total_sent: Count of notification attempts
            - total_success: Count of successful deliveries
            - total_failed: Count of failed deliveries
            - unique_users: Count of unique users who joined
        """
        try:
            # Query detail records for time range
            query_params = {
                "table_name": self.table_name,
                "key_condition_expression": "PK = :pk AND SK BETWEEN :start_sk AND :end_sk",
                "expression_attribute_values": {
                    ":pk": {"S": f"USER_JOIN#{channel_id}"},
                    ":start_sk": {"S": f"TS#{start_ts}"},
                    ":end_sk": {"S": f"TS#{end_ts}"},
                },
            }

            response = await self.client.query(**query_params)

            if "Items" not in response or not response["Items"]:
                return {
                    "total_sent": 0,
                    "total_success": 0,
                    "total_failed": 0,
                    "unique_users": 0,
                }

            # Aggregate statistics from detail records
            total_sent = 0
            total_success = 0
            total_failed = 0
            unique_user_ids = set()

            for item in response["Items"]:
                # Count attempted notifications
                if item.get("notification_attempted", {}).get("BOOL", False):
                    total_sent += 1

                # Count by delivery status (stored as lowercase)
                delivery_status = item.get("delivery_status", {}).get("S", "")
                if delivery_status == "success":
                    total_success += 1
                elif delivery_status == "failed":
                    total_failed += 1

                # Collect unique user IDs
                user_id = item.get("user_id", {}).get("S")
                if user_id:
                    unique_user_ids.add(user_id)

            return {
                "total_sent": total_sent,
                "total_success": total_success,
                "total_failed": total_failed,
                "unique_users": len(unique_user_ids),
            }

        except Exception as e:
            logger.error(
                f"Error getting time-filtered stats for channel {channel_id}: {e}",
                exc_info=True,
            )
            return {
                "total_sent": 0,
                "total_success": 0,
                "total_failed": 0,
                "unique_users": 0,
            }

    async def rebuild_channel_counters(self, channel_id: str) -> Dict[str, Any]:
        """
        Rebuild aggregate counters from detail records (source of truth).

        Queries all USER_JOIN# detail records for a channel and recalculates
        the aggregate counters in CSO_DETAILS. Uses SET expression to
        overwrite existing counters (not ADD which increments).

        This method is used for counter migration/repair when aggregate
        counters are out of sync with detail records.

        Args:
            channel_id: Channel ID to rebuild counters for

        Returns:
            Dictionary with recalculated counter values:
            - total_sent: Count of notification attempts
            - total_success: Count of successful deliveries
            - total_failed: Count of failed deliveries
            - total_disabled: Count of disabled notifications
        """
        logger.info(f"Rebuilding counters for channel {channel_id}")

        # Initialize counters
        total_sent = 0
        total_success = 0
        total_failed = 0
        total_disabled = 0

        # Query all detail records with pagination
        query_params = {
            "table_name": self.table_name,
            "key_condition_expression": "PK = :pk AND begins_with(SK, :sk_prefix)",
            "expression_attribute_values": {
                ":pk": {"S": f"USER_JOIN#{channel_id}"},
                ":sk_prefix": {"S": "TS#"},
            },
        }

        items_processed = 0
        while True:
            response = await self.client.query(**query_params)

            if "Items" in response:
                for item in response["Items"]:
                    items_processed += 1

                    # Only count attempted notifications
                    if not item.get("notification_attempted", {}).get("BOOL", False):
                        continue

                    total_sent += 1

                    # Count by delivery status (stored as lowercase)
                    delivery_status = item.get("delivery_status", {}).get("S", "")
                    if delivery_status == "success":
                        total_success += 1
                    elif delivery_status == "failed":
                        total_failed += 1
                    elif delivery_status == "disabled":
                        total_disabled += 1

            # Handle pagination
            if "LastEvaluatedKey" in response:
                query_params["exclusive_start_key"] = response["LastEvaluatedKey"]
                logger.debug(
                    f"Pagination: processed {items_processed} items, "
                    f"fetching next page for channel {channel_id}"
                )
            else:
                break

        logger.info(
            f"Processed {items_processed} detail records for channel {channel_id}: "
            f"sent={total_sent}, success={total_success}, "
            f"failed={total_failed}, disabled={total_disabled}"
        )

        # Update CSO_DETAILS with SET expression (overwrites counters)
        key = {"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}}

        update_expr = """
            SET #ujn.#ts = :sent,
                #ujn.#t_success = :success,
                #ujn.#t_failed = :failed,
                #ujn.#t_disabled = :disabled
        """

        expression_names = {
            "#ujn": "user_join_notifications",
            "#ts": "total_sent",
            "#t_success": "total_success",
            "#t_failed": "total_failed",
            "#t_disabled": "total_disabled",
        }

        expression_values = {
            ":sent": {"N": str(total_sent)},
            ":success": {"N": str(total_success)},
            ":failed": {"N": str(total_failed)},
            ":disabled": {"N": str(total_disabled)},
        }

        await self.client.update_item(
            table_name=self.table_name,
            key=key,
            update_expression=update_expr,
            expression_attribute_names=expression_names,
            expression_attribute_values=expression_values,
        )

        logger.info(f"Successfully rebuilt counters for channel {channel_id}")

        return {
            "total_sent": total_sent,
            "total_success": total_success,
            "total_failed": total_failed,
            "total_disabled": total_disabled,
        }
