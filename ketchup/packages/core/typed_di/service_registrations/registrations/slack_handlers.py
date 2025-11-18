"""
Slack Handlers Registration Module

Registers Slack interactive element handlers that process user interactions:
- FeedbackReactionsHandler for processing user feedback reactions
- FeedbackReportHandler for handling feedback reports
- ChannelMetadataEditHandler for channel metadata editing
- ShortcutHandler for processing Slack shortcuts
- UserVerifier for user verification operations

These handlers form the interactive layer between users and the Slack application,
providing rich interactive experiences through reactions, reports, editing, and shortcuts.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Slack handler imports
from packages.slack.authorisation.user_verification import UserVerifier
from packages.slack.interactive_elements.channel_metadata_edit import (
    ChannelMetadataEditHandler,
)
from packages.slack.interactive_elements.feedback_reactions import (
    FeedbackReactionsHandler,
)
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler


# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import protocols from the protocols module to avoid circular dependencies
from ..protocols import (
    ChannelMetadataEditHandlerProtocol,
    FeedbackReactionsHandlerProtocol,
    FeedbackReportHandlerProtocol,

    UserVerifierProtocol,
)

# Import required dependencies
from packages.core.local_metrics import MetricsStorage
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore
from packages.secrets.manager import SecretsManager
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


def register_slack_handlers(manager: "ServiceRegistrationManager") -> None:
    """
    Register Slack interactive element handlers for user interaction processing.

    These handlers provide the interactive layer for Slack functionality, processing
    user reactions, feedback, metadata editing, shortcuts, and user verification.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical handler registration fails
    """
    logger.info("Registering Slack interactive handler services")

    # Register feedback handlers
    _register_feedback_handlers(manager)  # Required for test compatibility

    # Register metadata and interaction handlers
    _register_metadata_and_interaction_handlers(manager)

    # Register verification handlers
    _register_verification_handlers(manager)

    logger.info("Slack interactive handler services registered successfully")


def _register_feedback_handlers(manager: "ServiceRegistrationManager") -> None:
    """Register feedback-related handlers for reactions and reports."""
    # FeedbackReactionsHandler with protocol
    async def create_feedback_reactions_handler(resolver) -> FeedbackReactionsHandler:
        """Factory function for FeedbackReactionsHandler using TypedResolver."""
        logger.info("Creating FeedbackReactionsHandler instance via TypedDI")
        slack_posting = await resolver.aget(SlackPostingHandler)
        dynamodb_store = await resolver.aget(DynamoDBStore)
        metrics = await resolver.aget(MetricsStorage)
        return FeedbackReactionsHandler(
            posting_handler=slack_posting,
            dynamodb_store=dynamodb_store,
            metrics=metrics,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=FeedbackReactionsHandlerProtocol,
        concrete_type=FeedbackReactionsHandler,
        factory=create_feedback_reactions_handler,
        dependencies=[
            DependencySpec(SlackPostingHandler),
            DependencySpec(DynamoDBStore),
            DependencySpec(MetricsStorage),
        ],
        lifetime="singleton",
    )

    # FeedbackReportHandler with protocol
    async def create_feedback_report_handler(resolver) -> FeedbackReportHandler:
        """Factory function for FeedbackReportHandler using TypedResolver."""
        logger.info("Creating FeedbackReportHandler instance via TypedDI")
        slack_posting = await resolver.aget(SlackPostingHandler)
        secrets_manager = await resolver.aget(SecretsManager)
        return FeedbackReportHandler(
            posting_handler=slack_posting, secrets_manager=secrets_manager
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=FeedbackReportHandlerProtocol,
        concrete_type=FeedbackReportHandler,
        factory=create_feedback_report_handler,
        dependencies=[
            DependencySpec(SlackPostingHandler),
            DependencySpec(SecretsManager),
        ],
        lifetime="singleton",
    )


def _register_metadata_and_interaction_handlers(manager: "ServiceRegistrationManager") -> None:
    """Register metadata editing and shortcut interaction handlers."""
    # ChannelMetadataEditHandler with protocol
    async def create_channel_metadata_edit_handler(resolver) -> ChannelMetadataEditHandler:
        """Factory function for ChannelMetadataEditHandler using TypedResolver."""
        logger.info("Creating ChannelMetadataEditHandler instance via TypedDI")
        slack_posting = await resolver.aget(SlackPostingHandler)
        secrets_manager = await resolver.aget(SecretsManager)
        dynamodb_store = await resolver.aget(DynamoDBStore)
        return ChannelMetadataEditHandler(
            posting_handler=slack_posting,
            secrets_manager=secrets_manager,
            dynamodb_store=dynamodb_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelMetadataEditHandlerProtocol,
        concrete_type=ChannelMetadataEditHandler,
        factory=create_channel_metadata_edit_handler,
        dependencies=[
            DependencySpec(SlackPostingHandler),
            DependencySpec(SecretsManager),
            DependencySpec(DynamoDBStore),
        ],
        lifetime="singleton",
    )




def _register_verification_handlers(manager: "ServiceRegistrationManager") -> None:
    """Register user verification handlers."""
    # UserVerifier with protocol
    async def create_user_verifier(resolver) -> UserVerifier:
        """Factory function for UserVerifier using TypedResolver."""
        logger.info("Creating UserVerifier instance via TypedDI")
        user_store = await resolver.aget(UserStore)
        user_ops = await resolver.aget(SlackUserOps)
        secrets_manager = await resolver.aget(SecretsManager)
        return UserVerifier(
            user_store=user_store,
            user_ops=user_ops,
            secrets_manager=secrets_manager,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=UserVerifierProtocol,
        concrete_type=UserVerifier,
        factory=create_user_verifier,
        dependencies=[
            DependencySpec(UserStore),
            DependencySpec(SlackUserOps),
            DependencySpec(SecretsManager),
        ],
        lifetime="singleton",
    )