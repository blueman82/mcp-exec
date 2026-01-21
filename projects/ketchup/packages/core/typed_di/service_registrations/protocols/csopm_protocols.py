"""
CSOPM Notifier Protocol Definitions.

This module contains protocol definitions for CSOPM (Customer Success Operations
Project Management) notifier services. These protocols define the contracts for:
- JIRA ticket polling and discovery
- State tracking for notification records
- Slack DM notifications for new assignments
- Reminder services for RCA and closure
- Metrics collection and instrumentation

Architectural Note:
These protocols are foundational for the CSOPM notification system, which monitors
JIRA tickets in the CSOPM project and sends proactive notifications to assignees
when new tickets are assigned to them. The system tracks notification state to
prevent duplicate notifications and provides RCA/closure reminders.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Protocol, runtime_checkable

__all__ = [
    # Data classes
    "CSOPMTicket",
    "NotificationRecord",
    "FollowupRecord",
    "StatusCheckResult",
    # Protocols
    "CSOPMJIRAPollerProtocol",
    "CSOPMStateTrackerProtocol",
    "CSOPMSlackNotifierProtocol",
    "CSOPMReminderServiceProtocol",
    "CSOPMMetricsProtocol",
    "CSOPMButtonActionHandlerProtocol",
    "CSOPMHandlerProtocol",
    "CSOPMTicketStatusPollerProtocol",
    "UserPATOperationsProtocol",
]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CSOPMTicket:
    """Data class representing a CSOPM JIRA ticket.

    This represents the core ticket information needed for notification purposes.
    Fields are extracted from JIRA ticket data during polling operations.

    Attributes:
        key: The JIRA ticket key (e.g., "CSOPM-1234")
        summary: The ticket summary/title
        assignee_username: The username of the assigned user (JIRA username format)
        created_at: When the ticket was created
        status: Current workflow status of the ticket
        exigence_id: Optional Exigence event ID if linked to an incident
    """

    key: str
    summary: str
    assignee_username: str
    created_at: datetime
    status: str
    exigence_id: Optional[str] = None


@dataclass
class NotificationRecord:
    """Data class representing the notification state for a ticket.

    Tracks what notifications have been sent for a given ticket to prevent
    duplicates and manage the notification lifecycle.

    Attributes:
        ticket_key: The JIRA ticket key this record is for
        notification_status: Current notification state ("pending", "sent", "ack", "escalated", "reminders_stopped")
        rca_ping_count: Number of RCA reminder pings sent
        closure_ping_count: Number of closure reminder pings sent
        assignee_slack_id: The Slack user ID of the assignee (resolved from username)
        assignee_jira_username: The JIRA username of the current assignee (for reassignment detection)
        rca_reminder_sent: Whether the RCA reminder has been sent
        closure_reminder_sent: Whether the closure reminder has been sent
        created_at: Unix timestamp of when the notification record was created
        updated_at: Unix timestamp of last update (used as acknowledged_at when status is "ack")
        followup_ticket_keys: List of JIRA ticket keys created as follow-ups from this notification
        completed_at: Unix timestamp of when the ticket reached "Complete" status (for metrics)
        closed_at: Unix timestamp of when the ticket reached "Closed/Done/Resolved" status (for metrics)
    """

    ticket_key: str
    notification_status: str
    rca_ping_count: int
    closure_ping_count: int
    assignee_slack_id: Optional[str]
    assignee_jira_username: Optional[str]
    rca_reminder_sent: bool
    closure_reminder_sent: bool
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
    followup_ticket_keys: List[str] = field(default_factory=list)
    completed_at: Optional[int] = None
    closed_at: Optional[int] = None


@dataclass
class FollowupRecord:
    """Data class representing a scheduled followup reminder.

    Tracks when followup reminders should be sent for tickets requiring
    additional attention (e.g., missing RCA, pending closure).

    Attributes:
        ticket_key: The JIRA ticket key this followup is for
        followup_type: Type of followup ("rca_reminder", "closure_reminder", "ping")
        scheduled_at: When the followup should be sent
        completed: Whether the followup has been completed
        completed_at: When the followup was completed (if applicable)
    """

    ticket_key: str
    followup_type: str
    scheduled_at: datetime
    completed: bool
    completed_at: Optional[datetime] = None


@dataclass
class StatusCheckResult:
    """Data class representing the result of a ticket status check.

    Returned by CSOPMTicketStatusPoller.poll_ticket_statuses() to indicate
    the current status and whether any transitions were recorded.

    Attributes:
        ticket_key: The JIRA ticket key that was checked
        current_status: The current JIRA status (or None if fetch failed)
        was_completed: Whether this check triggered a mark_completed() call
        was_closed: Whether this check triggered a mark_closed() call
        is_followup: Whether this ticket is a followup (not a main notification)
    """

    ticket_key: str
    current_status: Optional[str]
    was_completed: bool
    was_closed: bool
    is_followup: bool = False


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class CSOPMJIRAPollerProtocol(Protocol):
    """Protocol for polling JIRA for new CSOPM ticket assignments.

    This service is responsible for querying JIRA to discover new ticket
    assignments that need notifications. It handles the JQL queries and
    transforms JIRA response data into CSOPMTicket instances.
    """

    async def poll_for_new_assignments(self) -> List[CSOPMTicket]:
        """Poll JIRA for newly assigned tickets requiring notification.

        Returns:
            List of CSOPMTicket instances representing new assignments.
            Empty list if no new assignments found or on error.
        """
        ...

    async def get_ticket_details(self, ticket_key: str) -> Optional[CSOPMTicket]:
        """Get detailed information for a specific ticket.

        Args:
            ticket_key: The JIRA ticket key (e.g., "CSOPM-1234")

        Returns:
            CSOPMTicket instance if found, None otherwise.
        """
        ...

    async def get_tickets_by_assignee(self, assignee_username: str) -> List[CSOPMTicket]:
        """Get all active tickets assigned to a specific user.

        Args:
            assignee_username: The JIRA username of the assignee

        Returns:
            List of CSOPMTicket instances assigned to the user.
        """
        ...


@runtime_checkable
class CSOPMStateTrackerProtocol(Protocol):
    """Protocol for tracking notification state in DynamoDB.

    This service manages the persistence of notification records,
    tracking which tickets have been notified about and the state
    of each notification lifecycle.
    """

    async def get_notification_record(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Get the notification record for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            NotificationRecord if exists, None otherwise.
        """
        ...

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
        ...

    async def update_notification_status(
        self, ticket_key: str, status: str
    ) -> Optional[NotificationRecord]:
        """Update the notification status for a ticket.

        Args:
            ticket_key: The JIRA ticket key
            status: New status ("pending", "sent", "failed")

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        ...

    async def increment_rca_ping_count(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Increment the RCA ping count for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        ...

    async def increment_closure_ping_count(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Increment the closure ping count for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        ...

    async def mark_rca_reminder_sent(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Mark the RCA reminder as sent for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        ...

    async def mark_closure_reminder_sent(self, ticket_key: str) -> Optional[NotificationRecord]:
        """Mark the closure reminder as sent for a ticket.

        Args:
            ticket_key: The JIRA ticket key

        Returns:
            Updated NotificationRecord if found, None otherwise.
        """
        ...

    async def get_pending_notifications(self) -> List[NotificationRecord]:
        """Get all notifications in pending state.

        Returns:
            List of NotificationRecords with pending status.
        """
        ...

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
        ...

    async def handle_reassignment(
        self, ticket_key: str, new_jira_username: str, new_slack_id: str
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
        ...

    async def get_all_notification_records(self) -> List[NotificationRecord]:
        """Get all notification records for metrics collection.

        Scans for all notification records regardless of status.
        Used for dashboard metrics aggregation.

        Returns:
            List of all NotificationRecords.
        """
        ...

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
        ...

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
        ...

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
        ...


@runtime_checkable
class CSOPMSlackNotifierProtocol(Protocol):
    """Protocol for sending Slack notifications to assignees.

    This service handles the construction and delivery of Slack DM
    notifications for new ticket assignments.
    """

    async def send_assignment_dm(self, ticket: CSOPMTicket, slack_user_id: str) -> bool:
        """Send a DM notification about a new ticket assignment.

        Args:
            ticket: The CSOPMTicket being assigned
            slack_user_id: The Slack user ID to send the DM to

        Returns:
            True if DM was sent successfully, False otherwise.
        """
        ...

    async def send_reminder_dm(
        self, ticket: CSOPMTicket, slack_user_id: str, reminder_type: str
    ) -> bool:
        """Send a reminder DM for a ticket.

        Args:
            ticket: The CSOPMTicket requiring reminder
            slack_user_id: The Slack user ID to send the DM to
            reminder_type: Type of reminder ("rca", "closure", "ping")

        Returns:
            True if DM was sent successfully, False otherwise.
        """
        ...

    async def resolve_slack_user_id(self, jira_username: str) -> Optional[str]:
        """Resolve a JIRA username to a Slack user ID.

        Uses the established email lookup pattern to find the Slack user
        corresponding to a JIRA username.

        Args:
            jira_username: The JIRA username to resolve

        Returns:
            Slack user ID if found, None otherwise.
        """
        ...

    async def handle_button_action(
        self, action_id: str, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle a Slack button action from a CSOPM notification message.

        Processes interactive button clicks from CSOPM notification DMs,
        such as "Acknowledge", "Snooze", or "View in JIRA" actions.

        Args:
            action_id: The ID of the action button clicked
            user_id: The Slack user ID who clicked the button
            ticket_key: The JIRA ticket key associated with the action
            payload: The full Slack interaction payload

        Returns:
            True if action was handled successfully, False otherwise.
        """
        ...


