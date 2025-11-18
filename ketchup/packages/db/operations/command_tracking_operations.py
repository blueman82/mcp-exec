"""
command_tracking_operations.py

This module provides operations for tracking and querying command usage data in DynamoDB.
It allows logging of commands executed by users and retrieving usage statistics.
"""

import datetime
import time
from datetime import datetime as dt
from datetime import timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from packages.core.logging import setup_logger
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)


def get_current_week_timestamps() -> Tuple[int, int]:
    """
    Get timestamps for current week (Monday 00:00 to Sunday 23:59:59 UTC).

    Returns:
        Tuple[int, int]: (start_timestamp, end_timestamp) for the current week
    """
    now = dt.now(timezone.utc)
    # Find this week's Monday (weekday: Monday = 0, Sunday = 6)
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    monday_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)

    # Sunday end (6 days after Monday, at 23:59:59)
    sunday_end = monday_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return int(monday_start.timestamp()), int(sunday_end.timestamp())


def get_previous_week_timestamps() -> Tuple[int, int]:
    """
    Get timestamps for previous week (Monday 00:00 to Sunday 23:59:59 UTC).

    Returns:
        Tuple[int, int]: (start_timestamp, end_timestamp) for the previous week
    """
    current_start, _ = get_current_week_timestamps()
    # Previous week starts 7 days before current week
    previous_start = current_start - (7 * 86400)  # 7 days in seconds
    previous_end = current_start - 1  # One second before current week starts

    return previous_start, previous_end


def get_week_date_range(timestamp: Optional[int] = None) -> str:
    """
    Get formatted date range for the week containing the given timestamp.

    Args:
        timestamp: Unix timestamp (defaults to current time)

    Returns:
        str: Formatted date range like "Dec 16-22, 2024"
    """
    if timestamp is None:
        now = dt.now(timezone.utc)
    else:
        now = dt.fromtimestamp(timestamp, tz=timezone.utc)

    # Find Monday of that week
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    monday_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday_start + timedelta(days=6)

    # Format the date range
    if monday.month == sunday.month:
        return f"{monday.strftime('%b %d')}-{sunday.strftime('%d, %Y')}"
    else:
        return f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d, %Y')}"


