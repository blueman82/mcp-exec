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

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
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

# Import protocols from the protocols module to avoid circular dependencies
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

    # Register basic channel operations
    _register_basic_channel_ops(manager)

    # Register advanced channel operations
    _register_advanced_channel_ops(manager)

    # Register user and utility operations
    _register_user_and_utility_ops(manager)

    logger.info("Slack core operation services registered successfully")


def _register_basic_channel_ops(manager: "ServiceRegistrationManager") -> None:
    """Register basic channel operations: info, membership, and archiving."""

    # ChannelInfoOps with protocol
    async def create_channel_info_ops(resolver) -> ChannelInfoOps:
        """Factory function for ChannelInfoOps using TypedResolver."""
        logger.info("Creating ChannelInfoOps instance via TypedDI")
        posting_handler = await resolver.aget(SlackPostingHandler)
        slack_config = await resolver.aget(SlackConfig)
        return ChannelInfoOps(
            posting_handler=posting_handler,
            slack_config=slack_config,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelInfoOpsProtocol,
        concrete_type=ChannelInfoOps,
        factory=create_channel_info_ops,
        dependencies=[
            DependencySpec(SlackPostingHandler),
            DependencySpec(SlackConfig),
        ],
        lifetime="singleton",
    )

    # ChannelMembershipOps with protocol
    async def create_channel_membership_ops(resolver) -> ChannelMembershipOps:
        """Factory function for ChannelMembershipOps using TypedResolver."""
        logger.info("Creating ChannelMembershipOps instance via TypedDI")
        slack_config = await resolver.aget(SlackConfig)
        return ChannelMembershipOps(slack_config=slack_config)

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelMembershipOpsProtocol,
        concrete_type=ChannelMembershipOps,
        factory=create_channel_membership_ops,
        dependencies=[DependencySpec(SlackConfig)],
        lifetime="singleton",
    )

    # SlackChannelArchiveOps with protocol
    async def create_slack_channel_archive_ops(resolver) -> SlackChannelArchiveOps:
        """Factory function for SlackChannelArchiveOps using TypedResolver."""
        logger.info("Creating SlackChannelArchiveOps instance via TypedDI")
        posting_handler = await resolver.aget(SlackPostingHandler)
        secrets_manager = await resolver.aget(SecretsManager)
        dynamodb_store = await resolver.aget(DynamoDBStore)
        state_manager = await resolver.aget(RestoreStateManager)
        slack_config = await resolver.aget(SlackConfig)
        return SlackChannelArchiveOps(
            posting_handler=posting_handler,
            secrets_manager=secrets_manager,
            dynamodb_store=dynamodb_store,
            state_manager=state_manager,
            slack_config=slack_config,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackChannelArchiveOpsProtocol,
        concrete_type=SlackChannelArchiveOps,
        factory=create_slack_channel_archive_ops,
        dependencies=[
            DependencySpec(SlackPostingHandler),
            DependencySpec(SecretsManager),
            DependencySpec(DynamoDBStore),
            DependencySpec(RestoreStateManager),
            DependencySpec(SlackConfig),
        ],
        lifetime="singleton",
    )


def _register_advanced_channel_ops(manager: "ServiceRegistrationManager") -> None:
    """Register advanced channel operations: bot membership, restore, and messaging."""

    # SlackChannelBotMembershipOps with protocol
    async def create_slack_channel_bot_membership_ops(resolver) -> SlackChannelBotMembershipOps:
        """Factory function for SlackChannelBotMembershipOps using TypedResolver."""
        logger.info("Creating SlackChannelBotMembershipOps instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)
        posting_handler = await resolver.aget(SlackPostingHandler)
        slack_config = await resolver.aget(SlackConfig)
        return SlackChannelBotMembershipOps(
            secrets_manager=secrets_manager,
            posting_handler=posting_handler,
            slack_config=slack_config,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackChannelBotMembershipOpsProtocol,
        concrete_type=SlackChannelBotMembershipOps,
        factory=create_slack_channel_bot_membership_ops,
        dependencies=[
            DependencySpec(SecretsManager),
            DependencySpec(SlackPostingHandler),
            DependencySpec(SlackConfig),
        ],
        lifetime="singleton",
    )

    # SlackChannelRestoreOps with protocol
    async def create_slack_channel_restore_ops(resolver) -> SlackChannelRestoreOps:
        """Factory function for SlackChannelRestoreOps using TypedResolver."""
        logger.info("Creating SlackChannelRestoreOps instance via TypedDI")
        posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        archive_ops = await resolver.aget(SlackChannelArchiveOpsProtocol)
        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        dynamodb_store = await resolver.aget(DynamoDBStoreProtocol)
        restore_state_manager = await resolver.aget(RestoreStateManagerProtocol)
        bot_membership_ops = await resolver.aget(SlackChannelBotMembershipOpsProtocol)
        slack_config = await resolver.aget(SlackConfigProtocol)
        return SlackChannelRestoreOps(
            posting_handler=posting_handler,
            archive_ops=archive_ops,
            secrets_manager=secrets_manager,
            dynamodb_store=dynamodb_store,
            restore_state_manager=restore_state_manager,
            bot_membership_ops=bot_membership_ops,
            slack_config=slack_config,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackChannelRestoreOpsProtocol,
        concrete_type=SlackChannelRestoreOps,
        factory=create_slack_channel_restore_ops,
        dependencies=[
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(SlackChannelArchiveOpsProtocol),
            DependencySpec(SecretsManagerProtocol),
            DependencySpec(DynamoDBStoreProtocol),
            DependencySpec(RestoreStateManagerProtocol),
            DependencySpec(SlackChannelBotMembershipOpsProtocol),
            DependencySpec(SlackConfigProtocol),
        ],
        lifetime="singleton",
    )

    # SlackChannelMessageOps with protocol
    async def create_slack_channel_message_ops(resolver) -> SlackChannelMessageOps:
        """Factory function for SlackChannelMessageOps using TypedResolver."""
        logger.info("Creating SlackChannelMessageOps instance via TypedDI")
        slack_config = await resolver.aget(SlackConfig)
        user_ops = await resolver.aget(SlackUserOps)
        archive_ops = await resolver.aget(SlackChannelArchiveOps)
        return SlackChannelMessageOps(
            user_ops=user_ops, archive_ops=archive_ops, slack_config=slack_config
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackChannelMessageOpsProtocol,
        concrete_type=SlackChannelMessageOps,
        factory=create_slack_channel_message_ops,
        dependencies=[
            DependencySpec(SlackUserOps),
            DependencySpec(SlackChannelArchiveOps),
            DependencySpec(SlackConfig),
        ],
        lifetime="singleton",
    )


def _register_user_and_utility_ops(manager: "ServiceRegistrationManager") -> None:
    """Register user operations and utility services."""

    # SlackUserOps with protocol (required by other services)
    async def create_slack_user_ops(resolver) -> SlackUserOps:
        """Factory function for SlackUserOps using TypedResolver."""
        logger.info("Creating SlackUserOps instance via TypedDI")
        user_store = await resolver.aget(UserStore)
        slack_config = await resolver.aget(SlackConfig)
        return SlackUserOps(user_store=user_store, slack_config=slack_config)

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackUserOpsProtocol,
        concrete_type=SlackUserOps,
        factory=create_slack_user_ops,
        dependencies=[
            DependencySpec(UserStore),
            DependencySpec(SlackConfig),
        ],
        lifetime="singleton",
    )

    # ChannelNameResolver with protocol
    async def create_channel_name_resolver(resolver) -> ChannelNameResolver:
        """Factory function for ChannelNameResolver using TypedResolver."""
        logger.info("Creating ChannelNameResolver instance via TypedDI")
        slack_config = await resolver.aget(SlackConfig)
        return ChannelNameResolver(slack_config=slack_config)

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelNameResolverProtocol,
        concrete_type=ChannelNameResolver,
        factory=create_channel_name_resolver,
        dependencies=[DependencySpec(SlackConfig)],
        lifetime="singleton",
    )

    # BatchSizeManager with protocol
    async def create_batch_size_manager(resolver) -> BatchSizeManager:
        """Factory function for BatchSizeManager."""
        return BatchSizeManager()

    manager.register_protocol_with_concrete_alias(
        protocol_type=BatchSizeManagerProtocol,
        concrete_type=BatchSizeManager,
        factory=create_batch_size_manager,
        dependencies=[],
        lifetime="singleton",
    )

    # UserJoinNotificationService with protocol
    async def create_user_join_notification_service(resolver) -> "UserJoinNotificationService":
        """Factory function for UserJoinNotificationService using TypedResolver."""
        from packages.slack.services.user_join_notification_service import (
            UserJoinNotificationService,
        )

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
        dependencies=[
            DependencySpec(OpenAIHandlerProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(SlackChannelMessageOpsProtocol),
            DependencySpec(JoinNotificationOpsProtocol, optional=True),
        ],
        lifetime="singleton",
    )
