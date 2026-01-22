"""
Slack Handlers Registration Module

Registers Slack interactive element handlers that process user interactions:
- FeedbackReactionsHandler for processing user feedback reactions
- FeedbackReportHandler for handling feedback reports
- ChannelMetadataEditHandler for channel metadata editing
- UserVerifier for user verification operations

These handlers form the interactive layer between users and the Slack application,
providing rich interactive experiences through reactions, reports, editing, and shortcuts.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, List

from packages.core.logging import setup_logger
from packages.core.typed_di.service_spec import ServiceSpec, register_from_specs

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

# Import required dependencies
from packages.core.local_metrics import MetricsStorage
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore
from packages.secrets.manager import SecretsManager
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

from ..protocols import (
    ChannelMetadataEditHandlerProtocol,
    FeedbackReactionsHandlerProtocol,
    FeedbackReportHandlerProtocol,
    UserVerifierProtocol,
)

logger = setup_logger(__name__)


# =============================================================================
# ServiceSpec Declarations (declarative registration - minimal boilerplate)
# =============================================================================


def _get_feedback_handler_specs() -> List[ServiceSpec]:
    """Return specs for feedback-related handlers."""
    return [
        ServiceSpec(
            protocol=FeedbackReactionsHandlerProtocol,
            concrete=FeedbackReactionsHandler,
            deps={
                "posting_handler": SlackPostingHandler,
                "dynamodb_store": DynamoDBStore,
                "metrics": MetricsStorage,
            },
        ),
        ServiceSpec(
            protocol=FeedbackReportHandlerProtocol,
            concrete=FeedbackReportHandler,
            deps={
                "posting_handler": SlackPostingHandler,
                "secrets_manager": SecretsManager,
            },
        ),
    ]


def _get_metadata_handler_specs() -> List[ServiceSpec]:
    """Return specs for metadata and interaction handlers."""
    return [
        ServiceSpec(
            protocol=ChannelMetadataEditHandlerProtocol,
            concrete=ChannelMetadataEditHandler,
            deps={
                "posting_handler": SlackPostingHandler,
                "secrets_manager": SecretsManager,
                "dynamodb_store": DynamoDBStore,
            },
        ),
    ]


def _get_verification_handler_specs() -> List[ServiceSpec]:
    """Return specs for user verification handlers."""
    return [
        ServiceSpec(
            protocol=UserVerifierProtocol,
            concrete=UserVerifier,
            deps={
                "user_store": UserStore,
                "user_ops": SlackUserOps,
                "secrets_manager": SecretsManager,
            },
        ),
    ]


# =============================================================================
# Main Registration Entry Point
# =============================================================================


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

    # Register all handlers via ServiceSpec
    register_from_specs(manager, _get_feedback_handler_specs(), "feedback_handlers")
    register_from_specs(manager, _get_metadata_handler_specs(), "metadata_handlers")
    register_from_specs(manager, _get_verification_handler_specs(), "verification_handlers")

    logger.info("Slack interactive handler services registered successfully (4 services)")
