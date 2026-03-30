"""
UI Services Registration Module

Registers UI and user interface services including BlockKit builders, modal handlers,
home tab handlers, and UI interaction services:
- BlockKit UI builders and formatters
- Home tab handlers and formatters
- Modal and view submission handlers
- UI interaction and block construction services

These services handle user interface generation and user interactions.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    SlackPostingHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.ui_protocols import (
    FeedbackReportHandlerProtocol,
)
from packages.core.typed_di.types import DependencySpec

# Essential imports for UI services
try:
    from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
    from packages.db.operations.feedback_operations import FeedbackOperations
    from packages.db.operations.trust_operations import TrustOperations
    from packages.secrets.manager import SecretsManager
    from packages.slack.blockkits.handlers.archive import ArchiveMessageHandler
    from packages.slack.blockkits.handlers.lookup import LookupMessageHandler
    from packages.slack.blockkits.handlers.parameter import ParameterMessageHandler
    from packages.slack.blockkits.handlers.query import QueryMessageHandler
    from packages.slack.blockkits.handlers.report import ReportMessageHandler
    from packages.slack.blockkits.handlers.status import StatusMessageHandler
    from packages.slack.channel_operations.slack_message_formatter import SlackMessageFormatter
    from packages.slack.interactive_elements.flag_review.block_builder import BlockBuilder

    # Additional UI services
    from packages.slack.interactive_elements.flag_review.modals import FlagReviewModalManager
    from packages.slack.interactive_elements.shortcuts import ShortcutHandler
    from packages.slack.user_operations.user_ops import SlackUserOps
except ImportError:
    # Allow module to load even with missing imports for testing
    pass

# Protocol imports
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

from ..protocols import (  # Additional UI service protocols
    ArchiveMessageHandlerProtocol,
    BlockBuilderProtocol,
    FeedbackOperationsProtocol,
    FlagReviewModalManagerProtocol,
    LookupMessageHandlerProtocol,
    ParameterMessageHandlerProtocol,
    QueryMessageHandlerProtocol,
    ReportMessageHandlerProtocol,
    ShortcutHandlerProtocol,
    SlackMessageFormatterProtocol,
    StatusMessageHandlerProtocol,
    SummaryMessageHandlerProtocol,
    TrustOperationsProtocol,
)

logger = setup_logger(__name__)


def register_ui_services(manager: "ServiceRegistrationManager") -> None:
    """
    Register UI and user interface services for Slack UI components and interactions.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical service registration fails
    """
    logger.info("Registering UI services")

    _register_block_kit_services(manager)
    _register_interactive_services(manager)
    _register_home_tab_services(manager)
    _register_message_handler_services(manager)
    _register_additional_ui_services(manager)

    logger.info("UI services registered successfully (21 services)")


def _register_block_kit_services(manager: "ServiceRegistrationManager") -> None:
    """Register BlockKit UI construction services."""
    # BlockKitBuilder is registered in ai_operational.py with correct constructor
    logger.info("BlockKit services registration - BlockKitBuilder handled by ai_operational.py")


def _register_interactive_services(manager: "ServiceRegistrationManager") -> None:
    """Register interactive UI services for user interactions."""

    # ShortcutHandler
    async def create_shortcut_handler(resolver) -> ShortcutHandler:
        """Factory function for ShortcutHandler using TypedResolver."""
        logger.info("Creating ShortcutHandler instance via TypedDI")
        from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler

        feedback_report_handler = await resolver.aget(FeedbackReportHandler)
        posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        return ShortcutHandler(
            feedback_report_handler=feedback_report_handler, posting_handler=posting_handler
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ShortcutHandlerProtocol,
        concrete_type=ShortcutHandler,
        factory=create_shortcut_handler,
        dependencies=[
            DependencySpec(FeedbackReportHandlerProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
        ],
        lifetime="singleton",
    )


def _register_home_tab_services(manager: "ServiceRegistrationManager") -> None:
    """Register home tab and usage export services."""


def _register_message_handler_services(manager: "ServiceRegistrationManager") -> None:
    """Register specialized message handler services for different message types."""

    # ArchiveMessageHandler
    async def create_archive_message_handler(resolver) -> ArchiveMessageHandler:
        """Factory function for ArchiveMessageHandler using TypedResolver."""
        logger.info("Creating ArchiveMessageHandler instance via TypedDI")
        # ArchiveMessageHandler doesn't take any constructor parameters
        return ArchiveMessageHandler()

    manager.register_protocol_with_concrete_alias(
        protocol_type=ArchiveMessageHandlerProtocol,
        concrete_type=ArchiveMessageHandler,
        factory=create_archive_message_handler,
        dependencies=[],
        lifetime="singleton",
    )

    # LookupMessageHandler
    async def create_lookup_message_handler(resolver) -> LookupMessageHandler:
        """Factory function for LookupMessageHandler using TypedResolver."""
        logger.info("Creating LookupMessageHandler instance via TypedDI")
        # LookupMessageHandler doesn't take any constructor parameters
        return LookupMessageHandler()

    manager.register_protocol_with_concrete_alias(
        protocol_type=LookupMessageHandlerProtocol,
        concrete_type=LookupMessageHandler,
        factory=create_lookup_message_handler,
        dependencies=[],
        lifetime="singleton",
    )

    # QueryMessageHandler
    async def create_query_message_handler(resolver) -> QueryMessageHandler:
        """Factory function for QueryMessageHandler using TypedResolver."""
        logger.info("Creating QueryMessageHandler instance via TypedDI")
        # QueryMessageHandler doesn't take any constructor parameters
        return QueryMessageHandler()

    manager.register_protocol_with_concrete_alias(
        protocol_type=QueryMessageHandlerProtocol,
        concrete_type=QueryMessageHandler,
        factory=create_query_message_handler,
        dependencies=[],
        lifetime="singleton",
    )

    # ReportMessageHandler
    async def create_report_message_handler(resolver) -> ReportMessageHandler:
        """Factory function for ReportMessageHandler using TypedResolver."""
        logger.info("Creating ReportMessageHandler instance via TypedDI")
        # ReportMessageHandler uses dependency injection via configure method
        handler = ReportMessageHandler()
        # Dependencies will be configured by calling code as needed
        return handler

    manager.register_protocol_with_concrete_alias(
        protocol_type=ReportMessageHandlerProtocol,
        concrete_type=ReportMessageHandler,
        factory=create_report_message_handler,
        dependencies=[],
        lifetime="singleton",
    )

    # StatusMessageHandler
    async def create_status_message_handler(resolver) -> StatusMessageHandler:
        """Factory function for StatusMessageHandler using TypedResolver."""
        logger.info("Creating StatusMessageHandler instance via TypedDI")
        # StatusMessageHandler uses dependency injection via configure method
        handler = StatusMessageHandler()
        # Dependencies will be configured by calling code as needed
        return handler

    manager.register_protocol_with_concrete_alias(
        protocol_type=StatusMessageHandlerProtocol,
        concrete_type=StatusMessageHandler,
        factory=create_status_message_handler,
        dependencies=[],
        lifetime="singleton",
    )

    # SummaryMessageHandler
    async def create_summary_message_handler(resolver) -> SummaryMessageHandler:
        """Factory function for SummaryMessageHandler using TypedResolver."""
        logger.info("Creating SummaryMessageHandler instance via TypedDI")
        # SummaryMessageHandler doesn't take any constructor parameters
        return SummaryMessageHandler()

    manager.register_protocol_with_concrete_alias(
        protocol_type=SummaryMessageHandlerProtocol,
        concrete_type=SummaryMessageHandler,
        factory=create_summary_message_handler,
        dependencies=[],
        lifetime="singleton",
    )

    # ParameterMessageHandler
    async def create_parameter_message_handler(resolver) -> ParameterMessageHandler:
        """Factory function for ParameterMessageHandler using TypedResolver."""
        logger.info("Creating ParameterMessageHandler instance via TypedDI")
        # ParameterMessageHandler uses dependency injection via configure method
        handler = ParameterMessageHandler()
        # Dependencies will be configured by calling code as needed
        return handler

    manager.register_protocol_with_concrete_alias(
        protocol_type=ParameterMessageHandlerProtocol,
        concrete_type=ParameterMessageHandler,
        factory=create_parameter_message_handler,
        dependencies=[],
        lifetime="singleton",
    )


def _register_additional_ui_services(manager: "ServiceRegistrationManager") -> None:
    """Register additional UI services including modal manager, formatter, and operations."""

    # FlagReviewModalManager
    async def create_flag_review_modal_manager(resolver) -> FlagReviewModalManager:
        """Factory function for FlagReviewModalManager using TypedResolver."""
        logger.info("Creating FlagReviewModalManager instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)
        return FlagReviewModalManager(secrets_manager=secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=FlagReviewModalManagerProtocol,
        concrete_type=FlagReviewModalManager,
        factory=create_flag_review_modal_manager,
        dependencies=[DependencySpec(SecretsManager)],
        lifetime="singleton",
    )

    # SlackMessageFormatter
    async def create_slack_message_formatter(resolver) -> SlackMessageFormatter:
        """Factory function for SlackMessageFormatter using TypedResolver."""
        logger.info("Creating SlackMessageFormatter instance via TypedDI")
        user_ops = await resolver.aget(SlackUserOps)
        return SlackMessageFormatter(user_ops=user_ops)

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackMessageFormatterProtocol,
        concrete_type=SlackMessageFormatter,
        factory=create_slack_message_formatter,
        dependencies=[DependencySpec(SlackUserOps)],
        lifetime="singleton",
    )

    # FeedbackOperations
    async def create_feedback_operations(resolver) -> FeedbackOperations:
        """Factory function for FeedbackOperations using TypedResolver."""
        logger.info("Creating FeedbackOperations instance via TypedDI")
        dynamodb_client = await resolver.aget(DynamoDBAsyncClient)
        table_name = "ketchup_channel_information"
        return FeedbackOperations(client=dynamodb_client, table_name=table_name)

    manager.register_protocol_with_concrete_alias(
        protocol_type=FeedbackOperationsProtocol,
        concrete_type=FeedbackOperations,
        factory=create_feedback_operations,
        dependencies=[DependencySpec(DynamoDBAsyncClient)],
        lifetime="singleton",
    )

    # TrustOperations
    async def create_trust_operations(resolver) -> TrustOperations:
        """Factory function for TrustOperations using TypedResolver."""
        logger.info("Creating TrustOperations instance via TypedDI")
        client = await resolver.aget(DynamoDBAsyncClient)
        table_name = "ketchup_channel_information"
        return TrustOperations(client=client, table_name=table_name)

    manager.register_protocol_with_concrete_alias(
        protocol_type=TrustOperationsProtocol,
        concrete_type=TrustOperations,
        factory=create_trust_operations,
        dependencies=[DependencySpec(DynamoDBAsyncClient)],
        lifetime="singleton",
    )

    # BlockBuilder
    async def create_block_builder(resolver) -> BlockBuilder:
        """Factory function for BlockBuilder using TypedResolver."""
        logger.info("Creating BlockBuilder instance via TypedDI")
        return BlockBuilder(resolver)

    manager.register_protocol_with_concrete_alias(
        protocol_type=BlockBuilderProtocol,
        concrete_type=BlockBuilder,
        factory=create_block_builder,
        dependencies=[],
        lifetime="singleton",
    )
