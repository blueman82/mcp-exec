"""
CSOPM Interactive Element Handler.

Handles Slack interactive elements for CSOPM notifications including:
- Block action button clicks (csopm_acknowledge, csopm_create_followup, csopm_stop_reminders, etc.)
- Modal view submissions (csopm_create_followup_modal)

This handler routes interactive events from payload_processor.py to the
CSOPMButtonActionHandler service for processing.

Architectural Note:
This is the first CSOPM interactive handler in the Ketchup system. It establishes
patterns for how CSOPM-related interactions are processed:
1. Action IDs use the 'csopm_' prefix for routing in payload_processor.py
2. Button values contain the ticket_key for context
3. Modal submissions use callback_id 'csopm_create_followup_modal'
4. MCP integration for JIRA operations (create_jira_issue, link_issues)

Action ID Naming Convention:
- csopm_acknowledge: Mark ticket as acknowledged
- csopm_create_followup: Open modal to create follow-up ticket
- csopm_stop_reminders: Stop ketchup reminders for this ticket
- csopm_enable_reminders: Re-enable ketchup reminders
- csopm_snooze: Snooze closure reminder for 7 days
- csopm_close_ticket: Close ticket in JIRA
- csopm_view_jira: Link button (no backend handling needed)

Modal Callback IDs:
- csopm_create_followup_modal: Create follow-up ticket submission
"""

import json
from typing import Any, Dict, List, Optional, Union

import aiohttp

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import CSOPMButtonActionHandlerProtocol
from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
    CSOPMStateTrackerProtocol,
    UserPATOperationsProtocol,
)
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    SlackUserOpsProtocol,
)
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


# CSOPM action ID prefix for routing
CSOPM_ACTION_PREFIX = "csopm_"

# Modal callback IDs
CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID = "csopm_create_followup_modal"
CSOPM_STATUS_TRANSITION_MODAL_CALLBACK_ID = "csopm_status_transition_modal"
CSOPM_REASSIGN_MODAL_CALLBACK_ID = "csopm_reassign_modal"

# Action IDs for modal selections (triggers dynamic updates)
CSOPM_PROJECT_SELECT_ACTION_ID = "csopm_project_select"
CSOPM_ISSUETYPE_SELECT_ACTION_ID = "csopm_issuetype_select"


