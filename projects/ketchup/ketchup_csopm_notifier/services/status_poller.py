"""
CSOPM Ticket Status Poller Service.

This module implements the CSOPMTicketStatusPoller service for periodically polling
JIRA to track ticket completion and closure status. When a ticket transitions to
a terminal status, the service records the transition timestamp for metrics tracking.

Terminal Status Mapping:
- "Complete" -> mark_completed() - Records completed_at timestamp
- "Closed", "Done", "Resolved" -> mark_closed() - Records closed_at timestamp

This enables key metrics:
- "Completed within 7 days" (compare completed_at to created_at)
- "Closed within 45 days" (compare closed_at to created_at)

Architectural Note:
This service follows the existing CSOPM services pattern:
- Protocol defined in csopm_protocols.py
- Implementation in ketchup_csopm_notifier/services/
- Registration in csopm_services.py
- Called from scheduler.py during each poll cycle
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from packages.core.constants import KETCHUP_ALERTS_CHANNEL
from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
    CSOPMStateTrackerProtocol,
    CSOPMTicketStatusPollerProtocol,
    NotificationRecord,
    StatusCheckResult,
)
from packages.integrations.async_mcp_client import AsyncMCPClient

logger = setup_logger(__name__)

# Terminal statuses that indicate ticket completion
COMPLETED_STATUSES: Set[str] = {"Complete"}

# Terminal statuses that indicate ticket closure (distinct from completion)
CLOSED_STATUSES: Set[str] = {"Closed", "Done", "Resolved"}


class CSOPMTicketStatusPoller(CSOPMTicketStatusPollerProtocol):
    """Service for polling JIRA ticket statuses and recording terminal transitions.

    This service periodically checks the status of all tracked CSOPM tickets
    and records timestamps when tickets reach terminal states. This enables
    tracking metrics like "completed within 7 days" and "closed within 45 days".

    The service uses batch fetching via AsyncMCPClient.get_issues_batch() to
    efficiently retrieve multiple ticket statuses in a single API call.

    Architectural Note:
    This service is designed to run alongside the existing reminder checks in
    the CSOPM scheduler. It can be called during each scheduler cycle to
    update ticket completion/closure timestamps.
    """

    # Fields to retrieve from JIRA for status checks
    STATUS_FIELDS = ["status"]

    def __init__(
        self,
        mcp_client: AsyncMCPClient,
        state_tracker: CSOPMStateTrackerProtocol,
    ) -> None:
        """Initialize the CSOPM ticket status poller.

        Args:
            mcp_client: AsyncMCPClient for JIRA API access via MCP.
            state_tracker: CSOPMStateTracker for updating notification records.
        """
        self._mcp_client = mcp_client
        self._state_tracker = state_tracker
        self._corrupted_records: List[Dict[str, Any]] = []
        logger.info("CSOPMTicketStatusPoller initialized")

    def get_corrupted_records(self) -> List[Dict[str, Any]]:
        """Get list of corrupted records detected during last poll.

        Returns:
            List of dicts with slack_id and notification_status for each corrupted record.
        """
        return self._corrupted_records

    def _get_status_from_issue(self, issue: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract the status name from a JIRA issue.

        Args:
            issue: Raw JIRA issue data from MCP response.

        Returns:
            The status name if found, None otherwise.
        """
        if not issue:
            return None

        fields = issue.get("fields", {})
        status_obj = fields.get("status", {})

        if isinstance(status_obj, dict):
            return status_obj.get("name")

        return None

    def _is_completed_status(self, status: str) -> bool:
        """Check if the status indicates ticket completion.

        Args:
            status: The JIRA status name.

        Returns:
            True if the status is a completion status.
        """
        return status in COMPLETED_STATUSES

    def _is_closed_status(self, status: str) -> bool:
        """Check if the status indicates ticket closure.

        Args:
            status: The JIRA status name.

        Returns:
            True if the status is a closure status.
        """
        return status in CLOSED_STATUSES

    async def poll_ticket_statuses(self) -> Dict[str, StatusCheckResult]:
        """Poll JIRA for status updates on all tracked tickets.

        Fetches all notification records, batch retrieves their current JIRA
        statuses, and updates records when tickets reach terminal states.

        For each notification record:
        1. Check if completed_at is already set (skip if so)
        2. Fetch current JIRA status
        3. If status is in COMPLETED_STATUSES, call mark_completed()
        4. If status is in CLOSED_STATUSES, call mark_closed()

        Also checks followup_ticket_keys for each notification record and
        tracks their completion/closure status.

        Returns:
            Dictionary mapping ticket keys to StatusCheckResult containing
            the current status and whether transitions were recorded.
        """
        logger.info("Starting CSOPM ticket status polling")
        results: Dict[str, StatusCheckResult] = {}
        self._corrupted_records = []  # Clear from previous poll

        try:
            # Step 1: Get all notification records
            all_records = await self._state_tracker.get_all_notification_records()
            if not all_records:
                logger.info("No notification records to poll")
                return results

            logger.info("Found %d notification records to check", len(all_records))

            # Step 2: Collect all ticket keys to poll (main tickets + followups)
            main_ticket_keys: List[str] = []
            followup_ticket_keys: List[str] = []
            record_map: Dict[str, NotificationRecord] = {}

            for record in all_records:
                # Validate ticket_key - skip and track if corrupted
                if not record.ticket_key or not record.ticket_key.strip():
                    logger.error(
                        "CSOPM Data Corruption: Empty ticket_key in notification record. "
                        "slack_id=%s, notification_status=%s. Skipping record.",
                        record.assignee_slack_id,
                        record.notification_status,
                    )
                    self._corrupted_records.append({
                        "slack_id": record.assignee_slack_id,
                        "notification_status": record.notification_status,
                    })
                    continue

                main_ticket_keys.append(record.ticket_key)
                record_map[record.ticket_key] = record

                # Collect followup ticket keys
                if record.followup_ticket_keys:
                    followup_ticket_keys.extend(record.followup_ticket_keys)

            # Deduplicate followup keys (in case a followup is tracked in multiple records)
            followup_ticket_keys = list(set(followup_ticket_keys))

            # Step 3: Batch fetch all ticket statuses
            all_keys = main_ticket_keys + followup_ticket_keys
            if not all_keys:
                logger.info("No ticket keys to poll")
                return results

            logger.info(
                "Batch fetching statuses for %d main tickets and %d followup tickets",
                len(main_ticket_keys),
                len(followup_ticket_keys),
            )

            issues_map = await self._mcp_client.get_issues_batch(
                issue_keys=all_keys,
                fields=self.STATUS_FIELDS,
            )

            # Step 4: Process main tickets
            completed_count = 0
            closed_count = 0

            for ticket_key in main_ticket_keys:
                record = record_map[ticket_key]
                issue = issues_map.get(ticket_key)
                status = self._get_status_from_issue(issue)

                result = StatusCheckResult(
                    ticket_key=ticket_key,
                    current_status=status,
                    was_completed=False,
                    was_closed=False,
                )

                if not status:
                    logger.warning("Could not get status for ticket: %s", ticket_key)
                    results[ticket_key] = result
                    continue

                logger.debug("Ticket %s has status: %s", ticket_key, status)

                # Check for completion transition (only if not already marked)
                if self._is_completed_status(status):
                    if record.completed_at is None:
                        success = await self._state_tracker.mark_completed(ticket_key)
                        if success:
                            completed_count += 1
                            result.was_completed = True
                            logger.info(
                                "Marked ticket %s as completed (status: %s)",
                                ticket_key,
                                status,
                            )
                    else:
                        logger.debug(
                            "Ticket %s already marked completed at %s",
                            ticket_key,
                            record.completed_at,
                        )

                # Check for closure transition (only if not already marked)
                elif self._is_closed_status(status):
                    if record.closed_at is None:
                        success = await self._state_tracker.mark_closed(ticket_key)
                        if success:
                            closed_count += 1
                            result.was_closed = True
                            logger.info(
                                "Marked ticket %s as closed (status: %s)",
                                ticket_key,
                                status,
                            )
                    else:
                        logger.debug(
                            "Ticket %s already marked closed at %s",
                            ticket_key,
                            record.closed_at,
                        )

                results[ticket_key] = result

            # Step 5: Process followup tickets (for tracking, less critical)
            # We log followup status changes but don't update parent notification records
            for followup_key in followup_ticket_keys:
                issue = issues_map.get(followup_key)
                status = self._get_status_from_issue(issue)

                result = StatusCheckResult(
                    ticket_key=followup_key,
                    current_status=status,
                    was_completed=False,
                    was_closed=False,
                    is_followup=True,
                )

                if status:
                    if self._is_completed_status(status):
                        logger.debug(
                            "Followup ticket %s is completed (status: %s)",
                            followup_key,
                            status,
                        )
                    elif self._is_closed_status(status):
                        logger.debug(
                            "Followup ticket %s is closed (status: %s)",
                            followup_key,
                            status,
                        )

                results[followup_key] = result

            logger.info(
                "CSOPM status polling complete: %d completed, %d closed (of %d main tickets)",
                completed_count,
                closed_count,
                len(main_ticket_keys),
            )

            return results

        except Exception as e:
            logger.error("Error polling ticket statuses: %s", e, exc_info=True)
            return results

    async def get_ticket_status(self, ticket_key: str) -> Optional[str]:
        """Get the current status of a single ticket.

        Args:
            ticket_key: The JIRA ticket key (e.g., "CSOPM-1234")

        Returns:
            The current status name if found, None otherwise.
        """
        try:
            issue = await self._mcp_client.get_issue(
                issue_key=ticket_key,
                fields=self.STATUS_FIELDS,
            )
            return self._get_status_from_issue(issue)
        except Exception as e:
            logger.error("Error getting status for %s: %s", ticket_key, e)
            return None