class CommandTrackingOperations(BaseOperations):
    """
    Operations for tracking and querying command usage in DynamoDB.

    This class provides methods to log command executions and retrieve
    command usage statistics for specific users.
    """

    # Re-use the existing shared table rather than a dedicated command-tracking table.
    # This keeps all bot-related data in one place while still allowing a distinct
    # PK/SK pattern (USER#… / COMMAND#…) that will *not* clash with the existing
    # channel records (CHANNEL#… / CSO_DETAILS).
    TABLE_NAME = "ketchup_channel_information"

    def __init__(self, dynamodb_client=None, table_name=None):
        """
        Initialize CommandTrackingOperations with optional custom client and table name.

        Args:
            dynamodb_client: Optional custom DynamoDB client
            table_name: Optional custom table name (defaults to ketchup_command_tracking)
        """
        # Resolve the table name before calling the base initializer
        effective_table_name = table_name or self.TABLE_NAME
        # BaseOperations expects both the client and the table name
        super().__init__(dynamodb_client, effective_table_name)
        # Store table name for local reference/consistency
        self.table_name = effective_table_name
        logger.info(
            f"CommandTrackingOperations initialized with table: {self.table_name}"
        )

    async def log_command(
        self,
        user_id: str,
        user_name: str,
        command_type: str,
        channel_id: str = "",
        command_text: str = "",
    ) -> bool:
        """
        Log a command execution to DynamoDB.

        Args:
            user_id: The Slack user ID of the user who executed the command
            user_name: The Slack username of the user who executed the command
            command_type: The type of command executed (e.g., 'status', 'report', 'analyze')
            channel_id: Optional channel ID where the command was executed
            command_text: Optional full text of the command

        Returns:
            bool: True if the command was logged successfully, False otherwise
        """
        try:
            # Generate timestamp for the current time
            timestamp = int(time.time())

            # Create the item to store in DynamoDB with proper type formatting
            item = {
                "PK": {"S": f"USER#{user_id}"},
                "SK": {"S": f"COMMAND#{timestamp}#{command_type}"},
                "user_id": {"S": user_id},
                "user_name": {"S": user_name},
                "command_type": {"S": command_type},
                "timestamp": {"N": str(timestamp)},
                "channel_id": {"S": channel_id},
                "command_text": {"S": command_text},
                "execution_date": {
                    "S": datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                },
                "execution_time": {
                    "S": datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
                },
            }

            # Put the item in DynamoDB
            await self.client.put_item(
                item=item,
                table_name=self.table_name,
            )
            logger.info(
                f"Command logged: user={user_id}, type={command_type}, timestamp={timestamp}"
            )
            return True

        except Exception as e:
            logger.error(f"Error logging command: {str(e)}")
            return False

    async def get_user_command_stats(
        self, user_id: str, days: int = 7
    ) -> Dict[str, int]:
        """
        Get aggregated command statistics for a user for the current week.

        Args:
            user_id: The Slack user ID to get statistics for
            days: Ignored - kept for backward compatibility

        Returns:
            Dict[str, int]: Dictionary mapping command types to their counts
        """
        try:
            # Get current week timestamps (Monday to Sunday)
            start_timestamp, end_timestamp = get_current_week_timestamps()

            # Query DynamoDB for commands within the current week
            commands = await self.get_recent_commands(
                user_id, start_timestamp, end_timestamp
            )

            # Aggregate commands by type
            command_counts: Dict[str, int] = {}
            for command in commands:
                command_type = command.get("command_type", "unknown")
                command_counts[command_type] = command_counts.get(command_type, 0) + 1

            logger.info(f"Retrieved command stats for user {user_id}: {command_counts}")
            return command_counts

        except Exception as e:
            logger.error(f"Error getting user command stats: {str(e)}")
            return {}

    async def get_recent_commands(
        self,
        user_id: str,
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get raw command data for a user within a specified time range.

        Args:
            user_id: The Slack user ID to get commands for
            start_timestamp: Optional start timestamp (inclusive)
            end_timestamp: Optional end timestamp (inclusive)

        Returns:
            List[Dict[str, Any]]: List of command records
        """
        try:
            # Prepare the query parameters
            key_condition = "PK = :pk"
            expression_values = {":pk": {"S": f"USER#{user_id}"}}

            # Add time range conditions if provided
            if start_timestamp is not None:
                key_condition += " AND SK BETWEEN :start_sk AND :end_sk"
                expression_values[":start_sk"] = {"S": f"COMMAND#{start_timestamp}"}
                # Use 'COMMAND$' as upper bound to exclude METADATA and other non-command records
                # '$' comes after '#' in ASCII, so this includes all COMMAND# records
                expression_values[":end_sk"] = {"S": "COMMAND$"}

                if end_timestamp is not None:
                    # Override end_sk with specific timestamp if provided
                    expression_values[":end_sk"] = {
                        "S": f"COMMAND#{end_timestamp + 1}#~"
                    }
            else:
                # No start timestamp, so just filter for COMMAND# prefix
                key_condition += " AND begins_with(SK, :sk_prefix)"
                expression_values[":sk_prefix"] = {"S": "COMMAND#"}

            # Query DynamoDB
            response = await self.client.query(
                key_condition_expression=key_condition,
                expression_attribute_values=expression_values,
                table_name=self.table_name,
            )

            # Extract and return the items
            commands = []
            for item in response.get("Items", []):
                normalized_item = self._normalize_item(item)
                commands.append(normalized_item)

            logger.info(f"Retrieved {len(commands)} recent commands for user {user_id}")
            return commands

        except Exception as e:
            logger.error(f"Error getting recent commands: {str(e)}")
            return []

    async def get_top_users(
        self, days: int = 7, limit: int = 10
    ) -> List[Tuple[str, str, int]]:
        """
        Get the top users by command count for the current week.

        Args:
            days: Ignored - kept for backward compatibility
            limit: Maximum number of users to return (default: 10)

        Returns:
            List[Tuple[str, str, int]]: List of (user_id, user_name, command_count) tuples
        """
        try:
            # Get current week timestamps (Monday to Sunday)
            start_timestamp, end_timestamp = get_current_week_timestamps()

            # This requires a full table scan with filtering, which is not ideal for large tables
            # In a production environment, consider using a GSI or analytics solution
            # "timestamp" is a DynamoDB reserved word, so we must alias it via
            # ExpressionAttributeNames.
            # Filter for command records only (PK starts with USER# and SK starts with COMMAND#)
            response = await self.client.scan(
                filter_expression="#ts >= :start AND #ts <= :end AND begins_with(PK, :pk_prefix) AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":start": {"N": str(start_timestamp)},
                    ":end": {"N": str(end_timestamp)},
                    ":pk_prefix": {"S": "USER#"},
                    ":sk_prefix": {"S": "COMMAND#"},
                },
                expression_attribute_names={"#ts": "timestamp"},
                table_name=self.table_name,
            )

            # Normalize the items
            normalized_items = []
            for item in response.get("Items", []):
                normalized_items.append(self._normalize_item(item))

            # Group by user_id and count commands
            user_counts: Dict[str, Dict[str, Any]] = {}
            for item in normalized_items:
                user_id = item.get("user_id")
                user_name = item.get("user_name", "unknown")

                # Skip records without user_id (shouldn't happen with our filter, but safety check)
                if not user_id:
                    logger.warning(f"Skipping record without user_id: {item}")
                    continue

                # Skip Gary Harrison from statistics
                if user_id == "W7MGASQ2K":
                    continue

                if user_id not in user_counts:
                    user_counts[user_id] = {"user_name": user_name, "count": 0}

                user_counts[user_id]["count"] += 1

            # Convert to list of tuples and sort by count (descending)
            user_list = [
                (uid, data["user_name"], data["count"])
                for uid, data in user_counts.items()
            ]
            user_list.sort(key=lambda x: x[2], reverse=True)

            # Get the top users
            top_users = user_list[:limit]

            # Fetch real names for the top users
            user_ids_to_fetch = [user[0] for user in top_users]
            real_names = await self._get_user_real_names(user_ids_to_fetch)

            # Replace usernames with real names
            enriched_top_users = []
            for user_id, user_name, count in top_users:
                real_name = real_names.get(
                    user_id, user_name
                )  # Fallback to username if not found
                enriched_top_users.append((user_id, real_name, count))

            logger.info(
                f"Retrieved top {len(enriched_top_users)} users over the past {days} days"
            )
            return enriched_top_users

        except Exception as e:
            logger.error(f"Error getting top users: {str(e)}")
            return []

    async def get_user_command_breakdown(
        self, days: int = 7, limit: int = 10
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed command breakdown for each user for the current week.

        Args:
            days: Ignored - kept for backward compatibility
            limit: Maximum number of users to return (default: 10)

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping user_id to {user_name, commands: {command_type: count}}
        """
        try:
            # Get current week timestamps (Monday to Sunday)
            start_timestamp, end_timestamp = get_current_week_timestamps()

            # Scan for all command records in the time window
            response = await self.client.scan(
                filter_expression="#ts >= :start AND #ts <= :end AND begins_with(PK, :pk_prefix) AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":start": {"N": str(start_timestamp)},
                    ":end": {"N": str(end_timestamp)},
                    ":pk_prefix": {"S": "USER#"},
                    ":sk_prefix": {"S": "COMMAND#"},
                },
                expression_attribute_names={"#ts": "timestamp"},
                table_name=self.table_name,
            )

            # Normalize the items
            normalized_items = []
            for item in response.get("Items", []):
                normalized_items.append(self._normalize_item(item))

            # Group by user_id and command_type
            user_command_breakdown: Dict[str, Dict[str, Any]] = {}
            for item in normalized_items:
                user_id = item.get("user_id")
                user_name = item.get("user_name", "unknown")
                command_type = item.get("command_type", "unknown")

                # Skip records without user_id
                if not user_id:
                    logger.warning(f"Skipping record without user_id: {item}")
                    continue

                # Skip Gary Harrison from statistics
                if user_id == "W7MGASQ2K":
                    continue

                # Initialize user entry if not exists
                if user_id not in user_command_breakdown:
                    user_command_breakdown[user_id] = {
                        "user_name": user_name,
                        "commands": {},
                        "total_count": 0,
                    }

                # Increment command count
                if command_type not in user_command_breakdown[user_id]["commands"]:
                    user_command_breakdown[user_id]["commands"][command_type] = 0

                user_command_breakdown[user_id]["commands"][command_type] += 1
                user_command_breakdown[user_id]["total_count"] += 1

            # Sort users by total command count and limit
            sorted_users = sorted(
                user_command_breakdown.items(),
                key=lambda x: x[1]["total_count"],
                reverse=True,
            )[:limit]

            # Fetch real names for all users
            user_ids = [user_id for user_id, _ in sorted_users]
            real_names = await self._get_user_real_names(user_ids)

            # Convert back to dict with real names
            result = {}
            for user_id, data in sorted_users:
                # Sort commands by count for each user
                sorted_commands = dict(
                    sorted(data["commands"].items(), key=lambda x: x[1], reverse=True)
                )
                # Use real name if available, fallback to username
                display_name = real_names.get(user_id, data["user_name"])
                result[user_id] = {
                    "user_name": display_name,
                    "commands": sorted_commands,
                    "total_count": data["total_count"],
                }

            logger.info(
                f"Retrieved command breakdown for {len(result)} users over the past {days} days"
            )
            return result

        except Exception as e:
            logger.error(f"Error getting user command breakdown: {str(e)}")
            return {}

    async def _get_period_data(self, start_ts: int, end_ts: int) -> Dict[str, Any]:
        """
        Get command data for a specific time period.

        Args:
            start_ts: Start timestamp
            end_ts: End timestamp

        Returns:
            Dict with commands and users data
        """
        try:
            # Scan for all command records in the time window
            response = await self.client.scan(
                filter_expression="#ts >= :start AND #ts < :end AND begins_with(PK, :pk_prefix) AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":start": {"N": str(start_ts)},
                    ":end": {"N": str(end_ts)},
                    ":pk_prefix": {"S": "USER#"},
                    ":sk_prefix": {"S": "COMMAND#"},
                },
                expression_attribute_names={"#ts": "timestamp"},
                table_name=self.table_name,
            )

            # Aggregate data
            commands = {}
            users = {}

            for item in response.get("Items", []):
                normalized_item = self._normalize_item(item)
                command_type = normalized_item.get("command_type", "unknown")
                user_id = normalized_item.get("user_id")

                # Count commands
                commands[command_type] = commands.get(command_type, 0) + 1

                # Count user activity
                if user_id and user_id != "W7MGASQ2K":  # Skip Gary Harrison
                    users[user_id] = users.get(user_id, 0) + 1

            return {"commands": commands, "users": users}

        except Exception as e:
            logger.error(f"Error getting period data: {str(e)}")
            return {"commands": {}, "users": {}}

    async def _get_user_real_names(self, user_ids: List[str]) -> Dict[str, str]:
        """
        Fetch real names for a list of user IDs from USER metadata records.

        Args:
            user_ids: List of user IDs to fetch real names for

        Returns:
            Dict mapping user_id to real_name
        """
        if not user_ids:
            return {}

        try:
            real_names = {}
            batch_size = 100  # DynamoDB batch get limit

            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i : i + batch_size]
                keys = [
                    {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "METADATA"}}
                    for user_id in batch
                    if user_id and isinstance(user_id, str)
                ]

                if not keys:
                    continue

                # Get the underlying aioboto3 client
                underlying_client = await self.client._get_client()

                # Use the underlying client to make the batch_get_item call
                request_items = {self.table_name: {"Keys": keys}}
                response = await underlying_client.batch_get_item(
                    RequestItems=request_items
                )

                items = response.get("Responses", {}).get(self.table_name, [])
                for item in items:
                    # Extract user_id from PK
                    pk = item.get("PK", {}).get("S", "")
                    if pk.startswith("USER#"):
                        user_id = pk.replace("USER#", "")
                        real_name = item.get("real_name", {}).get("S", user_id)
                        real_names[user_id] = real_name

            return real_names

        except Exception as e:
            logger.error(f"Error fetching user real names: {str(e)}")
            return {}

    def _calculate_trends(
        self, current_data: Dict[str, Any], previous_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate trends between two periods.

        Args:
            current_data: Current period data
            previous_data: Previous period data

        Returns:
            Trends with deltas and percentages
        """
        trends = {"commands": {}, "total_usage": {}}

        # Get all unique commands
        all_commands = set(current_data.get("commands", {}).keys()) | set(
            previous_data.get("commands", {}).keys()
        )

        # Calculate command trends
        for cmd in all_commands:
            current = current_data.get("commands", {}).get(cmd, 0)
            previous = previous_data.get("commands", {}).get(cmd, 0)
            delta = current - previous

            if previous > 0:
                percent = (delta / previous) * 100
            else:
                percent = 100.0 if current > 0 else 0.0

            trends["commands"][cmd] = {
                "current": current,
                "previous": previous,
                "delta": delta,
                "percent": percent,
            }

        # Calculate total usage trends
        current_total = sum(current_data.get("commands", {}).values())
        previous_total = sum(previous_data.get("commands", {}).values())
        total_delta = current_total - previous_total

        if previous_total > 0:
            total_percent = (total_delta / previous_total) * 100
        else:
            total_percent = 100.0 if current_total > 0 else 0.0

        trends["total_usage"] = {
            "current": current_total,
            "previous": previous_total,
            "delta": total_delta,
            "percent": total_percent,
        }

        return trends

    async def get_command_trends(
        self, days: int = 7, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get command usage trends comparing current period with previous period.

        Returns:
            {
                "current_period": {
                    "start": timestamp,
                    "end": timestamp,
                    "commands": {"status": 45, "report": 32, ...},
                    "users": {"user123": 20, ...}
                },
                "previous_period": {
                    "start": timestamp,
                    "end": timestamp,
                    "commands": {"status": 40, "report": 35, ...},
                    "users": {"user123": 18, ...}
                },
                "trends": {
                    "commands": {
                        "status": {"current": 45, "previous": 40, "delta": 5, "percent": 12.5},
                        ...
                    },
                    "total_usage": {"current": 120, "previous": 110, "delta": 10, "percent": 9.1}
                }
            }
        """
        try:
            # Get current and previous week timestamps
            current_start, current_end = get_current_week_timestamps()
            previous_start, previous_end = get_previous_week_timestamps()

            # Get data for both periods using existing scan logic
            current_data = await self._get_period_data(current_start, current_end)
            previous_data = await self._get_period_data(previous_start, current_start)

            # Calculate trends
            trends = self._calculate_trends(current_data, previous_data)

            return {
                "current_period": {
                    "start": current_start,
                    "end": current_end,
                    **current_data,
                },
                "previous_period": {
                    "start": previous_start,
                    "end": current_start,
                    **previous_data,
                },
                "trends": trends,
            }

        except Exception as e:
            logger.error(f"Error getting command trends: {str(e)}")
            return {}

    async def get_full_export_data(self, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive data for CSV export including all users and commands.
        """
        try:
            # Get trends data
            trends_data = await self.get_command_trends(days=days, limit=None)

            # Get detailed user breakdown (no limit for export)
            user_breakdown = await self.get_user_command_breakdown(
                days=days, limit=None
            )

            # Get top metrics (no limit for export)
            top_users = await self.get_top_users(days=days, limit=None)

            # Get current week date range
            current_week_range = get_week_date_range()

            return {
                "trends": trends_data,
                "user_breakdown": user_breakdown,
                "top_users": top_users,
                "export_timestamp": dt.now(timezone.utc).isoformat(),
                "period_days": days,
                "current_week_range": current_week_range,
                "previous_week_range": get_week_date_range(
                    get_previous_week_timestamps()[0]
                ),
            }

        except Exception as e:
            logger.error(f"Error getting export data: {str(e)}")
            return {}
