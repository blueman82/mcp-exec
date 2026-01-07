"""
CSOPM Notifier Scheduler.

Time-based scheduler running the CSOPM notification poll cycle at 08:00 and 16:00 UTC.
Extends BaseScheduler with dual-time scheduling (08:00 and 16:00 UTC).

Poll Cycle Orchestration:
1. Fetch new assignments from JIRA (CSOPMJIRAPoller)
2. Check for reassignments (compare with StateTracker)
3. Send notifications (CSOPMSlackNotifier)
4. Process reminders (CSOPMReminderService)

Architectural Note:
This scheduler runs as a standalone container with its own TypedDI container,
separate from the unified scheduler. This enables:
- Independent scaling and deployment
- Isolated error handling and restarts
- Simpler dependency graph (CSOPM-specific services only)
"""

import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from packages.core.logging import setup_logger
from packages.core.schedulers.base_scheduler import BaseScheduler
from packages.core.typed_di import TypedServiceRegistry
from packages.core.typed_di.protocols import (
    CSOPMJIRAPollerProtocol,
    CSOPMReminderServiceProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
)
from packages.core.config.csopm_config import CSOPM_SCHEDULE_TIMES


class CSOPMScheduler(BaseScheduler):
    """
    Time-based scheduler for CSOPM notification system.

    Runs the notification poll cycle at 08:00 and 16:00 UTC daily.
    Each cycle:
    1. Polls JIRA for new assignments
    2. Checks for ticket reassignments
    3. Sends DM notifications to assignees
    4. Processes RCA and closure reminders

    Uses dual-time scheduling: calculates sleep time to reach either
    08:00 or 16:00 UTC, whichever comes first.

    Health File:
        /tmp/csopm_notifier_health: {unix_timestamp}:{status}
        Status values: starting, running, idle, error, stopped

    Example:
        container = await get_unified_container()
        scheduler = CSOPMScheduler(container=container)
        await scheduler.start()
    """

    # Schedule times in UTC (24-hour format) - configurable via CSOPM_SCHEDULE_TIMES env var
    SCHEDULE_TIMES_UTC = CSOPM_SCHEDULE_TIMES

    def __init__(
        self,
        container: TypedServiceRegistry,
        health_file_prefix: str = "csopm_notifier",
        base_path: str = "/tmp",
        run_on_start: bool = True,
        scheduler_name: Optional[str] = None,
    ):
        """
        Initialize the CSOPM scheduler.

        Args:
            container: TypedServiceRegistry with CSOPM services.
            health_file_prefix: Prefix for health files (default: 'csopm_notifier').
            base_path: Base directory for health files (default: '/tmp').
            run_on_start: Whether to run task immediately on startup (default: True).
            scheduler_name: Name for logging (defaults to 'CSOPMScheduler').
        """
        # Use 12-hour interval as fallback (480 minutes = 8 hours)
        # Actual scheduling uses get_sleep_seconds() with dual-time calculation
        super().__init__(
            health_file_prefix=health_file_prefix,
            base_path=base_path,
            interval_minutes=480,
            run_on_start=run_on_start,
            scheduler_name=scheduler_name or "CSOPMScheduler",
        )

        self._container = container
        self.logger = setup_logger(__name__)
        self.logger.info(
            "CSOPMScheduler initialized with schedule times: %s",
            self.SCHEDULE_TIMES_UTC,
        )

    def get_sleep_seconds(self) -> int:
        """
        Calculate seconds to sleep until next scheduled time (08:00 or 16:00 UTC).

        Implements dual-time scheduling by finding the nearest occurrence
        of either 08:00 or 16:00 UTC.

        Returns:
            Number of seconds to sleep until next scheduled run.
        """
        now = datetime.now(timezone.utc)

        # Calculate next occurrence for each schedule time
        next_times: List[datetime] = []

        for schedule_time in self.SCHEDULE_TIMES_UTC:
            parts = schedule_time.split(":")
            target_hour = int(parts[0])
            target_minute = int(parts[1])

            # Create target time for today
            target_today = now.replace(
                hour=target_hour, minute=target_minute, second=0, microsecond=0
            )

            # If target time has passed today, schedule for tomorrow
            if now >= target_today:
                target_today = target_today + timedelta(days=1)

            next_times.append(target_today)

        # Find the nearest scheduled time
        next_run = min(next_times)
        seconds_until = (next_run - now).total_seconds()

        self.logger.debug(
            "Next CSOPM run at %s (in %d seconds)",
            next_run.strftime("%Y-%m-%d %H:%M:%S UTC"),
            int(seconds_until),
        )

        return int(max(seconds_until, 60))  # Minimum 1 minute sleep

    async def run_task(self) -> None:
        """
        Execute the CSOPM notification poll cycle.

        Orchestrates the full notification cycle:
        1. Fetch new assignments from JIRA
        2. Filter out already-notified tickets
        3. Check for reassignments (compare StateTracker with current assignees)
        4. Send DM notifications to assignees
        5. Process RCA and closure reminders

        All services are resolved from the TypedDI container.
        """
        self.logger.info("Starting CSOPM notification poll cycle")
        start_time = time.time()

        try:
            # Resolve services from container
            poller = await self._container.aget(CSOPMJIRAPollerProtocol)
            notifier = await self._container.aget(CSOPMSlackNotifierProtocol)
            state_tracker = await self._container.aget(CSOPMStateTrackerProtocol)
            reminder_service = await self._container.aget(CSOPMReminderServiceProtocol)

            # Step 1: Poll JIRA for new assignments
            self.logger.info("Step 1: Polling JIRA for new assignments")
            new_tickets = await poller.poll_for_new_assignments()
            self.logger.info("Found %d tickets from JIRA", len(new_tickets))

            # Step 2: Filter out already-notified tickets and check for reassignments
            self.logger.info("Step 2: Checking notification state and reassignments")
            tickets_to_notify: List[CSOPMTicket] = []
            reassignment_count = 0

            for ticket in new_tickets:
                record = await state_tracker.get_notification_record(ticket.key)

                if record is None:
                    # New ticket - needs notification
                    tickets_to_notify.append(ticket)
                    self.logger.debug(
                        "Ticket %s is new, adding to notification queue",
                        ticket.key,
                    )
                else:
                    # Existing record - check for reassignment
                    stored_assignee = record.assignee_jira_username
                    current_assignee = ticket.assignee_username

                    if stored_assignee and current_assignee != stored_assignee:
                        # Reassignment detected - handle it
                        self.logger.info(
                            "Reassignment detected for %s: %s -> %s",
                            ticket.key,
                            stored_assignee,
                            current_assignee,
                        )

                        try:
                            # Resolve new assignee's Slack ID
                            new_slack_id = await notifier.resolve_slack_user_id(
                                current_assignee
                            )

                            if new_slack_id:
                                # Call handle_reassignment to update state
                                await state_tracker.handle_reassignment(
                                    ticket_key=ticket.key,
                                    new_jira_username=current_assignee,
                                    new_slack_id=new_slack_id,
                                )

                                # Send notification to new assignee
                                await notifier.send_assignment_dm(ticket, new_slack_id)
                                reassignment_count += 1

                                self.logger.info(
                                    "Handled reassignment for %s to %s",
                                    ticket.key,
                                    current_assignee,
                                )
                            else:
                                self.logger.warning(
                                    "Could not resolve Slack ID for new assignee %s on %s",
                                    current_assignee,
                                    ticket.key,
                                )
                        except Exception as e:
                            self.logger.error(
                                "Error handling reassignment for %s: %s",
                                ticket.key,
                                e,
                            )
                    else:
                        self.logger.debug(
                            "Ticket %s already tracked (status: %s, assignee: %s)",
                            ticket.key,
                            record.notification_status,
                            current_assignee,
                        )

            self.logger.info(
                "Filtered to %d new tickets needing notification",
                len(tickets_to_notify),
            )

            # Step 3: Send notifications for new tickets
            self.logger.info("Step 3: Sending notifications")
            notification_count = 0
            notification_failures = 0

            for ticket in tickets_to_notify:
                try:
                    # Resolve Slack user ID from JIRA username
                    slack_user_id = await notifier.resolve_slack_user_id(
                        ticket.assignee_username
                    )

                    if not slack_user_id:
                        self.logger.warning(
                            "Could not resolve Slack ID for %s (assignee: %s)",
                            ticket.key,
                            ticket.assignee_username,
                        )
                        notification_failures += 1
                        continue

                    # Send DM notification
                    success = await notifier.send_assignment_dm(ticket, slack_user_id)

                    if success:
                        # Create notification record in StateTracker
                        # Uses correct API signature: (ticket: CSOPMTicket, slack_id: str)
                        await state_tracker.create_notification_record(
                            ticket=ticket,
                            slack_id=slack_user_id,
                        )
                        notification_count += 1
                        self.logger.info(
                            "Sent notification for %s to %s",
                            ticket.key,
                            slack_user_id,
                        )
                    else:
                        notification_failures += 1
                        self.logger.warning(
                            "Failed to send notification for %s",
                            ticket.key,
                        )

                except Exception as e:
                    self.logger.error(
                        "Error processing ticket %s: %s",
                        ticket.key,
                        e,
                    )
                    notification_failures += 1

            self.logger.info(
                "Sent %d notifications (%d failures)",
                notification_count,
                notification_failures,
            )

            # Step 4: Process reminders (RCA and closure)
            self.logger.info("Step 4: Processing reminders")

            # Check RCA reminders (7-day threshold)
            rca_due = await reminder_service.check_rca_reminders()
            self.logger.info("Found %d tickets due for RCA reminder", len(rca_due))

            for reminder in rca_due:
                try:
                    # Get ticket details
                    ticket = await poller.get_ticket_details(reminder.ticket_key)
                    if not ticket:
                        self.logger.warning(
                            "Could not get details for RCA reminder: %s",
                            reminder.ticket_key,
                        )
                        continue

                    # Resolve Slack user and send reminder
                    slack_user_id = await notifier.resolve_slack_user_id(
                        ticket.assignee_username
                    )
                    if slack_user_id:
                        success = await notifier.send_reminder_dm(
                            ticket, slack_user_id, "rca"
                        )
                        if success:
                            await state_tracker.mark_rca_reminder_sent(ticket.key)
                            await state_tracker.increment_ping_count(ticket.key)

                except Exception as e:
                    self.logger.error(
                        "Error processing RCA reminder for %s: %s",
                        reminder.ticket_key,
                        e,
                    )

            # Check closure reminders (45-day threshold)
            closure_due = await reminder_service.check_closure_reminders()
            self.logger.info("Found %d tickets due for closure reminder", len(closure_due))

            for reminder in closure_due:
                try:
                    ticket = await poller.get_ticket_details(reminder.ticket_key)
                    if not ticket:
                        self.logger.warning(
                            "Could not get details for closure reminder: %s",
                            reminder.ticket_key,
                        )
                        continue

                    slack_user_id = await notifier.resolve_slack_user_id(
                        ticket.assignee_username
                    )
                    if slack_user_id:
                        success = await notifier.send_reminder_dm(
                            ticket, slack_user_id, "closure"
                        )
                        if success:
                            await state_tracker.mark_closure_reminder_sent(ticket.key)
                            await state_tracker.increment_ping_count(ticket.key)

                except Exception as e:
                    self.logger.error(
                        "Error processing closure reminder for %s: %s",
                        reminder.ticket_key,
                        e,
                    )

            # Log cycle summary
            elapsed = time.time() - start_time
            self.logger.info(
                "CSOPM poll cycle completed in %.2fs: %d notifications, %d reassignments, %d RCA reminders, %d closure reminders",
                elapsed,
                notification_count,
                reassignment_count,
                len(rca_due),
                len(closure_due),
            )

        except Exception as e:
            self.logger.error("CSOPM poll cycle failed: %s", e, exc_info=True)
            raise
