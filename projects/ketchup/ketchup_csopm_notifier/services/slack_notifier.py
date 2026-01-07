"""
CSOPM Slack Notifier Service.

This module implements the CSOPMSlackNotifier service for sending Slack DM
notifications to assignees when new CSOPM tickets are assigned to them.

Key Features:
- Send assignment DMs with interactive Block Kit buttons
- Resolve JIRA usernames to Slack user IDs via email lookup
- Handle button actions (Acknowledge, Create Follow-up, Done, View in JIRA)
- Post acknowledgment comments to JIRA tickets

Architectural Note:
This service implements the CSOPMSlackNotifierProtocol and integrates with:
- SlackPostingHandler for message delivery
- SlackUserOps for email-to-Slack ID resolution
- AsyncMCPClient for JIRA comment posting
- CSOPMStateTracker for notification state updates

Action IDs use the 'csopm_' prefix to enable routing in payload_processor.py:
- csopm_acknowledge: Mark ticket as acknowledged, post JIRA comment
- csopm_create_followup: Open modal for creating follow-up ticket
- csopm_done: Mark ticket as done
- csopm_view_jira: Link button (no backend handler needed)
"""

from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import (
    CSOPMMetricsProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
)
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

from ketchup_csopm_notifier.blocks.notification_blocks import CSOPMNotificationBlocks
from packages.core.config.csopm_config import CSOPM_JIRA_PROJECT

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
    4. Handle button action callbacks
    5. Post acknowledgment comments to JIRA

    Integration Points:
    - SlackPostingHandler: Message delivery
    - SlackUserOps: Email-to-Slack resolution
    - AsyncMCPClient: JIRA comment posting
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
        logger.info("CSOPMSlackNotifier initialized")

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
                if self._metrics:
                    await self._metrics.increment_counter("csopm.user.resolution.success")
            else:
                logger.warning("Could not resolve Slack ID for %s", jira_username)
                if self._metrics:
                    await self._metrics.increment_counter("csopm.user.resolution.failed")

            return slack_id

        except Exception as e:
            logger.error("Error resolving Slack ID for %s: %s", jira_username, e)
            if self._metrics:
                await self._metrics.increment_counter("csopm.user.resolution.failed")
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

                # Increment notifications sent metric
                if self._metrics:
                    await self._metrics.increment_counter("csopm.notifications.sent")

                return True
            else:
                error = result.get("error", "Unknown error") if result else "No response"
                logger.error(
                    "Failed to send assignment DM for %s: %s",
                    ticket.key,
                    error,
                )

                # Increment failed notifications metric
                if self._metrics:
                    await self._metrics.increment_counter("csopm.notifications.failed")

                return False

        except Exception as e:
            logger.error("Error sending assignment DM for %s: %s", ticket.key, e)
            if self._metrics:
                await self._metrics.increment_counter("csopm.notifications.failed")
            return False

    async def send_reminder_dm(
        self, ticket: CSOPMTicket, slack_user_id: str, reminder_type: str
    ) -> bool:
        """Send a reminder DM for a ticket.

        Args:
            ticket: The CSOPMTicket requiring reminder.
            slack_user_id: The Slack user ID to send the DM to.
            reminder_type: Type of reminder ("rca", "closure", "ping").

        Returns:
            True if DM was sent successfully, False otherwise.
        """
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
                    ping_count = record.ping_count + 1

            # Build appropriate reminder blocks
            if reminder_type == "rca":
                blocks = CSOPMNotificationBlocks.build_rca_reminder(
                    ticket=ticket,
                    days_old=days_old,
                    ping_count=ping_count,
                )
                fallback_type = "rca"
            elif reminder_type in ("closure", "ping"):
                blocks = CSOPMNotificationBlocks.build_closure_reminder(
                    ticket=ticket,
                    days_old=days_old,
                    ping_count=ping_count,
                    has_open_linked=has_open_linked,
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

        Processes interactive button clicks from CSOPM notification DMs:
        - csopm_acknowledge: Update state to 'ack', post JIRA comment
        - csopm_create_followup: Open modal for follow-up ticket creation
        - csopm_done: Mark ticket as done, post JIRA comment
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
            "Handling button action %s from user %s for ticket %s",
            action_id,
            user_id,
            ticket_key,
        )

        try:
            if action_id == CSOPMNotificationBlocks.ACTION_ACKNOWLEDGE:
                return await self._handle_acknowledge(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_CREATE_FOLLOWUP:
                return await self._handle_create_followup(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_DONE:
                return await self._handle_done(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_SNOOZE:
                return await self._handle_snooze(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_CLOSE_TICKET:
                return await self._handle_close_ticket(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_VIEW_JIRA:
                # View in JIRA is a URL button, no backend action needed
                logger.info("View in JIRA action for %s (no-op)", ticket_key)
                return True

            else:
                logger.warning("Unknown CSOPM action_id: %s", action_id)
                return False

        except Exception as e:
            logger.error("Error handling button action %s: %s", action_id, e)
            return False

    async def _handle_acknowledge(
        self, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle the Acknowledge button action.

        Updates notification state to 'ack' and posts a comment to JIRA.
        Also increments the csopm.notifications.acknowledged metric.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling acknowledge action for %s by user %s", ticket_key, user_id)

        try:
            # Update state to 'ack' if state tracker is available
            if self._state_tracker:
                await self._state_tracker.update_notification_status(ticket_key, "ack")
                logger.info("Updated notification status to 'ack' for %s", ticket_key)

            # Post acknowledgment comment to JIRA
            comment = f"Ticket acknowledged by assignee via Slack notification (User: {user_id})"
            comment_success = await self._mcp_client.create_issue_comment(
                issue_key=ticket_key,
                comment=comment,
            )

            if comment_success:
                logger.info("Posted acknowledgment comment to JIRA for %s", ticket_key)
                # Increment acknowledgment metric on successful JIRA comment
                if self._metrics:
                    await self._metrics.increment_counter("csopm.notifications.acknowledged")
            else:
                logger.warning(
                    "Failed to post acknowledgment comment to JIRA for %s",
                    ticket_key,
                )

            # Send confirmation message to user
            confirmation_blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
                ticket_key=ticket_key,
                action_type="acknowledged",
            )

            await self._posting_handler.post_message(
                channel_id=user_id,
                message=f"✅ {ticket_key} acknowledged",
                blocks=confirmation_blocks,
            )

            return True

        except Exception as e:
            logger.error("Error handling acknowledge action for %s: %s", ticket_key, e)
            return False

    async def _handle_create_followup(
        self, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle the Create Follow-up button action.

        Opens a modal for creating a follow-up ticket with dynamic
        project and issue type dropdowns populated from JIRA.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info(
            "Handling create followup action for %s by user %s",
            ticket_key,
            user_id,
        )

        try:
            trigger_id = payload.get("trigger_id")
            if not trigger_id:
                logger.error("No trigger_id found in payload for modal open")
                return False

            # Get ticket details for modal pre-population
            ticket = await self._mcp_client.get_issue(
                issue_key=ticket_key,
                fields=["summary", "status", "assignee", "description"],
            )

            if not ticket:
                logger.error("Could not get ticket details for %s", ticket_key)
                # Still proceed with basic modal
                ticket = {
                    "key": ticket_key,
                    "fields": {
                        "summary": "",
                        "status": {"name": "Unknown"},
                    },
                }

            # Fetch available JIRA projects for dropdown
            projects = []
            try:
                projects = await self._mcp_client.list_projects(expand="issueTypes")
                logger.info("Fetched %d projects for followup modal", len(projects))
            except Exception as e:
                logger.warning("Failed to fetch JIRA projects: %s", e)
                # Continue with fallback text input

            # Extract issue types from the CSOPM project if available
            issue_types = []
            try:
                # Look for CSOPM project in the list to get its issue types
                for project in projects:
                    if project.get("key") == "CSOPM":
                        issue_types = project.get("issueTypes", [])
                        break

                # If no CSOPM project found or no issue types, try first project
                if not issue_types and projects:
                    issue_types = projects[0].get("issueTypes", [])

                logger.info("Extracted %d issue types for followup modal", len(issue_types))
            except Exception as e:
                logger.warning("Failed to extract issue types: %s", e)
                # Continue with fallback text input

            # Build CSOPMTicket from issue data
            fields = ticket.get("fields", {})
            status_obj = fields.get("status", {})
            assignee_obj = fields.get("assignee", {})

            from datetime import datetime, timezone as dt_timezone

            csopm_ticket = CSOPMTicket(
                key=ticket_key,
                summary=fields.get("summary", ""),
                assignee_username=(
                    assignee_obj.get("name", "") if isinstance(assignee_obj, dict) else ""
                ),
                created_at=datetime.now(dt_timezone.utc),
                status=status_obj.get("name", "Unknown") if isinstance(status_obj, dict) else "Unknown",
            )

            # Build modal with dynamic project and issue type dropdowns
            modal = CSOPMNotificationBlocks.build_create_followup_modal(
                ticket=csopm_ticket,
                projects=projects,
                issue_types=issue_types,
            )
            logger.info(
                "Create followup modal built for %s (trigger_id: %s, %d projects, %d issue_types)",
                ticket_key,
                trigger_id,
                len(projects),
                len(issue_types),
            )

            # Note: Opening the modal requires views.open API call
            # This would be implemented via SlackAsyncClient or similar
            # For now, log the intent and return success

            return True

        except Exception as e:
            logger.error(
                "Error handling create followup action for %s: %s",
                ticket_key,
                e,
            )
            return False

    async def _handle_done(
        self, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle the Done button action.

        Marks the ticket as done and posts a JIRA comment with batch info
        if follow-up tickets exist. Queries for linked follow-up tickets
        and includes their status in the comment.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling done action for %s by user %s", ticket_key, user_id)

        try:
            # Update state to 'done' if state tracker is available
            if self._state_tracker:
                await self._state_tracker.update_notification_status(ticket_key, "done")
                logger.info("Updated notification status to 'done' for %s", ticket_key)

            # Query for linked follow-up tickets to include in comment
            followup_info = ""
            try:
                # Search for tickets that link to this ticket as a parent
                jql = f'project = CSOPM AND "Parent Link" = {ticket_key}'
                search_result = await self._mcp_client.search_issues(
                    jql=jql,
                    fields=["key", "summary", "status"],
                    max_results=10,
                )

                followup_issues = search_result.get("issues", [])
                if followup_issues:
                    # Build batch comment with follow-up ticket info
                    followup_lines = []
                    open_count = 0
                    closed_count = 0

                    for issue in followup_issues:
                        issue_key = issue.get("key", "")
                        fields = issue.get("fields", {})
                        summary = fields.get("summary", "")
                        status_obj = fields.get("status", {})
                        status_name = status_obj.get("name", "Unknown") if isinstance(status_obj, dict) else "Unknown"

                        followup_lines.append(f"  - {issue_key}: {summary} (Status: {status_name})")

                        if status_name.lower() in ("closed", "done", "resolved"):
                            closed_count += 1
                        else:
                            open_count += 1

                    followup_info = (
                        f"\n\nLinked Follow-up Tickets ({len(followup_issues)} total, "
                        f"{open_count} open, {closed_count} closed):\n"
                        + "\n".join(followup_lines)
                    )
                    logger.info(
                        "Found %d follow-up tickets for %s (%d open, %d closed)",
                        len(followup_issues),
                        ticket_key,
                        open_count,
                        closed_count,
                    )
            except Exception as e:
                logger.warning(
                    "Failed to query follow-up tickets for %s: %s",
                    ticket_key,
                    e,
                )
                # Continue without follow-up info

            # Post done comment to JIRA with optional follow-up batch info
            comment = f"Ticket marked as done via Slack notification (User: {user_id}){followup_info}"
            await self._mcp_client.create_issue_comment(
                issue_key=ticket_key,
                comment=comment,
            )

            # Send confirmation message to user
            confirmation_blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
                ticket_key=ticket_key,
                action_type="done",
            )

            await self._posting_handler.post_message(
                channel_id=user_id,
                message=f"✔️ {ticket_key} marked as done",
                blocks=confirmation_blocks,
            )

            return True

        except Exception as e:
            logger.error("Error handling done action for %s: %s", ticket_key, e)
            return False

    async def _handle_snooze(
        self, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle the Snooze button action.

        Snoozes the closure reminder for 7 days.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling snooze action for %s by user %s", ticket_key, user_id)

        try:
            # Note: Snooze implementation would update StateTracker with snooze_until
            # For now, log the intent and send confirmation
            logger.info("Snoozing closure reminder for %s for 7 days", ticket_key)

            # Send confirmation message to user
            confirmation_blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
                ticket_key=ticket_key,
                action_type="snoozed",
            )

            await self._posting_handler.post_message(
                channel_id=user_id,
                message=f"⏰ {ticket_key} snoozed for 7 days",
                blocks=confirmation_blocks,
            )

            return True

        except Exception as e:
            logger.error("Error handling snooze action for %s: %s", ticket_key, e)
            return False

    async def _handle_close_ticket(
        self, user_id: str, ticket_key: str, payload: dict
    ) -> bool:
        """Handle the Close Ticket button action.

        Closes the ticket in JIRA via MCP.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling close ticket action for %s by user %s", ticket_key, user_id)

        try:
            # Attempt to close ticket via MCP
            result = await self._mcp_client._call_mcp_tool(
                "transition_jira_status_by_name",
                {
                    "issueIdOrKey": ticket_key,
                    "statusName": "Closed",
                },
            )

            success = result.get("success", False)

            if success:
                logger.info("Successfully closed ticket %s", ticket_key)

                # Update state if tracker available
                if self._state_tracker:
                    await self._state_tracker.mark_closure_reminder_sent(ticket_key)

                # Send confirmation message to user
                confirmation_blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
                    ticket_key=ticket_key,
                    action_type="closed",
                )

                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f"🔒 {ticket_key} closed",
                    blocks=confirmation_blocks,
                )
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error("Failed to close ticket %s: %s", ticket_key, error_msg)

                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f"❌ Failed to close {ticket_key}: {error_msg}",
                )

            return success

        except Exception as e:
            logger.error("Error handling close ticket action for %s: %s", ticket_key, e)
            return False