@runtime_checkable
class CSOPMReminderServiceProtocol(Protocol):
    """Protocol for managing followup reminders.

    This service handles the scheduling and delivery of followup
    reminders for tickets that need additional attention.
    """

    async def schedule_rca_reminder(
        self, ticket: CSOPMTicket, delay_hours: int = 24
    ) -> FollowupRecord:
        """Schedule an RCA reminder for a ticket.

        Args:
            ticket: The CSOPMTicket to remind about
            delay_hours: Hours to wait before sending reminder (default 24)

        Returns:
            The created FollowupRecord.
        """
        ...

    async def schedule_closure_reminder(
        self, ticket: CSOPMTicket, delay_hours: int = 48
    ) -> FollowupRecord:
        """Schedule a closure reminder for a ticket.

        Args:
            ticket: The CSOPMTicket to remind about
            delay_hours: Hours to wait before sending reminder (default 48)

        Returns:
            The created FollowupRecord.
        """
        ...

    async def get_due_reminders(self) -> List[FollowupRecord]:
        """Get all reminders that are due to be sent.

        Returns:
            List of FollowupRecords that are scheduled before now
            and not yet completed.
        """
        ...

    async def complete_reminder(self, ticket_key: str, followup_type: str) -> bool:
        """Mark a reminder as completed.

        Args:
            ticket_key: The JIRA ticket key
            followup_type: Type of followup being completed

        Returns:
            True if reminder was found and marked complete, False otherwise.
        """
        ...

    async def check_rca_reminders(self) -> List[FollowupRecord]:
        """Check for RCA reminders that are due to be sent.

        Queries for all scheduled RCA reminders whose scheduled_at time
        has passed and which have not been completed.

        Returns:
            List of FollowupRecords for due RCA reminders.
        """
        ...

    async def check_closure_reminders(self) -> List[FollowupRecord]:
        """Check for closure reminders that are due to be sent.

        Queries for all scheduled closure reminders whose scheduled_at time
        has passed and which have not been completed.

        Returns:
            List of FollowupRecords for due closure reminders.
        """
        ...


