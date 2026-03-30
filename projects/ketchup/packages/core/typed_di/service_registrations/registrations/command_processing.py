"""
Command Processing Registration Module

Registers command handling services that process user commands and interactions:
- Core command handlers (AccessCommand, CommandRouter)
- Slack command services (SlackListCommand, SlackQueryHandler, etc.)
- Command feature services and routing infrastructure

These services handle user-initiated commands across various platforms.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Essential imports for command processing services
try:
    from packages.core.exports.html_generator import MetricsHTMLGenerator
    from packages.slack.command_processing.access_command import AccessCommand
    from packages.slack.command_processing.command_router import CommandRouter
    from packages.slack.command_processing.feature_command import FeatureCommand
    from packages.slack.command_processing.feature_service import FeatureService
    from packages.slack.command_processing.list_command import SlackListCommand
    from packages.slack.command_processing.metrics_command import MetricsCommand
    from packages.slack.command_processing.query_command import SlackQueryHandler
    from packages.slack.command_processing.status_report_command import SlackReports
    from packages.slack.interactive_elements.metrics_export_handler import MetricsExportHandler
    from packages.slack.services.metrics_data_collector import MetricsDataCollector
except ImportError:
    # Allow module to load even with missing imports for testing
    pass

# Protocol imports
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import MetricsDataCollectorProtocol directly from service_protocols
# (not yet exported in __init__.py)
from packages.core.typed_di.service_protocols import MetricsDataCollectorProtocol

from ..protocols import (
    AccessCommandProtocol,
    BaseCommandHandlerProtocol,
    BlockKitBuilderProtocol,
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    ChannelOperationsProtocol,
    CommandRouterProtocol,
    CommandTrackingOperationsProtocol,
    CSOPMStateTrackerProtocol,
    DynamoDBStoreProtocol,
    FeatureCommandProtocol,
    FeatureServiceProtocol,
    FeedbackReactionsHandlerProtocol,
    JoinNotificationOpsProtocol,
    ListCommandProtocol,
    OpenAIHandlerProtocol,
    QueryCommandProtocol,
    SecretsManagerProtocol,
    SlackArchiveCommandProtocol,
    SlackChannelArchiveOpsProtocol,
    SlackChannelMessageOpsProtocol,
    SlackChannelRestoreOpsProtocol,
    SlackConfigProtocol,
    SlackListCommandProtocol,
    SlackPostingHandlerProtocol,
    SlackQueryHandlerProtocol,
    SlackReportsProtocol,
    SlackUserOpsProtocol,
    StatusReportCommandProtocol,
    UserStoreProtocol,
    UserVerifierProtocol,
    VerifyCommandProtocol,
)

logger = setup_logger(__name__)


def register_command_processing(manager: "ServiceRegistrationManager") -> None:
    """
    Register command processing services for handling user commands and interactions.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical service registration fails
    """
    logger.info("Registering command processing services")

    # Register metrics services FIRST so MetricsCommand is available when CommandRouter is created
    _register_metrics_services(manager)
    _register_core_command_services(manager)
    _register_slack_command_services(manager)
    _register_feature_command_services(manager)

    logger.info("Command processing services registered successfully (17 services)")


def _register_core_command_services(manager: "ServiceRegistrationManager") -> None:
    """Register core command handling services."""
    _register_access_command(manager)
    _register_command_router(manager)


def _register_access_command(manager: "ServiceRegistrationManager") -> None:
    """Register AccessCommand service."""

    async def create_access_command(resolver) -> AccessCommand:
        """Factory function for AccessCommand using TypedResolver."""
        logger.info("Creating AccessCommand instance via TypedDI")
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        user_verifier = await resolver.aget(UserVerifierProtocol)
        return AccessCommand(
            slack_posting_handler=slack_posting_handler, user_verifier=user_verifier
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=AccessCommandProtocol,
        concrete_type=AccessCommand,
        factory=create_access_command,
        dependencies=[
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(UserVerifierProtocol),
        ],
        lifetime="singleton",
    )


def _register_command_router(manager: "ServiceRegistrationManager") -> None:
    """Register CommandRouter service with dependency injection."""

    async def create_command_router(resolver) -> CommandRouter:
        """Factory function for CommandRouter using TypedResolver."""
        logger.info("Creating CommandRouter instance via TypedDI")

        # Build command handlers dictionary mapping command types to handlers
        command_handlers = await _build_command_handlers_dict(resolver)

        # Resolve required dependencies
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        user_verifier = await resolver.aget(UserVerifierProtocol)
        user_store = await resolver.aget(UserStoreProtocol)

        # Optional dependency - command tracking operations
        command_tracking_ops = None
        try:
            command_tracking_ops = await resolver.aget(CommandTrackingOperationsProtocol)
        except Exception as e:
            logger.info("CommandTrackingOperations not available: %s", e)

        return CommandRouter(
            command_handlers=command_handlers,
            slack_posting_handler=slack_posting_handler,
            user_verifier=user_verifier,
            user_store=user_store,
            command_tracking_ops=command_tracking_ops,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=CommandRouterProtocol,
        concrete_type=CommandRouter,
        factory=create_command_router,
        dependencies=[
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(UserVerifierProtocol),
            DependencySpec(UserStoreProtocol),
            # Command handlers are optional dependencies resolved within factory
            DependencySpec(AccessCommandProtocol, optional=True),
            DependencySpec(SlackArchiveCommandProtocol, optional=True),
            DependencySpec(FeatureCommandProtocol, optional=True),
            DependencySpec(SlackListCommandProtocol, optional=True),
            DependencySpec(MetricsCommand, optional=True),
            DependencySpec(SlackQueryHandlerProtocol, optional=True),
            DependencySpec(SlackReportsProtocol, optional=True),
            DependencySpec(CommandTrackingOperationsProtocol, optional=True),
        ],
        lifetime="singleton",
    )


async def _build_command_handlers_dict(resolver) -> dict:
    """Build command handlers dictionary for CommandRouter."""
    command_handlers = {}

    # Populate with available command handlers
    try:
        command_handlers["access"] = await resolver.aget(AccessCommandProtocol)
    except Exception as e:
        logger.warning("Failed to resolve AccessCommand handler: %s", e)

    try:
        command_handlers["archive"] = await resolver.aget(SlackArchiveCommandProtocol)
    except Exception as e:
        logger.warning("Failed to resolve SlackArchiveCommand handler: %s", e)

    try:
        command_handlers["feature"] = await resolver.aget(FeatureCommandProtocol)
    except Exception as e:
        logger.warning("Failed to resolve FeatureCommand handler: %s", e)

    try:
        command_handlers["list"] = await resolver.aget(SlackListCommandProtocol)
    except Exception as e:
        logger.warning("Failed to resolve SlackListCommand handler: %s", e)

    try:
        command_handlers["metrics"] = await resolver.aget(MetricsCommand)
    except Exception as e:
        logger.warning("Failed to resolve MetricsCommand handler: %s", e)

    try:
        command_handlers["query"] = await resolver.aget(SlackQueryHandlerProtocol)
    except Exception as e:
        logger.warning("Failed to resolve SlackQueryHandler: %s", e)

    try:
        command_handlers["status"] = await resolver.aget(SlackReportsProtocol)
        command_handlers["report"] = await resolver.aget(SlackReportsProtocol)
    except Exception as e:
        logger.warning("Failed to resolve SlackReports handler: %s", e)

    return command_handlers


def _register_slack_command_services(manager: "ServiceRegistrationManager") -> None:
    """Register Slack-specific command services."""

    # SlackListCommand
    async def create_slack_list_command(resolver) -> SlackListCommand:
        """Factory function for SlackListCommand using TypedResolver."""
        logger.info("Creating SlackListCommand instance via TypedDI")

        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        channel_membership_ops = await resolver.aget(ChannelMembershipOpsProtocol)
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        dynamodb_store = await resolver.aget(DynamoDBStoreProtocol)
        block_kit_builder = await resolver.aget(BlockKitBuilderProtocol)
        user_store = await resolver.aget(UserStoreProtocol)

        return SlackListCommand(
            channel_info_ops=channel_info_ops,
            channel_membership_ops=channel_membership_ops,
            slack_posting_handler=slack_posting_handler,
            dynamodb_store=dynamodb_store,
            block_kit_builder=block_kit_builder,
            user_store=user_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackListCommandProtocol,
        concrete_type=SlackListCommand,
        factory=create_slack_list_command,
        dependencies=[
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(ChannelMembershipOpsProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(DynamoDBStoreProtocol),
            DependencySpec(BlockKitBuilderProtocol),
            DependencySpec(UserStoreProtocol),
        ],
        lifetime="singleton",
    )

    # SlackQueryHandler
    async def create_slack_query_handler(resolver) -> SlackQueryHandler:
        """Factory function for SlackQueryHandler using TypedResolver."""
        logger.info("Creating SlackQueryHandler instance via TypedDI")

        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        archive_ops = await resolver.aget(SlackChannelArchiveOpsProtocol)
        openai_handler = await resolver.aget(OpenAIHandlerProtocol)
        block_kit_builder = await resolver.aget(BlockKitBuilderProtocol)
        channel_message_ops = await resolver.aget(SlackChannelMessageOpsProtocol)
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        user_store = await resolver.aget(UserStoreProtocol)
        slack_config = await resolver.aget(SlackConfigProtocol)
        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        user_ops = await resolver.aget(SlackUserOpsProtocol)

        # Optional: Resolve channel_restore_ops for archived channel handling
        channel_restore_ops = None
        try:
            channel_restore_ops = await resolver.aget(SlackChannelRestoreOpsProtocol)
        except Exception as e:
            logger.info("SlackChannelRestoreOps not available for query handler: %s", e)

        feedback_reactions_handler = None
        try:
            feedback_reactions_handler = await resolver.aget(FeedbackReactionsHandlerProtocol)
        except Exception as e:
            logger.info("FeedbackReactionsHandler not available for SlackQueryHandler: %s", e)

        return SlackQueryHandler(
            channel_info_ops=channel_info_ops,
            archive_ops=archive_ops,
            openai_handler=openai_handler,
            block_kit_builder=block_kit_builder,
            channel_message_ops=channel_message_ops,
            slack_posting_handler=slack_posting_handler,
            user_store=user_store,
            slack_config=slack_config,
            secrets_manager=secrets_manager,
            user_ops=user_ops,
            channel_restore_ops=channel_restore_ops,
            feedback_reactions_handler=feedback_reactions_handler,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackQueryHandlerProtocol,
        concrete_type=SlackQueryHandler,
        factory=create_slack_query_handler,
        dependencies=[
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(SlackChannelArchiveOpsProtocol),
            DependencySpec(OpenAIHandlerProtocol),
            DependencySpec(BlockKitBuilderProtocol),
            DependencySpec(SlackChannelMessageOpsProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(UserStoreProtocol),
            DependencySpec(SlackConfigProtocol),
            DependencySpec(SecretsManagerProtocol),
            DependencySpec(SlackUserOpsProtocol),
        ],
        lifetime="singleton",
    )

    # SlackReports
    async def create_slack_reports(resolver) -> SlackReports:
        """Factory function for SlackReports using TypedResolver."""
        logger.info("Creating SlackReports instance via TypedDI")

        # Import dependencies for SlackReports

        # Resolve all required dependencies
        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        archive_ops = await resolver.aget(SlackChannelArchiveOpsProtocol)
        openai_handler = await resolver.aget(OpenAIHandlerProtocol)
        block_kit_builder = await resolver.aget(BlockKitBuilderProtocol)
        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        slack_config = await resolver.aget(SlackConfigProtocol)
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        user_store = await resolver.aget(UserStoreProtocol)
        dynamodb_store = await resolver.aget(DynamoDBStoreProtocol)

        # Optional dependencies
        channel_restore_ops = None
        try:
            channel_restore_ops = await resolver.aget(SlackChannelRestoreOpsProtocol)
        except Exception as e:
            logger.info("SlackChannelRestoreOps not available: %s", e)

        feedback_reactions_handler = None
        try:
            feedback_reactions_handler = await resolver.aget(FeedbackReactionsHandlerProtocol)
        except Exception as e:
            logger.info("FeedbackReactionsHandler not available for SlackReports: %s", e)

        return SlackReports(
            channel_info_ops=channel_info_ops,
            archive_ops=archive_ops,
            openai_handler=openai_handler,
            block_kit_builder=block_kit_builder,
            secrets_manager=secrets_manager,
            slack_config=slack_config,
            slack_posting_handler=slack_posting_handler,
            user_store=user_store,
            dynamodb_store=dynamodb_store,
            channel_restore_ops=channel_restore_ops,
            feedback_reactions_handler=feedback_reactions_handler,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackReportsProtocol,
        concrete_type=SlackReports,
        factory=create_slack_reports,
        dependencies=[
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(SlackChannelArchiveOpsProtocol),
            DependencySpec(OpenAIHandlerProtocol),
            DependencySpec(BlockKitBuilderProtocol),
            DependencySpec(SecretsManagerProtocol),
            DependencySpec(SlackConfigProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(UserStoreProtocol),
            DependencySpec(DynamoDBStoreProtocol),
        ],
        lifetime="singleton",
    )

def _register_feature_command_services(manager: "ServiceRegistrationManager") -> None:
    """Register feature command and base command services."""

    # FeatureService registration
    async def create_feature_service(resolver) -> "FeatureService":
        """Factory function for FeatureService using TypedResolver."""
        logger.info("Creating FeatureService instance via TypedDI")
        from packages.slack.command_processing.feature_service import FeatureService

        user_store = await resolver.aget(UserStoreProtocol)
        channel_operations = await resolver.aget(ChannelOperationsProtocol)
        return FeatureService(user_store=user_store, channel_operations=channel_operations)

    manager.register_protocol_with_concrete_alias(
        protocol_type=FeatureServiceProtocol,
        concrete_type=FeatureService,
        factory=create_feature_service,
        dependencies=[
            DependencySpec(UserStoreProtocol),
            DependencySpec(ChannelOperationsProtocol),
        ],
        lifetime="singleton",
    )

    # FeatureCommand registration (actual implementation, not delegation)
    async def create_feature_command(resolver) -> FeatureCommand:
        """Factory function for FeatureCommand using TypedResolver."""
        logger.info("Creating FeatureCommand instance via TypedDI")

        feature_service = await resolver.aget(FeatureServiceProtocol)
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        slack_user_ops = await resolver.aget(SlackUserOpsProtocol)
        secrets_manager = await resolver.aget(SecretsManagerProtocol)

        return FeatureCommand(
            feature_service=feature_service,
            slack_posting_handler=slack_posting_handler,
            slack_user_ops=slack_user_ops,
            secrets_manager=secrets_manager,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=FeatureCommandProtocol,
        concrete_type=FeatureCommand,
        factory=create_feature_command,
        dependencies=[
            DependencySpec(FeatureServiceProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(SlackUserOpsProtocol),
            DependencySpec(SecretsManagerProtocol),
        ],
        lifetime="singleton",
    )

    # ListCommandProtocol (generic interface) - delegate to existing SlackListCommandProtocol
    # Don't re-register concrete class to avoid duplicate registration
    async def create_list_command_from_slack(resolver) -> SlackListCommand:
        return await resolver.aget(SlackListCommandProtocol)

    # Register protocol only (no concrete alias since SlackListCommand is already registered)
    manager.registry.register(
        service_type=ListCommandProtocol,
        factory=create_list_command_from_slack,
        dependencies=[DependencySpec(SlackListCommandProtocol)],
        lifetime="singleton",
        lazy=True,
        essential=False,
    )

    # QueryCommandProtocol (generic interface) - delegate to existing SlackQueryHandlerProtocol
    async def create_query_command_from_slack(resolver) -> SlackQueryHandler:
        return await resolver.aget(SlackQueryHandlerProtocol)

    manager.registry.register(
        service_type=QueryCommandProtocol,
        factory=create_query_command_from_slack,
        dependencies=[DependencySpec(SlackQueryHandlerProtocol)],
        lifetime="singleton",
        lazy=True,
        essential=False,
    )

    # StatusReportCommandProtocol (generic interface) - delegate to existing SlackReportsProtocol
    async def create_status_report_command_from_slack(resolver) -> SlackReports:
        return await resolver.aget(SlackReportsProtocol)

    manager.registry.register(
        service_type=StatusReportCommandProtocol,
        factory=create_status_report_command_from_slack,
        dependencies=[DependencySpec(SlackReportsProtocol)],
        lifetime="singleton",
        lazy=True,
        essential=False,
    )

    # BaseCommandHandlerProtocol - delegate to existing CommandRouterProtocol
    async def create_base_command_handler_from_router(resolver) -> CommandRouter:
        return await resolver.aget(CommandRouterProtocol)

    manager.registry.register(
        service_type=BaseCommandHandlerProtocol,
        factory=create_base_command_handler_from_router,
        dependencies=[DependencySpec(CommandRouterProtocol)],
        lifetime="singleton",
        lazy=True,
        essential=False,
    )

    # VerifyCommandProtocol - delegate to existing AccessCommandProtocol
    async def create_verify_command_from_access(resolver) -> AccessCommand:
        return await resolver.aget(AccessCommandProtocol)

    manager.registry.register(
        service_type=VerifyCommandProtocol,
        factory=create_verify_command_from_access,
        dependencies=[DependencySpec(AccessCommandProtocol)],
        lifetime="singleton",
        lazy=True,
        essential=False,
    )


def _register_metrics_services(manager: "ServiceRegistrationManager") -> None:
    """Register metrics dashboard services."""

    # MetricsDataCollector
    async def create_metrics_data_collector(resolver) -> MetricsDataCollector:
        """Factory function for MetricsDataCollector using TypedResolver."""
        logger.info("Creating MetricsDataCollector instance via TypedDI")
        channel_ops = await resolver.aget(ChannelOperationsProtocol)
        join_notification_ops = await resolver.aget(JoinNotificationOpsProtocol)
        channel_membership_ops = await resolver.aget(ChannelMembershipOpsProtocol)
        csopm_state_tracker = await resolver.aget(CSOPMStateTrackerProtocol)
        return MetricsDataCollector(
            channel_ops=channel_ops,
            join_notification_ops=join_notification_ops,
            channel_membership_ops=channel_membership_ops,
            csopm_state_tracker=csopm_state_tracker,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=MetricsDataCollectorProtocol,
        concrete_type=MetricsDataCollector,
        factory=create_metrics_data_collector,
        dependencies=[
            DependencySpec(ChannelOperationsProtocol),
            DependencySpec(JoinNotificationOpsProtocol),
            DependencySpec(ChannelMembershipOpsProtocol),
            DependencySpec(CSOPMStateTrackerProtocol),
        ],
        lifetime="singleton",
    )

    # MetricsHTMLGenerator (no dependencies)
    async def create_metrics_html_generator(resolver) -> MetricsHTMLGenerator:
        """Factory function for MetricsHTMLGenerator using TypedResolver."""
        logger.info("Creating MetricsHTMLGenerator instance via TypedDI")
        return MetricsHTMLGenerator()

    manager.registry.register(
        service_type=MetricsHTMLGenerator,
        factory=create_metrics_html_generator,
        dependencies=[],
        lifetime="singleton",
    )

    # MetricsExportHandler
    async def create_metrics_export_handler(resolver) -> MetricsExportHandler:
        """Factory function for MetricsExportHandler using TypedResolver."""
        logger.info("Creating MetricsExportHandler instance via TypedDI")
        metrics_data_collector = await resolver.aget(MetricsDataCollectorProtocol)
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        html_generator = await resolver.aget(MetricsHTMLGenerator)
        return MetricsExportHandler(
            metrics_data_collector=metrics_data_collector,
            slack_posting_handler=slack_posting_handler,
            html_generator=html_generator,
        )

    manager.registry.register(
        service_type=MetricsExportHandler,
        factory=create_metrics_export_handler,
        dependencies=[
            DependencySpec(MetricsDataCollectorProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(MetricsHTMLGenerator),
        ],
        lifetime="singleton",
    )

    # MetricsCommand
    async def create_metrics_command(resolver) -> MetricsCommand:
        """Factory function for MetricsCommand using TypedResolver."""
        logger.info("Creating MetricsCommand instance via TypedDI")
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        metrics_export_handler = await resolver.aget(MetricsExportHandler)
        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        slack_user_ops = await resolver.aget(SlackUserOpsProtocol)
        return MetricsCommand(
            slack_posting_handler=slack_posting_handler,
            metrics_export_handler=metrics_export_handler,
            secrets_manager=secrets_manager,
            slack_user_ops=slack_user_ops,
        )

    manager.registry.register(
        service_type=MetricsCommand,
        factory=create_metrics_command,
        dependencies=[
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(MetricsExportHandler),
            DependencySpec(SecretsManagerProtocol),
            DependencySpec(SlackUserOpsProtocol),
        ],
        lifetime="singleton",
    )
