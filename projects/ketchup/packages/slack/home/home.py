"""
home.py

This module handles the Slack Home tab interface for Ketchup.
It provides functionality to display and update a user's personalized preferences.
"""

from typing import Any, Dict, List, Optional, Tuple

from packages.core.logging import setup_logger
from packages.db.operations.command_tracking_operations import (
    CommandTrackingOperations,
)
from packages.db.user_store import UserStore
from packages.secrets.manager import SecretsManager
from packages.slack.core.slack_async_client import SlackAsyncClient
from packages.slack.home.home_utils import (
    build_home_tab_blocks,
    normalize_user_preferences,
    save_user_preferences,
)
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler
from packages.slack.interactive_elements.usage_export_handler import UsageExportHandler
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


class HomeTabHandler:
    """
    Handler for Slack Home tab operations.
    Provides methods for publishing views to the Home tab and handling interactions.
    """

    def __init__(
        self,
        secrets_manager: SecretsManager,
        user_store: UserStore,
        slack_client: SlackAsyncClient,
        slack_user_ops: SlackUserOps,
        feedback_report_handler: FeedbackReportHandler = None,
        command_tracking_ops: Optional[CommandTrackingOperations] = None,
        admin_user_list: Optional[List[str]] = None,
        usage_export_handler: Optional[UsageExportHandler] = None,
    ):
        """
        Initialize the HomeTabHandler with dependencies.

        Args:
            secrets_manager: Manager for Slack secrets
            user_store: Store for user preference data
            slack_client: SlackAsyncClient for Slack API interactions
            slack_user_ops: SlackUserOps for fetching user info
            feedback_report_handler: Handler for feedback reporting functionality
        """
        self._secrets_manager = secrets_manager
        self._user_store = user_store
        self._slack_client = slack_client
        self._slack_user_ops = slack_user_ops
        self._feedback_report_handler = feedback_report_handler
        self._command_tracking_ops = command_tracking_ops
        self._usage_export_handler = usage_export_handler
        # Normalize admin user list - handle both "FirstName LastName" and "firstname lastname" formats
        self._admin_user_list = []
        if admin_user_list:
            for user in admin_user_list:
                # Add both the original lowercase and a normalized version
                self._admin_user_list.append(user.lower())
                # Also add version with spaces normalized (in case of extra spaces)
                normalized = " ".join(user.lower().split())
                if normalized != user.lower():
                    self._admin_user_list.append(normalized)
        logger.info("HomeTabHandler initialized with dependencies")
        # Debug: log count of admin users (not names for privacy)
        logger.info(
            "Usage-stats admin user list initialised with %d users", len(self._admin_user_list)
        )

    async def handle_app_home_opened(self, event: Dict[str, Any]) -> bool:
        """
        Handle the app_home_opened event from Slack.

        Args:
            event: The app_home_opened event data from Slack

        Returns:
            bool: True if the Home tab was published successfully, False otherwise
        """
        user_id = event.get("user")
        if not user_id:
            logger.error("Missing user_id in app_home_opened event")
            return False

        logger.info("Publishing Home tab for user: %s", user_id)

        # Get user preferences from DynamoDB
        raw_prefs, normalized_prefs, first_name = await self._get_user_preferences(
            user_id
        )

        logger.info(
            "Home tab context for user %s: Name=%s, Raw Prefs=%s, Normalized Prefs=%s",
            user_id,
            first_name,
            raw_prefs,
            normalized_prefs,
        )

        # -------------------------------------------------
        #  Gather usage statistics if tracking is enabled
        # -------------------------------------------------
        command_stats: Optional[Dict[str, int]] = None
        admin_stats: Optional[List[tuple]] = None
        admin_command_breakdown: Optional[Dict[str, Dict[str, Any]]] = None
        is_admin_user: bool = False

        try:
            # Resolve username for admin check
            user_name_map = await self._slack_user_ops.get_user_names([user_id])
            user_name = user_name_map.get(user_id, "").lower()

            logger.info(
                "Resolved Slack username for %s ➜ '%s' (admin list check)",
                user_id,
                user_name,
            )

            # Personal stats
            if self._command_tracking_ops:
                command_stats = await self._command_tracking_ops.get_user_command_stats(
                    user_id, days=7
                )

            # Admin stats
            if user_name and user_name in self._admin_user_list:
                is_admin_user = True
                if self._command_tracking_ops:
                    admin_stats = await self._command_tracking_ops.get_top_users(
                        days=7, limit=5
                    )
                    logger.info(
                        "Admin stats retrieved for '%s' -> %d records",
                        user_name,
                        len(admin_stats or []),
                    )
                    # Get detailed command breakdown for admins
                    admin_command_breakdown = (
                        await self._command_tracking_ops.get_user_command_breakdown(
                            days=7, limit=5
                        )
                    )
                    logger.info(
                        "Admin command breakdown retrieved for '%s' -> %d users",
                        user_name,
                        len(admin_command_breakdown or {}),
                    )
            else:
                logger.info(
                    "User '%s' is not in admin list; admin_stats will not be shown",
                    user_name,
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Error retrieving usage statistics for home tab: %s", str(e))

        # Publish the Home tab view
        return await self._publish_home_tab(
            user_id,
            raw_prefs,
            first_name,
            command_stats=command_stats,
            is_admin_user=is_admin_user,
            admin_stats=admin_stats,
            admin_command_breakdown=admin_command_breakdown,
        )

    async def _get_user_preferences(
        self, user_id: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """
        Get a user's preferences from the database, returning both raw and normalized versions.

        The raw preferences are used for UI display/storage, while normalized preferences
        are used for AI prompts (status.py, report.py etc).

        Args:
            user_id: The Slack user ID

        Returns:
            Tuple containing:
                - raw_prefs: The user's raw preferences (for UI/storage)
                - normalized_prefs: Normalized preferences (for AI prompts)
                - first_name: User's first name
        """
        # Define default preferences
        default_raw_prefs = {
            "product_focus": ["all_products"],
            "detail_level": "technical_details",
            "time_window": "past_24_hours",
        }
        raw_user_prefs = default_raw_prefs.copy()
        first_name = "there"

        try:
            # Ensure user info is cached by calling the user ops, which has API fallback
            await self._slack_user_ops.get_user_names([user_id])

            # Try to get user preferences from the database
            user_data = await self._user_store.get_user(user_id)
            if user_data and "preferences" in user_data:
                raw_user_prefs = user_data["preferences"]

            # Extract user's first name
            real_name = user_data.get("real_name", "there") if user_data else "there"
            first_name = (
                real_name.split()[0] if real_name and real_name != "there" else "there"
            )

        except Exception as e:
            logger.error(
                f"Error getting user preferences for user {user_id}: {str(e)}. Using defaults."
            )
            # Ensure raw_user_prefs and first_name are at defaults if an error occurs
            raw_user_prefs = default_raw_prefs.copy()
            first_name = "there"

        # Normalize the preferences for AI use
        normalized_user_prefs = normalize_user_preferences(raw_user_prefs)

        logger.info(
            f"_get_user_preferences returning for user {user_id}: raw_prefs={raw_user_prefs}, normalized_prefs={normalized_user_prefs}, first_name={first_name}"
        )
        return raw_user_prefs, normalized_user_prefs, first_name

    async def _publish_home_tab(
        self,
        user_id: str,
        user_prefs: Dict[str, Any],
        first_name: str,
        *,
        command_stats: Optional[Dict[str, int]] = None,
        is_admin_user: bool = False,
        admin_stats: Optional[List[tuple]] = None,
        admin_command_breakdown: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> bool:
        """
        Publish the Home tab view for a user.

        Args:
            user_id: The Slack user ID
            user_prefs: The user's preferences
            first_name: The user's first name

        Returns:
            bool: True if the view was published successfully, False otherwise
        """
        try:
            blocks = build_home_tab_blocks(
                user_prefs,
                first_name,
                command_stats=command_stats,
                is_admin_user=is_admin_user,
                admin_stats=admin_stats,
                admin_command_breakdown=admin_command_breakdown,
            )
            view = {"type": "home", "blocks": blocks}
            payload = {
                "user_id": user_id,
                "view": view,
            }

            # Use SlackAsyncClient's api_call
            data = await self._slack_client.api_call("views.publish", payload)
            if not data.get("ok"):
                logger.error("Error publishing Home tab: %s", data)
                return False
            logger.info("Successfully published Home tab for user: %s", user_id)
            return True
        except Exception as e:
            logger.error("Error publishing Home tab: %s", str(e))
            return False

    async def handle_block_actions(self, payload: Dict[str, Any]) -> bool:
        """
        Handle block actions from the Home tab.

        Args:
            payload: The block_actions payload from Slack

        Returns:
            bool: True if the action was handled successfully, False otherwise
        """
        user_id = payload.get("user", {}).get("id")
        if not user_id:
            logger.error("Missing user_id in block_actions payload")
            return False

        # Check for actions
        actions = payload.get("actions", [])
        if not actions:
            return False

        # Get the action ID from the first action
        action = actions[0]
        action_id = action.get("action_id")

        # Check if save button was clicked
        if action_id == "save_preferences_button":
            # Save all current state values
            success = await save_user_preferences(
                user_id,
                payload,
                self._user_store,
                self._slack_user_ops,
                self._slack_client,
            )

            # If save was successful, refresh the home tab to show updated preferences
            if success:
                logger.info(
                    "Preferences saved successfully, refreshing home tab for user %s",
                    user_id,
                )
                # Add a small delay to ensure DynamoDB write is fully committed
                import asyncio

                await asyncio.sleep(0.5)
                # Create an event object that mimics app_home_opened event
                refresh_event = {"user": user_id}
                await self.handle_app_home_opened(refresh_event)

            return success
        elif action_id == "home_open_feedback_modal":
            logger.info("Feedback button clicked by user %s", user_id)
            trigger_id = payload.get("trigger_id")
            if not trigger_id:
                logger.error("Missing trigger_id in feedback button payload")
                return False

            if self._feedback_report_handler is None:
                logger.error("Feedback report handler not initialized")
                return False

            success = await self._feedback_report_handler.open_feedback_report_modal(
                trigger_id
            )
            return success
        elif action_id == "export_usage_csv":
            # Handle export button click
            trigger_id = payload.get("trigger_id")

            if not self._usage_export_handler:
                logger.error("Usage export handler not initialized")
                return False

            # Check if user is admin
            user_name_map = await self._slack_user_ops.get_user_names([user_id])
            user_name = user_name_map.get(user_id, "").lower()

            if user_name not in self._admin_user_list:
                # Since Home tab actions don't have response_url, send DM directly
                await self._slack_client.api_call(
                    "chat.postMessage",
                    {
                        "channel": user_id,
                        "text": "This feature is only available to administrators.",
                    },
                )
                return False

            # Run export in background to avoid blocking
            import asyncio

            asyncio.create_task(
                self._usage_export_handler.handle_export_request(
                    trigger_id=trigger_id,
                    user_id=user_id,
                    response_url=None,  # Home tab actions don't have response_url
                )
            )
            return True

        # For other actions, we'll update the view in real-time
        # But we don't need to save to the database until the save button is clicked
        return True