@runtime_checkable
class CSOPMMetricsProtocol(Protocol):
    """Protocol for CSOPM metrics collection and instrumentation.

    This service provides a metrics interface for tracking CSOPM
    notification system performance and health.
    """

    async def increment_counter(self, counter_name: str, value: int = 1) -> None:
        """Increment a named counter metric.

        Standard counter names:

        Notifications:
        - "csopm.tickets.polled" - Tickets discovered in polling
        - "csopm.notifications.sent" - DM notifications sent
        - "csopm.notifications.failed" - Failed notification attempts
        - "csopm.notifications.acknowledged" - Acknowledge button clicked

        Reminders:
        - "csopm.reminders.rca.sent" - RCA reminders sent
        - "csopm.reminders.closure.sent" - Closure reminders sent

        User Resolution:
        - "csopm.user.resolution.success" - Successful username->Slack ID resolutions
        - "csopm.user.resolution.failed" - Failed username->Slack ID resolutions

        User Actions:
        - "csopm.actions.stop_reminders" - Stop Reminders button clicked
        - "csopm.actions.enable_reminders" - Enable Reminders button clicked
        - "csopm.actions.snooze" - Snooze button clicked
        - "csopm.actions.unsnooze" - Unsnooze button clicked

        Ticket Transitions:
        - "csopm.transitions.complete" - Marked Complete via Slack modal
        - "csopm.transitions.closed" - Closed via Slack modal
        - "csopm.followups.created" - Follow-up tickets created

        State Changes:
        - "csopm.reassignments" - Ticket reassignments detected

        Args:
            counter_name: The name of the counter to increment
            value: Amount to increment by (default 1)
        """
        ...

    async def record_gauge(self, gauge_name: str, value: float) -> None:
        """Record a gauge metric value.

        Standard gauge names:
        - "csopm.pending.notifications" - Number of pending notifications
        - "csopm.pending.reminders" - Number of pending reminders

        Args:
            gauge_name: The name of the gauge
            value: The gauge value to record
        """
        ...

    async def record_latency(self, operation_name: str, latency_ms: float) -> None:
        """Record an operation latency metric.

        Standard operation names:
        - "csopm.poll.jira" - JIRA polling latency
        - "csopm.send.dm" - Slack DM sending latency
        - "csopm.resolve.user" - User resolution latency

        Args:
            operation_name: The name of the operation
            latency_ms: The latency in milliseconds
        """
        ...

    async def get_metrics_summary(self) -> dict:
        """Get a summary of all current metrics.

        Returns:
            Dictionary containing all tracked metrics and their values.
        """
        ...


