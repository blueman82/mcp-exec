"""
Slack Core Operations Registration Module

Registers core Slack channel operation services that handle fundamental Slack interactions:
- ChannelInfoOps for channel information retrieval
- ChannelMembershipOps for membership management
- SlackChannelArchiveOps for channel archiving operations
- SlackChannelMessageOps for message operations
- SlackChannelBotMembershipOps for bot membership management
- SlackChannelRestoreOps for channel restoration
- ChannelNameResolver for channel name resolution
- SlackUserOps for user operations
- BatchSizeManager for batch operation management

These services provide the core Slack functionality for channel and user management.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, List

from packages.core.logging import setup_logger
from packages.core.typed_di.service_spec import ServiceSpec, register_from_specs
from packages.core.typed_di.types import DependencySpec

# Core Slack operations imports
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_bot_membership_ops import (
    SlackChannelBotMembershipOps,
)
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_membership_ops import ChannelMembershipOps
from packages.slack.channel_operations.channel_msg_ops import (
    BatchSizeManager,
    SlackChannelMessageOps,
)
from packages.slack.channel_operations.channel_name_resolver import ChannelNameResolver
from packages.slack.channel_operations.channel_restore_ops import SlackChannelRestoreOps
from packages.slack.user_operations.user_ops import SlackUserOps

# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import required dependencies from core primitives
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore
from packages.secrets.manager import SecretsManager
from packages.slack.channel_operations.restore_state_manager import RestoreStateManager
from packages.slack.config.slack_config import SlackConfig
from packages.slack.messages.posting import SlackPostingHandler

from ..protocols import (
    BatchSizeManagerProtocol,
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    ChannelNameResolverProtocol,
    DynamoDBStoreProtocol,
    JIRADataExtractorProtocol,
    JoinNotificationOpsProtocol,
    OpenAIHandlerProtocol,
    RestoreStateManagerProtocol,
    SecretsManagerProtocol,
    SlackChannelArchiveOpsProtocol,
    SlackChannelBotMembershipOpsProtocol,
    SlackChannelMessageOpsProtocol,
    SlackChannelRestoreOpsProtocol,
    SlackConfigProtocol,
    SlackPostingHandlerProtocol,
    SlackUserOpsProtocol,
    UserJoinNotificationServiceProtocol,
    UserStoreProtocol,
)

logger = setup_logger(__name__)


# =============================================================================
# ServiceSpec Declarations (declarative registration - minimal boilerplate)
# =============================================================================


def _get_basic_channel_ops_specs() -> List[ServiceSpec]:
    """Return specs for basic channel operations."""
    return [
        ServiceSpec(
            protocol=ChannelInfoOpsProtocol,
            concrete=ChannelInfoOps,
            deps={
                "posting_handler": SlackPostingHandler,
                "slack_config": SlackConfig,
            },
        ),
        ServiceSpec(
            protocol=ChannelMembershipOpsProtocol,
            concrete=ChannelMembershipOps,
            deps={"slack_config": SlackConfig},
        ),
        ServiceSpec(
            protocol=SlackChannelArchiveOpsProtocol,
            concrete=SlackChannelArchiveOps,
            deps={
                "posting_handler": SlackPostingHandler,
                "secrets_manager": SecretsManager,
                "dynamodb_store": DynamoDBStore,
                "state_manager": RestoreStateManager,
                "slack_config": SlackConfig,
            },
        ),
    ]


def _get_advanced_channel_ops_specs() -> List[ServiceSpec]:
    """Return specs for advanced channel operations."""
    return [
        ServiceSpec(
            protocol=SlackChannelBotMembershipOpsProtocol,
            concrete=SlackChannelBotMembershipOps,
            deps={
                "secrets_manager": SecretsManager,
                "posting_handler": SlackPostingHandler,
                "slack_config": SlackConfig,
            },
        ),
        ServiceSpec(
            protocol=SlackChannelRestoreOpsProtocol,
            concrete=SlackChannelRestoreOps,
            deps={
                "posting_handler": SlackPostingHandlerProtocol,
                "archive_ops": SlackChannelArchiveOpsProtocol,
                "secrets_manager": SecretsManagerProtocol,
                "dynamodb_store": DynamoDBStoreProtocol,
                "restore_state_manager": RestoreStateManagerProtocol,
                "bot_membership_ops": SlackChannelBotMembershipOpsProtocol,
                "slack_config": SlackConfigProtocol,
            },
        ),
        ServiceSpec(
            protocol=SlackChannelMessageOpsProtocol,
            concrete=SlackChannelMessageOps,
            deps={
                "user_ops": SlackUserOps,
                "archive_ops": SlackChannelArchiveOps,
                "slack_config": SlackConfig,
            },
        ),
    ]


def _get_user_and_utility_specs() -> List[ServiceSpec]:
    """Return specs for user operations and utilities."""
    return [
        ServiceSpec(
            protocol=SlackUserOpsProtocol,
            concrete=SlackUserOps,
            deps={
                "user_store": UserStore,
                "slack_config": SlackConfig,
            },
        ),
        ServiceSpec(
            protocol=ChannelNameResolverProtocol,
            concrete=ChannelNameResolver,
            deps={"slack_config": SlackConfig},
        ),
        ServiceSpec(
            protocol=BatchSizeManagerProtocol,
            concrete=BatchSizeManager,
            deps={},
        ),
    ]


# =============================================================================
# Main Registration Entry Point
# =============================================================================


def register_slack_core(manager: "ServiceRegistrationManager") -> None:
    """
    Register core Slack channel operation services.

    These services handle fundamental Slack channel and user operations that are
    essential for all Slack-based functionality in the application.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical Slack service registration fails
    """
    logger.info("Registering Slack core operation services")

    # Register declarative specs
    register_from_specs(manager, _get_basic_channel_ops_specs(), "basic_channel_ops")
    register_from_specs(manager, _get_advanced_channel_ops_specs(), "advanced_channel_ops")
    register_from_specs(manager, _get_user_and_utility_specs(), "user_and_utility_ops")

    # Register services requiring custom factory logic
    _register_user_join_notification_service(manager)

    logger.info("Slack core operation services registered successfully (10 services)")


# =============================================================================
# Custom Factories (for services with non-standard initialization)
# =============================================================================


def _register_user_join_notification_service(manager: "ServiceRegistrationManager") -> None:
    """Register UserJoinNotificationService (has inline import + optional deps)."""

    async def create_user_join_notification_service(resolver) -> "UserJoinNotificationService":
        from packages.slack.services.user_join_notification_service import (
            UserJoinNotificationService,
        )

        logger.info("Creating UserJoinNotificationService instance via TypedDI")

        # Resolve required dependencies
        openai_handler = await resolver.aget(OpenAIHandlerProtocol)
        posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        channel_msg_ops = await resolver.aget(SlackChannelMessageOpsProtocol)

        # Optional dependencies
        jira_extractor = None
        try:
            jira_extractor = await resolver.aget(JIRADataExtractorProtocol)
        except Exception:
            pass

        user_store = None
        try:
            user_store = await resolver.aget(UserStoreProtocol)
        except Exception:
            pass

        join_notification_ops = None
        try:
            join_notification_ops = await resolver.aget(JoinNotificationOpsProtocol)
        except Exception:
            pass

        return UserJoinNotificationService(
            openai_handler=openai_handler,
            posting_handler=posting_handler,
            channel_info_ops=channel_info_ops,
            channel_msg_ops=channel_msg_ops,
            jira_extractor=jira_extractor,
            user_store=user_store,
            join_notification_ops=join_notification_ops,
        )

    # Import the concrete class for registration
    from packages.slack.services.user_join_notification_service import UserJoinNotificationService

    manager.register_protocol_with_concrete_alias(
        protocol_type=UserJoinNotificationServiceProtocol,
        concrete_type=UserJoinNotificationService,
        factory=create_user_join_notification_service,
        dependencies=[  # type: ignore[arg-type]
            DependencySpec(OpenAIHandlerProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(SlackChannelMessageOpsProtocol),
            DependencySpec(JoinNotificationOpsProtocol, optional=True),
        ],
        lifetime="singleton",
    )
