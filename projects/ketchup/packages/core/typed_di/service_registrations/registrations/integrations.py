"""
Integrations Registration Module

Registers third-party integration services:
- JIRA integration services (Cache, Data Extractor, MCP clients)
- MCP (Model Context Protocol) services and async clients
- External API integrations and rate limiting
- IMS token management
- Command tracking and usage export operations
- Trust endorsement and home tab handlers
- CSV generation and webhook processing services

These services provide connectivity to external systems and APIs.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec
from packages.db.config.dynamodb_config import DynamoDBConfig
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.dynamodb_store import DynamoDBStore

# Integration service imports (with try/except for optional dependencies)
from packages.db.operations.command_tracking_operations import (
    CommandTrackingOperations,
)
from packages.db.user_store import UserStore
from packages.secrets.manager import SecretsManager
from packages.slack.core.slack_async_client import SlackAsyncClient
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import protocols from the protocols module to avoid circular dependencies
from ..protocols import (
    ChannelOperationsProtocol,
    CommandTrackingOperationsProtocol,
    CommandUsageCSVGeneratorProtocol,
    FlagReviewHandlerProtocol,
    HomeTabHandlerProtocol,
    IMSTokenManagerProtocol,
    JIRACacheProtocol,
    JIRADataExtractorProtocol,
    MCPAsyncClientProtocol,
    MCPClientProtocol,
    MCPConfigProtocol,
    TrustEndorsementHandlerProtocol,
    UsageExportHandlerProtocol,
    iPaaSRateLimiterProtocol,
)

# Set up logger
logger = setup_logger(__name__)


def register_integrations(manager: "ServiceRegistrationManager") -> None:
    """
    Register integration services.

    Provides connectivity to external systems including JIRA,
    MCP services, token management, command tracking, usage export,
    trust endorsement, and CSV generation capabilities.

    Args:
        manager: ServiceRegistrationManager instance
    """
    logger.info("Starting Integration Services registration")

    # CommandTrackingOperations with protocol
    try:

        async def create_command_tracking_operations(resolver) -> CommandTrackingOperations:
            """Factory function for CommandTrackingOperations using TypedResolver."""
            logger.info("Creating CommandTrackingOperations instance via TypedDI")
            async_client = await resolver.aget(DynamoDBAsyncClient)
            return CommandTrackingOperations(dynamodb_client=async_client)

        manager.register_protocol_with_concrete_alias(
            protocol_type=CommandTrackingOperationsProtocol,
            concrete_type=CommandTrackingOperations,
            factory=create_command_tracking_operations,
            dependencies=[DependencySpec(DynamoDBAsyncClient)],
            lifetime="singleton",
        )
        logger.info("CommandTrackingOperations registered successfully")
    except ImportError as e:
        logger.warning(f"CommandTrackingOperations not available: {e}")

    # ChannelOperations with protocol
    try:
        from packages.db.operations.channel_operations import ChannelOperations

        async def create_channel_operations(resolver) -> ChannelOperations:
            """Factory function for ChannelOperations using TypedResolver."""
            logger.info("Creating ChannelOperations instance via TypedDI")
            async_client = await resolver.aget(DynamoDBAsyncClient)
            config = await resolver.aget(DynamoDBConfig)
            table_name = config.get_table_name()
            return ChannelOperations(client=async_client, table_name=table_name)

        manager.register_protocol_with_concrete_alias(
            protocol_type=ChannelOperationsProtocol,
            concrete_type=ChannelOperations,
            factory=create_channel_operations,
            dependencies=[
                DependencySpec(DynamoDBAsyncClient),
                DependencySpec(DynamoDBConfig),
            ],
            lifetime="singleton",
        )
        logger.info("ChannelOperations registered successfully")
    except ImportError as e:
        logger.warning(f"ChannelOperations not available: {e}")

    # IMSTokenManager with protocol (flagged async migration)
    try:
        from packages.core.config.mcp_feature_flags import MCPFeatureFlags
        from packages.integrations.async_ims_token_manager import AsyncIMSTokenManager
        from packages.integrations.ims_token_manager import IMSTokenManager

        use_async_ims = MCPFeatureFlags.use_async_clients()
        ims_token_manager_cls = AsyncIMSTokenManager if use_async_ims else IMSTokenManager

        async def create_ims_token_manager(resolver):
            """Factory function selecting legacy vs async IMS token manager."""

            secrets_manager = await resolver.aget(SecretsManager)
            logger.info(
                "Creating %s via TypedDI",
                ims_token_manager_cls.__name__,
            )
            return ims_token_manager_cls(secrets_manager=secrets_manager)

        manager.register_protocol_with_concrete_alias(
            protocol_type=IMSTokenManagerProtocol,
            concrete_type=ims_token_manager_cls,
            factory=create_ims_token_manager,
            dependencies=[DependencySpec(SecretsManager)],
            lifetime="singleton",
        )
        logger.info("IMSTokenManager registered successfully (async flag=%s)", use_async_ims)
    except ImportError as e:
        logger.warning(f"IMSTokenManager not available: {e}")

    # JIRA and MCP services
    try:
        from packages.core.config.mcp_feature_flags import MCPFeatureFlags
        from packages.integrations.async_mcp_client import AsyncMCPClient
        from packages.integrations.jira_cache import JIRACache
        from packages.integrations.jira_data_extractor import JIRADataExtractor
        from packages.integrations.mcp_async_client import MCPAsyncClient, MCPConfig
        from packages.integrations.mcp_client import MCPClient, iPaaSRateLimiter

        use_async_mcp = MCPFeatureFlags.use_async_clients()
        mcp_client_cls = AsyncMCPClient if use_async_mcp else MCPClient
        # Reuse IMS class decision if already computed, otherwise fallback.
        try:
            ims_token_manager_cls  # noqa: B018 - check existence in scope
        except NameError:  # pragma: no cover - safeguard when previous block failed
            ims_token_manager_cls = AsyncIMSTokenManager if use_async_mcp else IMSTokenManager

        # JIRACache
        async def create_jira_cache(resolver) -> JIRACache:
            """Factory function for JIRACache using TypedResolver."""
            logger.info("Creating JIRACache instance via TypedDI")
            return JIRACache()

        manager.register_protocol_with_concrete_alias(
            protocol_type=JIRACacheProtocol,
            concrete_type=JIRACache,
            factory=create_jira_cache,
            dependencies=[],
            lifetime="singleton",
        )

        # JIRADataExtractor
        async def create_jira_data_extractor(resolver) -> JIRADataExtractor:
            """Factory function for JIRADataExtractor using TypedResolver."""
            logger.info("Creating JIRADataExtractor instance via TypedDI")
            from packages.db.dynamodb_store import DynamoDBStore

            mcp_client = await resolver.aget(MCPAsyncClientProtocol)
            dynamodb_store = await resolver.aget(DynamoDBStore)
            jira_cache = await resolver.aget(JIRACache)
            return JIRADataExtractor(
                mcp_client=mcp_client, dynamodb_store=dynamodb_store, cache=jira_cache
            )

        # Use MCPAsyncClientProtocol for JIRADataExtractor since that's what the constructor expects
        manager.register_protocol_with_concrete_alias(
            protocol_type=JIRADataExtractorProtocol,
            concrete_type=JIRADataExtractor,
            factory=create_jira_data_extractor,
            dependencies=[
                DependencySpec(MCPAsyncClientProtocol),
                DependencySpec(DynamoDBStore),
                DependencySpec(JIRACache),
            ],
            lifetime="singleton",
        )

        # MCPConfig
        async def create_mcp_config(resolver) -> MCPConfig:
            """Factory function for MCPConfig using TypedResolver."""
            logger.info("Creating MCPConfig instance via TypedDI")
            token_manager = await resolver.aget(ims_token_manager_cls)
            return MCPConfig(base_url="http://mcp-jira:8081", token_manager=token_manager)

        manager.register_protocol_with_concrete_alias(
            protocol_type=MCPConfigProtocol,
            concrete_type=MCPConfig,
            factory=create_mcp_config,
            dependencies=[DependencySpec(ims_token_manager_cls)],
            lifetime="singleton",
        )

        # Always register MCPAsyncClient when available, needed for JIRADataExtractor
        if MCPAsyncClient:

            async def create_mcp_async_client(resolver):
                """Factory function for MCPAsyncClient using TypedResolver."""
                logger.info("Creating MCPAsyncClient instance via TypedDI")
                mcp_config = await resolver.aget(MCPConfig)
                return MCPAsyncClient(mcp_config=mcp_config)

            manager.register_protocol_with_concrete_alias(
                protocol_type=MCPAsyncClientProtocol,
                concrete_type=MCPAsyncClient,
                factory=create_mcp_async_client,
                dependencies=[DependencySpec(MCPConfig)],
                lifetime="singleton",
            )

        # iPaaSRateLimiter
        async def create_ipaas_rate_limiter(resolver) -> iPaaSRateLimiter:
            """Factory function for iPaaSRateLimiter using TypedResolver."""
            logger.info("Creating iPaaSRateLimiter instance via TypedDI")
            return iPaaSRateLimiter()

        manager.register_protocol_with_concrete_alias(
            protocol_type=iPaaSRateLimiterProtocol,
            concrete_type=iPaaSRateLimiter,
            factory=create_ipaas_rate_limiter,
            dependencies=[],
            lifetime="singleton",
        )

        # MCPClient
        async def create_mcp_client(resolver):
            """Factory selecting between legacy and async MCP implementations."""

            logger.info(
                "Creating %s instance via TypedDI",
                mcp_client_cls.__name__,
            )

            if mcp_client_cls.__name__ == "AsyncMCPClient":
                # AsyncMCPClient takes base_url and token_manager
                token_manager = await resolver.aget(ims_token_manager_cls)
                return mcp_client_cls(base_url="http://mcp-jira:8081", token_manager=token_manager)
            else:
                # Legacy MCPClient takes token_manager parameter
                token_manager = await resolver.aget(ims_token_manager_cls)
                return mcp_client_cls(token_manager=token_manager)

        manager.register_protocol_with_concrete_alias(
            protocol_type=MCPClientProtocol,
            concrete_type=mcp_client_cls,
            factory=create_mcp_client,
            dependencies=[
                DependencySpec(ims_token_manager_cls),
                DependencySpec(MCPConfig),
            ],
            lifetime="singleton",
        )

        logger.info(
            "JIRA and MCP services registered successfully (async flag=%s)",
            use_async_mcp,
        )
    except ImportError as e:
        logger.warning(f"JIRA/MCP services not available: {e}")

    # CommandUsageCSVGenerator with protocol
    try:
        from packages.core.exports.csv_generator import CommandUsageCSVGenerator

        async def create_command_usage_csv_generator(resolver) -> CommandUsageCSVGenerator:
            """Factory function for CommandUsageCSVGenerator using TypedResolver."""
            logger.info("Creating CommandUsageCSVGenerator instance via TypedDI")
            return CommandUsageCSVGenerator()

        manager.register_protocol_with_concrete_alias(
            protocol_type=CommandUsageCSVGeneratorProtocol,
            concrete_type=CommandUsageCSVGenerator,
            factory=create_command_usage_csv_generator,
            dependencies=[],
            lifetime="singleton",
        )
        logger.info("CommandUsageCSVGenerator registered successfully")
    except ImportError as e:
        logger.warning(f"CommandUsageCSVGenerator not available: {e}")

    # TrustEndorsementHandler with protocol
    try:
        from packages.slack.interactive_elements.trust_endorsement_handler import (
            TrustEndorsementHandler,
        )

        async def create_trust_endorsement_handler(resolver) -> TrustEndorsementHandler:
            """Factory function for TrustEndorsementHandler using TypedResolver."""
            logger.info("Creating TrustEndorsementHandler instance via TypedDI")
            posting_handler = await resolver.aget(SlackPostingHandler)
            dynamodb_store = await resolver.aget(DynamoDBStore)
            secrets_manager = await resolver.aget(SecretsManager)
            return TrustEndorsementHandler(
                posting_handler=posting_handler,
                db_store=dynamodb_store,
                secrets_manager=secrets_manager,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=TrustEndorsementHandlerProtocol,
            concrete_type=TrustEndorsementHandler,
            factory=create_trust_endorsement_handler,
            dependencies=[
                DependencySpec(SlackPostingHandler),
                DependencySpec(DynamoDBStore),
                DependencySpec(SecretsManager),
            ],
            lifetime="singleton",
        )
        logger.info("TrustEndorsementHandler registered successfully")
    except ImportError as e:
        logger.warning(f"TrustEndorsementHandler not available: {e}")

    # FlagReviewHandler with protocol
    try:
        from packages.slack.interactive_elements.flag_review_handler import (
            FlagReviewHandler,
        )

        async def create_flag_review_handler(resolver) -> FlagReviewHandler:
            """Factory function for FlagReviewHandler using TypedResolver."""
            logger.info("Creating FlagReviewHandler instance via TypedDI")
            posting_handler = await resolver.aget(SlackPostingHandler)
            dynamodb_store = await resolver.aget(DynamoDBStore)
            secrets_manager = await resolver.aget(SecretsManager)
            return FlagReviewHandler(
                posting_handler=posting_handler,
                db_store=dynamodb_store,
                secrets_manager=secrets_manager,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=FlagReviewHandlerProtocol,
            concrete_type=FlagReviewHandler,
            factory=create_flag_review_handler,
            dependencies=[
                DependencySpec(SlackPostingHandler),
                DependencySpec(DynamoDBStore),
                DependencySpec(SecretsManager),
            ],
            lifetime="singleton",
        )
        logger.info("FlagReviewHandler registered successfully")
    except ImportError as e:
        logger.warning(f"FlagReviewHandler not available: {e}")

    # HomeTabHandler with protocol
    try:
        from packages.slack.home.home import HomeTabHandler
        from packages.slack.interactive_elements.feedback_report import (
            FeedbackReportHandler,
        )
        from packages.slack.interactive_elements.usage_export_handler import (
            UsageExportHandler,
        )

        async def create_home_tab_handler(resolver) -> HomeTabHandler:
            """Factory function for HomeTabHandler using TypedResolver."""
            logger.info("Creating HomeTabHandler instance via TypedDI")
            secrets_manager = await resolver.aget(SecretsManager)
            user_store = await resolver.aget(UserStore)
            slack_client = await resolver.aget(SlackAsyncClient)
            slack_user_ops = await resolver.aget(SlackUserOps)

            # Optional dependencies
            try:
                feedback_report_handler = await resolver.aget(FeedbackReportHandler)
            except (KeyError, RuntimeError) as e:
                logger.warning(f"FeedbackReportHandler not available: {e}")
                feedback_report_handler = None
            try:
                command_tracking_ops = await resolver.aget(CommandTrackingOperations)
            except (KeyError, RuntimeError) as e:
                logger.warning(f"CommandTrackingOperations not available: {e}")
                command_tracking_ops = None
            try:
                usage_export_handler = await resolver.aget(UsageExportHandler)
            except (KeyError, RuntimeError) as e:
                logger.warning(f"UsageExportHandler not available: {e}")
                usage_export_handler = None

            # Load admin user list from secrets (users allowed to see team-wide stats on Home tab)
            admin_user_list = []
            if secrets_manager is not None:
                try:
                    # Fetch from the dedicated Ketchup_Token_Secrets secret
                    kt_secrets = await secrets_manager.get_secret_async("Ketchup_Token_Secrets")
                    admin_users = kt_secrets.get("usage_stats_admin_users", [])

                    logger.info(
                        "Loaded usage_stats_admin_users from secrets (type: %s, length: %s)",
                        type(admin_users).__name__,
                        len(admin_users) if isinstance(admin_users, (list, str)) else "N/A",
                    )

                    # If it's a string (JSON), parse it
                    if isinstance(admin_users, str):
                        import json

                        admin_user_list = json.loads(admin_users)
                        logger.info(
                            "Parsed admin list from JSON string: %d users", len(admin_user_list)
                        )
                    else:
                        admin_user_list = admin_users
                        logger.info(
                            "Using admin list directly: %d users",
                            len(admin_user_list) if isinstance(admin_user_list, list) else 0,
                        )

                except Exception as exc:  # noqa: BLE001  – ensure Home tab still loads
                    logger.error("Failed to retrieve usage_stats_admin_users from secrets: %s", exc)
                    logger.warning(
                        "Admin list will be EMPTY - no users will have admin access to usage stats"
                    )

            return HomeTabHandler(
                secrets_manager=secrets_manager,
                user_store=user_store,
                slack_client=slack_client,
                slack_user_ops=slack_user_ops,
                feedback_report_handler=feedback_report_handler,
                command_tracking_ops=command_tracking_ops,
                admin_user_list=admin_user_list,
                usage_export_handler=usage_export_handler,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=HomeTabHandlerProtocol,
            concrete_type=HomeTabHandler,
            factory=create_home_tab_handler,
            dependencies=[
                DependencySpec(SecretsManager),
                DependencySpec(UserStore),
                DependencySpec(SlackAsyncClient),
                DependencySpec(SlackUserOps),
                DependencySpec(FeedbackReportHandler),
                DependencySpec(CommandTrackingOperations),
                DependencySpec(UsageExportHandler),
            ],
            lifetime="singleton",
        )
        logger.info("HomeTabHandler registered successfully")
    except ImportError as e:
        logger.warning(f"HomeTabHandler not available: {e}")

    # UsageExportHandler with protocol
    try:
        from packages.slack.interactive_elements.usage_export_handler import (
            UsageExportHandler,
        )

        async def create_usage_export_handler(resolver) -> UsageExportHandler:
            """Factory function for UsageExportHandler using TypedResolver."""
            logger.info("Creating UsageExportHandler instance via TypedDI")
            command_tracking_ops = await resolver.aget(CommandTrackingOperations)
            slack_posting_handler = await resolver.aget(SlackPostingHandler)
            csv_generator = await resolver.aget(CommandUsageCSVGenerator)
            return UsageExportHandler(
                command_tracking_ops=command_tracking_ops,
                slack_posting_handler=slack_posting_handler,
                csv_generator=csv_generator,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=UsageExportHandlerProtocol,
            concrete_type=UsageExportHandler,
            factory=create_usage_export_handler,
            dependencies=[
                DependencySpec(CommandTrackingOperations),
                DependencySpec(SlackPostingHandler),
                DependencySpec(CommandUsageCSVGenerator),
            ],
            lifetime="singleton",
        )
        logger.info("UsageExportHandler registered successfully")
    except ImportError as e:
        logger.warning(f"UsageExportHandler not available: {e}")

    logger.info("Integration Services registered successfully")