@runtime_checkable
class CSOPMButtonActionHandlerProtocol(Protocol):
    """Protocol for handling CSOPM button actions in Slack notification messages.

    This handler processes interactive button clicks from CSOPM notification DMs
    and performs the appropriate actions (JIRA comments, state updates, confirmations).

    Key Responsibilities:
    1. Dispatch button actions to appropriate handlers
    2. Post acknowledgment comments to JIRA
    3. Update notification state (if tracker available)
    4. Send confirmation messages to users
    5. Coordinate JIRA transitions (close, transition status)

    This protocol is implemented by CSOPMButtonActionHandler in packages/slack/csopm/
    and is used by both ketchup-app (interactive handlers) and ketchup_csopm_notifier.
    """

    async def handle_button_action(
        self, action_id: str, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle a Slack button action from a CSOPM notification message.

        Processes interactive button clicks from CSOPM notification DMs:
        - csopm_acknowledge: Update state to 'ack', post JIRA comment
        - csopm_create_followup: Return True to signal modal should open
        - csopm_stop_reminders: Stop ketchup reminders for this ticket
        - csopm_enable_reminders: Re-enable ketchup reminders
        - csopm_snooze: Snooze closure reminder for 7 days
        - csopm_close_ticket: Close ticket in JIRA
        - csopm_view_jira: Link button (no backend action needed)

        Args:
            action_id: The ID of the action button clicked.
            user_id: The Slack user ID who clicked the button.
            ticket_key: The JIRA ticket key associated with the action.
            payload: The full Slack interaction payload.

        Returns:
            True if action was handled successfully, False otherwise.
        """
        ...


@runtime_checkable
class CSOPMHandlerProtocol(Protocol):
    """Protocol for handling CSOPM interactive elements in Slack.

    This handler processes block actions and modal submissions for CSOPM notifications.
    It routes interactive events to the CSOPMButtonActionHandler for processing.

    Key Responsibilities:
    1. Extract action context from Slack payloads
    2. Route button clicks to CSOPMButtonActionHandler
    3. Handle modal submissions for follow-up ticket creation
    4. Coordinate MCP calls for JIRA operations

    This protocol is implemented by CSOPMHandler in packages/slack/interactive_elements/
    and is used by ketchup-app for handling interactive CSOPM elements.
    """

    async def handle_block_action(self, payload: dict) -> bool:
        """Handle a block_actions payload for CSOPM buttons.

        Extracts action context and delegates to the appropriate handler
        based on action_id.

        Args:
            payload: The Slack block_actions payload.

        Returns:
            True if action was handled successfully, False otherwise.
        """
        ...

    async def handle_view_submission(self, payload: dict) -> bool:
        """Handle a view_submission payload for CSOPM modals.

        Currently handles:
        - csopm_create_followup_modal: Create follow-up ticket in JIRA

        Args:
            payload: The Slack view_submission payload.

        Returns:
            True if submission was handled successfully, False otherwise.
        """
        ...


@runtime_checkable
class UserPATOperationsProtocol(Protocol):
    """Protocol for storing and retrieving user JIRA Personal Access Tokens.

    PATs are stored with a 1-hour TTL and automatically deleted by DynamoDB
    after expiry. Used to allow users to authenticate JIRA operations with
    their own credentials when the service account lacks permissions.
    """

    async def store_pat(self, user_id: str, pat: str) -> None:
        """Store a user's JIRA PAT with 1-hour TTL.

        Args:
            user_id: The Slack user ID
            pat: The JIRA Personal Access Token
        """
        ...

    async def get_pat(self, user_id: str) -> Optional[str]:
        """Retrieve a user's JIRA PAT if not expired.

        Args:
            user_id: The Slack user ID

        Returns:
            The PAT if found and not expired, None otherwise.
        """
        ...

    async def delete_pat(self, user_id: str) -> None:
        """Delete a user's stored PAT.

        Args:
            user_id: The Slack user ID
        """
        ...

    async def has_valid_pat(self, user_id: str) -> bool:
        """Check if a user has a valid (non-expired) PAT stored.

        Args:
            user_id: The Slack user ID

        Returns:
            True if user has a valid PAT, False otherwise.
        """
        ...


@runtime_checkable
class CSOPMTicketStatusPollerProtocol(Protocol):
    """Protocol for polling JIRA ticket statuses to track completion/closure.

    This service periodically checks the status of all tracked CSOPM tickets
    and records timestamps when tickets reach terminal states (Complete, Closed,
    Done, Resolved). This enables metrics tracking:
    - "Completed within 7 days" (compare completed_at to created_at)
    - "Closed within 45 days" (compare closed_at to created_at)

    Terminal Status Mapping:
    - "Complete" -> mark_completed() - Records completed_at timestamp
    - "Closed", "Done", "Resolved" -> mark_closed() - Records closed_at timestamp

    The service also tracks followup ticket statuses for visibility.
    """

    async def poll_ticket_statuses(self) -> dict:
        """Poll JIRA for status updates on all tracked tickets.

        Fetches all notification records, batch retrieves their current JIRA
        statuses, and updates records when tickets reach terminal states.

        For each notification record:
        1. Check if completed_at/closed_at is already set (skip if so)
        2. Fetch current JIRA status
        3. If status is "Complete", call mark_completed()
        4. If status is "Closed/Done/Resolved", call mark_closed()

        Also checks followup_ticket_keys for each notification record.

        Returns:
            Dictionary mapping ticket keys to StatusCheckResult containing
            the current status and whether transitions were recorded.
        """
        ...

    async def get_ticket_status(self, ticket_key: str) -> Optional[str]:
        """Get the current status of a single ticket.

        Args:
            ticket_key: The JIRA ticket key (e.g., "CSOPM-1234")

        Returns:
            The current status name if found, None otherwise.
        """
        ...
