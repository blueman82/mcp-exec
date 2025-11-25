"""
feature_command.py

This module contains the FeatureCommand class for managing feature flags.
"""

import time
from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_parameters.models import (
    FeatureCommandParams,
)
from packages.slack.command_processing.feature_service import FeatureService
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


class FeatureCommand(BaseCommandHandler):
    """
    Handler for the /ketchup feature command, which manages feature flags.

    This command follows the pattern:
    /ketchup feature <feature_name> <action> [user_mention]

    Available actions:
    - enable @user - Enable the feature for a user
    - disable @user - Disable the feature for a user
    - list - List all users with the feature
    - status - Show the current status of the feature
    """

    def __init__(
        self,
        feature_service: FeatureService,
        slack_posting_handler: SlackPostingHandler,
        slack_user_ops: SlackUserOps,
        secrets_manager: SecretsManager,
    ):
        """
        Initialize the FeatureCommand with dependencies.

        Args:
            feature_service: Service for managing feature flags
            slack_posting_handler: Handler for posting Slack messages
            slack_user_ops: Operations for Slack users
            secrets_manager: Manager for secrets (used for admin check)
        """
        super().__init__()
        self.feature_service = feature_service
        self.posting_handler = slack_posting_handler
        self.slack_user_ops = slack_user_ops
        self.secrets_manager = secrets_manager
        logger.info("FeatureCommand initialized")

    async def process_feature_params(
        self,
        params: FeatureCommandParams,
        user_id: str,
        incoming_channel: str,
        response_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process feature command params and execute the appropriate action.

        Args:
            params: Command parameters extracted by the parameter extractor
            user_id: ID of the user who issued the command
            incoming_channel: Channel ID where the command was issued
            response_url: Optional response URL for delayed responses

        Returns:
            Dict with status code and body
        """
        logger.info(f"Processing feature command with params: {params}")

        # Check if user is admin
        is_admin = await self._check_if_admin(user_id)
        if not is_admin:
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="You are not authorized to manage feature flags. This command is restricted to administrators.",
                response_url=response_url,
            )
            return {"statusCode": 200, "body": "Unauthorized"}

        # Process command based on action type
        feature_name = params.feature_name
        action = params.action

        # Handle access_management feature separately
        if feature_name == "access_management":
            return await self._handle_access_management(
                user_id, incoming_channel, action, params, response_url
            )

        if action == "enable":
            return await self._handle_enable_feature(
                user_id, incoming_channel, feature_name, params, response_url
            )
        elif action == "disable":
            return await self._handle_disable_feature(
                user_id, incoming_channel, feature_name, params, response_url
            )
        elif action == "list":
            return await self._handle_list_feature(
                user_id, incoming_channel, feature_name, response_url
            )
        elif action == "status":
            return await self._handle_feature_status(
                user_id, incoming_channel, feature_name, response_url
            )
        else:
            # Invalid action
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=(
                    "Invalid feature command action. Available actions:\n"
                    "- `/ketchup feature status_updater enable C1234567890` - Enable status updater for a channel\n"
                    "- `/ketchup feature status_updater disable C1234567890` - Disable status updater for a channel\n"
                    "- `/ketchup feature status_updater list` - List channels with status updater enabled\n"
                    "- `/ketchup feature status_updater status` - Show status updater feature status\n\n"
                    "- `/ketchup feature trust_endorsement enable C1234567890` - Enable trust endorsement for a channel\n"
                    "- `/ketchup feature trust_endorsement disable C1234567890` - Disable trust endorsement for a channel\n"
                    "- `/ketchup feature trust_endorsement list` - List channels with trust endorsement enabled\n"
                    "- `/ketchup feature trust_endorsement status` - Show trust endorsement feature status\n\n"
                    "- `/ketchup feature access_management grant @user` - Add user access\n"
                    "- `/ketchup feature access_management revoke @user` - Remove user access\n"
                    "- `/ketchup feature access_management list` - List authorized users\n"
                    "- `/ketchup feature access_management status` - Show current state"
                ),
                response_url=response_url,
            )
            return {"statusCode": 200, "body": "Invalid action"}

    async def _handle_enable_feature(
        self,
        user_id: str,
        channel_id: str,
        feature_name: str,
        params: FeatureCommandParams,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """
        Handle the enable feature action.

        Args:
            user_id: ID of the user who issued the command
            channel_id: Channel where the command was issued
            feature_name: Name of the feature to enable
            params: Full command parameters
            response_url: Optional response URL

        Returns:
            Dict with status code and body
        """
        # Handle based on feature type
        if feature_name in ["status_updater", "jira_reporter", "trust_endorsement"]:
            if not params.target_channel_id:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message="You must specify a channel to enable the feature for (e.g., `/ketchup feature status_updater enable C1234567890`).",
                    response_url=response_url,
                )
                return {"statusCode": 200, "body": "Missing target channel"}

            # Enable the feature for channel
            success = await self.feature_service.enable_feature_for_channel(
                params.target_channel_id, feature_name
            )

            if success:
                message = f"Successfully enabled {feature_name.upper()} feature for channel <#{params.target_channel_id}>"
            else:
                message = f"Failed to enable {feature_name.upper()} feature for channel. Please check the logs for details."

            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=channel_id,
                message=message,
                response_url=response_url,
            )

        else:  # User-based features
            if not params.target_user_id:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message="You must specify a user to enable the feature for.",
                    response_url=response_url,
                )
                return {"statusCode": 200, "body": "Missing target user"}

            # Get user display name for a nicer message
            user_names = await self.slack_user_ops.get_user_names(
                [params.target_user_id]
            )
            display_name = user_names.get(params.target_user_id, params.target_user_id)

            # Enable the feature
            success = await self.feature_service.enable_feature_for_user(
                params.target_user_id, feature_name
            )

            if success:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message=f"Successfully enabled {feature_name.upper()} feature for user {display_name}.",
                    response_url=response_url,
                )
            else:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message=f"Failed to enable {feature_name.upper()} feature for user {display_name}. Please check the logs for details.",
                    response_url=response_url,
                )

        return {"statusCode": 200, "body": "Feature enabled"}

    async def _handle_disable_feature(
        self,
        user_id: str,
        channel_id: str,
        feature_name: str,
        params: FeatureCommandParams,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """
        Handle the disable feature action.

        Args:
            user_id: ID of the user who issued the command
            channel_id: Channel where the command was issued
            feature_name: Name of the feature to disable
            params: Full command parameters
            response_url: Optional response URL

        Returns:
            Dict with status code and body
        """
        # Handle based on feature type
        if feature_name in ["status_updater", "jira_reporter", "trust_endorsement"]:
            if not params.target_channel_id:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message="You must specify a channel to disable the feature for (e.g., `/ketchup feature status_updater disable C1234567890`).",
                    response_url=response_url,
                )
                return {"statusCode": 200, "body": "Missing target channel"}

            # Disable the feature for channel
            success = await self.feature_service.disable_feature_for_channel(
                params.target_channel_id, feature_name
            )

            if success:
                message = f"Successfully disabled {feature_name.upper()} feature for channel <#{params.target_channel_id}>"
            else:
                message = f"Failed to disable {feature_name.upper()} feature for channel. Please check the logs for details."

            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=channel_id,
                message=message,
                response_url=response_url,
            )

        else:  # User-based features
            if not params.target_user_id:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message="You must specify a user to disable the feature for.",
                    response_url=response_url,
                )
                return {"statusCode": 200, "body": "Missing target user"}

            # Get user display name for a nicer message
            user_names = await self.slack_user_ops.get_user_names(
                [params.target_user_id]
            )
            display_name = user_names.get(params.target_user_id, params.target_user_id)

            # Disable the feature
            success = await self.feature_service.disable_feature_for_user(
                params.target_user_id, feature_name
            )

            if success:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message=f"Successfully disabled {feature_name.upper()} feature for user {display_name}.",
                    response_url=response_url,
                )
            else:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message=f"Failed to disable {feature_name.upper()} feature for user {display_name}. Please check the logs for details.",
                    response_url=response_url,
                )

        return {"statusCode": 200, "body": "Feature disabled"}

    async def _handle_list_feature(
        self,
        user_id: str,
        channel_id: str,
        feature_name: str,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """
        Handle the list feature action.

        Args:
            user_id: ID of the user who issued the command
            channel_id: Channel where the command was issued
            feature_name: Name of the feature to list
            response_url: Optional response URL

        Returns:
            Dict with status code and body
        """
        # Handle based on feature type
        if feature_name in ["status_updater", "jira_reporter", "trust_endorsement"]:
            # Get channels with feature enabled
            channels = await self.feature_service.get_channels_with_feature(
                feature_name
            )

            if not channels:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message=f"No channels have the {feature_name.upper()} feature enabled.",
                    response_url=response_url,
                )
                return {"statusCode": 200, "body": "No channels"}

            # Format the message with channel names
            channel_lines = []
            for channel in channels:
                ch_id = channel.get("channel_id")
                ch_name = channel.get("channel_name", "unknown")
                channel_lines.append(f"• <#{ch_id}|{ch_name}>")

            channel_list = "\n".join(channel_lines)

            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=channel_id,
                message=f"Channels with {feature_name.upper()} feature enabled:\n\n{channel_list}",
                response_url=response_url,
            )

            return {"statusCode": 200, "body": "Feature channels listed"}

        else:  # User-based features
            # Get users with feature enabled
            users = await self.feature_service.get_users_with_feature(feature_name)

            if not users:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message=f"No users have the {feature_name.upper()} feature enabled.",
                    response_url=response_url,
                )
                return {"statusCode": 200, "body": "No users"}

            # Format the message
            user_lines = []
            for user in users:
                u_id = user.get("user_id")
                real_name = user.get("real_name", "Unknown")
                user_lines.append(f"• <@{u_id}> ({real_name})")

            user_list = "\n".join(user_lines)

            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=channel_id,
                message=f"Users with {feature_name.upper()} feature enabled:\n\n{user_list}",
                response_url=response_url,
            )

            return {"statusCode": 200, "body": "Feature users listed"}

    async def _handle_feature_status(
        self,
        user_id: str,
        channel_id: str,
        feature_name: str,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """
        Handle the feature status action.

        Args:
            user_id: ID of the user who issued the command
            channel_id: Channel where the command was issued
            feature_name: Name of the feature to get status for
            response_url: Optional response URL

        Returns:
            Dict with status code and body
        """
        # Get feature status
        status = self.feature_service.get_feature_status(feature_name)

        # Format the message
        message = f"*{feature_name.upper()} Feature Status:*\n\n"
        message += f"• Feature enabled: {status['feature_enabled']}\n"
        message += f"• Global access: {status['global_access']}\n"
        message += "• Environment variables:\n"
        message += f"  - {status['env_var']}: {status['feature_enabled']}\n"
        message += f"  - {status['global_env_var']}: {status['global_access']}\n"

        # Get count based on feature type
        if feature_name in ["status_updater", "jira_reporter", "trust_endorsement"]:
            if feature_name == "status_updater" and status["global_access"]:
                # In global mode, individual channel flags are irrelevant
                message += "\n• Mode: Global (all channels processed)"
            else:
                channels = await self.feature_service.get_channels_with_feature(
                    feature_name
                )
                message += f"\n• Channels with feature enabled: {len(channels)}"
            if "channel_field" in status:
                message += f"\n• DynamoDB field: {status['channel_field']}"
        else:
            users = await self.feature_service.get_users_with_feature(feature_name)
            message += f"\n• Users with feature enabled: {len(users)}"

        # Add rollout stage info
        rollout_stage = (
            "Global Rollout"
            if status["global_access"]
            else ("Beta Testing" if status["feature_enabled"] else "Disabled")
        )
        message += f"\n• Rollout stage: {rollout_stage}"

        await self.posting_handler.post_message(
            user_id=user_id,
            channel_id=channel_id,
            message=message,
            response_url=response_url,
        )

        return {"statusCode": 200, "body": "Feature status"}

    async def _handle_access_management(
        self,
        user_id: str,
        incoming_channel: str,
        action: str,
        params: FeatureCommandParams,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """
        Handle access management actions (grant/revoke/list/status).

        Args:
            user_id: ID of the user who issued the command
            incoming_channel: Channel where the command was issued
            action: The action to perform (grant/revoke/list/status)
            params: Full command parameters
            response_url: Optional response URL

        Returns:
            Dict with status code and body
        """
        logger.info(f"Processing access_management action: {action}")

        if action == "grant":
            return await self._handle_grant_access(
                user_id, incoming_channel, params, response_url
            )
        elif action == "revoke":
            return await self._handle_revoke_access(
                user_id, incoming_channel, params, response_url
            )
        elif action == "list":
            return await self._handle_list_authorized_users(
                user_id, incoming_channel, response_url
            )
        elif action == "status":
            return await self._handle_access_management_status(
                user_id, incoming_channel, response_url
            )
        else:
            # Invalid action
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=(
                    "Invalid access management action. Available actions:\n"
                    "- `/ketchup feature access_management grant @user` - Add user access\n"
                    "- `/ketchup feature access_management revoke @user` - Remove user access\n"
                    "- `/ketchup feature access_management list` - List authorized users\n"
                    "- `/ketchup feature access_management status` - Show current state"
                ),
                response_url=response_url,
            )
            return {"statusCode": 200, "body": "Invalid action"}

    async def _handle_grant_access(
        self,
        user_id: str,
        incoming_channel: str,
        params: FeatureCommandParams,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """Handle granting access to a user."""
        if not params.target_user_id:
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="You must specify a user to grant access to. Example: `/ketchup feature access_management grant @user`",
                response_url=response_url,
            )
            return {"statusCode": 200, "body": "Missing target user"}

        try:
            # Get user display name
            user_names = await self.slack_user_ops.get_user_names(
                [params.target_user_id]
            )
            display_name = user_names.get(params.target_user_id, params.target_user_id)

            # Extract LDAP username from user profile (copy pattern from access_request_handler)
            ldap_username = None
            try:
                user_info = await self.slack_user_ops._fetch_user_info_internal(
                    params.target_user_id
                )
                if user_info:
                    user_email = user_info.get("profile", {}).get("email", "")
                    if user_email and "@adobe.com" in user_email:
                        ldap_username = user_email.split("@adobe.com")[0]
                        logger.info(
                            f"Extracted LDAP username '{ldap_username}' from email '{user_email}'"
                        )
            except Exception as e:
                logger.error(f"Error extracting LDAP username: {e}")

            # Add user to authorized list
            if ldap_username:
                added = await self.secrets_manager.add_authorized_user_with_ldap(
                    params.target_user_id, ldap_username
                )
                ldap_info = f" (ldap: {ldap_username})"
            else:
                added = await self.secrets_manager.add_authorized_user(
                    params.target_user_id
                )
                ldap_info = ""

            if added:
                # Send notification to ketchup_access channel
                await self._send_access_notification(
                    action="granted",
                    target_user_id=params.target_user_id,
                    display_name=display_name,
                    granted_by_id=user_id,
                    ldap_info=ldap_info,
                )

                # Send welcome DM to user (copy pattern from access_request_handler)
                await self._send_access_granted_dm(params.target_user_id)

                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=f"✅ Successfully granted access to {display_name}{ldap_info}",
                    response_url=response_url,
                )
            else:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=f"ℹ️ {display_name}{ldap_info} already has access",
                    response_url=response_url,
                )

            return {"statusCode": 200, "body": "Access granted"}

        except Exception as e:
            logger.error(f"Error granting access: {e}")
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="❌ Failed to grant access. Please check the logs for details.",
                response_url=response_url,
            )
            return {"statusCode": 500, "body": "Error granting access"}

    async def _handle_revoke_access(
        self,
        user_id: str,
        incoming_channel: str,
        params: FeatureCommandParams,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """Handle revoking access from a user."""
        if not params.target_user_id:
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="You must specify a user to revoke access from. Example: `/ketchup feature access_management revoke @user`",
                response_url=response_url,
            )
            return {"statusCode": 200, "body": "Missing target user"}

        try:
            # Get user display name
            user_names = await self.slack_user_ops.get_user_names(
                [params.target_user_id]
            )
            display_name = user_names.get(params.target_user_id, params.target_user_id)

            # Extract LDAP username from user profile (copy pattern from access_request_handler)
            ldap_username = None
            try:
                user_info = await self.slack_user_ops._fetch_user_info_internal(
                    params.target_user_id
                )
                if user_info:
                    user_email = user_info.get("profile", {}).get("email", "")
                    if user_email and "@adobe.com" in user_email:
                        ldap_username = user_email.split("@adobe.com")[0]
                        logger.info(
                            f"Extracted LDAP username '{ldap_username}' from email '{user_email}'"
                        )
            except Exception as e:
                logger.error(f"Error extracting LDAP username: {e}")

            # Remove user from authorized list
            if ldap_username:
                removed = await self.secrets_manager.remove_authorized_user_with_ldap(
                    params.target_user_id, ldap_username
                )
                ldap_info = f" (ldap: {ldap_username})"
            else:
                removed = await self.secrets_manager.remove_authorized_user(
                    params.target_user_id
                )
                ldap_info = ""

            if removed:
                # Send notification to ketchup_access channel
                await self._send_access_notification(
                    action="revoked",
                    target_user_id=params.target_user_id,
                    display_name=display_name,
                    granted_by_id=user_id,
                    ldap_info=ldap_info,
                )

                # Send revocation DM to user
                await self._send_access_revoked_dm(params.target_user_id)

                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=f"✅ Successfully revoked access from {display_name}{ldap_info}",
                    response_url=response_url,
                )
            else:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=f"ℹ️ {display_name}{ldap_info} didn't have access",
                    response_url=response_url,
                )

            return {"statusCode": 200, "body": "Access revoked"}

        except Exception as e:
            logger.error(f"Error revoking access: {e}")
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="❌ Failed to revoke access. Please check the logs for details.",
                response_url=response_url,
            )
            return {"statusCode": 500, "body": "Error revoking access"}

    async def _handle_list_authorized_users(
        self,
        user_id: str,
        incoming_channel: str,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """Handle listing authorized users."""
        try:
            # Get authorized users from SecretsManager
            authorized_users = (
                await self.secrets_manager.get_authorised_slack_user_ids()
            )

            if not authorized_users:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message="No authorized users found.",
                    response_url=response_url,
                )
                return {"statusCode": 200, "body": "No authorized users"}

            # Get user names for display
            user_names = await self.slack_user_ops.get_user_names(authorized_users)

            # Format the message
            user_lines = []
            for user_id_item in authorized_users:
                display_name = user_names.get(user_id_item, user_id_item)
                user_lines.append(f"• <@{user_id_item}> ({display_name})")

            user_list = "\n".join(user_lines)

            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=f"**Authorized Ketchup Users** ({len(authorized_users)} total):\n\n{user_list}",
                response_url=response_url,
            )

            return {"statusCode": 200, "body": "Authorized users listed"}

        except Exception as e:
            logger.error(f"Error listing authorized users: {e}")
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="❌ Failed to retrieve authorized users. Please check the logs for details.",
                response_url=response_url,
            )
            return {"statusCode": 500, "body": "Error listing users"}

    async def _handle_access_management_status(
        self,
        user_id: str,
        incoming_channel: str,
        response_url: Optional[str],
    ) -> Dict[str, Any]:
        """Handle access management status."""
        try:
            # Get counts from SecretsManager
            authorized_users = (
                await self.secrets_manager.get_authorised_slack_user_ids()
            )
            ldap_users = await self.secrets_manager.get_authorised_users_ldap_backup()

            # Format the message
            message = "**Access Management Status:**\n\n"
            message += f"• Authorized Slack users: {len(authorized_users)}\n"
            message += f"• LDAP backup entries: {len(ldap_users)}\n"
            message += "• Access verification: Dynamic (fresh from AWS)\n"
            message += "• Available actions: grant, revoke, list, status"

            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=message,
                response_url=response_url,
            )

            return {"statusCode": 200, "body": "Access management status"}

        except Exception as e:
            logger.error(f"Error getting access management status: {e}")
            await self.posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="❌ Failed to retrieve access management status. Please check the logs for details.",
                response_url=response_url,
            )
            return {"statusCode": 500, "body": "Error getting status"}

    async def _send_access_notification(
        self,
        action: str,
        target_user_id: str,
        display_name: str,
        granted_by_id: str,
        ldap_info: str = "",
    ):
        """Send notification to ketchup_access channel."""
        try:
            from packages.core.constants import ACCESS_REQUEST_CHANNEL

            # Get granter name
            granter_names = await self.slack_user_ops.get_user_names([granted_by_id])
            granter_name = granter_names.get(granted_by_id, granted_by_id)

            # Format message based on action
            if action == "granted":
                emoji = "✅"
                message = f"{emoji} *Access Granted*\n\n"
                message += (
                    f"• *User:* <@{target_user_id}> ({display_name}){ldap_info}\n"
                )
                message += f"• *Granted by:* <@{granted_by_id}> ({granter_name})\n"
                message += "• **Method:** Manual grant via `/ketchup feature access_management grant`\n"
                message += (
                    f"• *Time:* {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
                )
            else:  # revoked
                emoji = "❌"
                message = f"{emoji} *Access Revoked*\n\n"
                message += (
                    f"• *User:* <@{target_user_id}> ({display_name}){ldap_info}\n"
                )
                message += f"• *Revoked by:* <@{granted_by_id}> ({granter_name})\n"
                message += "• *Method:* Manual revoke via `/ketchup feature access_management revoke`\n"
                message += (
                    f"• *Time:* {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
                )

            await self.posting_handler.post_message(
                channel_id=ACCESS_REQUEST_CHANNEL, message=message
            )

        except Exception as e:
            logger.error(f"Error sending access notification: {e}")

    async def _send_access_granted_dm(self, target_user_id: str):
        """Send welcome DM to user (copy pattern from access_request_handler)."""
        try:
            from packages.slack.blockkits.handlers.access_request_blocks import (
                AccessRequestBlocks,
            )

            # Get blocks for approval DM
            blocks = AccessRequestBlocks.build_approval_dm(target_user_id)

            await self.posting_handler.post_message(
                user_id=target_user_id,
                message=":wave: Welcome to Ketchup 1.0!",
                blocks=blocks,
            )

        except Exception as e:
            logger.error(f"Error sending access granted DM: {e}")

    async def _send_access_revoked_dm(self, target_user_id: str):
        """Send revocation DM to user."""
        try:
            await self.posting_handler.post_message(
                user_id=target_user_id,
                message="❌ Your Ketchup access has been revoked.\n\nIf you have questions, please contact the team org-omeara-all@adobe.com.",
            )

        except Exception as e:
            logger.error(f"Error sending access revoked DM: {e}")

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
                import json

                admin_users = json.loads(admin_users)

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
