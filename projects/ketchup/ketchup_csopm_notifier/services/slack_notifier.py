"""
CSOPM Slack Notifier Service.

This module implements the CSOPMSlackNotifier service for sending Slack DM
notifications to assignees when new CSOPM tickets are assigned to them.

Key Features:
- Send assignment DMs with interactive Block Kit buttons
- Resolve JIRA usernames to Slack user IDs via email lookup
- Handle button actions (delegated to CSOPMButtonActionHandler)

Architectural Note:
This service implements the CSOPMSlackNotifierProtocol and integrates with:
- SlackPostingHandler for message delivery
- SlackUserOps for email-to-Slack ID resolution
- CSOPMButtonActionHandler for button action handling (from packages/)
- CSOPMStateTracker for notification state updates

Refactored to import shared components from packages/slack/csopm/:
- CSOPMNotificationBlocks: Block Kit builders for notifications
- CSOPMButtonActionHandler: Handler for interactive button actions

This eliminates ~460 lines of duplicated button handling code.
"""

from typing import Dict, List, Optional

from packages.core.config.csopm_config import is_pilot_user
from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import (
    CSOPMMetricsProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
)
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.slack.csopm.actions import CSOPMButtonActionHandler
from packages.slack.csopm.blocks import CSOPMNotificationBlocks
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


# Adobe email domain for JIRA username to email conversion
ADOBE_EMAIL_DOMAIN = "@adobe.com"


