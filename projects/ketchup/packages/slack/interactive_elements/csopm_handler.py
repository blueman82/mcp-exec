"""
CSOPM Interactive Element Handler.

Handles Slack interactive elements for CSOPM notifications including:
- Block action button clicks (csopm_acknowledge, csopm_create_followup, csopm_done, etc.)
- Modal view submissions (csopm_create_followup_modal)

This handler routes interactive events from payload_processor.py to the
CSOPMSlackNotifier service for processing.

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
- csopm_done: Mark ticket as done
- csopm_snooze: Snooze closure reminder for 7 days
- csopm_close_ticket: Close ticket in JIRA
- csopm_view_jira: Link button (no backend handling needed)

Modal Callback IDs:
- csopm_create_followup_modal: Create follow-up ticket submission
"""

from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import CSOPMSlackNotifierProtocol
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


# CSOPM action ID prefix for routing
CSOPM_ACTION_PREFIX = "csopm_"

# Modal callback ID for follow-up creation
CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID = "csopm_create_followup_modal"


class CSOPMHandler:
    """
    Handler for CSOPM interactive elements.

    Processes block actions and modal submissions for CSOPM notifications.
    Delegates business logic to CSOPMSlackNotifier service.

    Key Responsibilities:
    1. Extract action context from Slack payloads
    2. Route button clicks to appropriate notifier methods
    3. Handle modal submissions for follow-up ticket creation
    4. Coordinate MCP calls for JIRA operations
    """

    def __init__(
        self,
        slack_notifier: CSOPMSlackNotifierProtocol,
        mcp_client: AsyncMCPClient,
        posting_handler: SlackPostingHandler,
    ) -> None:
        """
        Initialize the CSOPM handler.

        Args:
            slack_notifier: CSOPMSlackNotifier service for notification handling.
            mcp_client: AsyncMCPClient for JIRA MCP operations.
            posting_handler: SlackPostingHandler for modal opening and messages.
        """
        self._notifier = slack_notifier
        self._mcp_client = mcp_client
        self._posting_handler = posting_handler
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

            # Delegate to notifier's handle_button_action
            success = await self._notifier.handle_button_action(
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

            return success

        except Exception as e:
            logger.error("Error handling CSOPM block action: %s", e, exc_info=True)
            return False

    async def handle_view_submission(self, payload: Dict[str, Any]) -> bool:
        """
        Handle a view_submission payload for CSOPM modals.

        Currently handles:
        - csopm_create_followup_modal: Create follow-up ticket in JIRA

        Args:
            payload: The Slack view_submission payload.

        Returns:
            True if submission was handled successfully, False otherwise.
        """
        try:
            view = payload.get("view", {})
            callback_id = view.get("callback_id", "")

            if callback_id != CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID:
                logger.warning("Unknown CSOPM modal callback_id: %s", callback_id)
                return False

            return await self._handle_create_followup_submission(payload)

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
                projects = await self._mcp_client.list_projects(expand="issueTypes")
                logger.info("Fetched %d projects for followup modal", len(projects))
            except Exception as e:
                logger.warning("Failed to fetch JIRA projects: %s", e)

            # Extract issue types from CSOPM project if available
            issue_types = []
            try:
                for project in projects:
                    if project.get("key") == "CSOPM":
                        issue_types = project.get("issueTypes", [])
                        break

                if not issue_types and projects:
                    issue_types = projects[0].get("issueTypes", [])

                logger.info("Extracted %d issue types for modal", len(issue_types))
            except Exception as e:
                logger.warning("Failed to extract issue types: %s", e)

            # Build modal from notification blocks
            from datetime import datetime, timezone

            from ketchup_csopm_notifier.blocks.notification_blocks import (
                CSOPMNotificationBlocks,
            )
            from packages.core.typed_di.protocols import CSOPMTicket

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

            # Build modal view
            modal = CSOPMNotificationBlocks.build_create_followup_modal(
                ticket=csopm_ticket,
                projects=projects,
                issue_types=issue_types,
            )

            # Open modal via SlackPostingHandler (or direct API call)
            # Note: This requires views.open API access
            result = await self._posting_handler.open_modal(
                trigger_id=trigger_id,
                view=modal,
            )

            if result and result.get("ok"):
                logger.info("Successfully opened create followup modal for %s", ticket_key)
                return True
            else:
                error = result.get("error", "Unknown error") if result else "No response"
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

    async def _handle_create_followup_submission(
        self,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Handle the create follow-up modal submission.

        Creates a new JIRA issue and links it to the parent CSOPM ticket
        using the 'Relates' link type.

        Flow:
        1. Extract form values from modal submission
        2. Create new JIRA issue via MCP
        3. Link new issue to parent CSOPM ticket
        4. Send confirmation message to user

        Args:
            payload: The Slack view_submission payload.

        Returns:
            True if follow-up was created successfully, False otherwise.
        """
        try:
            view = payload.get("view", {})
            user = payload.get("user", {})
            user_id = user.get("id")

            # Extract parent ticket key from private_metadata
            parent_ticket_key = view.get("private_metadata", "")
            if not parent_ticket_key:
                logger.error("No parent ticket key in private_metadata")
                return False

            # Extract form values
            state_values = view.get("state", {}).get("values", {})

            # Get project key
            project_block = state_values.get("project_block", {})
            project_input = project_block.get("project_input", {})
            # Handle both static_select and plain_text_input
            if project_input.get("type") == "static_select":
                project_key = project_input.get("selected_option", {}).get("value", "CSOPM")
            else:
                project_key = project_input.get("value", "CSOPM")

            # Get issue type
            issue_type_block = state_values.get("issue_type_block", {})
            issue_type_input = issue_type_block.get("issue_type_input", {})
            if issue_type_input.get("type") == "static_select":
                issue_type = issue_type_input.get("selected_option", {}).get("value", "Task")
            else:
                issue_type = issue_type_input.get("value", "Task")

            # Get summary and description
            summary_block = state_values.get("summary_block", {})
            summary = summary_block.get("summary_input", {}).get("value", "")

            description_block = state_values.get("description_block", {})
            description = description_block.get("description_input", {}).get("value", "")

            if not summary:
                logger.error("No summary provided for follow-up ticket")
                return False

            logger.info(
                "Creating follow-up ticket: project=%s, type=%s, parent=%s",
                project_key,
                issue_type,
                parent_ticket_key,
            )

            # Create the new JIRA issue via MCP
            create_result = await self._mcp_client._call_mcp_tool(
                "create_jira_issue",
                {
                    "projectKey": project_key,
                    "issueType": issue_type,
                    "summary": summary,
                    "description": description,
                },
            )

            if not create_result or not create_result.get("success"):
                error_msg = (
                    create_result.get("message", "Unknown error")
                    if create_result
                    else "No response"
                )
                logger.error("Failed to create follow-up ticket: %s", error_msg)

                # Send error message to user
                await self._posting_handler.post_message(
                    channel_id=user_id,
                    message=f"Failed to create follow-up ticket: {error_msg}",
                )
                return False

            # Extract new ticket key from response
            new_ticket_key = create_result.get("key", "")
            if not new_ticket_key:
                logger.error("No ticket key returned from create_jira_issue")
                return False

            logger.info(
                "Created follow-up ticket %s, linking to parent %s",
                new_ticket_key,
                parent_ticket_key,
            )

            # Link the new issue to the parent CSOPM ticket
            link_result = await self._mcp_client._call_mcp_tool(
                "link_issues",
                {
                    "inwardIssue": parent_ticket_key,  # Parent CSOPM ticket
                    "outwardIssue": new_ticket_key,  # New follow-up ticket
                    "linkType": "Relates",
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
                    link_result.get("message", "Unknown error") if link_result else "No response",
                )
                # Continue anyway - the ticket was created

            # Record follow-up in state tracker if available
            if hasattr(self._notifier, "_state_tracker") and self._notifier._state_tracker:
                try:
                    await self._notifier._state_tracker.record_followup(
                        parent_key=parent_ticket_key,
                        followup_key=new_ticket_key,
                    )
                except Exception as e:
                    logger.warning("Failed to record follow-up in state tracker: %s", e)

            # Build JIRA URL for the new ticket
            jira_url = f"https://jira.corp.adobe.com/browse/{new_ticket_key}"

            # Send success confirmation to user
            confirmation_text = (
                f":white_check_mark: Follow-up ticket *<{jira_url}|{new_ticket_key}>* created!\n"
                f"Linked to parent ticket {parent_ticket_key}"
            )

            await self._posting_handler.post_message(
                channel_id=user_id,
                message=confirmation_text,
            )

            logger.info(
                "Follow-up ticket %s created and linked to %s successfully",
                new_ticket_key,
                parent_ticket_key,
            )

            return True

        except Exception as e:
            logger.error(
                "Error handling create followup submission: %s",
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
    return callback_id == CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID
