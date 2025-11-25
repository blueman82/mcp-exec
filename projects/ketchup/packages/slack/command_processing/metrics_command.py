"""
metrics_command.py

This module contains the MetricsCommand class for generating metrics dashboard.
"""

from typing import Any, Dict, Optional

import orjson

from packages.core.logging import setup_logger
from packages.slack.user_operations.user_ops import SlackUserOps
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_parameters.models import (
    MetricsCommandParams,
)
from packages.slack.interactive_elements.metrics_export_handler import (
    MetricsExportHandler
)
from packages.slack.messages.posting import SlackPostingHandler
from packages.secrets.manager import SecretsManager
from packages.core.exports.time_period_formatter import (
    format_confirmation_message,
)

logger = setup_logger(__name__)


class MetricsCommand(BaseCommandHandler):
    """
    Handler for the /ketchup metrics command.

    Generates comprehensive HTML dashboard covering:
    - Executive CSO Management metrics (product coverage, war room readiness)
    - Technical System Health (status updates, auto-messages, system health)

    The metrics command follows the pattern:
    /ketchup metrics
    """

    def __init__(
        self,
        slack_posting_handler: SlackPostingHandler,
        metrics_export_handler: MetricsExportHandler,
        secrets_manager: SecretsManager,
        slack_user_ops: SlackUserOps,
    ):
        """
        Initialize the MetricsCommand with dependencies.

        Args:
            slack_posting_handler: Handler for posting Slack messages
            metrics_export_handler: Handler for metrics export and delivery
            secrets_manager: Manager for accessing AWS secrets
            slack_user_ops: Operations for Slack user info
        """
        super().__init__()
        self.posting_handler = slack_posting_handler
        self.metrics_export_handler = metrics_export_handler
        self.secrets_manager = secrets_manager
        self.slack_user_ops = slack_user_ops
        logger.info("MetricsCommand initialized")

    async def process_metrics_params(
        self,
        params: MetricsCommandParams,
        user_id: str,
        incoming_channel: str,
        response_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process metrics command params and generate HTML dashboard.

        Args:
            params: Command parameters extracted by the parameter extractor
            user_id: ID of the user who issued the command
            incoming_channel: Channel ID where the command was issued
            response_url: Optional response URL for delayed responses

        Returns:
            Dict with status code and body
        """
        logger.info(
            f"Processing metrics command for user {user_id} "
            f"(period: {params.time_period_type})"
        )

        # Check if user is admin
        is_admin = await self._check_if_admin(user_id)
        if not is_admin:
            logger.warning(
                f"User {user_id} attempted to access metrics command without admin rights"
            )
            await self.posting_handler.post_message(
                channel_id=user_id,
                message="⛔ Access Denied: The `/ketchup metrics` command is restricted to authorized administrators only.",
            )
            return {"statusCode": 403, "body": "Access denied"}

        # Send immediate confirmation message
        confirmation_msg = format_confirmation_message(
            params.time_period_type,
            params.month,
            params.quarter,
            params.year,
            params.is_partial,
            params.start_date,
            params.end_date,
        )
        
        await self.posting_handler.post_message(
            channel_id=user_id,
            message=confirmation_msg,
        )
        
        logger.info(f"Sent confirmation: {confirmation_msg}")

        # Call metrics export handler to generate and deliver dashboard
        success = await self.metrics_export_handler.handle_metrics_request(
            user_id=user_id,
            response_url=response_url,
            time_params={
                "period_type": params.time_period_type,
                "start_ts": int(params.start_date.timestamp()),
                "end_ts": int(params.end_date.timestamp()),
                "month": params.month,
                "quarter": params.quarter,
                "year": params.year,
                "is_partial": params.is_partial,
                "start_date": params.start_date,
                "end_date": params.end_date,
            },
        )

        if success:
            return {"statusCode": 200, "body": "Metrics dashboard generated"}
        else:
            return {"statusCode": 500, "body": "Failed to generate metrics"}

    async def _check_if_admin(self, user_id: str) -> bool:
        """
        Check if a user is an admin.

        Args:
            user_id: ID of the user to check

        Returns:
            True if user is admin, False otherwise
        """
        try:
            # Get the admin user list from secrets
            kt_secrets = await self.secrets_manager.get_secret_async(
                "Ketchup_Token_Secrets"
            )
            admin_users = kt_secrets.get("usage_stats_admin_users", [])

            # If it's a string (JSON), parse it
            if isinstance(admin_users, str):
                admin_users = orjson.loads(admin_users)

            # Get user info to check against admin list
            user_info = await self.slack_user_ops._fetch_user_info_internal(user_id)

            if not user_info:
                logger.error(f"Failed to fetch info for user {user_id}")
                return False

            # Check by user ID (direct match)
            if user_id in admin_users:
                logger.info(f"User {user_id} is admin by ID")
                return True

            # Check by email (domain)
            user_email = user_info.get("profile", {}).get("email", "").lower()
            if user_email.endswith("@adobe.com") and user_email in admin_users:
                logger.info(f"User {user_id} is admin by email")
                return True

            # Check by name (case-insensitive)
            user_name = (
                user_info.get("profile", {}).get("real_name", "")
                or user_info.get("real_name", "")
                or user_info.get("name", "")
            ).lower()

            if user_name in [name.lower() for name in admin_users]:
                logger.info(f"User {user_id} is admin by name")
                return True

            # Not an admin
            logger.info(f"User {user_id} is not an admin")
            return False
        except Exception as e:
            logger.error(f"Error checking admin status for user {user_id}: {e}")
            return False