class CSOPMHandler:
    """
    Handler for CSOPM interactive elements.

    Processes block actions and modal submissions for CSOPM notifications.
    Delegates business logic to CSOPMButtonActionHandler service.

    Key Responsibilities:
    1. Extract action context from Slack payloads
    2. Route button clicks to CSOPMButtonActionHandler
    3. Handle modal submissions for follow-up ticket creation
    4. Coordinate MCP calls for JIRA operations
    """

    def __init__(
        self,
        button_handler: CSOPMButtonActionHandlerProtocol,
        mcp_client: AsyncMCPClient,
        posting_handler: SlackPostingHandler,
        user_pat_ops: Optional[UserPATOperationsProtocol] = None,
        state_tracker: Optional[CSOPMStateTrackerProtocol] = None,
        user_ops: Optional[SlackUserOpsProtocol] = None,
    ) -> None:
        """
        Initialize the CSOPM handler.

        Args:
            button_handler: CSOPMButtonActionHandler for button action processing.
            mcp_client: AsyncMCPClient for JIRA MCP operations.
            posting_handler: SlackPostingHandler for modal opening and messages.
            user_pat_ops: Optional UserPATOperations for storing user PATs.
            state_tracker: Optional CSOPMStateTracker for tracking follow-up tickets.
            user_ops: Optional SlackUserOps for email-to-Slack ID resolution.
        """
        self._button_handler = button_handler
        self._mcp_client = mcp_client
        self._posting_handler = posting_handler
        self._user_pat_ops = user_pat_ops
        self._state_tracker = state_tracker
        self._user_ops = user_ops
        logger.info("CSOPMHandler initialized")

    async def handle_block_action(self, payload: Dict[str, Any]) -> bool:
        """
        Handle a block_actions payload for CSOPM buttons.

        Extracts action context and delegates to the appropriate handler
        based on action_id.

        Args:
            payload: The Slack block_actions payload.

        Returns:
            True if action was handled successfully, False otherwise.
        """
        try:
            # Extract action details
            actions = payload.get("actions", [])
            if not actions:
                logger.warning("No actions found in CSOPM block_actions payload")
                return False

            action = actions[0]
            action_id = action.get("action_id", "")
            ticket_key = action.get("value", "")

            # Extract user info
            user = payload.get("user", {})
            user_id = user.get("id")

            if not action_id.startswith(CSOPM_ACTION_PREFIX):
                logger.warning(
                    "Action ID %s does not start with CSOPM prefix",
                    action_id,
                )
                return False

            logger.info(
                "Handling CSOPM block action: action_id=%s, ticket_key=%s, user_id=%s",
                action_id,
                ticket_key,
                user_id,
            )

            # Check if this is a selection action from inside a modal
            # When dispatch_action is True on a modal input, Slack sends block_actions
            # with the view info included
            if action_id == CSOPM_PROJECT_SELECT_ACTION_ID and payload.get("view"):
                logger.info("Detected project selection inside modal, updating issue types")
                return await self.handle_modal_project_selection(payload)

            if action_id == CSOPM_ISSUETYPE_SELECT_ACTION_ID and payload.get("view"):
                logger.info("Detected issue type selection inside modal, fetching field metadata")
                return await self.handle_modal_issuetype_selection(payload)

            if action_id == "csopm_edit_pat" and payload.get("view"):
                logger.info("Detected PAT edit button click, showing PAT input field")
                return await self._handle_edit_pat_button(payload)

            if action_id == "csopm_save_pat" and payload.get("view"):
                logger.info("Detected PAT save button click, storing PAT")
                return await self._handle_save_pat_button(payload)

            # Handle reassign locally (opens modal, no delegation needed)
            if action_id == "csopm_reassign":
                await self._open_reassign_modal(
                    trigger_id=payload.get("trigger_id"),
                    ticket_key=ticket_key,
                    user_id=user_id,
                )
                return True

            # Delegate to notifier's handle_button_action
            success = await self._button_handler.handle_button_action(
                action_id=action_id,
                user_id=user_id,
                ticket_key=ticket_key,
                payload=payload,
            )

            # For create_followup action, we need to open the modal
            if action_id == "csopm_create_followup" and success:
                await self._open_create_followup_modal(
                    trigger_id=payload.get("trigger_id"),
                    ticket_key=ticket_key,
                    user_id=user_id,
                )

            # For mark_complete action, open transition modal with "Complete" target
            elif action_id == "csopm_mark_complete" and success:
                await self._open_status_transition_modal(
                    trigger_id=payload.get("trigger_id"),
                    ticket_key=ticket_key,
                    user_id=user_id,
                    target_status="Complete",
                )

            # For close_ticket action, open transition modal with "Closed" target
            elif action_id == "csopm_close_ticket" and success:
                await self._open_status_transition_modal(
                    trigger_id=payload.get("trigger_id"),
                    ticket_key=ticket_key,
                    user_id=user_id,
                    target_status="Closed",
                )

            return success

        except Exception as e:
            logger.error("Error handling CSOPM block action: %s", e, exc_info=True)
            return False

    async def handle_view_submission(self, payload: Dict[str, Any]) -> Union[bool, Dict[str, Any]]:
        """
        Handle a view_submission payload for CSOPM modals.

        Currently handles:
        - csopm_create_followup_modal: Create follow-up ticket in JIRA

        Args:
            payload: The Slack view_submission payload.

        Returns:
            True if submission was handled successfully.
            False if submission failed.
            Dict with response_action: "errors" for validation errors (keeps modal open).
        """
        try:
            view = payload.get("view", {})
            callback_id = view.get("callback_id", "")

            if callback_id == CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID:
                return await self._handle_create_followup_submission(payload)
            elif callback_id == CSOPM_STATUS_TRANSITION_MODAL_CALLBACK_ID:
                return await self._handle_status_transition_submission(payload)
            elif callback_id == CSOPM_REASSIGN_MODAL_CALLBACK_ID:
                return await self._handle_reassign_submission(payload)
            else:
                logger.warning("Unknown CSOPM modal callback_id: %s", callback_id)
                return False

        except Exception as e:
            logger.error(
                "Error handling CSOPM view submission: %s",
                e,
                exc_info=True,
            )
            return False

    async def _open_create_followup_modal(
        self,
        trigger_id: Optional[str],
        ticket_key: str,
        user_id: str,
    ) -> bool:
        """
        Open the create follow-up modal.

        Fetches JIRA projects and issue types to populate dropdown options,
        then opens the modal via views.open API.

        Args:
            trigger_id: Slack trigger_id for opening modal (required).
            ticket_key: Parent CSOPM ticket key.
            user_id: Slack user ID opening the modal.

        Returns:
            True if modal was opened successfully, False otherwise.
        """
        if not trigger_id:
            logger.error("No trigger_id provided for create followup modal")
            return False

        logger.info(
            "Opening create followup modal for ticket %s (user: %s)",
            ticket_key,
            user_id,
        )

        try:
            # Fetch ticket details for modal pre-population
            ticket_data = await self._mcp_client.get_issue(
                issue_key=ticket_key,
                fields=["summary", "status", "assignee"],
            )

            # Fetch available JIRA projects for dropdown
            projects = []
            try:
                projects = await self._mcp_client.list_projects()
                logger.info("Fetched %d projects for followup modal", len(projects))
            except Exception as e:
                logger.warning("Failed to fetch JIRA projects: %s", e)

            # Determine default project (prefer CSOPM if available)
            default_project_key = None
            if any(p.get("key") == "CSOPM" for p in projects):
                default_project_key = "CSOPM"
            elif projects:
                default_project_key = projects[0].get("key")

            # Fetch issue types for the default project using the new endpoint
            # This endpoint works via iPaaS (unlike expand=issueTypes)
            issue_types = []
            if default_project_key:
                try:
                    issue_types = await self._mcp_client.get_project_issue_types(
                        default_project_key
                    )
                    logger.info(
                        "Fetched %d issue types for default project %s",
                        len(issue_types),
                        default_project_key,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to fetch issue types for %s: %s",
                        default_project_key,
                        e,
                    )

            # Build modal from notification blocks
            from datetime import datetime, timezone

            from packages.core.typed_di.protocols import CSOPMTicket
            from packages.slack.csopm import CSOPMNotificationBlocks

            # Construct CSOPMTicket from JIRA response
            fields = ticket_data.get("fields", {}) if ticket_data else {}
            status_obj = fields.get("status", {})
            assignee_obj = fields.get("assignee", {})

            csopm_ticket = CSOPMTicket(
                key=ticket_key,
                summary=fields.get("summary", ""),
                assignee_username=(
                    assignee_obj.get("name", "") if isinstance(assignee_obj, dict) else ""
                ),
                created_at=datetime.now(timezone.utc),
                status=(
                    status_obj.get("name", "Unknown") if isinstance(status_obj, dict) else "Unknown"
                ),
            )

            # Check if user has a stored PAT and get expiry time
            pat_expiry_minutes = None
            if self._user_pat_ops:
                pat_expiry_minutes = await self._user_pat_ops.get_pat_expiry_minutes(user_id)
                if pat_expiry_minutes:
                    logger.info(
                        "User %s has stored PAT, expires in %d min", user_id, pat_expiry_minutes
                    )

            # Build modal view - issue types are now fetched dynamically on project change
            modal = CSOPMNotificationBlocks.build_create_followup_modal(
                ticket=csopm_ticket,
                projects=projects,
                issue_types=issue_types,
                selected_project_key=default_project_key,
                pat_expiry_minutes=pat_expiry_minutes,
            )

            # Open modal via direct Slack API call (views.open)
            slack_api_token = (
                await self._posting_handler._secrets_manager.get_slack_api_token_async()
            )
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }
            payload = {"trigger_id": trigger_id, "view": modal}

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    result = await response.json()

                    if result.get("ok"):
                        logger.info("Successfully opened create followup modal for %s", ticket_key)
                        return True
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error("Failed to open create followup modal: %s", error)
                        return False

        except Exception as e:
            logger.error(
                "Error opening create followup modal for %s: %s",
                ticket_key,
                e,
                exc_info=True,
            )
            return False

    async def _open_status_transition_modal(
        self,
        trigger_id: Optional[str],
        ticket_key: str,
        user_id: str,
        target_status: str,
    ) -> bool:
        """
        Open a modal for transitioning a ticket to a new status.

        Fetches transition fields required for the target status and opens
        a modal with dynamic field inputs.

        Args:
            trigger_id: Slack trigger_id for opening modal (required).
            ticket_key: JIRA ticket key to transition.
            user_id: Slack user ID opening the modal.
            target_status: Target status name (e.g., "Complete", "Closed").

        Returns:
            True if modal was opened successfully, False otherwise.
        """
        if not trigger_id:
            logger.error("No trigger_id provided for status transition modal")
            return False

        logger.info(
            "Opening status transition modal for %s -> %s (user: %s)",
            ticket_key,
            target_status,
            user_id,
        )

        try:
            import asyncio

            from packages.slack.csopm import CSOPMNotificationBlocks

            # Use hardcoded fields for CSOPM (JIRA API returns nothing for this project)
            field_metadata: List[Dict[str, Any]] = []
            if ticket_key.startswith("CSOPM-") and target_status == "Complete":
                field_metadata = CSOPMNotificationBlocks.CSOPM_COMPLETE_FIELDS
                logger.info(
                    "Using hardcoded CSOPM Complete fields (%d fields)",
                    len(field_metadata),
                )

            # Fetch summary and PAT expiry in parallel to stay within 3s trigger window
            async def _get_summary() -> str:
                try:
                    data = await self._mcp_client.get_issue(
                        issue_key=ticket_key, fields=["summary"]
                    )
                    return data.get("fields", {}).get("summary", "") if data else ""
                except Exception as e:
                    logger.warning("Failed to fetch ticket summary for %s: %s", ticket_key, e)
                    return ""

            async def _get_pat_expiry() -> Optional[int]:
                if self._user_pat_ops:
                    try:
                        return await self._user_pat_ops.get_pat_expiry_minutes(user_id)
                    except Exception:
                        pass
                return None

            async def _get_transition_fields() -> List[Dict[str, Any]]:
                try:
                    result = await self._mcp_client.get_transition_fields(
                        ticket_key=ticket_key, target_status=target_status
                    )
                    logger.info(
                        "Fetched %d fields for transition %s -> %s",
                        len(result),
                        ticket_key,
                        target_status,
                    )
                    return result
                except Exception as e:
                    logger.warning(
                        "Failed to fetch transition fields for %s -> %s: %s",
                        ticket_key,
                        target_status,
                        e,
                    )
                    return []

            if field_metadata:
                # CSOPM: skip transition fields API, just fetch summary + PAT in parallel
                ticket_summary, pat_expiry_minutes = await asyncio.gather(
                    _get_summary(), _get_pat_expiry()
                )
            else:
                # Non-CSOPM: fetch all three in parallel
                ticket_summary, pat_expiry_minutes, field_metadata = await asyncio.gather(
                    _get_summary(), _get_pat_expiry(), _get_transition_fields()
                )

            if pat_expiry_minutes:
                logger.info(
                    "User %s has stored PAT, expires in %d min", user_id, pat_expiry_minutes
                )

            # Build modal
            modal = CSOPMNotificationBlocks.build_status_transition_modal(
                ticket_key=ticket_key,
                target_status=target_status,
                field_metadata=field_metadata,
                ticket_summary=ticket_summary,
                pat_expiry_minutes=pat_expiry_minutes,
            )

            # Open modal via Slack API
            slack_api_token = (
                await self._posting_handler._secrets_manager.get_slack_api_token_async()
            )
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }
            payload_data = {"trigger_id": trigger_id, "view": modal}

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload_data) as response:
                    result = await response.json()

                    if result.get("ok"):
                        logger.info(
                            "Successfully opened status transition modal for %s -> %s",
                            ticket_key,
                            target_status,
                        )
                        return True
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error("Failed to open status transition modal: %s", error)
                        return False

        except Exception as e:
            logger.error(
                "Error opening status transition modal for %s: %s",
                ticket_key,
                e,
                exc_info=True,
            )
            return False

    async def handle_modal_project_selection(self, payload: Dict[str, Any]) -> bool:
        """
        Handle project selection inside the create follow-up modal.

        When a user selects a different project, this method updates the modal
        to show the issue types available for that project using views.update.

        Args:
            payload: The Slack block_actions payload from inside the modal.

        Returns:
            True if modal was updated successfully, False otherwise.
        """
        import json

        try:
            # Extract action details
            actions = payload.get("actions", [])
            if not actions:
                return False

            action = actions[0]
            selected_project_key = action.get("selected_option", {}).get("value")

            if not selected_project_key:
                logger.warning("No project key in selection action")
                return False

            # Get view info for update
            view = payload.get("view", {})
            view_id = view.get("id")
            private_metadata_str = view.get("private_metadata", "{}")

            if not view_id:
                logger.error("No view_id in modal project selection payload")
                return False

            # Parse private_metadata to get issue types map
            try:
                metadata = json.loads(private_metadata_str)
            except json.JSONDecodeError:
                # Legacy format - just ticket key string
                metadata = {"ticket_key": private_metadata_str}

            ticket_key = metadata.get("ticket_key", "")

            logger.info(
                "Project selection: %s for ticket %s",
                selected_project_key,
                ticket_key,
            )

            # Fetch issue types dynamically for the selected project
            # This uses the working /project/{key}/statuses endpoint
            issue_types = []
            try:
                issue_types = await self._mcp_client.get_project_issue_types(selected_project_key)
                logger.info(
                    "Fetched %d issue types for project %s",
                    len(issue_types),
                    selected_project_key,
                )
            except Exception as e:
                logger.warning(
                    "Failed to fetch issue types for %s: %s",
                    selected_project_key,
                    e,
                )

            # We need to rebuild the modal blocks with new issue types
            # Since we don't have full project list in metadata, we just update issue types
            from datetime import datetime, timezone

            from packages.core.typed_di.protocols import CSOPMTicket

            # Reconstruct minimal ticket for modal rebuild (kept for future use)
            _csopm_ticket = CSOPMTicket(
                key=ticket_key,
                summary=metadata.get("ticket_summary", ""),
                assignee_username="",
                created_at=datetime.now(timezone.utc),
                status="",
            )

            # Build new modal with updated issue types
            # Note: We need projects list for the dropdown - we'll rebuild from current view state
            # For now, just update issue types block directly via views.update

            # Get current state values to preserve user input (kept for future use)
            state_values = view.get("state", {}).get("values", {})
            _summary_value = (
                state_values.get("summary_block", {}).get("summary_input", {}).get("value", "")
            )
            _description_value = (
                state_values.get("description_block", {})
                .get("description_input", {})
                .get("value", "")
            )

            # Build updated issue type options
            issue_type_options = [
                {
                    "text": {"type": "plain_text", "text": it.get("name", "Unknown")[:75]},
                    "value": it.get("id", it.get("name", "Task")),
                }
                for it in issue_types
                if it.get("name")
            ]

            if not issue_type_options:
                # Fallback to generic Task if no issue types
                issue_type_options = [
                    {"text": {"type": "plain_text", "text": "Task"}, "value": "Task"}
                ]

            # Build updated blocks for the modal
            _jira_url = f"https://jira.corp.adobe.com/browse/{ticket_key}"  # kept for future use
            blocks = view.get("blocks", [])

            # Find and update the issue_type_block
            updated_blocks = []
            for block in blocks:
                if block.get("block_id") == "issue_type_block":
                    # Replace with new issue type options
                    # Use CSOPM_ISSUETYPE_SELECT_ACTION_ID and dispatch_action for dynamic fields
                    updated_block = {
                        "type": "input",
                        "block_id": "issue_type_block",
                        "dispatch_action": True,  # Trigger field metadata fetch on selection
                        "label": {"type": "plain_text", "text": "Issue Type"},
                        "element": {
                            "type": "static_select",
                            "action_id": CSOPM_ISSUETYPE_SELECT_ACTION_ID,
                            "placeholder": {"type": "plain_text", "text": "Select issue type"},
                            "options": issue_type_options[:100],
                        },
                    }
                    updated_blocks.append(updated_block)
                else:
                    updated_blocks.append(block)

            # Update modal via views.update
            slack_api_token = (
                await self._posting_handler._secrets_manager.get_slack_api_token_async()
            )
            url = "https://slack.com/api/views.update"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            updated_view = {
                "type": "modal",
                "callback_id": CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID,
                "private_metadata": private_metadata_str,  # Keep original metadata
                "title": {"type": "plain_text", "text": "Create Follow-up"},
                "submit": {"type": "plain_text", "text": "Create"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": updated_blocks,
            }

            update_payload = {
                "view_id": view_id,
                "view": updated_view,
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=update_payload) as response:
                    result = await response.json()

                    if result.get("ok"):
                        logger.info(
                            "Successfully updated modal with %d issue types for project %s",
                            len(issue_type_options),
                            selected_project_key,
                        )
                        return True
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error("Failed to update modal: %s", error)
                        return False

        except Exception as e:
            logger.error("Error handling modal project selection: %s", e, exc_info=True)
            return False

    async def handle_modal_issuetype_selection(self, payload: Dict[str, Any]) -> bool:
        """
        Handle issue type selection inside the create follow-up modal.

        When a user selects a different issue type, this method fetches the
        required field metadata for that issue type and updates the modal
        to show dynamic required fields.

        Args:
            payload: The Slack block_actions payload from inside the modal.

        Returns:
            True if modal was updated successfully, False otherwise.
        """
        try:
            # Extract action details
            actions = payload.get("actions", [])
            if not actions:
                return False

            action = actions[0]
            selected_issue_type_id = action.get("selected_option", {}).get("value")

            if not selected_issue_type_id:
                logger.warning("No issue type ID in selection action")
                return False

            # Get view info for update
            view = payload.get("view", {})
            view_id = view.get("id")
            private_metadata_str = view.get("private_metadata", "{}")

            if not view_id:
                logger.error("No view_id in modal issue type selection payload")
                return False

            # Parse private_metadata
            try:
                metadata = json.loads(private_metadata_str)
            except json.JSONDecodeError:
                metadata = {"ticket_key": private_metadata_str}

            ticket_key = metadata.get("ticket_key", "")

            # Get currently selected project from view state
            state_values = view.get("state", {}).get("values", {})
            project_block = state_values.get("project_block", {})

            # Handle both dropdown (csopm_project_select) and text input (project_input)
            project_select = project_block.get(CSOPM_PROJECT_SELECT_ACTION_ID, {})
            project_input = project_block.get("project_input", {})

            selected_project_key = (
                project_select.get("selected_option", {}).get("value")
                or project_input.get("value")
                or "CSOPM"
            )

            logger.info(
                "Issue type selection: %s for project %s (ticket %s)",
                selected_issue_type_id,
                selected_project_key,
                ticket_key,
            )

            # Get user's PAT for the metadata request
            user = payload.get("user", {})
            user_id = user.get("id")
            user_pat = None
            if user_id and self._user_pat_ops:
                user_pat = await self._user_pat_ops.get_pat(user_id)

            # Fetch field metadata for the selected issue type
            from packages.slack.csopm import CSOPMNotificationBlocks

            field_metadata = []
            dynamic_blocks = []
            try:
                metadata_result = await self._mcp_client.get_issuetype_metadata(
                    selected_project_key, selected_issue_type_id, user_pat=user_pat
                )
                field_metadata = metadata_result.get("values", [])
                logger.info(
                    "Fetched %d fields for %s/%s, building dynamic blocks",
                    len(field_metadata),
                    selected_project_key,
                    selected_issue_type_id,
                )

                # Build dynamic field blocks for required fields
                dynamic_blocks = CSOPMNotificationBlocks.build_dynamic_fields_blocks(
                    field_metadata, required_only=True
                )
                logger.info("Generated %d dynamic field blocks", len(dynamic_blocks))

            except Exception as e:
                logger.warning(
                    "Failed to fetch field metadata for %s/%s: %s",
                    selected_project_key,
                    selected_issue_type_id,
                    e,
                )

            # Get current blocks and rebuild with dynamic fields
            blocks = view.get("blocks", [])

            # Build updated blocks:
            # 1. Keep header, project, issue type blocks
            # 2. Add dynamic required fields after issue type
            # 3. Keep summary, description, and context at the end
            updated_blocks = []
            found_issue_type = False
            skip_until_summary = False

            for block in blocks:
                block_id = block.get("block_id", "")

                # Skip old dynamic blocks (they start with 'dynamic_')
                if block_id.startswith("dynamic_"):
                    continue

                # If we're between issue_type and summary, skip (we'll re-add dynamic blocks)
                if skip_until_summary:
                    if block_id == "summary_block":
                        skip_until_summary = False
                    else:
                        continue

                updated_blocks.append(block)

                # After issue type block, insert dynamic fields
                if block_id == "issue_type_block":
                    found_issue_type = True
                    skip_until_summary = True
                    # Add dynamic field blocks
                    updated_blocks.extend(dynamic_blocks)
                    # Re-add summary and remaining blocks will continue in loop

            # If we didn't find issue_type_block, just append dynamic blocks before summary
            if not found_issue_type and dynamic_blocks:
                # Find summary block index and insert before it
                summary_idx = next(
                    (
                        i
                        for i, b in enumerate(updated_blocks)
                        if b.get("block_id") == "summary_block"
                    ),
                    len(updated_blocks),
                )
                updated_blocks = (
                    updated_blocks[:summary_idx] + dynamic_blocks + updated_blocks[summary_idx:]
                )

            # Add context about dynamic fields if any were added
            if dynamic_blocks:
                # Find context block and update it
                for i, block in enumerate(updated_blocks):
                    if block.get("type") == "context":
                        updated_blocks[i] = {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f":white_check_mark: Showing {len(dynamic_blocks)} required field(s) for this issue type.",
                                }
                            ],
                        }
                        break

            # Update modal via views.update
            slack_api_token = (
                await self._posting_handler._secrets_manager.get_slack_api_token_async()
            )
            url = "https://slack.com/api/views.update"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            updated_view = {
                "type": "modal",
                "callback_id": CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID,
                "private_metadata": private_metadata_str,
                "title": {"type": "plain_text", "text": "Create Follow-up"},
                "submit": {"type": "plain_text", "text": "Create"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": updated_blocks,
            }

            update_payload = {
                "view_id": view_id,
                "view": updated_view,
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=update_payload) as response:
                    result = await response.json()

                    if result.get("ok"):
                        logger.info(
                            "Successfully updated modal with %d dynamic fields for issue type %s",
                            len(dynamic_blocks),
                            selected_issue_type_id,
                        )
                        return True
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error("Failed to update modal with dynamic fields: %s", error)
                        return False

        except Exception as e:
            logger.error("Error handling modal issue type selection: %s", e, exc_info=True)
            return False

    async def _handle_edit_pat_button(self, payload: Dict[str, Any]) -> bool:
        """
        Handle the Edit PAT button click inside the modal.

        Replaces the PAT status section with an input field for entering a new PAT.

        Args:
            payload: The Slack block_actions payload from inside the modal.

        Returns:
            True if modal was updated successfully, False otherwise.
        """
        try:
            view = payload.get("view", {})
            view_id = view.get("id")
            private_metadata_str = view.get("private_metadata", "{}")

            if not view_id:
                logger.error("No view_id in edit PAT button payload")
                return False

            # Get current blocks and replace PAT status with input field
            blocks = view.get("blocks", [])
            updated_blocks = []

            for block in blocks:
                block_id = block.get("block_id", "")

                # Replace pat_status_block with pat_block input + Save button
                if block_id == "pat_status_block":
                    updated_blocks.append(
                        {
                            "type": "input",
                            "block_id": "pat_block",
                            "label": {
                                "type": "plain_text",
                                "text": "JIRA Personal Access Token",
                            },
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "pat_input",
                                "placeholder": {
                                    "type": "plain_text",
                                    "text": "Enter your new JIRA PAT",
                                },
                            },
                            "hint": {
                                "type": "plain_text",
                                "text": "Enter a new PAT to replace the stored one.",
                            },
                            "optional": False,
                        }
                    )
                    # Add Save button
                    updated_blocks.append(
                        {
                            "type": "actions",
                            "block_id": "pat_save_block",
                            "elements": [
                                {
                                    "type": "button",
                                    "action_id": "csopm_save_pat",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Save PAT",
                                    },
                                    "style": "primary",
                                }
                            ],
                        }
                    )
                else:
                    updated_blocks.append(block)

            # Update modal via views.update
            slack_api_token = (
                await self._posting_handler._secrets_manager.get_slack_api_token_async()
            )
            url = "https://slack.com/api/views.update"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            updated_view = {
                "type": "modal",
                "callback_id": CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID,
                "private_metadata": private_metadata_str,
                "title": {"type": "plain_text", "text": "Create Follow-up"},
                "submit": {"type": "plain_text", "text": "Create"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": updated_blocks,
            }

            update_payload = {
                "view_id": view_id,
                "view": updated_view,
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=update_payload) as response:
                    result = await response.json()

                    if result.get("ok"):
                        logger.info("Successfully updated modal to show PAT input field")
                        return True
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error("Failed to update modal for PAT edit: %s", error)
                        return False

        except Exception as e:
            logger.error("Error handling edit PAT button: %s", e, exc_info=True)
            return False

    async def _handle_save_pat_button(self, payload: Dict[str, Any]) -> bool:
        """
        Handle the Save PAT button click inside the modal.

        Stores the PAT and updates the modal to show the stored status.

        Args:
            payload: The Slack block_actions payload from inside the modal.

        Returns:
            True if PAT was saved and modal updated, False otherwise.
        """
        try:
            view = payload.get("view", {})
            view_id = view.get("id")
            private_metadata_str = view.get("private_metadata", "{}")
            user = payload.get("user", {})
            user_id = user.get("id")

            if not view_id:
                logger.error("No view_id in save PAT button payload")
                return False

            # Get PAT from view state
            state_values = view.get("state", {}).get("values", {})
            pat_block = state_values.get("pat_block", {})
            pat_value = pat_block.get("pat_input", {}).get("value", "")

            if not pat_value:
                logger.warning("No PAT value entered")
                return False

            # Store the PAT
            if self._user_pat_ops:
                await self._user_pat_ops.store_pat(user_id, pat_value)
                logger.info("Stored PAT for user %s", user_id)

                # Get expiry minutes for display
                expiry_minutes = await self._user_pat_ops.get_pat_expiry_minutes(user_id)
            else:
                logger.error("No user_pat_ops available to store PAT")
                return False

            # Get current blocks and replace PAT input + Save button with status
            blocks = view.get("blocks", [])
            updated_blocks = []

            skip_next = False
            for block in blocks:
                if skip_next:
                    skip_next = False
                    continue

                block_id = block.get("block_id", "")

                # Replace pat_block and pat_save_block with pat_status_block
                if block_id == "pat_block":
                    updated_blocks.append(
                        {
                            "type": "section",
                            "block_id": "pat_status_block",
                            "text": {
                                "type": "mrkdwn",
                                "text": f":white_check_mark: *JIRA PAT stored* (expires in {expiry_minutes} min)",
                            },
                            "accessory": {
                                "type": "button",
                                "action_id": "csopm_edit_pat",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Edit",
                                },
                            },
                        }
                    )
                    skip_next = True  # Skip the pat_save_block that follows
                elif block_id == "pat_save_block":
                    continue  # Skip save button block
                else:
                    updated_blocks.append(block)

            # Update modal via views.update
            slack_api_token = (
                await self._posting_handler._secrets_manager.get_slack_api_token_async()
            )
            url = "https://slack.com/api/views.update"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            updated_view = {
                "type": "modal",
                "callback_id": CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID,
                "private_metadata": private_metadata_str,
                "title": {"type": "plain_text", "text": "Create Follow-up"},
                "submit": {"type": "plain_text", "text": "Create"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": updated_blocks,
            }

            update_payload = {
                "view_id": view_id,
                "view": updated_view,
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=update_payload) as response:
                    result = await response.json()

                    if result.get("ok"):
                        logger.info("Successfully saved PAT and updated modal")
                        return True
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error("Failed to update modal after PAT save: %s", error)
                        return False

        except Exception as e:
            logger.error("Error handling save PAT button: %s", e, exc_info=True)
            return False

    async def _handle_create_followup_submission(
        self,
        payload: Dict[str, Any],
    ) -> Union[bool, Dict[str, Any]]:
        """
        Handle the create follow-up modal submission.

        Validates input and kicks off background ticket creation to avoid
        Slack's 3-second timeout. Returns immediate modal update.

        Args:
            payload: The Slack view_submission payload.

        Returns:
            Dict with response_action to update modal, or error dict.
        """
        import asyncio

        try:
            view = payload.get("view", {})
            user = payload.get("user", {})
            user_id = user.get("id")

            # Extract parent ticket key from private_metadata
            private_metadata_str = view.get("private_metadata", "")
            if not private_metadata_str:
                logger.error("No private_metadata in view submission")
                return False

            try:
                metadata = json.loads(private_metadata_str)
                parent_ticket_key = metadata.get("ticket_key", "")
            except json.JSONDecodeError:
                parent_ticket_key = private_metadata_str

            if not parent_ticket_key:
                logger.error("No parent ticket key in private_metadata")
                return False

            # Extract form values
            state_values = view.get("state", {}).get("values", {})

            # Get project key - check both action_ids (new and legacy)
            project_block = state_values.get("project_block", {})
            project_input = project_block.get(CSOPM_PROJECT_SELECT_ACTION_ID) or project_block.get(
                "project_input", {}
            )
            if project_input.get("type") == "static_select":
                project_key = project_input.get("selected_option", {}).get("value", "CSOPM")
            else:
                project_key = project_input.get("value", "CSOPM")

            # Get issue type - check both action_ids (new and legacy)
            # For static_select, we need the NAME (text.text) not the ID (value)
            # because the MCP create_jira_issue schema expects issuetype.name
            issue_type_block = state_values.get("issue_type_block", {})
            issue_type_input = issue_type_block.get(
                CSOPM_ISSUETYPE_SELECT_ACTION_ID
            ) or issue_type_block.get("issue_type_input", {})
            if issue_type_input.get("type") == "static_select" or issue_type_input.get(
                "selected_option"
            ):
                selected = issue_type_input.get("selected_option", {})
                issue_type = selected.get("text", {}).get("text", selected.get("value", "Task"))
            else:
                issue_type = issue_type_input.get("value", "Task")

            # Get issue type ID for metadata lookup
            issue_type_id = None
            if issue_type_input.get("selected_option"):
                issue_type_id = issue_type_input.get("selected_option", {}).get("value")

            # Get PAT
            pat_block = state_values.get("pat_block", {})
            user_pat = pat_block.get("pat_input", {}).get("value")

            # Store PAT if provided
            if user_pat and self._user_pat_ops:
                try:
                    await self._user_pat_ops.store_pat(user_id, user_pat)
                    logger.info("Stored PAT for user %s", user_id)
                except Exception as e:
                    logger.warning("Failed to store PAT: %s", e)
            elif not user_pat and self._user_pat_ops:
                user_pat = await self._user_pat_ops.get_pat(user_id)
                if user_pat:
                    logger.info("Using stored PAT for user %s", user_id)

            # Validate PAT - required for ticket creation
            if not user_pat:
                logger.warning("No PAT available for user %s - rejecting submission", user_id)
                return {
                    "response_action": "errors",
                    "errors": {
                        "pat_block": "A JIRA Personal Access Token is required. Please enter your PAT and click Save PAT first."
                    },
                }

            # Get summary and description
            summary_block = state_values.get("summary_block", {})
            summary = summary_block.get("summary_input", {}).get("value", "")

            description_block = state_values.get("description_block", {})
            description = description_block.get("description_input", {}).get("value", "")

            if not summary:
                return {
                    "response_action": "errors",
                    "errors": {"summary_block": "Summary is required."},
                }

            # Get issue type ID for field metadata lookup
            issue_type_id = None
            if issue_type_input.get("selected_option"):
                issue_type_id = issue_type_input.get("selected_option", {}).get("value")

            # Extract dynamic field values from the modal
            # Dynamic fields have block_id like "dynamic_{fieldId}_block"
            # MCP create_jira_issue expects components/versions as: [{"name": "..."}]
            dynamic_fields: Dict[str, Any] = {}
            for block_id, block_values in state_values.items():
                if block_id.startswith("dynamic_") and block_id.endswith("_block"):
                    field_id = block_id[8:-6]  # Strip "dynamic_" prefix and "_block" suffix
                    for action_id, action_value in block_values.items():
                        if action_value.get("selected_option"):
                            selected = action_value["selected_option"]
                            # Get the display name from text.text
                            name = selected.get("text", {}).get("text", selected.get("value"))
                            # components/versions need array format with "name" key for create
                            if field_id in ("components", "versions"):
                                dynamic_fields[field_id] = [{"name": name}]
                            else:
                                dynamic_fields[field_id] = {"id": selected.get("value")}
                        elif action_value.get("selected_options"):
                            # Multi-select - array format with names
                            if field_id in ("components", "versions"):
                                dynamic_fields[field_id] = [
                                    {"name": opt.get("text", {}).get("text", opt.get("value"))}
                                    for opt in action_value["selected_options"]
                                ]
                            else:
                                dynamic_fields[field_id] = [
                                    {"id": opt["value"]} for opt in action_value["selected_options"]
                                ]
                        elif action_value.get("value"):
                            # Text input
                            dynamic_fields[field_id] = action_value["value"]

            logger.info(
                "Starting background follow-up creation: project=%s, type=%s, parent=%s, dynamic_fields=%s",
                project_key,
                issue_type,
                parent_ticket_key,
                list(dynamic_fields.keys()),
            )

            # Kick off background task for JIRA work (fire and forget)
            asyncio.create_task(
                self._create_followup_ticket_background(
                    user_id=user_id,
                    parent_ticket_key=parent_ticket_key,
                    project_key=project_key,
                    issue_type=issue_type,
                    issue_type_id=issue_type_id,
                    summary=summary,
                    description=description,
                    user_pat=user_pat,
                    dynamic_fields=dynamic_fields,
                )
            )

            # Close modal immediately - user will receive DM confirmation
            return {"response_action": "clear"}

        except Exception as e:
            logger.error(
                "Error handling create followup submission: %s",
                e,
                exc_info=True,
            )
            return False

    async def _create_followup_ticket_background(
        self,
        user_id: str,
        parent_ticket_key: str,
        project_key: str,
        issue_type: str,
        issue_type_id: Optional[str],
        summary: str,
        description: str,
        user_pat: str,
        dynamic_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Background task to create a follow-up JIRA ticket.

        Called via asyncio.create_task() to avoid blocking the modal response.
        Handles JIRA ticket creation, linking, and sends confirmation/error to user.

        Args:
            user_id: Slack user ID to send confirmation to.
            parent_ticket_key: Parent CSOPM ticket key.
            project_key: JIRA project key for the new ticket.
            issue_type: Issue type name.
            issue_type_id: Issue type ID for metadata lookup.
            summary: Ticket summary.
            description: Ticket description.
            user_pat: User's JIRA PAT.
            dynamic_fields: Optional dict of dynamic field values (components, versions, etc.)
        """
        try:
            logger.info(
                "Background: Creating follow-up ticket for %s in %s",
                parent_ticket_key,
                project_key,
            )

            # Fetch field metadata to know which fields are allowed
            allowed_fields = None
            if issue_type_id:
                try:
                    metadata_result = await self._mcp_client.get_issuetype_metadata(
                        project_key, issue_type_id, user_pat=user_pat
                    )
                    if metadata_result and metadata_result.get("success"):
                        fields_data = metadata_result.get("data", {}).get("values", [])
                        if fields_data:
                            allowed_fields = {
                                f.get("fieldId") for f in fields_data if f.get("fieldId")
                            }
                            logger.info(
                                "Fetched %d allowed fields for %s/%s",
                                len(allowed_fields),
                                project_key,
                                issue_type_id,
                            )
                except Exception as e:
                    logger.warning("Failed to fetch field metadata: %s", e)

            # Build fields object
            fields: Dict[str, Any] = {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
            }

            if allowed_fields is None or "summary" in allowed_fields:
                fields["summary"] = summary

            if allowed_fields is None or "description" in allowed_fields:
                if description:
                    fields["description"] = description

            # Add dynamic fields (components, versions, etc.)
            if dynamic_fields:
                for field_id, field_value in dynamic_fields.items():
                    if allowed_fields is None or field_id in allowed_fields:
                        fields[field_id] = field_value
                        logger.info(
                            "Added dynamic field %s=%s to create request", field_id, field_value
                        )

            # Create the new JIRA issue via MCP
            create_args: Dict[str, Any] = {"fields": fields}
            if user_pat:
                create_args["userPat"] = user_pat

            create_result = await self._mcp_client._call_mcp_tool(
                "create_jira_issue",
                create_args,
            )

            if not create_result or not create_result.get("success"):
                error_msg = (
                    create_result.get("message", "Unknown error")
                    if create_result
                    else "No response"
                )
                logger.error("Failed to create follow-up ticket: %s", error_msg)
                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f":x: Failed to create follow-up ticket: {error_msg}",
                )
                return

            # Extract new ticket key
            new_ticket_key = create_result.get("key") or create_result.get("data", {}).get(
                "key", ""
            )
            if not new_ticket_key:
                logger.error("No ticket key returned from create_jira_issue")
                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=":x: Failed to create follow-up ticket: No ticket key returned",
                )
                return

            logger.info(
                "Created follow-up ticket %s, linking to parent %s",
                new_ticket_key,
                parent_ticket_key,
            )

            # Link the new issue to the parent CSOPM ticket
            try:
                link_result = await self._mcp_client._call_mcp_tool(
                    "link_issues",
                    {
                        "inwardIssue": parent_ticket_key,
                        "outwardIssue": new_ticket_key,
                        "linkType": "Relates",
                        "userPat": user_pat,
                    },
                )
                if link_result and link_result.get("success"):
                    logger.info(
                        "Successfully linked %s to parent %s",
                        new_ticket_key,
                        parent_ticket_key,
                    )
                else:
                    logger.warning(
                        "Failed to link %s to parent %s: %s",
                        new_ticket_key,
                        parent_ticket_key,
                        link_result.get("message", "Unknown") if link_result else "No response",
                    )
            except Exception as link_error:
                logger.warning(
                    "Failed to link %s to parent %s: %s",
                    new_ticket_key,
                    parent_ticket_key,
                    str(link_error),
                )

            # Add comment to parent ticket
            try:
                followup_url = f"https://jira.corp.adobe.com/browse/{new_ticket_key}"
                comment_lines = [
                    f"h3. Follow-up ticket created: [{new_ticket_key}|{followup_url}]",
                    "",
                    "*Summary:*",
                    summary,
                ]
                if description:
                    comment_lines.extend(["", "*Description:*", description])

                await self._mcp_client.create_issue_comment(
                    issue_key=parent_ticket_key,
                    comment="\n".join(comment_lines),
                    user_pat=user_pat,
                )
            except Exception as comment_error:
                logger.warning(
                    "Failed to add comment to parent %s: %s",
                    parent_ticket_key,
                    str(comment_error),
                )

            # Track the follow-up ticket in notification record
            if self._state_tracker:
                try:
                    await self._state_tracker.add_followup_ticket(
                        ticket_key=parent_ticket_key,
                        followup_key=new_ticket_key,
                    )
                except Exception as track_error:
                    logger.warning(
                        "Failed to track follow-up ticket: %s",
                        str(track_error),
                    )

            # Send success confirmation
            from packages.slack.csopm import CSOPMNotificationBlocks

            jira_url = f"https://jira.corp.adobe.com/browse/{new_ticket_key}"
            confirmation_blocks = CSOPMNotificationBlocks.build_followup_confirmation(
                new_ticket_key=new_ticket_key,
                parent_ticket_key=parent_ticket_key,
                jira_url=jira_url,
            )

            await self._posting_handler.post_message(
                channel_id=user_id,
                blocks=confirmation_blocks,
            )

            logger.info(
                "Follow-up ticket %s created and linked to %s successfully",
                new_ticket_key,
                parent_ticket_key,
            )

        except Exception as e:
            logger.error(
                "Error in background followup creation: %s",
                e,
                exc_info=True,
            )
            try:
                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f":x: Failed to create follow-up ticket: {str(e)}",
                )
            except Exception:
                pass

    async def _handle_status_transition_submission(
        self,
        payload: Dict[str, Any],
    ) -> Union[bool, Dict[str, Any]]:
        """
        Handle the status transition modal submission.

        Transitions a JIRA ticket to a new status (e.g., Complete, Closed)
        using the user's PAT for authentication.

        Flow:
        1. Extract form values from modal submission
        2. Validate PAT availability
        3. Extract dynamic field values
        4. Perform JIRA status transition with field updates
        5. Optionally add comment to ticket
        6. Send confirmation message to user

        Args:
            payload: The Slack view_submission payload.

        Returns:
            True if transition was successful.
            False if transition failed.
            Dict with response_action: "errors" for validation errors.
        """
        try:
            view = payload.get("view", {})
            user = payload.get("user", {})
            user_id = user.get("id")

            # Extract metadata from private_metadata
            private_metadata_str = view.get("private_metadata", "")
            if not private_metadata_str:
                logger.error("No private_metadata in status transition submission")
                return False

            try:
                metadata = json.loads(private_metadata_str)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in private_metadata")
                return False

            ticket_key = metadata.get("ticket_key", "")
            target_status = metadata.get("target_status", "")

            if not ticket_key or not target_status:
                logger.error("Missing ticket_key or target_status in metadata")
                return False

            logger.info(
                "Processing status transition: %s -> %s (user: %s)",
                ticket_key,
                target_status,
                user_id,
            )

            # Extract form values
            state_values = view.get("state", {}).get("values", {})

            # Get PAT if provided
            pat_block = state_values.get("pat_block", {})
            user_pat = pat_block.get("pat_input", {}).get("value")

            # Store PAT if provided
            if user_pat and self._user_pat_ops:
                try:
                    await self._user_pat_ops.store_pat(user_id, user_pat)
                    logger.info("Stored PAT for user %s", user_id)
                except Exception as e:
                    logger.warning("Failed to store PAT: %s", e)
            elif not user_pat and self._user_pat_ops:
                # Try to retrieve stored PAT
                user_pat = await self._user_pat_ops.get_pat(user_id)
                if user_pat:
                    logger.info("Using stored PAT for user %s", user_id)

            # Validate PAT - required for transition
            if not user_pat:
                logger.warning("No PAT available for user %s - rejecting submission", user_id)
                return {
                    "response_action": "errors",
                    "errors": {
                        "pat_block": "A JIRA Personal Access Token is required to transition this ticket."
                    },
                }

            # Get optional comment
            comment_block = state_values.get("comment_block", {})
            comment = comment_block.get("comment_input", {}).get("value")

            # Extract dynamic field values from the modal
            # Dynamic fields have block_id like "dynamic_{fieldId}_block"
            # JIRA expects select fields as {"id": "value"} format, not raw strings
            transition_fields = {}
            for block_id, block_values in state_values.items():
                if block_id.startswith("dynamic_") and block_id.endswith("_block"):
                    field_id = block_id[8:-6]  # Strip "dynamic_" prefix and "_block" suffix
                    # Get the first (and only) action_id in this block
                    for action_id, action_value in block_values.items():
                        if action_value.get("selected_option"):
                            # Select element - wrap in {"id": value} for JIRA
                            # customfield_17309 (Issue Attributes) needs array format
                            if field_id == "customfield_17309":
                                transition_fields[field_id] = [
                                    {"id": action_value["selected_option"]["value"]}
                                ]
                            else:
                                transition_fields[field_id] = {
                                    "id": action_value["selected_option"]["value"]
                                }
                        elif action_value.get("selected_options"):
                            # Multi-select element - list of {"id": value} objects
                            transition_fields[field_id] = [
                                {"id": opt["value"]} for opt in action_value["selected_options"]
                            ]
                        elif action_value.get("value"):
                            # Text input - keep as string
                            transition_fields[field_id] = action_value["value"]

            logger.info(
                "Starting background transition: %s -> %s with fields: %s",
                ticket_key,
                target_status,
                list(transition_fields.keys()),
            )

            # Kick off background task for JIRA work (fire and forget)
            import asyncio

            asyncio.create_task(
                self._transition_ticket_background(
                    user_id=user_id,
                    ticket_key=ticket_key,
                    target_status=target_status,
                    transition_fields=transition_fields,
                    comment=comment,
                    user_pat=user_pat,
                )
            )

            # Close modal immediately - user will receive DM confirmation
            return {"response_action": "clear"}

        except Exception as e:
            logger.error(
                "Error handling status transition submission: %s",
                e,
                exc_info=True,
            )
            return False

    async def _transition_ticket_background(
        self,
        user_id: str,
        ticket_key: str,
        target_status: str,
        transition_fields: Dict[str, Any],
        comment: Optional[str],
        user_pat: str,
    ) -> None:
        """
        Background task to transition a JIRA ticket status.

        Called via asyncio.create_task() to avoid blocking the modal response.
        Handles JIRA transition, optional comment, and sends confirmation/error to user.
        """
        try:
            logger.info(
                "Background: Transitioning %s to %s",
                ticket_key,
                target_status,
            )

            # Build transition args
            transition_args: Dict[str, Any] = {
                "issueIdOrKey": ticket_key,
                "statusName": target_status,
            }
            if transition_fields:
                transition_args["fields"] = transition_fields
            if user_pat:
                transition_args["userPat"] = user_pat

            transition_result = await self._mcp_client._call_mcp_tool(
                "transition_jira_status_by_name",
                transition_args,
            )

            if not transition_result or not transition_result.get("success"):
                error_msg = (
                    transition_result.get("message", "Unknown error")
                    if transition_result
                    else "No response"
                )
                logger.error(
                    "Failed to transition %s to %s: %s",
                    ticket_key,
                    target_status,
                    error_msg,
                )
                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f":x: Failed to transition {ticket_key} to {target_status}: {error_msg}",
                )
                return

            logger.info("Successfully transitioned %s to %s", ticket_key, target_status)

            # Add comment if provided
            if comment:
                try:
                    await self._mcp_client.create_issue_comment(
                        issue_key=ticket_key,
                        comment=comment,
                        user_pat=user_pat,
                    )
                except Exception as comment_error:
                    logger.warning(
                        "Failed to add comment to %s: %s", ticket_key, str(comment_error)
                    )

            # Send confirmation
            from packages.slack.csopm import CSOPMNotificationBlocks

            confirmation_blocks = CSOPMNotificationBlocks.build_transition_confirmation(
                ticket_key=ticket_key,
                new_status=target_status,
            )

            await self._posting_handler.post_message(
                channel_id=user_id,
                blocks=confirmation_blocks,
            )

        except Exception as e:
            logger.error("Error in background transition: %s", e, exc_info=True)
            try:
                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f":x: Failed to transition {ticket_key}: {str(e)}",
                )
            except Exception:
                pass

    async def _open_reassign_modal(
        self,
        trigger_id: Optional[str],
        ticket_key: str,
        user_id: str,
    ) -> bool:
        """
        Open a modal to reassign a CSOPM ticket to another user.

        The modal prompts for an LDAP username (e.g., "harrison") which
        will be used to reassign the ticket in JIRA.

        Args:
            trigger_id: Slack trigger_id for opening modal (required).
            ticket_key: The CSOPM ticket key to reassign.
            user_id: Slack user ID opening the modal.

        Returns:
            True if modal was opened successfully, False otherwise.
        """
        if not trigger_id:
            logger.error("No trigger_id provided for reassign modal")
            return False

        logger.info(
            "Opening reassign modal for ticket %s (user: %s)",
            ticket_key,
            user_id,
        )

        try:
            # Build the modal view
            modal_view = {
                "type": "modal",
                "callback_id": CSOPM_REASSIGN_MODAL_CALLBACK_ID,
                "private_metadata": json.dumps({"ticket_key": ticket_key}),
                "title": {
                    "type": "plain_text",
                    "text": "Reassign Ticket",
                    "emoji": True,
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Reassign",
                    "emoji": True,
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True,
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Reassign *{ticket_key}* to another user.",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "ldap_username_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "ldap_username_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "e.g., jsmith",
                            },
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "LDAP Username",
                            "emoji": True,
                        },
                        "hint": {
                            "type": "plain_text",
                            "text": "Enter the LDAP username (without @adobe.com) of the new assignee.",
                        },
                    },
                ],
            }

            # Open the modal via Slack API
            slack_api_token = (
                await self._posting_handler._secrets_manager.get_slack_api_token_async()
            )
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }
            body = {
                "trigger_id": trigger_id,
                "view": modal_view,
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=body) as response:
                    result = await response.json()
                    if result.get("ok"):
                        logger.info("Successfully opened reassign modal for %s", ticket_key)
                        return True
                    else:
                        logger.error(
                            "Failed to open reassign modal: %s",
                            result.get("error", "Unknown error"),
                        )
                        return False

        except Exception as e:
            logger.error(
                "Error opening reassign modal for %s: %s",
                ticket_key,
                e,
                exc_info=True,
            )
            return False

    async def _handle_reassign_submission(
        self,
        payload: Dict[str, Any],
    ) -> Union[bool, Dict[str, Any]]:
        """
        Handle the reassign modal submission.

        Updates the JIRA ticket assignee using the provided LDAP username.
        JIRA call is synchronous to allow validation errors, then modal
        closes and confirmation is sent via DM.
        """
        try:
            view = payload.get("view", {})
            user = payload.get("user", {})
            user_id = user.get("id")

            # Extract metadata
            private_metadata_str = view.get("private_metadata", "")
            if not private_metadata_str:
                logger.error("No private_metadata in reassign submission")
                return False

            try:
                metadata = json.loads(private_metadata_str)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in private_metadata")
                return False

            ticket_key = metadata.get("ticket_key", "")
            if not ticket_key:
                logger.error("Missing ticket_key in metadata")
                return False

            # Extract LDAP username from form
            state_values = view.get("state", {}).get("values", {})
            ldap_block = state_values.get("ldap_username_block", {})
            ldap_username = ldap_block.get("ldap_username_input", {}).get("value", "").strip()

            if not ldap_username:
                return {
                    "response_action": "errors",
                    "errors": {
                        "ldap_username_block": "Please enter an LDAP username.",
                    },
                }

            # Remove @ prefix if user included it
            if ldap_username.startswith("@"):
                ldap_username = ldap_username[1:]

            # Remove @adobe.com if user included it
            if ldap_username.endswith("@adobe.com"):
                ldap_username = ldap_username.replace("@adobe.com", "")

            logger.info(
                "Reassigning %s to %s (requested by user %s)",
                ticket_key,
                ldap_username,
                user_id,
            )

            # Update the ticket assignee via MCP (sync to validate username)
            update_result = await self._mcp_client._call_mcp_tool(
                "update_jira_issue",
                {
                    "issueIdOrKey": ticket_key,
                    "fields": {
                        "assignee": {"name": ldap_username},
                    },
                },
            )

            if not update_result or not update_result.get("success"):
                error_msg = (
                    update_result.get("message", "Unknown error")
                    if update_result
                    else "No response"
                )
                logger.error(
                    "Failed to reassign %s to %s: %s",
                    ticket_key,
                    ldap_username,
                    error_msg,
                )

                # Check for common errors - show in modal
                if (
                    "does not exist" in error_msg.lower()
                    or "cannot be assigned" in error_msg.lower()
                ):
                    return {
                        "response_action": "errors",
                        "errors": {
                            "ldap_username_block": f"User '{ldap_username}' not found or cannot be assigned to this ticket.",
                        },
                    }

                # Other errors - send DM
                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f":x: Failed to reassign {ticket_key} to {ldap_username}: {error_msg}",
                )
                return False

            logger.info("Successfully reassigned %s to %s", ticket_key, ldap_username)

            # Send notification to new assignee and confirmation to requester (background)
            import asyncio

            asyncio.create_task(
                self._send_reassignment_notification(
                    ticket_key=ticket_key,
                    new_assignee_ldap=ldap_username,
                )
            )

            # Send confirmation DM to requester
            jira_url = f"https://jira.corp.adobe.com/browse/{ticket_key}"
            asyncio.create_task(
                self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f":white_check_mark: *{ticket_key}* has been reassigned to *{ldap_username}*.\n<{jira_url}|View in JIRA>",
                )
            )

            # Close modal immediately
            return {"response_action": "clear"}

        except Exception as e:
            logger.error(
                "Error handling reassign submission: %s",
                e,
                exc_info=True,
            )
            return False

    async def _send_reassignment_notification(
        self,
        ticket_key: str,
        new_assignee_ldap: str,
    ) -> bool:
        """
        Send an immediate assignment notification to the new assignee.

        Preserves followup_ticket_keys from the previous assignee's record.
        """
        if not self._user_ops:
            logger.warning("Cannot send immediate notification - user_ops not available")
            return False

        try:
            # 1. Get existing record to preserve followup_ticket_keys
            existing_followups: List[str] = []
            if self._state_tracker:
                existing_record = await self._state_tracker.get_notification_record(ticket_key)
                if existing_record and existing_record.followup_ticket_keys:
                    existing_followups = existing_record.followup_ticket_keys
                    logger.info(
                        "Preserving %d followup tickets from previous assignee for %s",
                        len(existing_followups),
                        ticket_key,
                    )

            # 2. Resolve new assignee Slack ID
            email = f"{new_assignee_ldap.lower()}@adobe.com"
            new_slack_id = await self._user_ops.get_slack_id_by_email(email)

            if not new_slack_id:
                logger.warning(
                    "Could not resolve Slack ID for %s, notification will be sent on next poll",
                    new_assignee_ldap,
                )
                return False

            # 3. Fetch ticket details for notification
            ticket_data = await self._mcp_client.get_issue(
                issue_key=ticket_key,
                fields=["summary", "created", "description", "status"],
            )

            if not ticket_data:
                logger.warning("Could not fetch ticket details for %s", ticket_key)
                return False

            fields = ticket_data.get("fields", {})
            summary = fields.get("summary", "")
            description = fields.get("description", "")
            status_obj = fields.get("status", {})
            status = status_obj.get("name", "New") if isinstance(status_obj, dict) else "New"

            # Extract exigence ID from description if present
            exigence_id = None
            if description:
                import re

                match = re.search(r"exigence\.corp\.adobe\.com/event/(\d+)", description)
                if match:
                    exigence_id = match.group(1)

            # 4. Build CSOPMTicket object for notification
            from datetime import datetime, timezone

            from packages.core.typed_di.protocols import CSOPMTicket
            from packages.slack.csopm import CSOPMNotificationBlocks

            ticket = CSOPMTicket(
                key=ticket_key,
                summary=summary,
                assignee_username=new_assignee_ldap,
                created_at=datetime.now(timezone.utc),
                status=status,
                exigence_id=exigence_id,
            )

            blocks = CSOPMNotificationBlocks.build_assignment_notification(
                ticket=ticket,
                exigence_id=exigence_id,
            )

            await self._posting_handler.post_message(
                channel_id=new_slack_id,
                blocks=blocks,
            )

            logger.info(
                "Sent immediate reassignment notification for %s to %s (%s)",
                ticket_key,
                new_assignee_ldap,
                new_slack_id,
            )

            # 5. Update state tracker - create new record then restore followups
            if self._state_tracker:
                await self._state_tracker.create_notification_record(
                    ticket=ticket,
                    slack_id=new_slack_id,
                )

                # Restore followup tickets from previous assignee
                if existing_followups:
                    for followup_key in existing_followups:
                        try:
                            await self._state_tracker.add_followup_ticket(
                                ticket_key=ticket_key,
                                followup_key=followup_key,
                            )
                        except Exception as e:
                            logger.warning("Failed to restore followup %s: %s", followup_key, e)
                    logger.info(
                        "Restored %d followup tickets for %s",
                        len(existing_followups),
                        ticket_key,
                    )

            return True

        except Exception as e:
            logger.error(
                "Error sending reassignment notification for %s: %s",
                ticket_key,
                e,
                exc_info=True,
            )
            return False


def is_csopm_action(action_id: str) -> bool:
    """
    Check if an action_id is a CSOPM action.

    Args:
        action_id: The action ID to check.

    Returns:
        True if the action_id starts with 'csopm_'.
    """
    return action_id.startswith(CSOPM_ACTION_PREFIX)


def is_csopm_modal(callback_id: str) -> bool:
    """
    Check if a callback_id is a CSOPM modal.

    Args:
        callback_id: The modal callback ID to check.

    Returns:
        True if the callback_id is a known CSOPM modal.
    """
    return callback_id in (
        CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID,
        CSOPM_STATUS_TRANSITION_MODAL_CALLBACK_ID,
        CSOPM_REASSIGN_MODAL_CALLBACK_ID,
    )
