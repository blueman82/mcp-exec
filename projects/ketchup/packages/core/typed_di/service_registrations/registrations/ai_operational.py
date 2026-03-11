"""
AI Operational Services Registration Module

Registers AI and operational services that provide intelligent functionality:
- TokenTracker for AI token usage tracking
- OpenAIHandler for AI processing and responses
- BlockKitBuilder for Slack UI block construction
- SlackArchiveCommand for archive command processing
- ApiExecutor for AI API interaction and execution
- MessagePreparer for AI message preparation
- AzureConfig for Azure OpenAI configuration

These services provide the intelligent operational layer, handling AI interactions,
token tracking, UI building, and command processing with Azure OpenAI integration.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.ai.core.azure_async_client import AzureConfig
from packages.ai.core.openai_handler import OpenAIHandler
from packages.ai.core.operations.api_interaction import ApiExecutor
from packages.ai.core.operations.message_preparation import MessagePreparer
from packages.ai.cost_calculator import TokenTracker
from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec
from packages.slack.blockkits.base import BlockKitBuilder
from packages.slack.command_processing.archive_command import SlackArchiveCommand

# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import protocols from the protocols module to avoid circular dependencies
from ..protocols import (
    ApiExecutorProtocol,
    AzureConfigProtocol,
    BlockKitBuilderProtocol,
    ChannelInfoOpsProtocol,
    DynamoDBStoreProtocol,
    JIRADataExtractorProtocol,
    MessagePreparerProtocol,
    OpenAIHandlerProtocol,
    SecretsManagerProtocol,
    SlackArchiveCommandProtocol,
    SlackChannelArchiveOpsProtocol,
    SlackChannelMessageOpsProtocol,
    SlackChannelRestoreOpsProtocol,
    SlackPostingHandlerProtocol,
    TokenTrackerProtocol,
    UserStoreProtocol,
)

# Import required dependencies

logger = setup_logger(__name__)


def register_ai_operational(manager: "ServiceRegistrationManager") -> None:
    """
    Register AI and operational services for intelligent functionality.

    These services provide AI capabilities, token tracking, UI construction,
    and intelligent command processing with Azure OpenAI integration.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical AI service registration fails
    """
    logger.info("Registering AI and operational services")

    # Register AI tracking and core services
    _register_ai_core_services(manager)

    # Register UI and command services
    _register_ui_and_command_services(manager)

    # Register AI operations and configuration
    _register_ai_operations_and_config(manager)

    logger.info("AI and operational services registered successfully")


def _register_ai_core_services(manager: "ServiceRegistrationManager") -> None:
    """Register core AI services: TokenTracker and OpenAIHandler."""

    # TokenTracker with protocol (no dependencies)
    async def create_token_tracker(resolver) -> TokenTracker:
        """Factory function for TokenTracker using TypedResolver."""
        logger.info("Creating TokenTracker instance via TypedDI")
        return TokenTracker()

    manager.register_protocol_with_concrete_alias(
        protocol_type=TokenTrackerProtocol,
        concrete_type=TokenTracker,
        factory=create_token_tracker,
        dependencies=[],
        lifetime="singleton",
    )

    # OpenAIHandler with protocol (AI service)
    async def create_openai_handler(resolver) -> OpenAIHandler:
        """Factory function for OpenAIHandler using TypedResolver."""
        logger.info("Creating OpenAIHandler instance via TypedDI")
        token_tracker = await resolver.aget(TokenTrackerProtocol)
        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        channel_msg_ops = await resolver.aget(SlackChannelMessageOpsProtocol)
        channel_ops = await resolver.aget(SlackChannelArchiveOpsProtocol)

        # Resolve JIRA extractor for ticket enrichment in status reports
        jira_extractor = None
        try:
            jira_extractor = await resolver.aget(JIRADataExtractorProtocol)
            logger.info("JIRADataExtractor resolved successfully for OpenAIHandler")
        except Exception as e:
            logger.warning(f"JIRADataExtractor not available for OpenAIHandler: {e}")

        handler = OpenAIHandler(
            token_tracker=token_tracker,
            secrets_manager=secrets_manager,
            channel_info_ops=channel_info_ops,
            channel_msg_ops=channel_msg_ops,
            channel_ops=channel_ops,
            jira_extractor=jira_extractor,
        )
        # Initialize handler to set up API key and submodules
        await handler.initialize()
        logger.info("OpenAIHandler initialized successfully via TypedDI")
        return handler

    manager.register_protocol_with_concrete_alias(
        protocol_type=OpenAIHandlerProtocol,
        concrete_type=OpenAIHandler,
        factory=create_openai_handler,
        dependencies=[
            DependencySpec(TokenTrackerProtocol),
            DependencySpec(SecretsManagerProtocol),
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(SlackChannelMessageOpsProtocol),
            DependencySpec(SlackChannelArchiveOpsProtocol),
            DependencySpec(JIRADataExtractorProtocol),
        ],
        lifetime="singleton",
    )


def _register_ui_and_command_services(manager: "ServiceRegistrationManager") -> None:
    """Register UI and command services: BlockKitBuilder and SlackArchiveCommand."""

    # BlockKitBuilder with protocol
    async def create_block_kit_builder(resolver) -> BlockKitBuilder:
        """Factory function for BlockKitBuilder using TypedResolver."""
        logger.info("Creating BlockKitBuilder instance via TypedDI")
        from packages.core.typed_di.service_registrations.protocols.core_protocols import (
            SlackPostingHandlerProtocol,
        )
        from packages.core.typed_di.service_registrations.protocols.ui_protocols import (
            FeedbackReactionsHandlerProtocol,
        )

        posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        dynamodb_store = await resolver.aget(DynamoDBStoreProtocol)

        # Optionally resolve FeedbackReactionsHandler for feedback blocks
        feedback_reactions_handler = None
        build_feedback_blocks_func = None
        try:
            feedback_reactions_handler = await resolver.aget(FeedbackReactionsHandlerProtocol)
            build_feedback_blocks_func = feedback_reactions_handler.build_feedback_blocks
            logger.info("FeedbackReactionsHandler resolved successfully for BlockKitBuilder")
        except Exception as e:
            logger.info("FeedbackReactionsHandler not available for BlockKitBuilder: %s", e)

        # Create and configure the BlockKitBuilder
        # Use dynamodb_store.get_channel_details (takes channel_id only)
        # NOT channel_info_ops.get_channel_details (takes user_id, channel_id, dm_channel_id)
        builder = BlockKitBuilder(posting_handler=posting_handler)
        builder.configure(
            channel_details_getter=dynamodb_store.get_channel_details,
            build_feedback_blocks_func=build_feedback_blocks_func,
        )
        return builder

    manager.register_protocol_with_concrete_alias(
        protocol_type=BlockKitBuilderProtocol,
        concrete_type=BlockKitBuilder,
        factory=create_block_kit_builder,
        dependencies=[
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(DynamoDBStoreProtocol),
        ],
        lifetime="singleton",
    )

    # SlackArchiveCommand with protocol
    async def create_slack_archive_command(resolver) -> SlackArchiveCommand:
        """Factory function for SlackArchiveCommand using TypedResolver."""
        logger.info("Creating SlackArchiveCommand instance via TypedDI")
        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        archive_ops = await resolver.aget(SlackChannelArchiveOpsProtocol)
        dynamodb_store = await resolver.aget(DynamoDBStoreProtocol)
        block_kit_builder = await resolver.aget(BlockKitBuilderProtocol)
        channel_restore_ops = await resolver.aget(SlackChannelRestoreOpsProtocol)
        user_store = await resolver.aget(UserStoreProtocol)
        return SlackArchiveCommand(
            channel_info_ops=channel_info_ops,
            slack_posting_handler=posting_handler,
            archive_ops=archive_ops,
            dynamodb_store=dynamodb_store,
            block_kit_builder=block_kit_builder,
            channel_restore_ops=channel_restore_ops,
            user_store=user_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackArchiveCommandProtocol,
        concrete_type=SlackArchiveCommand,
        factory=create_slack_archive_command,
        dependencies=[
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(SlackChannelArchiveOpsProtocol),
            DependencySpec(DynamoDBStoreProtocol),
            DependencySpec(BlockKitBuilderProtocol),
            DependencySpec(SlackChannelRestoreOpsProtocol),
            DependencySpec(UserStoreProtocol),
        ],
        lifetime="singleton",
    )


def _register_ai_operations_and_config(manager: "ServiceRegistrationManager") -> None:
    """Register AI operations and configuration: ApiExecutor, MessagePreparer, AzureConfig."""

    # ApiExecutor with protocol
    async def create_api_executor(resolver) -> ApiExecutor:
        """Factory function for ApiExecutor.

        Uses the same endpoint and API key sources as OpenAIHandler.initialize():
        - Endpoint: AZURE_OPENAI_ENDPOINT from constants.py (full deployment URL)
        - API key: AZURE_OPENAI_LB_API_KEY from Secrets Manager (LB key)
        """
        from packages.ai.core.azure_async_client import AzureAsyncClient
        from packages.core.constants import AZURE_OPENAI_ENDPOINT

        token_tracker = await resolver.aget(TokenTrackerProtocol)
        slack_channel_archive_ops = await resolver.aget(SlackChannelArchiveOpsProtocol)
        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        api_key = await secrets_manager.get_azure_openai_lb_api_key()

        azure_client = AzureAsyncClient(api_key=api_key, endpoint=AZURE_OPENAI_ENDPOINT)

        return ApiExecutor(
            api_request_func=azure_client._make_azure_api_request,
            endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=api_key,
            token_tracker=token_tracker,
            channel_archive_ops=slack_channel_archive_ops,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ApiExecutorProtocol,
        concrete_type=ApiExecutor,
        factory=create_api_executor,
        dependencies=[
            DependencySpec(TokenTrackerProtocol),
            DependencySpec(SlackChannelArchiveOpsProtocol),
            DependencySpec(SecretsManagerProtocol),
        ],
        lifetime="singleton",
    )

    # MessagePreparer with protocol
    async def create_message_preparer(resolver) -> MessagePreparer:
        """Factory function for MessagePreparer."""
        token_tracker = await resolver.aget(TokenTrackerProtocol)
        channel_msg_ops = await resolver.aget(SlackChannelMessageOpsProtocol)
        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        return MessagePreparer(
            token_tracker=token_tracker,
            channel_msg_ops=channel_msg_ops,
            channel_info_ops=channel_info_ops,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=MessagePreparerProtocol,
        concrete_type=MessagePreparer,
        factory=create_message_preparer,
        dependencies=[
            DependencySpec(TokenTrackerProtocol),
            DependencySpec(SlackChannelMessageOpsProtocol),
            DependencySpec(ChannelInfoOpsProtocol),
        ],
        lifetime="singleton",
    )

    # AzureConfig with protocol
    async def create_azure_config(resolver) -> AzureConfig:
        """Factory function for AzureConfig."""
        from packages.core.constants import AZURE_OPENAI_ENDPOINT

        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        api_key = await secrets_manager.get_azure_openai_lb_api_key()
        return AzureConfig(
            api_key=api_key,
            endpoint=AZURE_OPENAI_ENDPOINT,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=AzureConfigProtocol,
        concrete_type=AzureConfig,
        factory=create_azure_config,
        dependencies=[DependencySpec(SecretsManagerProtocol)],
        lifetime="singleton",
    )