class CSOPMSlackNotifier(CSOPMSlackNotifierProtocol):
    """Slack notification service for CSOPM ticket assignments.

    This service handles the construction and delivery of Slack DM
    notifications for new ticket assignments, reminders, and action handling.

    Key Responsibilities:
    1. Resolve JIRA usernames to Slack user IDs via email
    2. Build Block Kit messages with interactive buttons
    3. Send DMs to assignees
    4. Handle button action callbacks (delegated to CSOPMButtonActionHandler)

    Integration Points:
    - SlackPostingHandler: Message delivery
    - SlackUserOps: Email-to-Slack resolution
    - CSOPMButtonActionHandler: Button action handling (from packages/)
    - CSOPMStateTracker: State updates on actions
    """

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        user_ops: SlackUserOps,
        mcp_client: AsyncMCPClient,
        state_tracker: Optional[CSOPMStateTrackerProtocol] = None,
        metrics: Optional[CSOPMMetricsProtocol] = None,
    ) -> None:
        """Initialize the CSOPM Slack notifier.

        Args:
            posting_handler: SlackPostingHandler for message delivery.
            user_ops: SlackUserOps for email-to-Slack ID resolution.
            mcp_client: AsyncMCPClient for JIRA comment posting.
            state_tracker: Optional CSOPMStateTrackerProtocol for state updates.
            metrics: Optional CSOPMMetricsProtocol for metrics tracking.
        """
        self._posting_handler = posting_handler
        self._user_ops = user_ops
        self._mcp_client = mcp_client
        self._state_tracker = state_tracker
        self._metrics = metrics

        # Initialize the shared button action handler from packages/
        self._button_handler = CSOPMButtonActionHandler(
            posting_handler=posting_handler,
            mcp_client=mcp_client,
            state_tracker=state_tracker,
        )

        logger.info("CSOPMSlackNotifier initialized with CSOPMButtonActionHandler")

    async def resolve_slack_user_id(self, jira_username: str) -> Optional[str]:
        """Resolve a JIRA username to a Slack user ID.

        Builds the email as {jira_username}@adobe.com and uses
        SlackUserOps.get_slack_id_by_email() for resolution.

        Args:
            jira_username: The JIRA username to resolve.

        Returns:
            Slack user ID if found, None otherwise.
        """
        if not jira_username:
            logger.warning("resolve_slack_user_id called with empty username")
            return None

        # Build email address from JIRA username
        email = f"{jira_username.lower()}{ADOBE_EMAIL_DOMAIN}"

        logger.info("Resolving Slack ID for JIRA user %s (email: %s)", jira_username, email)

        try:
            slack_id = await self._user_ops.get_slack_id_by_email(email)

            if slack_id:
                logger.info(
                    "Resolved %s to Slack ID %s",
                    jira_username,
                    slack_id,
                )
            else:
                logger.warning("Could not resolve Slack ID for %s", jira_username)

            return slack_id

        except Exception as e:
            logger.error("Error resolving Slack ID for %s: %s", jira_username, e)
            return None

    async def send_assignment_dm(self, ticket: CSOPMTicket, slack_user_id: str) -> bool:
        """Send a DM notification about a new ticket assignment.

        Builds a Block Kit message with interactive buttons and sends
        it to the assignee's Slack DM.

        Args:
            ticket: The CSOPMTicket being assigned.
            slack_user_id: The Slack user ID to send the DM to.

        Returns:
            True if DM was sent successfully, False otherwise.
        """
        # Check if user is in pilot program
        if not is_pilot_user(slack_user_id):
            logger.info(
                "Skipping assignment DM for %s - user %s not in pilot program",
                ticket.key,
                slack_user_id,
            )
            return True  # Return True to not trigger failure handling

        logger.info(
            "Sending assignment DM for %s to user %s",
            ticket.key,
            slack_user_id,
        )

        try:
            # Build Block Kit blocks for assignment notification
            blocks = CSOPMNotificationBlocks.build_assignment_notification(
                ticket=ticket,
                exigence_id=ticket.exigence_id,
            )

            # Get fallback text for clients that can't render blocks
            fallback_text = CSOPMNotificationBlocks.get_fallback_text(
                notification_type="assignment",
                ticket_key=ticket.key,
            )

            # Send DM (user_id serves as channel_id for DMs)
            result = await self._posting_handler.post_message(
                channel_id=slack_user_id,
                message=fallback_text,
                blocks=blocks,
            )

            if result and result.get("ok"):
                logger.info(
                    "Successfully sent assignment DM for %s to %s",
                    ticket.key,
                    slack_user_id,
                )
                return True
            else:
                error = result.get("error", "Unknown error") if result else "No response"
                logger.error(
                    "Failed to send assignment DM for %s: %s",
                    ticket.key,
                    error,
                )
                return False

        except Exception as e:
            logger.error("Error sending assignment DM for %s: %s", ticket.key, e)
            return False

    async def send_reminder_dm(
        self,
        ticket: CSOPMTicket,
        slack_user_id: str,
        reminder_type: str,
        open_followups: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """Send a reminder DM for a ticket.

        Args:
            ticket: The CSOPMTicket requiring reminder.
            slack_user_id: The Slack user ID to send the DM to.
            reminder_type: Type of reminder ("rca", "closure", "ping").
            open_followups: List of open followup tickets (for closure reminders).
                Format: [{'key': 'CAMP-123', 'status': 'In Progress'}, ...]

        Returns:
            True if DM was sent successfully, False otherwise.
        """
        # Check if user is in pilot program
        if not is_pilot_user(slack_user_id):
            logger.info(
                "Skipping %s reminder DM for %s - user %s not in pilot program",
                reminder_type,
                ticket.key,
                slack_user_id,
            )
            return True  # Return True to not trigger failure handling

        logger.info(
            "Sending %s reminder DM for %s to user %s",
            reminder_type,
            ticket.key,
            slack_user_id,
        )

        try:
            # Get notification record for ping count info
            days_old = 0
            ping_count = 1
            has_open_linked = False

            if self._state_tracker:
                record = await self._state_tracker.get_notification_record(ticket.key)
                if record:
                    # Use the appropriate ping count based on reminder type
                    if reminder_type == "rca":
                        ping_count = record.rca_ping_count + 1
                    else:
                        ping_count = record.closure_ping_count + 1

            # Build appropriate reminder blocks
            if reminder_type == "rca":
                blocks = CSOPMNotificationBlocks.build_rca_reminder(
                    ticket=ticket,
                    days_old=days_old,
                    ping_count=ping_count,
                )
                fallback_type = "rca"
            elif reminder_type in ("closure", "ping"):
                has_open = has_open_linked or bool(open_followups)
                blocks = CSOPMNotificationBlocks.build_closure_reminder(
                    ticket=ticket,
                    days_old=days_old,
                    ping_count=ping_count,
                    has_open_linked=has_open,
                    open_followups=open_followups,
                )
                fallback_type = "closure"
            else:
                logger.error("Unknown reminder type: %s", reminder_type)
                return False

            # Get fallback text
            fallback_text = CSOPMNotificationBlocks.get_fallback_text(
                notification_type=fallback_type,
                ticket_key=ticket.key,
            )

            # Send DM
            result = await self._posting_handler.post_message(
                channel_id=slack_user_id,
                message=fallback_text,
                blocks=blocks,
            )

            if result and result.get("ok"):
                logger.info(
                    "Successfully sent %s reminder DM for %s",
                    reminder_type,
                    ticket.key,
                )

                # Increment reminder metric
                if self._metrics:
                    metric_name = f"csopm.reminders.{reminder_type}.sent"
                    await self._metrics.increment_counter(metric_name)

                return True
            else:
                error = result.get("error", "Unknown error") if result else "No response"
                logger.error(
                    "Failed to send %s reminder DM for %s: %s",
                    reminder_type,
                    ticket.key,
                    error,
                )
                return False

        except Exception as e:
            logger.error(
                "Error sending %s reminder DM for %s: %s",
                reminder_type,
                ticket.key,
                e,
            )
            return False

    async def handle_button_action(
        self, action_id: str, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle a Slack button action from a CSOPM notification message.

        Delegates to the shared CSOPMButtonActionHandler from packages/slack/csopm/.

        Processes interactive button clicks from CSOPM notification DMs:
        - csopm_acknowledge: Update state to 'ack', post JIRA comment
        - csopm_create_followup: Open modal for follow-up ticket creation
        - csopm_stop_reminders: Stop ketchup reminders for this ticket
        - csopm_enable_reminders: Re-enable ketchup reminders
        - csopm_snooze: Snooze closure reminder for 7 days
        - csopm_close_ticket: Close ticket in JIRA

        Args:
            action_id: The ID of the action button clicked.
            user_id: The Slack user ID who clicked the button.
            ticket_key: The JIRA ticket key associated with the action.
            payload: The full Slack interaction payload.

        Returns:
            True if action was handled successfully, False otherwise.
        """
        logger.info(
            "Delegating button action %s to CSOPMButtonActionHandler for ticket %s",
            action_id,
            ticket_key,
        )

        # Track acknowledgment metric for the notifier service
        if action_id == CSOPMNotificationBlocks.ACTION_ACKNOWLEDGE and self._metrics:
            await self._metrics.increment_counter("csopm.notifications.acknowledged")

        # Delegate to the shared button action handler
        return await self._button_handler.handle_button_action(
            action_id=action_id,
            user_id=user_id,
            ticket_key=ticket_key,
            payload=payload,
        )
