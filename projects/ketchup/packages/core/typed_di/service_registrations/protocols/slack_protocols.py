"""Slack Service Protocol Definitions.

This module contains protocol definitions for Slack-related services
including authentication, clients, channels, and user management.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SlackAuthProtocol(Protocol):
    """Protocol for SlackAuth operations."""

    pass


@runtime_checkable
class SlackAsyncClientProtocol(Protocol):
    """Protocol for SlackAsyncClient operations."""

    pass


@runtime_checkable
class SlackUserStoreProtocol(Protocol):
    """Protocol for SlackUserStore operations."""

    async def get_user_info(self, user_id: str) -> dict: ...
    async def clear_user_cache(self) -> None: ...
    async def get_users_display_name(self, user_id: str) -> str: ...
    def set_client(self, client) -> None: ...


@runtime_checkable
class ChannelInfoOpsProtocol(Protocol):
    """Protocol for ChannelInfoOps operations."""

    pass


@runtime_checkable
class ChannelMembershipOpsProtocol(Protocol):
    """Protocol for ChannelMembershipOps operations."""

    pass


@runtime_checkable
class SlackChannelArchiveOpsProtocol(Protocol):
    """Protocol for SlackChannelArchiveOps operations."""

    pass


@runtime_checkable
class SlackChannelMessageOpsProtocol(Protocol):
    """Protocol for SlackChannelMessageOps operations."""

    pass


@runtime_checkable
class SlackEventHandlerProtocol(Protocol):
    """Protocol for Slack event handling."""

    pass


@runtime_checkable
class ChannelEligibilityServiceProtocol(Protocol):
    """Protocol for channel eligibility checking."""

    async def is_channel_eligible(self, channel_id: str, user_id: str, response_url: str = None) -> tuple: ...
    async def handle_ineligible_channel(self, channel_id: str, inviter_id: str, reason: str) -> None: ...


@runtime_checkable
class ChannelPolicyServiceProtocol(Protocol):
    """Protocol for channel policy management and enforcement."""

    async def validate_channel_policy(self, channel_id: str, policy_name: str) -> bool: ...
    async def get_channel_policies(self, channel_id: str) -> list: ...
    async def apply_policy(self, channel_id: str, policy_name: str) -> bool: ...
    async def check_policy_compliance(self, channel_id: str) -> dict: ...


@runtime_checkable
class ChannelMetricsServiceProtocol(Protocol):
    """Protocol for channel metrics collection and analysis."""

    async def collect_channel_metrics(self, channel_id: str) -> dict: ...
    async def get_message_count(self, channel_id: str, period: str = "day") -> int: ...
    async def get_member_activity(self, channel_id: str) -> dict: ...
    async def generate_metrics_report(self, channel_id: str, period: str) -> dict: ...


@runtime_checkable
class ChannelAnalyticsServiceProtocol(Protocol):
    """Protocol for advanced channel analytics and insights."""

    async def generate_channel_insights(self, channel_id: str) -> dict: ...
    async def analyze_channel_health(self, channel_id: str) -> dict: ...
    async def get_engagement_trends(self, channel_id: str, period: str) -> dict: ...
    async def predict_channel_activity(self, channel_id: str) -> dict: ...


@runtime_checkable
class ChannelValidationServiceProtocol(Protocol):
    """Protocol for channel validation and integrity checks."""

    async def validate_channel_structure(self, channel_id: str) -> dict: ...
    async def check_channel_integrity(self, channel_id: str) -> bool: ...
    async def validate_channel_permissions(self, channel_id: str) -> dict: ...
    async def perform_health_check(self, channel_id: str) -> dict: ...


@runtime_checkable
class ChannelMetadataEditHandlerProtocol(Protocol):
    """Protocol for channel metadata edit handler operations."""

    pass


@runtime_checkable
class ChannelNameResolverProtocol(Protocol):
    """Protocol for channel name resolver operations."""

    pass


@runtime_checkable
class ChannelOperationsProtocol(Protocol):
    """Protocol for channel operations."""

    pass


@runtime_checkable
class SlackChannelBotMembershipOpsProtocol(Protocol):
    """Protocol for Slack channel bot membership operations."""

    pass


@runtime_checkable
class SlackChannelRestoreOpsProtocol(Protocol):
    """Protocol for Slack channel restore operations."""

    pass


@runtime_checkable
class SlackUserOpsProtocol(Protocol):
    """Protocol for Slack user operations."""

    pass


@runtime_checkable
class UserJoinNotificationServiceProtocol(Protocol):
    """Protocol for user join notification service operations."""

    async def send_join_notification(self, user_id: str, channel_id: str, user_profile: dict = None) -> bool: ...


@runtime_checkable
class ChannelNotificationServiceProtocol(Protocol):
    """Protocol for channel notification service operations."""

    async def send_channel_update(self, channel_id: str, update_type: str, message: str) -> bool: ...
    async def send_channel_alert(self, channel_id: str, alert_type: str, details: dict) -> bool: ...


@runtime_checkable
class StatusNotificationServiceProtocol(Protocol):
    """Protocol for status notification service operations."""

    async def send_status_update(self, user_id: str, status_data: dict) -> bool: ...
    async def broadcast_status_change(self, status_type: str, message: str) -> bool: ...


@runtime_checkable
class AlertNotificationServiceProtocol(Protocol):
    """Protocol for alert notification service operations."""

    async def send_critical_alert(self, recipients: list, alert_data: dict) -> bool: ...
    async def send_warning_alert(self, recipients: list, message: str) -> bool: ...


@runtime_checkable
class SystemNotificationServiceProtocol(Protocol):
    """Protocol for system notification service operations."""

    async def send_system_message(self, channel_id: str, message: str) -> bool: ...
    async def broadcast_maintenance_notice(self, message: str, scheduled_time: str) -> bool: ...


@runtime_checkable
class UserVerifierProtocol(Protocol):
    """Protocol for user verifier operations."""

    pass


@runtime_checkable
class ArchiveProcessorProtocol(Protocol):
    """Protocol for archive processor operations."""

    async def process_channel_archive(self, channel_id: str, dynamodb_store) -> None:
        """Process a channel archive event with database updates and cleanup."""
        ...

    async def validate_archive_eligibility(self, channel_id: str) -> tuple[bool, str]:
        """Check if a channel is eligible for archiving."""
        ...

    async def cleanup_archived_channel_data(self, channel_id: str) -> bool:
        """Clean up various data associated with an archived channel."""
        ...


@runtime_checkable
class CreationProcessorProtocol(Protocol):
    """Protocol for creation processor operations."""

    pass


@runtime_checkable
class JoinProcessorProtocol(Protocol):
    """Protocol for join processor operations."""

    pass


@runtime_checkable
class PayloadProcessorProtocol(Protocol):
    """Protocol for payload processor operations."""

    pass


@runtime_checkable
class UnarchiveProcessorProtocol(Protocol):
    """Protocol for unarchive processor operations."""

    pass


@runtime_checkable
class UserManagementServiceProtocol(Protocol):
    """Protocol for user management service operations."""

    async def create_user(self, user_data: dict) -> dict: ...
    async def update_user(self, user_id: str, user_data: dict) -> dict: ...
    async def delete_user(self, user_id: str) -> bool: ...
    async def get_user(self, user_id: str) -> dict: ...
    async def list_users(self, filters: dict = None) -> list: ...


@runtime_checkable
class UserPermissionServiceProtocol(Protocol):
    """Protocol for user permission management operations."""

    async def grant_permission(self, user_id: str, permission: str) -> bool: ...
    async def revoke_permission(self, user_id: str, permission: str) -> bool: ...
    async def check_permission(self, user_id: str, permission: str) -> bool: ...
    async def get_user_permissions(self, user_id: str) -> list: ...
    async def get_users_with_permission(self, permission: str) -> list: ...


@runtime_checkable
class UserActivityServiceProtocol(Protocol):
    """Protocol for user activity tracking operations."""

    async def log_activity(self, user_id: str, activity: dict) -> bool: ...
    async def get_user_activity(self, user_id: str, limit: int = 100) -> list: ...
    async def get_activity_summary(self, user_id: str, period: str) -> dict: ...
    async def get_active_users(self, period: str) -> list: ...


@runtime_checkable
class UserPreferenceServiceProtocol(Protocol):
    """Protocol for user preference management operations."""

    async def set_preference(self, user_id: str, key: str, value: str) -> bool: ...
    async def get_preference(self, user_id: str, key: str) -> str: ...
    async def get_all_preferences(self, user_id: str) -> dict: ...
    async def delete_preference(self, user_id: str, key: str) -> bool: ...


@runtime_checkable
class UserAnalyticsServiceProtocol(Protocol):
    """Protocol for user analytics operations."""

    async def generate_user_report(self, user_id: str, period: str) -> dict: ...
    async def get_user_metrics(self, user_id: str) -> dict: ...
    async def get_platform_analytics(self, period: str) -> dict: ...
    async def export_user_data(self, user_id: str) -> dict: ...


__all__ = [
    "SlackAuthProtocol",
    "SlackAsyncClientProtocol",
    "SlackUserStoreProtocol",
    "ChannelInfoOpsProtocol",
    "ChannelMembershipOpsProtocol",
    "SlackChannelArchiveOpsProtocol",
    "SlackChannelMessageOpsProtocol",
    "SlackEventHandlerProtocol",
    "ChannelEligibilityServiceProtocol",
    "ChannelPolicyServiceProtocol",
    "ChannelMetricsServiceProtocol",
    "ChannelAnalyticsServiceProtocol",
    "ChannelValidationServiceProtocol",
    "ChannelMetadataEditHandlerProtocol",
    "ChannelNameResolverProtocol",
    "ChannelOperationsProtocol",
    "SlackChannelBotMembershipOpsProtocol",
    "SlackChannelRestoreOpsProtocol",
    "SlackUserOpsProtocol",
    "UserJoinNotificationServiceProtocol",
    "ChannelNotificationServiceProtocol",
    "StatusNotificationServiceProtocol",
    "AlertNotificationServiceProtocol",
    "SystemNotificationServiceProtocol",
    "UserVerifierProtocol",
    "ArchiveProcessorProtocol",
    "CreationProcessorProtocol",
    "JoinProcessorProtocol",
    "PayloadProcessorProtocol",
    "UnarchiveProcessorProtocol",
    "UserManagementServiceProtocol",
    "UserPermissionServiceProtocol",
    "UserActivityServiceProtocol",
    "UserPreferenceServiceProtocol",
    "UserAnalyticsServiceProtocol",
]
