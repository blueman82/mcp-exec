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
from datetime import datetime
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

    def _item_to_notification_record(
        self, item: Dict[str, Any]
    ) -> Optional[NotificationRecord]:
        """Convert a DynamoDB item to a NotificationRecord.

        Args:
            item: Raw DynamoDB item (in DynamoDB attribute format)

        Returns:
            NotificationRecord instance, or None if parsing fails.
        """
        try:
            normalized = self._normalize_item(item)

            return NotificationRecord(
                ticket_key=normalized.get("ticket_key", ""),
                notification_status=normalized.get("notification_status", "pending"),
                ping_count=int(normalized.get("ping_count", 0)),
                assignee_slack_id=normalized.get("assignee_slack_id"),
                assignee_jira_username=normalized.get("assignee_jira_username"),
                rca_reminder_sent=bool(normalized.get("rca_reminder_sent", False)),
                closure_reminder_sent=bool(
                    normalized.get("closure_reminder_sent", False)
                ),
            )
        except Exception as e:
            logger.error("Error parsing notification record: %s", e)
            return None

    def _item_to_followup_record(
        self, item: Dict[str, Any]
    ) -> Optional[FollowupRecord]:
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

    async def get_notification_record(
        self, ticket_key: str
    ) -> Optional[NotificationRecord]:
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
            logger.error(
                "Error getting notification record for %s: %s", ticket_key, e
            )
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
        """
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
            "ping_count": {"N": "0"},
            "assignee_slack_id": {"S": slack_id},
            "assignee_jira_username": {"S": ticket.assignee_username},
            "rca_reminder_sent": {"BOOL": False},
            "closure_reminder_sent": {"BOOL": False},
            "created_at": {"N": str(current_time)},
            "updated_at": {"N": str(current_time)},
            "ticket_summary": {"S": ticket.summary},
            "ticket_status": {"S": ticket.status},
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
                ping_count=0,
                assignee_slack_id=slack_id,
                assignee_jira_username=ticket.assignee_username,
                rca_reminder_sent=False,
                closure_reminder_sent=False,
            )

        except Exception as e:
            logger.error(
                "Error creating notification record for %s: %s", ticket.key, e
            )
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
        logger.info(
            "Updating notification status for %s to: %s", ticket_key, status
        )

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
                logger.warning(
                    "No record found to update status for: %s", ticket_key
                )
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error(
                "Error updating notification status for %s: %s", ticket_key, e
            )
            return None

    async def increment_ping_count(
        self, ticket_key: str
    ) -> Optional[NotificationRecord]:
        """Increment the ping count for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        logger.info("Incrementing ping count for: %s", ticket_key)

        try:
            current_time = int(time.time())

            response = await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": self._make_pk(ticket_key)},
                    "SK": {"S": SK_NOTIFICATION},
                },
                update_expression="SET ping_count = ping_count + :inc, updated_at = :updated_at",
                expression_attribute_values={
                    ":inc": {"N": "1"},
                    ":updated_at": {"N": str(current_time)},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning("No record found to increment ping for: %s", ticket_key)
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error(
                "Error incrementing ping count for %s: %s", ticket_key, e
            )
            return None

    async def mark_rca_reminder_sent(
        self, ticket_key: str
    ) -> Optional[NotificationRecord]:
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
                logger.warning(
                    "No record found to mark RCA reminder for: %s", ticket_key
                )
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error(
                "Error marking RCA reminder sent for %s: %s", ticket_key, e
            )
            return None

    async def mark_closure_reminder_sent(
        self, ticket_key: str
    ) -> Optional[NotificationRecord]:
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
                logger.warning(
                    "No record found to mark closure reminder for: %s", ticket_key
                )
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error(
                "Error marking closure reminder sent for %s: %s", ticket_key, e
            )
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
                "begins_with(PK, :pk_prefix) AND "
                "SK = :sk AND "
                "notification_status = :status"
            )

            response = await self.client.scan(
                table_name=self.table_name,
                filter_expression=filter_expression,
                expression_attribute_values={
                    ":pk_prefix": {"S": PK_NOTIFICATION_PREFIX},
                    ":sk": {"S": SK_NOTIFICATION},
                    ":status": {"S": "pending"},
                },
            )

            items = response.get("Items", [])
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
            logger.info(
                "Recorded followup for %s (type=%s)", ticket_key, followup_type
            )

            return FollowupRecord(
                ticket_key=ticket_key,
                followup_type=followup_type,
                scheduled_at=scheduled_at,
                completed=False,
                completed_at=None,
            )

        except Exception as e:
            logger.error(
                "Error recording followup for %s: %s", ticket_key, e
            )
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

            response = await self.client.scan(
                table_name=self.table_name,
                filter_expression=filter_expression,
                expression_attribute_values={
                    ":pk_prefix": {"S": PK_NOTIFICATION_PREFIX},
                    ":sk": {"S": SK_NOTIFICATION},
                    ":escalated_status": {"S": "escalated"},
                },
            )

            items = response.get("Items", [])
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

    async def handle_reassignment(
        self,
        ticket_key: str,
        new_jira_username: str,
        new_slack_id: str,
    ) -> Optional[NotificationRecord]:
        """Handle ticket reassignment by updating assignee and resetting ping count.

        When a ticket is reassigned:
        1. Updates assignee_jira_username and assignee_slack_id
        2. Resets ping_count to 1 (initial notification to new assignee)
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
                    "ping_count = :ping_count, "
                    "updated_at = :updated_at, "
                    "assignee_history = list_append(if_not_exists(assignee_history, :empty_list), :new_entry)"
                ),
                expression_attribute_values={
                    ":jira_user": {"S": new_jira_username},
                    ":slack_id": {"S": new_slack_id},
                    ":ping_count": {"N": "1"},
                    ":updated_at": {"N": str(current_time)},
                    ":empty_list": {"L": []},
                    ":new_entry": {"L": [new_history_entry]},
                },
                return_values="ALL_NEW",
            )

            attributes = response.get("Attributes")
            if not attributes:
                logger.warning(
                    "No record found for reassignment: %s", ticket_key
                )
                return None

            return self._item_to_notification_record(attributes)

        except Exception as e:
            logger.error(
                "Error handling reassignment for %s: %s", ticket_key, e
            )
            return None
