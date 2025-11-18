"""
Action handlers for flag review functionality.

This module handles all user interactions including button clicks,
modal submissions, and various action processing for flag reviews.
"""

from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.slack.interactive_elements.flag_review.flag_types import (
    ACTION_ACKNOWLEDGE_FEEDBACK,
    ACTION_COMMAND_ACKNOWLEDGE,
    ACTION_COMMAND_REPLY,
    ACTION_REPLY_TO_FEEDBACK,
    BLOCK_FEEDBACK_INPUT,
    BLOCK_REPLY_INPUT,
)

logger = setup_logger(__name__)


class FlagReviewActionHandler:
    """Handles user actions and interactions for flag review functionality."""

    def __init__(self):
        """Initialize the action handler."""
        pass

    async def handle_cancel_action(self, payload: Dict[str, Any]) -> bool:
        """
        Handle cancel action from modals or buttons.

        Args:
            payload: The interaction payload from Slack

        Returns:
            True if handled successfully, False otherwise
        """
        try:
            # Extract action details
            action_type = payload.get("type")

            if action_type == "view_closed":
                # Modal was closed/cancelled
                logger.info("User cancelled modal interaction")
                return True
            elif action_type == "block_actions":
                # Cancel button was clicked
                action = payload.get("actions", [{}])[0]
                if action.get("action_id") == "cancel_action":
                    logger.info("User cancelled via button")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error handling cancel action: {e}")
            return False

    async def handle_edit_action(
        self, payload: Dict[str, Any], flag_id: str, current_text: str
    ) -> Dict[str, Any]:
        """
        Handle edit action for existing feedback.

        Args:
            payload: The interaction payload from Slack
            flag_id: The ID of the flag to edit
            current_text: The current feedback text

        Returns:
            Dict with edit results
        """
        try:
            user_id = payload.get("user", {}).get("id")
            trigger_id = payload.get("trigger_id")

            # Prepare edit modal data
            edit_data = {
                "trigger_id": trigger_id,
                "flag_id": flag_id,
                "current_text": current_text,
                "user_id": user_id,
            }

            logger.info(f"User {user_id} editing flag {flag_id}")
            return {"success": True, "data": edit_data}

        except Exception as e:
            logger.error(f"Error handling edit action: {e}")
            return {"success": False, "error": str(e)}

    async def handle_submit_action(
        self, payload: Dict[str, Any], action_type: str
    ) -> Dict[str, Any]:
        """
        Handle submit action from modals.

        Args:
            payload: The interaction payload from Slack
            action_type: Type of submission ('flag', 'reply', 'edit')

        Returns:
            Dict with submission results
        """
        try:
            view = payload.get("view", {})
            user_id = payload.get("user", {}).get("id")

            # Extract submitted values
            values = view.get("state", {}).get("values", {})

            if action_type == "flag":
                # Extract feedback text
                feedback_text = self._extract_value_from_blocks(
                    values, "feedback_block", BLOCK_FEEDBACK_INPUT
                )
                private_metadata = view.get("private_metadata", "").split("|")

                return {
                    "success": True,
                    "type": "flag",
                    "user_id": user_id,
                    "feedback_text": feedback_text,
                    "metadata": private_metadata,
                }

            elif action_type == "reply":
                # Extract reply text
                reply_text = self._extract_value_from_blocks(
                    values, "reply_block", BLOCK_REPLY_INPUT
                )
                private_metadata = view.get("private_metadata", "").split("|")

                return {
                    "success": True,
                    "type": "reply",
                    "user_id": user_id,
                    "reply_text": reply_text,
                    "metadata": private_metadata,
                }

            else:
                logger.warning(f"Unknown submit action type: {action_type}")
                return {"success": False, "error": "Unknown action type"}

        except Exception as e:
            logger.error(f"Error handling submit action: {e}")
            return {"success": False, "error": str(e)}

    async def handle_review_action(
        self, payload: Dict[str, Any], review_type: str
    ) -> Dict[str, Any]:
        """
        Handle review-related actions.

        Args:
            payload: The interaction payload from Slack
            review_type: Type of review action

        Returns:
            Dict with review action results
        """
        try:
            user_id = payload.get("user", {}).get("id")
            action = payload.get("actions", [{}])[0]
            action_value = action.get("value")

            # Parse action value (typically contains flag_id and other data)
            if action_value:
                parts = action_value.split("|")
                flag_id = parts[0] if parts else None
            else:
                flag_id = None

            result = {
                "success": True,
                "review_type": review_type,
                "flag_id": flag_id,
                "user_id": user_id,
                "timestamp": payload.get("action_ts"),
            }

            logger.info(f"Handled review action: {review_type} for flag {flag_id}")
            return result

        except Exception as e:
            logger.error(f"Error handling review action: {e}")
            return {"success": False, "error": str(e)}

    async def handle_reminder_action(
        self,
        flag_id: str,
        user_id: str,
        reminder_type: str,
        reminder_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle reminder-related actions.

        Args:
            flag_id: The ID of the flag
            user_id: The user to remind
            reminder_type: Type of reminder ('daily', 'weekly', 'custom')
            reminder_time: Custom reminder time (optional)

        Returns:
            Dict with reminder setup results
        """
        try:
            reminder_data = {
                "flag_id": flag_id,
                "user_id": user_id,
                "type": reminder_type,
            }

            if reminder_type == "custom" and reminder_time:
                reminder_data["time"] = reminder_time
            elif reminder_type == "daily":
                reminder_data["time"] = "09:00"  # Default daily time
            elif reminder_type == "weekly":
                reminder_data["time"] = "monday_09:00"  # Default weekly time

            logger.info(f"Set {reminder_type} reminder for flag {flag_id}")
            return {"success": True, "reminder": reminder_data}

        except Exception as e:
            logger.error(f"Error handling reminder action: {e}")
            return {"success": False, "error": str(e)}

    async def handle_feedback_action(
        self, payload: Dict[str, Any], feedback_type: str
    ) -> Dict[str, Any]:
        """
        Handle feedback-specific actions.

        Args:
            payload: The interaction payload from Slack
            feedback_type: Type of feedback action

        Returns:
            Dict with feedback action results
        """
        try:
            user_id = payload.get("user", {}).get("id")

            action = payload.get("actions", [{}])[0]
            action_id = action.get("action_id")

            if action_id in [ACTION_ACKNOWLEDGE_FEEDBACK, ACTION_COMMAND_ACKNOWLEDGE]:
                # Handle acknowledgment
                flag_id = action.get("value")

                return {
                    "success": True,
                    "type": "acknowledge",
                    "flag_id": flag_id,
                    "admin_id": user_id,
                }

            elif action_id in [ACTION_REPLY_TO_FEEDBACK, ACTION_COMMAND_REPLY]:
                # Handle reply initiation
                action_value = action.get("value", "")
                parts = action_value.split("|")

                return {
                    "success": True,
                    "type": "reply_init",
                    "flag_id": parts[0] if parts else None,
                    "feedback_preview": parts[1] if len(parts) > 1 else "",
                    "admin_id": user_id,
                    "trigger_id": payload.get("trigger_id"),
                }

            else:
                logger.warning(f"Unknown feedback action type: {feedback_type}")
                return {"success": False, "error": "Unknown feedback type"}

        except Exception as e:
            logger.error(f"Error handling feedback action: {e}")
            return {"success": False, "error": str(e)}

    async def handle_modal_submission(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic handler for modal submissions.

        Args:
            payload: The interaction payload from Slack

        Returns:
            Dict with submission processing results
        """
        try:
            view = payload.get("view", {})
            callback_id = view.get("callback_id")
            # user_id = payload.get("user", {}).get("id")  # Available if needed

            # Route based on callback_id
            if callback_id == "flag_review_modal":
                return await self.handle_submit_action(payload, "flag")
            elif callback_id in [
                "reply_feedback_modal",
                "reply_command_feedback_modal",
            ]:
                return await self.handle_submit_action(payload, "reply")
            elif callback_id == "command_flag_review_modal":
                return await self.handle_submit_action(payload, "flag")
            else:
                logger.warning(f"Unknown modal callback_id: {callback_id}")
                return {"success": False, "error": f"Unknown modal: {callback_id}"}

        except Exception as e:
            logger.error(f"Error handling modal submission: {e}")
            return {"success": False, "error": str(e)}

    def _extract_value_from_blocks(
        self, values: Dict[str, Any], block_id: str, action_id: str
    ) -> Optional[str]:
        """
        Extract a value from modal submission blocks.

        Args:
            values: The values dict from modal state
            block_id: The block ID to look for
            action_id: The action ID within the block

        Returns:
            The extracted value or None
        """
        try:
            block = values.get(block_id, {})
            action = block.get(action_id, {})
            return action.get("value")
        except Exception as e:
            logger.error(f"Error extracting value from blocks: {e}")
            return None

    def validate_action_permissions(
        self, user_id: str, action_type: str, resource_id: Optional[str] = None
    ) -> bool:
        """
        Validate if a user has permission to perform an action.

        Args:
            user_id: The user attempting the action
            action_type: The type of action
            resource_id: The resource being acted upon (optional)

        Returns:
            True if permitted, False otherwise
        """
        # For now, basic validation - can be extended with role checks
        if not user_id:
            return False

        # Admin actions might require additional checks
        admin_actions = ["acknowledge", "reply", "delete", "escalate"]
        if action_type in admin_actions:
            # Would check admin status here
            logger.debug(f"Checking admin permission for {user_id}")

        return True
