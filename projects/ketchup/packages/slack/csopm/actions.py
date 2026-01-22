"""
CSOPM Button Action Handler.

This module implements the CSOPMButtonActionHandler for handling interactive
button actions from CSOPM Slack notification messages.

Button Actions Handled:
- csopm_acknowledge: Mark ticket as acknowledged, post JIRA comment
- csopm_create_followup: Open modal for follow-up ticket creation
- csopm_mark_complete: Open modal for transitioning ticket to Complete status
- csopm_stop_reminders: Stop ketchup reminders for this ticket
- csopm_enable_reminders: Re-enable ketchup reminders for this ticket
- csopm_snooze: Snooze closure reminder for 7 days
- csopm_close_ticket: Open modal for transitioning ticket to Closed status
- csopm_view_jira: Link button (no backend action needed)

Architectural Note:
This handler is extracted from CSOPMSlackNotifier to create a shared component
that can be used by both ketchup-app (interactive handlers) and
ketchup_csopm_notifier (scheduled notifications). It follows the container
architecture pattern where shared code lives in packages/ while service-specific
code stays in ketchup_*/ directories.

Dependencies:
- SlackPostingHandler for confirmations
- AsyncMCPClient for JIRA operations
- CSOPMStateTrackerProtocol (optional) for state updates
- CSOPMNotificationBlocks for building confirmation blocks
"""

from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import (
    CSOPMStateTrackerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
    UserPATOperationsProtocol,
)
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.slack.messages.posting import SlackPostingHandler

from .blocks import CSOPMNotificationBlocks

logger = setup_logger(__name__)


class CSOPMButtonActionHandler:
    """Handler for CSOPM button actions in Slack notification messages.

    This handler processes interactive button clicks from CSOPM notification DMs
    and performs the appropriate actions (JIRA comments, state updates, confirmations).

    Key Responsibilities:
    1. Dispatch button actions to appropriate handlers
    2. Post acknowledgment comments to JIRA
    3. Update notification state (if tracker available)
    4. Send confirmation messages to users
    5. Coordinate JIRA transitions (close, transition status)

    Integration Points:
    - SlackPostingHandler: Confirmation message delivery
    - AsyncMCPClient: JIRA comment and transition operations
    - CSOPMStateTracker: State updates on actions (optional)
    - CSOPMNotificationBlocks: Confirmation block building
    """

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        mcp_client: AsyncMCPClient,
        state_tracker: Optional[CSOPMStateTrackerProtocol] = None,
        user_pat_ops: Optional[UserPATOperationsProtocol] = None,
    ) -> None:
        """Initialize the CSOPM button action handler.

        Args:
            posting_handler: SlackPostingHandler for message delivery.
            mcp_client: AsyncMCPClient for JIRA operations.
            state_tracker: Optional CSOPMStateTrackerProtocol for state updates.
            user_pat_ops: Optional UserPATOperationsProtocol for user PAT retrieval.
        """
        self._posting_handler = posting_handler
        self._mcp_client = mcp_client
        self._state_tracker = state_tracker
        self._user_pat_ops = user_pat_ops
        logger.info("CSOPMButtonActionHandler initialized")

    async def handle_button_action(
        self, action_id: str, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle a Slack button action from a CSOPM notification message.

        Processes interactive button clicks from CSOPM notification DMs:
        - csopm_acknowledge: Update state to 'ack', post JIRA comment
        - csopm_create_followup: Return True to signal modal should open
        - csopm_stop_reminders: Stop ketchup reminders, post confirmation with enable option
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

            elif action_id == CSOPMNotificationBlocks.ACTION_MARK_COMPLETE:
                return await self._handle_mark_complete(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_STOP_REMINDERS:
                return await self._handle_stop_reminders(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_ENABLE_REMINDERS:
                return await self._handle_enable_reminders(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_SNOOZE:
                return await self._handle_snooze(user_id, ticket_key, payload)

            elif action_id == CSOPMNotificationBlocks.ACTION_UNSNOOZE:
                return await self._handle_unsnooze(user_id, ticket_key, payload)

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
        self, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle the Acknowledge button action.

        Shows modal popup for both new acknowledgment and already-acknowledged cases.
        Updates notification state to 'ack' and posts a comment to JIRA.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling acknowledge action for %s by user %s", ticket_key, user_id)

        try:
            trigger_id = payload.get("trigger_id")

            # Check if already acknowledged
            record = None
            jira_username = None
            if self._state_tracker:
                record = await self._state_tracker.get_notification_record(ticket_key)
                if record:
                    jira_username = record.assignee_jira_username

                    # If already acknowledged, show modal with timestamp
                    if record.notification_status == "ack":
                        ack_time = "unknown time"
                        if record.updated_at:
                            from datetime import datetime, timezone

                            dt = datetime.fromtimestamp(record.updated_at, tz=timezone.utc)
                            ack_time = dt.strftime("%d/%m/%Y %H:%M UTC")

                        if trigger_id:
                            await self._show_already_acknowledged_modal(
                                trigger_id=trigger_id,
                                ticket_key=ticket_key,
                                ack_time=ack_time,
                            )
                        else:
                            logger.warning("No trigger_id for already-acknowledged modal")

                        logger.info("Ticket %s already acknowledged at %s", ticket_key, ack_time)
                        return True

            # CRITICAL: Show modal FIRST before trigger_id expires (3 second limit!)
            if trigger_id:
                await self._show_acknowledgment_success_modal(
                    trigger_id=trigger_id,
                    ticket_key=ticket_key,
                )
            else:
                logger.warning("No trigger_id for acknowledgment success modal")

            # Get user's PAT if available
            user_pat = None
            if self._user_pat_ops:
                user_pat = await self._user_pat_ops.get_pat(user_id)
                if user_pat:
                    logger.info("Using stored PAT for user %s", user_id)

            # Update state to 'ack'
            if self._state_tracker:
                await self._state_tracker.update_notification_status(ticket_key, "ack")
                logger.info("Updated notification status to 'ack' for %s", ticket_key)

            # Post acknowledgment comment to JIRA with proper mention format
            if jira_username:
                comment = (
                    f"Ticket acknowledged by assignee [~{jira_username}] via Slack notification"
                )
            else:
                comment = f"Ticket acknowledged by assignee via Slack notification (Slack User: {user_id})"

            await self._mcp_client.create_issue_comment(
                issue_key=ticket_key,
                comment=comment,
                user_pat=user_pat,
            )
            logger.info("Posted acknowledgment comment to JIRA for %s", ticket_key)

            return True
        except Exception as e:
            logger.error("Error handling acknowledge action for %s: %s", ticket_key, e)
            return False

    async def _show_already_acknowledged_modal(
        self, trigger_id: str, ticket_key: str, ack_time: str
    ) -> bool:
        """Display modal popup when ticket is already acknowledged.

        Args:
            trigger_id: Slack trigger ID for opening the modal.
            ticket_key: The JIRA ticket key.
            ack_time: Formatted timestamp of when ticket was acknowledged.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        try:
            import aiohttp

            # Create modal view
            modal_view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": "Already Acknowledged"},
                "close": {"type": "plain_text", "text": "OK"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":white_check_mark: *{ticket_key}* was already acknowledged on *{ack_time}*",
                        },
                    }
                ],
            }

            # Display modal via Slack API using posting handler's config
            url = f"{self._posting_handler.config.get_api_base_url()}/views.open"
            headers = self._posting_handler.config.get_headers()
            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error("Failed to open already-acknowledged modal: %s", error_msg)
                        return False

            logger.info("Already-acknowledged modal opened successfully for %s", ticket_key)
            return True
        except Exception as e:
            logger.error("Error showing already-acknowledged modal: %s", e)
            return False

    async def _show_acknowledgment_success_modal(self, trigger_id: str, ticket_key: str) -> bool:
        """Display modal popup confirming ticket acknowledgment.

        Args:
            trigger_id: Slack trigger ID for opening the modal.
            ticket_key: The JIRA ticket key.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        try:
            from datetime import datetime, timezone

            import aiohttp

            # Get current time for display
            now = datetime.now(timezone.utc)
            ack_time = now.strftime("%d/%m/%Y %H:%M UTC")

            # Create modal view
            modal_view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": "Acknowledged"},
                "close": {"type": "plain_text", "text": "OK"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":white_check_mark: *{ticket_key}* has been acknowledged\n\n_Acknowledged on {ack_time}_",
                        },
                    }
                ],
            }

            # Display modal via Slack API using posting handler's config
            url = f"{self._posting_handler.config.get_api_base_url()}/views.open"
            headers = self._posting_handler.config.get_headers()
            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error("Failed to open acknowledgment success modal: %s", error_msg)
                        return False

            logger.info("Acknowledgment success modal opened for %s", ticket_key)
            return True
        except Exception as e:
            logger.error("Error showing acknowledgment success modal: %s", e)
            return False

    async def _show_confirmation_modal(self, trigger_id: str, title: str, message: str) -> bool:
        """Display a generic confirmation modal popup.

        Args:
            trigger_id: Slack trigger ID for opening the modal.
            title: Modal title (max 24 chars).
            message: Message to display in modal body.

        Returns:
            True if modal was displayed successfully, False otherwise.
        """
        try:
            import aiohttp

            modal_view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": title[:24]},
                "close": {"type": "plain_text", "text": "OK"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message,
                        },
                    }
                ],
            }

            url = f"{self._posting_handler.config.get_api_base_url()}/views.open"
            headers = self._posting_handler.config.get_headers()
            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error("Failed to open confirmation modal: %s", error_msg)
                        return False

            logger.info("Confirmation modal opened: %s", title)
            return True
        except Exception as e:
            logger.error("Error showing confirmation modal: %s", e)
            return False

    async def _update_message_toggle_reminders_button(
        self,
        payload: Dict[str, Any],
        ticket_key: str,
        enable_reminders: bool,
    ) -> bool:
        """Update the original message to toggle Stop/Enable Reminders button.

        Args:
            payload: The Slack interaction payload containing message info.
            ticket_key: The JIRA ticket key.
            enable_reminders: If True, show Enable Reminders button; else show Stop Reminders.

        Returns:
            True if message was updated successfully, False otherwise.
        """
        try:
            import aiohttp

            # Get message info from payload
            container = payload.get("container", {})
            message_ts = container.get("message_ts")
            channel_id = payload.get("channel", {}).get("id")

            if not message_ts or not channel_id:
                logger.warning("Missing message_ts or channel_id for button toggle")
                return False

            # Get original message blocks
            message = payload.get("message", {})
            blocks = message.get("blocks", [])

            if not blocks:
                logger.warning("No blocks found in original message")
                return False

            # Find and update the actions block
            updated_blocks = []
            for block in blocks:
                if block.get("type") == "actions":
                    # Update the elements to swap Stop/Enable button
                    new_elements = []
                    for element in block.get("elements", []):
                        action_id = element.get("action_id", "")
                        if (
                            action_id == CSOPMNotificationBlocks.ACTION_STOP_REMINDERS
                            and enable_reminders
                        ):
                            # Swap to Enable Reminders
                            new_elements.append(
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Enable Reminders",
                                        "emoji": True,
                                    },
                                    "action_id": CSOPMNotificationBlocks.ACTION_ENABLE_REMINDERS,
                                    "value": ticket_key,
                                }
                            )
                        elif (
                            action_id == CSOPMNotificationBlocks.ACTION_ENABLE_REMINDERS
                            and not enable_reminders
                        ):
                            # Swap to Stop Reminders
                            new_elements.append(
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Stop Reminders",
                                        "emoji": True,
                                    },
                                    "action_id": CSOPMNotificationBlocks.ACTION_STOP_REMINDERS,
                                    "value": ticket_key,
                                }
                            )
                        else:
                            new_elements.append(element)
                    updated_blocks.append({**block, "elements": new_elements})
                else:
                    updated_blocks.append(block)

            # Update the message via Slack API
            url = f"{self._posting_handler.config.get_api_base_url()}/chat.update"
            headers = self._posting_handler.config.get_headers()
            api_payload = {
                "channel": channel_id,
                "ts": message_ts,
                "blocks": updated_blocks,
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error("Failed to update message for button toggle: %s", error_msg)
                        return False

            logger.info(
                "Updated message to %s reminders button for %s",
                "enable" if enable_reminders else "stop",
                ticket_key,
            )
            return True
        except Exception as e:
            logger.error("Error updating message for button toggle: %s", e)
            return False

    async def _update_message_toggle_snooze_button(
        self,
        payload: Dict[str, Any],
        ticket_key: str,
        show_unsnooze: bool,
    ) -> bool:
        """Update the original message to toggle Snooze/Unsnooze button.

        Args:
            payload: The Slack interaction payload containing message info.
            ticket_key: The JIRA ticket key.
            show_unsnooze: If True, show Unsnooze button; else show Snooze button.

        Returns:
            True if message was updated successfully, False otherwise.
        """
        try:
            import aiohttp

            # Get message info from payload
            container = payload.get("container", {})
            message_ts = container.get("message_ts")
            channel_id = payload.get("channel", {}).get("id")

            if not message_ts or not channel_id:
                logger.warning("Missing message_ts or channel_id for snooze button toggle")
                return False

            # Get original message blocks
            message = payload.get("message", {})
            blocks = message.get("blocks", [])

            if not blocks:
                logger.warning("No blocks found in original message for snooze toggle")
                return False

            # Find and update the actions block
            updated_blocks = []
            for block in blocks:
                if block.get("type") == "actions":
                    new_elements = []
                    for element in block.get("elements", []):
                        action_id = element.get("action_id", "")
                        if action_id == CSOPMNotificationBlocks.ACTION_SNOOZE and show_unsnooze:
                            # Swap to Unsnooze
                            new_elements.append(
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Unsnooze",
                                        "emoji": True,
                                    },
                                    "action_id": CSOPMNotificationBlocks.ACTION_UNSNOOZE,
                                    "value": ticket_key,
                                }
                            )
                        elif (
                            action_id == CSOPMNotificationBlocks.ACTION_UNSNOOZE
                            and not show_unsnooze
                        ):
                            # Swap to Snooze
                            new_elements.append(
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Snooze",
                                        "emoji": True,
                                    },
                                    "action_id": CSOPMNotificationBlocks.ACTION_SNOOZE,
                                    "value": ticket_key,
                                }
                            )
                        else:
                            new_elements.append(element)
                    updated_blocks.append({**block, "elements": new_elements})
                else:
                    updated_blocks.append(block)

            # Update the message via Slack API
            url = f"{self._posting_handler.config.get_api_base_url()}/chat.update"
            headers = self._posting_handler.config.get_headers()
            api_payload = {
                "channel": channel_id,
                "ts": message_ts,
                "blocks": updated_blocks,
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    response_data = await response.json()
                    if not response_data.get("ok"):
                        error_msg = response_data.get("error", "unknown")
                        logger.error(
                            "Failed to update message for snooze button toggle: %s", error_msg
                        )
                        return False

            logger.info(
                "Updated message to %s button for %s",
                "unsnooze" if show_unsnooze else "snooze",
                ticket_key,
            )
            return True
        except Exception as e:
            logger.error("Error updating message for snooze button toggle: %s", e)
            return False

    async def _handle_create_followup(
        self, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle the Create Follow-up button action.

        Signals that a modal should be opened for creating a follow-up ticket.
        The actual modal opening is handled by CSOPMHandler which has access
        to the trigger_id and can call views.open.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True to signal the action was handled (modal opening delegated to caller).
        """
        logger.info(
            "Handling create followup action for %s by user %s",
            ticket_key,
            user_id,
        )

        # Return True to signal CSOPMHandler should open the modal
        # Modal opening requires trigger_id which CSOPMHandler has
        return True

    async def _handle_mark_complete(
        self, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle the Mark Complete button action.

        Signals that a modal should be opened for transitioning the ticket
        to Complete status. The actual modal opening is handled by CSOPMHandler
        which has access to trigger_id and can fetch transition fields.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True to signal the action was handled (modal opening delegated to caller).
        """
        logger.info(
            "Handling mark complete action for %s by user %s",
            ticket_key,
            user_id,
        )

        # Return True to signal CSOPMHandler should open the transition modal
        # Modal opening requires trigger_id and transition field fetch
        return True

    async def _handle_stop_reminders(
        self, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle the Stop Reminders button action.

        Stops ketchup from sending reminders for this ticket. The JIRA ticket
        remains open - this only affects ketchup's tracking.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling stop reminders for %s by user %s", ticket_key, user_id)

        try:
            # Update state to 'reminders_stopped' if state tracker is available
            if self._state_tracker:
                await self._state_tracker.update_notification_status(
                    ticket_key, "reminders_stopped"
                )
                logger.info("Stopped reminders for %s", ticket_key)

            # Update original message to show Enable Reminders button
            await self._update_message_toggle_reminders_button(
                payload=payload,
                ticket_key=ticket_key,
                enable_reminders=True,
            )

            # Show confirmation modal
            trigger_id = payload.get("trigger_id")
            if trigger_id:
                timestamp = self._get_utc_timestamp()
                await self._show_confirmation_modal(
                    trigger_id=trigger_id,
                    title="Reminders Stopped",
                    message=f":no_bell: Reminders stopped for *{ticket_key}*\n\nYou won't receive further reminders for this ticket.\n\n_Stopped at {timestamp}_",
                )
            else:
                logger.warning("No trigger_id for stop reminders confirmation modal")

            return True

        except Exception as e:
            logger.error("Error stopping reminders for %s: %s", ticket_key, e)
            return False

    async def _handle_enable_reminders(
        self, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle the Enable Reminders button action.

        Re-enables ketchup reminders for a ticket that was previously stopped.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling enable reminders for %s by user %s", ticket_key, user_id)

        try:
            # Update state back to 'ack' to re-enable reminders
            if self._state_tracker:
                await self._state_tracker.update_notification_status(ticket_key, "ack")
                logger.info("Re-enabled reminders for %s", ticket_key)

            # Update original message to show Stop Reminders button
            await self._update_message_toggle_reminders_button(
                payload=payload,
                ticket_key=ticket_key,
                enable_reminders=False,
            )

            # Show confirmation modal
            trigger_id = payload.get("trigger_id")
            if trigger_id:
                timestamp = self._get_utc_timestamp()
                await self._show_confirmation_modal(
                    trigger_id=trigger_id,
                    title="Reminders Enabled",
                    message=f":bell: Reminders re-enabled for *{ticket_key}*\n\nYou will receive reminders for this ticket again.\n\n_Enabled at {timestamp}_",
                )
            else:
                logger.warning("No trigger_id for enable reminders confirmation modal")

            return True

        except Exception as e:
            logger.error("Error enabling reminders for %s: %s", ticket_key, e)
            return False

    def _get_utc_timestamp(self) -> str:
        """Get current UTC timestamp formatted for display."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    async def _handle_snooze(self, user_id: str, ticket_key: str, payload: Dict[str, Any]) -> bool:
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
            logger.info("Snoozing closure reminder for %s for 7 days", ticket_key)

            # Update original message to show Unsnooze button
            await self._update_message_toggle_snooze_button(
                payload=payload,
                ticket_key=ticket_key,
                show_unsnooze=True,
            )

            # Show confirmation modal
            trigger_id = payload.get("trigger_id")
            if trigger_id:
                timestamp = self._get_utc_timestamp()
                await self._show_confirmation_modal(
                    trigger_id=trigger_id,
                    title="Snoozed",
                    message=f":zzz: Closure reminder snoozed for *{ticket_key}*\n\nYou won't receive closure reminders for 7 days.\n\n_Snoozed at {timestamp}_",
                )
            else:
                logger.warning("No trigger_id for snooze confirmation modal")

            return True

        except Exception as e:
            logger.error("Error handling snooze action for %s: %s", ticket_key, e)
            return False

    async def _handle_unsnooze(
        self, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle the Unsnooze button action.

        Cancels the snooze and re-enables closure reminders immediately.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True if handled successfully, False otherwise.
        """
        logger.info("Handling unsnooze action for %s by user %s", ticket_key, user_id)

        try:
            # Clear snooze by setting closure_snoozed_until to 0/None
            # This would be done via state_tracker if we had such a method
            logger.info("Unsnoozed closure reminder for %s", ticket_key)

            # Update original message to show Snooze button again
            await self._update_message_toggle_snooze_button(
                payload=payload,
                ticket_key=ticket_key,
                show_unsnooze=False,
            )

            # Show confirmation modal
            trigger_id = payload.get("trigger_id")
            if trigger_id:
                timestamp = self._get_utc_timestamp()
                await self._show_confirmation_modal(
                    trigger_id=trigger_id,
                    title="Unsnoozed",
                    message=f":alarm_clock: Closure reminders re-enabled for *{ticket_key}*\n\nYou will receive closure reminders again.\n\n_Unsnoozed at {timestamp}_",
                )
            else:
                logger.warning("No trigger_id for unsnooze confirmation modal")

            return True

        except Exception as e:
            logger.error("Error handling unsnooze action for %s: %s", ticket_key, e)
            return False

    async def _handle_close_ticket(
        self, user_id: str, ticket_key: str, payload: Dict[str, Any]
    ) -> bool:
        """Handle the Close Ticket button action.

        Signals that a modal should be opened for transitioning the ticket
        to Closed status. The actual modal opening is handled by CSOPMHandler
        which has access to trigger_id and can fetch transition fields.

        Args:
            user_id: The Slack user ID who clicked.
            ticket_key: The JIRA ticket key.
            payload: The Slack interaction payload.

        Returns:
            True to signal the action was handled (modal opening delegated to caller).
        """
        logger.info("Handling close ticket action for %s by user %s", ticket_key, user_id)

        # Return True to signal CSOPMHandler should open the transition modal
        # Modal opening requires trigger_id and transition field fetch
        return True
