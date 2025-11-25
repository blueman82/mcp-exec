"""
feature_service.py

Service for managing feature flags for users with database-backed persistence.
"""

from typing import Dict, List

from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger
from packages.db.operations.channel_operations import ChannelOperations
from packages.db.user_store import UserStore

logger = setup_logger(__name__)


class FeatureService:
    """
    Service for managing feature flags and checking user access to features.

    This service handles the user-level feature flag management and provides
    methods to determine if specific features should be enabled for users.
    """

    def __init__(self, user_store: UserStore, channel_operations: ChannelOperations):
        """
        Initialize the FeatureService with dependencies.

        Args:
            user_store: Store for user data including feature flags
            channel_operations: Operations for channel details from DB
        """
        self.user_store = user_store
        self.channel_operations = channel_operations
        logger.info("FeatureService initialized")

    async def is_legacy_message_analysis_enabled(self) -> bool:
        """
        Check if the legacy message analysis feature is enabled.

        Returns:
            True if legacy message analysis is enabled, False otherwise
        """
        return FeatureFlags.is_message_analysis_enabled()

    async def enable_feature_for_user(self, user_id: str, feature_name: str) -> bool:
        """
        Enable a feature for a specific user.

        Args:
            user_id: Slack user ID
            feature_name: Name of the feature to enable

        Returns:
            True if successful, False otherwise
        """
        return await self.user_store.set_user_feature(
            user_id, f"{feature_name}_enabled", True
        )

    async def disable_feature_for_user(self, user_id: str, feature_name: str) -> bool:
        """
        Disable a feature for a specific user.

        Args:
            user_id: Slack user ID
            feature_name: Name of the feature to disable

        Returns:
            True if successful, False otherwise
        """
        return await self.user_store.set_user_feature(
            user_id, f"{feature_name}_enabled", False
        )

    async def get_users_with_feature(self, feature_name: str) -> List[Dict]:
        """
        Get all users who have a specific feature enabled.

        Args:
            feature_name: Name of the feature to check

        Returns:
            List of user dictionaries with the feature enabled
        """
        return await self.user_store.get_users_with_feature(
            f"{feature_name}_enabled", True
        )

    async def enable_feature_for_channel(
        self, channel_id: str, feature_name: str
    ) -> bool:
        """
        Enable a feature for a specific channel.

        Args:
            channel_id: Slack channel ID
            feature_name: Name of the feature to enable

        Returns:
            True if successful, False otherwise
        """
        return await self.user_store.set_channel_feature(
            channel_id, f"{feature_name}_enabled", True
        )

    async def disable_feature_for_channel(
        self, channel_id: str, feature_name: str
    ) -> bool:
        """
        Disable a feature for a specific channel.

        Args:
            channel_id: Slack channel ID
            feature_name: Name of the feature to disable

        Returns:
            True if successful, False otherwise
        """
        return await self.user_store.set_channel_feature(
            channel_id, f"{feature_name}_enabled", False
        )

    async def get_channels_with_feature(
        self, feature_name: str
    ) -> List[Dict[str, str]]:
        """
        Get all channels with a feature enabled.

        Args:
            feature_name: Name of the feature to check

        Returns:
            List of dictionaries with channel_id and channel_name
        """
        channel_ids = await self.user_store.get_channels_with_feature(
            f"{feature_name}_enabled", True
        )

        # Fetch channel names from database
        channels_with_names = []
        for channel_id in channel_ids:
            try:
                # Use existing channel operations to get details from DB
                channel_details = await self.channel_operations.get_channel_details(
                    channel_id
                )
                if channel_details:
                    channels_with_names.append(
                        {
                            "channel_id": channel_id,
                            "channel_name": channel_details.get(
                                "channel_name", "unknown"
                            ),
                        }
                    )
                else:
                    # Channel not in DB (shouldn't happen for active channels)
                    channels_with_names.append(
                        {"channel_id": channel_id, "channel_name": "unknown"}
                    )
            except Exception as e:
                logger.warning(f"Could not fetch details for channel {channel_id}: {e}")
                channels_with_names.append(
                    {"channel_id": channel_id, "channel_name": "unknown"}
                )

        return channels_with_names

    async def is_status_updater_enabled_for_channel(self, channel_id: str) -> bool:
        """
        Check if status updater is enabled for a channel.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if status updater is enabled for the channel, False otherwise
        """
        # First check global flag
        if FeatureFlags.is_status_updater_global():
            return True

        # Then check channel-specific flag
        enabled = await self.user_store.get_channel_feature(
            channel_id, "status_updater_enabled"
        )
        return enabled is True

    async def is_jira_reporter_enabled_for_channel(self, channel_id: str) -> bool:
        """
        Check if JIRA reporter is enabled for a channel.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if JIRA reporter is enabled for the channel, False otherwise
        """
        # First check global flag
        if FeatureFlags.is_jira_reporter_global():
            return True

        # Then check channel-specific flag
        enabled = await self.user_store.get_channel_feature(
            channel_id, "jira_reporter_enabled"
        )
        return enabled is True

    async def is_trust_endorsement_enabled_for_channel(self, channel_id: str) -> bool:
        """
        Check if trust endorsement is enabled for a channel.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if trust endorsement is enabled for the channel, False otherwise
        """
        # First check global flag
        if FeatureFlags.is_trust_endorsement_global():
            return True

        # Then check channel-specific flag
        enabled = await self.user_store.get_channel_feature(
            channel_id, "trust_endorsement_enabled"
        )
        return enabled is True

    async def is_user_join_notifications_enabled_for_channel(
        self, channel_id: str
    ) -> bool:
        """
        Check if user join notifications is enabled for a channel.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if user join notifications is enabled for the channel, False otherwise
        """
        # First check if master feature is disabled
        if not FeatureFlags.is_user_join_notifications_enabled():
            return False

        # Then check global flag
        if FeatureFlags.is_user_join_notifications_global():
            return True

        # Finally check channel-specific flag
        enabled = await self.user_store.get_channel_feature(
            channel_id, "user_join_notifications_enabled"
        )
        return enabled is True

    async def is_user_join_notifications_enabled_for_user(self, user_id: str) -> bool:
        """
        Check if user join notifications is enabled for a user.

        Args:
            user_id: Slack user ID

        Returns:
            True if user join notifications is enabled for the user, False otherwise
        """
        # First check if master feature is disabled
        if not FeatureFlags.is_user_join_notifications_enabled():
            return False

        # Then check global flag
        if FeatureFlags.is_user_join_notifications_global():
            return True

        # Finally check user-specific flag
        try:
            enabled = await self.user_store.get_user_feature(
                user_id, "user_join_notifications_enabled"
            )
            return enabled is True
        except Exception as e:
            logger.error(f"Error checking user join notifications for user {user_id}: {e}")
            return False

    def get_feature_status(self, feature_name: str = "status_updater") -> Dict:
        """
        Get the current status of a feature.

        Args:
            feature_name: Name of the feature to check (default: "status_updater")

        Returns:
            Dictionary containing feature status information
        """
        if feature_name == "status_updater":
            return {
                "feature_enabled": FeatureFlags.is_status_updater_enabled(),
                "global_access": FeatureFlags.is_status_updater_global(),
                "env_var": "KETCHUP_STATUS_UPDATER_FEATURE",
                "global_env_var": "KETCHUP_STATUS_UPDATER_GLOBAL",
                "channel_field": "features.status_updater_enabled",
            }
        elif feature_name == "jira_reporter":
            return {
                "feature_enabled": FeatureFlags.is_jira_reporter_enabled(),
                "global_access": FeatureFlags.is_jira_reporter_global(),
                "env_var": "KETCHUP_JIRA_REPORTER_FEATURE",
                "global_env_var": "KETCHUP_JIRA_REPORTER_GLOBAL",
                "channel_field": "features.jira_reporter_enabled",
            }
        elif feature_name == "trust_endorsement":
            return {
                "feature_enabled": FeatureFlags.is_trust_endorsement_enabled(),
                "global_access": FeatureFlags.is_trust_endorsement_global(),
                "env_var": "KETCHUP_TRUST_ENDORSEMENT_FEATURE",
                "global_env_var": "KETCHUP_TRUST_ENDORSEMENT_GLOBAL",
                "channel_field": "features.trust_endorsement_enabled",
            }
        elif feature_name == "user_join_notifications":
            return {
                "feature_enabled": FeatureFlags.is_user_join_notifications_enabled(),
                "global_access": FeatureFlags.is_user_join_notifications_global(),
                "env_var": "KETCHUP_USER_JOIN_NOTIFICATIONS_FEATURE",
                "global_env_var": "KETCHUP_USER_JOIN_NOTIFICATIONS_GLOBAL",
                "user_field": "features.user_join_notifications_enabled",
            }

        # For future features, add additional cases here
        return {
            "feature_enabled": False,
            "global_access": False,
            "error": f"Unknown feature: {feature_name}",
        }
