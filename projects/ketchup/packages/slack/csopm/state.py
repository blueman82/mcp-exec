"""
CSOPM State Tracker Service.

This module implements the CSOPMStateTracker service for managing notification
state in DynamoDB. It tracks which CSOPM tickets have been notified about
and manages the notification lifecycle.

Follows the BaseOperations pattern established in:
packages/db/operations/base_operations.py

Architectural Note:
This is the first state persistence service for the CSOPM notification system.
It establishes patterns for how notification state is stored and queried in
DynamoDB. The partition key schema uses CSOPM_NOTIFICATION#{ticket_key} to
isolate CSOPM data from other Ketchup records in the same table.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import (
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
    FollowupRecord,
    NotificationRecord,
)
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)


# DynamoDB key prefixes for CSOPM notification records
PK_NOTIFICATION_PREFIX = "CSOPM_NOTIFICATION#"
SK_NOTIFICATION = "NOTIFICATION"
SK_FOLLOWUP_PREFIX = "FOLLOWUP#"


class CSOPMStateTracker(BaseOperations, CSOPMStateTrackerProtocol):
    """Service for tracking CSOPM notification state in DynamoDB.

    This service manages the persistence of notification records,
    tracking which tickets have been notified about and the state
    of each notification lifecycle.

    Key Schema:
    - PK: CSOPM_NOTIFICATION#{ticket_key}
    - SK: NOTIFICATION (for notification records)
    - SK: FOLLOWUP#{followup_type}#{timestamp} (for followup records)

    Inherits from BaseOperations to use shared DynamoDB utilities
    including _normalize_item for response parsing.
    """

    def __init__(self, client: DynamoDBAsyncClient, table_name: str) -> None:
        """Initialize the CSOPM state tracker.

        Args:
            client: DynamoDBAsyncClient for database access.
            table_name: The DynamoDB table name.
        """
        super().__init__(client, table_name)
        logger.info("CSOPMStateTracker initialized with table: %s", table_name)

    def _make_pk(self, ticket_key: str) -> str:
        """Generate the partition key for a notification record.

        Args:
            ticket_key: The JIRA ticket key (e.g., "CSOPM-1234")

        Returns:
            The formatted partition key.
        """
        return f"{PK_NOTIFICATION_PREFIX}{ticket_key}"

    def _make_followup_sk(self, followup_type: str, scheduled_at: datetime) -> str:
        """Generate the sort key for a followup record.

        Args:
            followup_type: Type of followup ("rca_reminder", "closure_reminder", "ping")
            scheduled_at: When the followup should be sent

        Returns:
            The formatted sort key.
        """
        timestamp = int(scheduled_at.timestamp())
        return f"{SK_FOLLOWUP_PREFIX}{followup_type}#{timestamp}"

    def _item_to_notification_record(self, item: Dict[str, Any]) -> Optional[NotificationRecord]:
        """Convert a DynamoDB item to a NotificationRecord.

        Args:
            item: Raw DynamoDB item (in DynamoDB attribute format)

        Returns:
            NotificationRecord instance, or None if parsing fails.
        """
        try:
            normalized = self._normalize_item(item)

            # Parse created_at as int if present
            created_at = normalized.get("created_at")
            if created_at is not None:
                created_at = int(created_at)

            # Parse updated_at as int if present
            updated_at = normalized.get("updated_at")
            if updated_at is not None:
                updated_at = int(updated_at)

            # Parse followup_ticket_keys as list of strings (default to empty list)
            followup_ticket_keys = normalized.get("followup_ticket_keys", [])
            if not isinstance(followup_ticket_keys, list):
                followup_ticket_keys = []

            # Parse completed_at as int if present
            completed_at = normalized.get("completed_at")
            if completed_at is not None:
                completed_at = int(completed_at)

            # Parse closed_at as int if present
            closed_at = normalized.get("closed_at")
            if closed_at is not None:
                closed_at = int(closed_at)

            return NotificationRecord(
                ticket_key=normalized.get("ticket_key", ""),
                notification_status=normalized.get("notification_status", "pending"),
                rca_ping_count=int(normalized.get("rca_ping_count", 0)),
                closure_ping_count=int(normalized.get("closure_ping_count", 0)),
                assignee_slack_id=normalized.get("assignee_slack_id"),
                assignee_jira_username=normalized.get("assignee_jira_username"),
                rca_reminder_sent=bool(normalized.get("rca_reminder_sent", False)),
                closure_reminder_sent=bool(normalized.get("closure_reminder_sent", False)),
                created_at=created_at,
                updated_at=updated_at,
                followup_ticket_keys=followup_ticket_keys,
                completed_at=completed_at,
                closed_at=closed_at,
                closure_snoozed_until=(
                    int(normalized["closure_snoozed_until"])
                    if normalized.get("closure_snoozed_until") is not None
                    else None
                ),
            )
        except Exception as e:
            logger.error("Error parsing notification record: %s", e)
            return None

    def _item_to_followup_record(self, item: Dict[str, Any]) -> Optional[FollowupRecord]:
        """Convert a DynamoDB item to a FollowupRecord.

        Args:
            item: Raw DynamoDB item (in DynamoDB attribute format)

        Returns:
            FollowupRecord instance, or None if parsing fails.
        """
        try:
            normalized = self._normalize_item(item)

            # Parse scheduled_at from epoch timestamp
            scheduled_at_epoch = normalized.get("scheduled_at", 0)
            scheduled_at = datetime.fromtimestamp(scheduled_at_epoch)

            # Parse completed_at if present
            completed_at = None
            if normalized.get("completed_at"):
                completed_at = datetime.fromtimestamp(normalized["completed_at"])

            return FollowupRecord(
                ticket_key=normalized.get("ticket_key", ""),
                followup_type=normalized.get("followup_type", ""),
                scheduled_at=scheduled_at,
                completed=bool(normalized.get("completed", False)),
                completed_at=completed_at,
            )
        except Exception as e:
            logger.error("Error parsing followup record: %s", e)
            return None

    async def get_notification_record(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Get the notification record for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            NotificationRecord if exists, None otherwise.
        """
        try:
            logger.debug("Getting notification record for: %s", ticket_key)

            key = {
                "PK": {"S": self._make_pk(ticket_key)},
                "SK": {"S": SK_NOTIFICATION},
            }

            response = await self.client.get_item(key=key, table_name=self.table_name)

            item = response.get("Item")
            if not item:
                logger.debug("No notification record found for: %s", ticket_key)
                return None

            return self._item_to_notification_record(item)

        except Exception as e:
            logger.error("Error getting notification record for %s: %s", ticket_key, e)
            return None

    async def create_notification_record(
        self, ticket: CSOPMTicket, slack_id: str
    ) -> NotificationRecord:
        """Create a new notification record for a ticket.

        Args:
            ticket: The CSOPMTicket being notified about
            slack_id: The resolved Slack user ID of the assignee

        Returns:
            The created NotificationRecord.

        Raises:
            ValueError: If ticket.key is empty (data corruption prevention).
        """
        # Validate ticket_key to prevent data corruption
        if not ticket.key or not ticket.key.strip():
            logger.error(
                "CSOPM Data Corruption Prevention: Attempted to create notification "
                "record with empty ticket_key. slack_id=%s, summary=%s",
                slack_id,
                ticket.summary[:50] if ticket.summary else "N/A",
            )
            raise ValueError("Cannot create notification record with empty ticket_key")

        logger.info(
            "Creating notification record for ticket: %s (slack_id=%s)",
            ticket.key,
            slack_id,
        )

        current_time = int(time.time())
        item = {
            "PK": {"S": self._make_pk(ticket.key)},
            "SK": {"S": SK_NOTIFICATION},
            "ticket_key": {"S": ticket.key},
            "notification_status": {"S": "pending"},
            "rca_ping_count": {"N": "0"},
            "closure_ping_count": {"N": "0"},
            "assignee_slack_id": {"S": slack_id},
            "assignee_jira_username": {"S": ticket.assignee_username},
            "rca_reminder_sent": {"BOOL": False},
            "closure_reminder_sent": {"BOOL": False},
            "created_at": {"N": str(current_time)},
            "updated_at": {"N": str(current_time)},
            "ticket_summary": {"S": ticket.summary},
            "ticket_status": {"S": ticket.status},
            "followup_ticket_keys": {"L": []},
            "assignee_history": {
                "L": [
                    {
                        "M": {
                            "jira_username": {"S": ticket.assignee_username},
                            "slack_id": {"S": slack_id},
                            "assigned_at": {"N": str(current_time)},
                        }
                    }
                ]
            },
        }

        # Add exigence_id if present
        if ticket.exigence_id:
            item["exigence_id"] = {"S": ticket.exigence_id}

        try:
            await self.client.put_item(item=item, table_name=self.table_name)
            logger.info("Created notification record for: %s", ticket.key)

            return NotificationRecord(
                ticket_key=ticket.key,
                notification_status="pending",
                rca_ping_count=0,
                closure_ping_count=0,
                assignee_slack_id=slack_id,
                assignee_jira_username=ticket.assignee_username,
                rca_reminder_sent=False,
                closure_reminder_sent=False,
                created_at=current_time,
                updated_at=current_time,
                followup_ticket_keys=[],
            )
        except Exception as e:
            logger.error("Error creating notification record for %s: %s", ticket.key, e)
            raise

    async def update_notification_status(
        self, ticket_key: str, status: str
    ) -> Optional[NotificationRecord]:
        """Update the notification status for a ticket.

        Args:
            ticket_key: The JIRA ticket key
            status: New status ("pending", "sent", "failed", "escalated")

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Updating notification status for %s to: %s", ticket_key, status)

        try:
            current_time = int(time.time())

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET notification_status = :status, updated_at = :updated_at",
                expression_attribute_values={
                    ":status": {"S": status},
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to update status for: %s", ticket_key)
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error("Error updating notification status for %s: %s", ticket_key, e)
            return None

    async def increment_rca_ping_count(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Increment the RCA ping count for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Incrementing RCA ping count for: %s", ticket_key)

        try:
            current_time = int(time.time())

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET rca_ping_count = rca_ping_count + :inc, updated_at = :updated_at",
                expression_attribute_values={
                    ":inc": {"N": "1"},
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to increment RCA ping for: %s", ticket_key)
                return None

            return self._item_to_notification_record(attributes)
        except Exception as e:
            logger.error("Error incrementing RCA ping count for %s: %s", ticket_key, e)
            return None

    async def increment_closure_ping_count(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Increment the closure ping count for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Incrementing closure ping count for: %s", ticket_key)

        try:
            current_time = int(time.time())

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET closure_ping_count = closure_ping_count + :inc, updated_at = :updated_at",
                expression_attribute_values={
                    ":inc": {"N": "1"},
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to increment closure ping for: %s", ticket_key)
                return None

            return self._item_to_notification_record(attributes)
        except Exception as e:
            logger.error("Error incrementing closure ping count for %s: %s", ticket_key, e)
            return None

    async def mark_rca_reminder_sent(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Mark the RCA reminder as sent for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Marking RCA reminder sent for: %s", ticket_key)

        try:
            current_time = int(time.time())

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET rca_reminder_sent = :val, rca_reminder_sent_at = :sent_at, updated_at = :updated_at",
                expression_attribute_values={
                    ":val": {"BOOL": True},
                    ":sent_at": {"N": str(current_time)},
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to mark RCA reminder for: %s", ticket_key)
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error("Error marking RCA reminder sent for %s: %s", ticket_key, e)
            return None

    async def mark_closure_reminder_sent(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Mark the closure reminder as sent for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Marking closure reminder sent for: %s", ticket_key)

        try:
            current_time = int(time.time())

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET closure_reminder_sent = :val, closure_reminder_sent_at = :sent_at, updated_at = :updated_at",
                expression_attribute_values={
                    ":val": {"BOOL": True},
                    ":sent_at": {"N": str(current_time)},
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to mark closure reminder for: %s", ticket_key)
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error("Error marking closure reminder sent for %s: %s", ticket_key, e)
            return None

    async def set_closure_snooze(
        self, ticket_key: str, snooze_days: int = 7
    ) -> Optional[NotificationRecord]:
        """Set closure_snoozed_until to now + snooze_days.

        Args:
            ticket_key: The JIRA ticket key
            snooze_days: Number of days to snooze (default 7)

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Setting closure snooze for %s for %d days", ticket_key, snooze_days)

        try:
            current_time = int(time.time())
            snooze_until = int(
                (datetime.now(timezone.utc) + timedelta(days=snooze_days)).timestamp()
            )

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET closure_snoozed_until = :snooze_until, updated_at = :updated_at",
                expression_attribute_values={
                    ":snooze_until": {"N": str(snooze_until)},
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to set closure snooze for: %s", ticket_key)
                return None

            logger.info(
                "Closure snooze set for %s until %d (%d days)",
                ticket_key,
                snooze_until,
                snooze_days,
            )
            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error("Error setting closure snooze for %s: %s", ticket_key, e)
            return None

    async def clear_closure_snooze(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Clear closure_snoozed_until (unsnooze).

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Clearing closure snooze for %s", ticket_key)

        try:
            current_time = int(time.time())

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="REMOVE closure_snoozed_until SET updated_at = :updated_at",
                expression_attribute_values={
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to clear closure snooze for: %s", ticket_key)
                return None

            logger.info("Closure snooze cleared for %s", ticket_key)
            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error("Error clearing closure snooze for %s: %s", ticket_key, e)
            return None

    async def get_pending_notifications(self) -> List[NotificationRecord]:
        """Get all notifications in pending state.

        Uses a scan with FilterExpression to find all notification records
        with notification_status = 'pending'.

        Returns:
            List of NotificationRecords with pending status.
        """
        logger.info("Getting all pending notifications")

        try:
            # Scan for pending notifications
            # Note: Uses scan because we don't have a GSI on notification_status
            filter_expression = (
                "begins_with(PK, :pk_prefix) AND " "SK = :sk AND " "notification_status = :status"
            )

            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": filter_expression,
                "expression_attribute_values": {
                    ":pk_prefix": {"S": PK_NOTIFICATION_PREFIX},
                    ":sk": {"S": SK_NOTIFICATION},
                    ":status": {"S": "pending"},
                },
            }

            items = []
            while True:
                response = await self.client.scan(**scan_kwargs)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key

            records: List[NotificationRecord] = []

            for item in items:
                record = self._item_to_notification_record(item)
                if record:
                    records.append(record)

            logger.info("Found %d pending notifications", len(records))
            return records

        except Exception as e:
            logger.error("Error getting pending notifications: %s", e)
            return []

    async def record_followup(
        self, ticket_key: str, followup_type: str, scheduled_at: datetime
    ) -> FollowupRecord:
        """Record a scheduled followup for a ticket.

        Args:
            ticket_key: The JIRA ticket key
            followup_type: Type of followup ("rca_reminder", "closure_reminder", "ping")
            scheduled_at: When the followup should be sent

        Returns:
            The created FollowupRecord.
        """
        logger.info(
            "Recording followup for %s: type=%s, scheduled_at=%s",
            ticket_key,
            followup_type,
            scheduled_at.isoformat(),
        )

        current_time = int(time.time())
        scheduled_epoch = int(scheduled_at.timestamp())

        item = {
            "PK": {"S": self._make_pk(ticket_key)},
            "SK": {"S": self._make_followup_sk(followup_type, scheduled_at)},
            "ticket_key": {"S": ticket_key},
            "followup_type": {"S": followup_type},
            "scheduled_at": {"N": str(scheduled_epoch)},
            "completed": {"BOOL": False},
            "created_at": {"N": str(current_time)},
        }

        try:
            await self.client.put_item(item=item, table_name=self.table_name)
            logger.info("Recorded followup for %s (type=%s)", ticket_key, followup_type)

            return FollowupRecord(
                ticket_key=ticket_key,
                followup_type=followup_type,
                scheduled_at=scheduled_at,
                completed=False,
                completed_at=None,
            )

        except Exception as e:
            logger.error("Error recording followup for %s: %s", ticket_key, e)
            raise

    async def get_all_active_notifications(self) -> List[NotificationRecord]:
        """Get all active (non-escalated) notification records.

        Scans for all notification records where notification_status is not 'escalated'.
        Used for periodic checks and monitoring.

        Returns:
            List of NotificationRecords that are still active.
        """
        logger.info("Getting all active notifications")

        try:
            # Scan for all non-escalated notifications
            filter_expression = (
                "begins_with(PK, :pk_prefix) AND "
                "SK = :sk AND "
                "notification_status <> :escalated_status"
            )

            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": filter_expression,
                "expression_attribute_values": {
                    ":pk_prefix": {"S": PK_NOTIFICATION_PREFIX},
                    ":sk": {"S": SK_NOTIFICATION},
                    ":escalated_status": {"S": "escalated"},
                },
            }

            items = []
            while True:
                response = await self.client.scan(**scan_kwargs)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key

            records: List[NotificationRecord] = []

            for item in items:
                record = self._item_to_notification_record(item)
                if record:
                    records.append(record)

            logger.info("Found %d active notifications", len(records))
            return records

        except Exception as e:
            logger.error("Error getting active notifications: %s", e)
            return []

    async def get_all_notification_records(self) -> List[NotificationRecord]:
        """Get all notification records for metrics collection.

        Scans for all notification records regardless of status.
        Used for dashboard metrics aggregation.

        Returns:
            List of all NotificationRecords.
        """
        logger.info("Getting all notification records for metrics")

        try:
            filter_expression = "begins_with(PK, :pk_prefix) AND " "SK = :sk"

            scan_kwargs: dict = {
                "table_name": self.table_name,
                "filter_expression": filter_expression,
                "expression_attribute_values": {
                    ":pk_prefix": {"S": PK_NOTIFICATION_PREFIX},
                    ":sk": {"S": SK_NOTIFICATION},
                },
            }

            items = []
            while True:
                response = await self.client.scan(**scan_kwargs)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["exclusive_start_key"] = last_key

            records: List[NotificationRecord] = []

            for item in items:
                record = self._item_to_notification_record(item)
                if record:
                    records.append(record)

            logger.info("Found %d total notification records", len(records))
            return records

        except Exception as e:
            logger.error("Error getting all notification records: %s", e)
            return []

    async def handle_reassignment(
        self,
        ticket_key: str,
        new_jira_username: str,
        new_slack_id: str,
    ) -> Optional[NotificationRecord]:
        """Handle ticket reassignment by updating assignee and resetting ping counts.

        When a ticket is reassigned:
        1. Updates assignee_jira_username and assignee_slack_id
        2. Resets rca_ping_count and closure_ping_count to 0 (fresh start for new assignee)
        3. Appends new assignee to assignee_history

        Args:
            ticket_key: The JIRA ticket key
            new_jira_username: The new assignee's JIRA username
            new_slack_id: The new assignee's Slack user ID

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info(
            "Handling reassignment for %s to %s (slack_id=%s)",
            ticket_key,
            new_jira_username,
            new_slack_id,
        )

        try:
            current_time = int(time.time())

            # Build the new history entry
            new_history_entry = {
                "M": {
                    "jira_username": {"S": new_jira_username},
                    "slack_id": {"S": new_slack_id},
                    "assigned_at": {"N": str(current_time)},
                }
            }

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression=(
                    "SET assignee_jira_username = :jira_user, "
                    "assignee_slack_id = :slack_id, "
                    "rca_ping_count = :zero, "
                    "closure_ping_count = :zero, "
                    "updated_at = :updated_at, "
                    "assignee_history = list_append(if_not_exists(assignee_history, :empty_list), :new_entry)"
                ),
                expression_attribute_values={
                    ":jira_user": {"S": new_jira_username},
                    ":slack_id": {"S": new_slack_id},
                    ":zero": {"N": "0"},
                    ":updated_at": {"N": str(current_time)},
                    ":empty_list": {"L": []},
                    ":new_entry": {"L": [new_history_entry]},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found for reassignment: %s", ticket_key)
                return None

            return self._item_to_notification_record(attributes)
        except Exception as e:
            logger.error("Error handling reassignment for %s: %s", ticket_key, e)
            return None

    async def add_followup_ticket(self, ticket_key: str, followup_key: str) -> bool:
        """Add a follow-up ticket key to a notification record.

        Atomically appends the follow-up ticket key to the followup_ticket_keys list
        in DynamoDB. Uses list_append with if_not_exists to handle missing attribute.

        Args:
            ticket_key: The JIRA ticket key of the parent CSOPM notification
            followup_key: The JIRA ticket key of the newly created follow-up ticket

        Returns:
            True if the follow-up was added successfully, False otherwise.
        """
        logger.info(
            "Adding follow-up ticket %s to notification record %s",
            followup_key,
            ticket_key,
        )

        try:
            current_time = int(time.time())

            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression=(
                    "SET followup_ticket_keys = list_append("
                    "if_not_exists(followup_ticket_keys, :empty_list), :new_key), "
                    "updated_at = :updated_at"
                ),
                expression_attribute_values={
                    ":empty_list": {"L": []},
                    ":new_key": {"L": [{"S": followup_key}]},
                    ":updated_at": {"N": str(current_time)},
                },
            )

            logger.info(
                "Successfully added follow-up ticket %s to %s",
                followup_key,
                ticket_key,
            )
            return True
        except Exception as e:
            logger.error(
                "Error adding follow-up ticket %s to %s: %s",
                followup_key,
                ticket_key,
                e,
            )
            return False

    async def mark_completed(self, ticket_key: str) -> bool:
        """Mark a ticket as completed by setting the completed_at timestamp.

        Records the timestamp when a ticket transitions to "Complete" status.
        Uses attribute_not_exists condition to prevent overwriting existing value.

        This timestamp is used for the "Completed within 7 days" metric
        (compare completed_at to created_at).

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            True if completed_at was set, False if already set or record not found.
        """
        logger.info("Marking ticket as completed: %s", ticket_key)

        try:
            current_time = int(time.time())

            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET completed_at = :timestamp, updated_at = :updated_at",
                condition_expression="attribute_not_exists(completed_at)",
                expression_attribute_values={
                    ":timestamp": {"N": str(current_time)},
                    ":updated_at": {"N": str(current_time)},
                },
            )

            logger.info("Successfully marked ticket %s as completed", ticket_key)
            return True
        except self.client.client.exceptions.ConditionalCheckFailedException:
            logger.debug("Ticket %s already marked as completed", ticket_key)
            return False
        except Exception as e:
            # Check if it's a conditional check failure (attribute already exists)
            if "ConditionalCheckFailedException" in str(e):
                logger.debug("Ticket %s already marked as completed", ticket_key)
                return False
            logger.error("Error marking ticket %s as completed: %s", ticket_key, e)
            return False

    async def mark_closed(self, ticket_key: str) -> bool:
        """Mark a ticket as closed by setting the closed_at timestamp.

        Records the timestamp when a ticket transitions to a terminal closure
        status (Closed, Done, Resolved). Uses attribute_not_exists condition
        to prevent overwriting existing value.

        This timestamp is used for the "Closed within 45 days" metric
        (compare closed_at to created_at).

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            True if closed_at was set, False if already set or record not found.
        """
        logger.info("Marking ticket as closed: %s", ticket_key)

        try:
            current_time = int(time.time())

            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET closed_at = :timestamp, updated_at = :updated_at",
                condition_expression="attribute_not_exists(closed_at)",
                expression_attribute_values={
                    ":timestamp": {"N": str(current_time)},
                    ":updated_at": {"N": str(current_time)},
                },
            )

            logger.info("Successfully marked ticket %s as closed", ticket_key)
            return True
        except self.client.client.exceptions.ConditionalCheckFailedException:
            logger.debug("Ticket %s already marked as closed", ticket_key)
            return False
        except Exception as e:
            # Check if it's a conditional check failure (attribute already exists)
            if "ConditionalCheckFailedException" in str(e):
                logger.debug("Ticket %s already marked as closed", ticket_key)
                return False
            logger.error("Error marking ticket %s as closed: %s", ticket_key, e)
            return False
