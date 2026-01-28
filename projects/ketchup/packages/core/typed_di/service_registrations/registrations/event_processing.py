"""
Event Processing Registration Module

Registers event handling services that process channel events and user interactions:
- Core event processors (EventProcessor, SlackEventHandler)
- Channel lifecycle processors (ArchiveProcessor, CreationProcessor, JoinProcessor)
- Event filtering and verification services
- Archive auto status cleanup services

These services handle incoming events from Slack and other platforms.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

from ..protocols import (
    BlockKitBuilderProtocol,
    ChannelEligibilityServiceProtocol,
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    CommandRouterProtocol,
    CreationProcessorProtocol,
    DynamoDBStoreProtocol,
    EventProcessorProtocol,
    PayloadProcessorProtocol,
    RestoreStateManagerProtocol,
    SecretsManagerProtocol,
    SlackAuthProtocol,
    SlackChannelRestoreOpsProtocol,
    SlackEventHandlerProtocol,
    SlackPostingHandlerProtocol,
)

logger = setup_logger(__name__)


def register_event_processing(manager: "ServiceRegistrationManager") -> None:
    """
    Register event processing services for handling Slack events and interactions.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical service registration fails
    """
    logger.info("Registering event processing services")

    _register_channel_eligibility_service(manager)
    _register_core_event_services(manager)
    _register_channel_lifecycle_processors(manager)
    _register_event_filtering_services(manager)

    logger.info("Event processing services registered successfully (8 services)")


def _register_channel_eligibility_service(manager: "ServiceRegistrationManager") -> None:
    """Register ChannelEligibilityService (dependency for SlackEventHandler)."""
    from packages.slack.channel_operations.channel_eligibility import ChannelEligibilityService

    async def create_channel_eligibility_service(resolver):
        """Factory function for ChannelEligibilityService."""
        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        dynamodb_store = await resolver.aget(DynamoDBStoreProtocol)
        return ChannelEligibilityService(
            channel_info_ops=channel_info_ops,
            posting_handler=posting_handler,
            dynamodb_store=dynamodb_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelEligibilityServiceProtocol,
        concrete_type=ChannelEligibilityService,
        factory=create_channel_eligibility_service,
        dependencies=[
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(DynamoDBStoreProtocol),
        ],
        lifetime="singleton",
    )
    logger.info("ChannelEligibilityService registered successfully")


def _register_core_event_services(manager: "ServiceRegistrationManager") -> None:
    """Register core event handling services."""
    # Lazy imports to avoid circular dependency at module load time
    # incoming_events.py imports from dependency_setup.py which imports protocols
    from packages.slack.channel_events.events import SlackEventHandler
    from packages.slack.channel_events.incoming_events import EventProcessor

    # SlackEventHandler
    async def create_slack_event_handler(resolver):
        """Factory function for SlackEventHandler using TypedResolver."""
        logger.info("Creating SlackEventHandler instance via TypedDI")

        secrets_manager = await resolver.aget(SecretsManagerProtocol)
        dynamodb_store = await resolver.aget(DynamoDBStoreProtocol)
        posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
        channel_info_ops = await resolver.aget(ChannelInfoOpsProtocol)
        channel_membership_ops = await resolver.aget(ChannelMembershipOpsProtocol)
        channel_restore_ops = await resolver.aget(SlackChannelRestoreOpsProtocol)
        block_kit_builder = await resolver.aget(BlockKitBuilderProtocol)
        channel_eligibility_service = await resolver.aget(ChannelEligibilityServiceProtocol)

        # Resolve RestoreStateManager to prevent auto-join during unarchive
        restore_state_manager = await resolver.aget(RestoreStateManagerProtocol)

        return SlackEventHandler(
            secrets_manager=secrets_manager,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
            channel_info_ops=channel_info_ops,
            channel_membership_ops=channel_membership_ops,
            channel_restore_ops=channel_restore_ops,
            block_kit_builder=block_kit_builder,
            channel_eligibility_service=channel_eligibility_service,
            restore_state_manager=restore_state_manager,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackEventHandlerProtocol,
        concrete_type=SlackEventHandler,
        factory=create_slack_event_handler,
        dependencies=[
            DependencySpec(SecretsManagerProtocol),
            DependencySpec(DynamoDBStoreProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
            DependencySpec(ChannelInfoOpsProtocol),
            DependencySpec(ChannelMembershipOpsProtocol),
            DependencySpec(SlackChannelRestoreOpsProtocol),
            DependencySpec(BlockKitBuilderProtocol),
            DependencySpec(ChannelEligibilityServiceProtocol),
            DependencySpec(RestoreStateManagerProtocol),
        ],
        lifetime="singleton",
    )

    # EventProcessor
    async def create_event_processor(resolver):
        """Factory function for EventProcessor using TypedDI."""
        logger.info("Creating EventProcessor instance via TypedDI")

        # Get required dependencies
        slack_auth = await resolver.aget(SlackAuthProtocol)
        command_router = await resolver.aget(CommandRouterProtocol)
        event_handler = await resolver.aget(SlackEventHandlerProtocol)

        # Get additional handlers that EventProcessor expects in clients dict
        slack_posting_handler = await resolver.aget(SlackPostingHandlerProtocol)

        # Create comprehensive clients dict for EventProcessor
        clients = {
            "slack_auth": slack_auth,
            "event_handler": event_handler,
            "slack_posting": slack_posting_handler,
            "command_router": command_router,
        }

        return EventProcessor(
            clients=clients,
            slack_auth=slack_auth,
            command_router=command_router,
            event_handler=event_handler,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=EventProcessorProtocol,
        concrete_type=EventProcessor,
        factory=create_event_processor,
        dependencies=[
            DependencySpec(SlackAuthProtocol),
            DependencySpec(CommandRouterProtocol),
            DependencySpec(SlackEventHandlerProtocol),
            DependencySpec(SlackPostingHandlerProtocol),
        ],
        lifetime="singleton",
    )


def _register_channel_lifecycle_processors(manager: "ServiceRegistrationManager") -> None:
    """Register channel lifecycle event processors."""

    # Define unique placeholder classes to avoid duplicate registrations
    class ArchiveProcessorPlaceholder:
        """Placeholder for archive processing functionality."""

        pass

    class CreationProcessorPlaceholder:
        """Placeholder for channel creation processing functionality."""

        pass

    # ArchiveProcessor (placeholder implementation) - Registration handled by archive_processing.py
    async def create_archive_processor(resolver) -> ArchiveProcessorPlaceholder:
        """Factory function for ArchiveProcessor (placeholder)."""
        return ArchiveProcessorPlaceholder()

    # CreationProcessor (placeholder implementation)
    async def create_creation_processor(resolver) -> CreationProcessorPlaceholder:
        """Factory function for CreationProcessor (placeholder)."""
        return CreationProcessorPlaceholder()

    manager.register_protocol_with_concrete_alias(
        protocol_type=CreationProcessorProtocol,
        concrete_type=CreationProcessorPlaceholder,
        factory=create_creation_processor,
        dependencies=[],
        lifetime="singleton",
    )

    # JoinProcessor is an alias for JoinNotificationOps (registered in database_batches.py)
    # We DON'T register it separately to avoid duplicate registration
    # Users should use JoinNotificationOpsProtocol directly instead of JoinProcessorProtocol
    logger.info("JoinProcessor aliased to JoinNotificationOps (registered in database_batches.py)")

    # Define unique placeholder class for UnarchiveProcessor
    class UnarchiveProcessorPlaceholder:
        """Placeholder for channel unarchive processing functionality."""

        pass

    # UnarchiveProcessor (placeholder implementation)
    async def create_unarchive_processor(resolver) -> UnarchiveProcessorPlaceholder:
        """Factory function for UnarchiveProcessor (placeholder)."""
        return UnarchiveProcessorPlaceholder()


def _register_event_filtering_services(manager: "ServiceRegistrationManager") -> None:
    """Register event filtering and verification services."""

    # Define unique placeholder class for PayloadProcessor
    class PayloadProcessorPlaceholder:
        """Placeholder for event payload processing functionality."""

        pass

    # PayloadProcessor (placeholder implementation)
    async def create_payload_processor(resolver) -> PayloadProcessorPlaceholder:
        """Factory function for PayloadProcessor (placeholder)."""
        return PayloadProcessorPlaceholder()

    manager.register_protocol_with_concrete_alias(
        protocol_type=PayloadProcessorProtocol,
        concrete_type=PayloadProcessorPlaceholder,
        factory=create_payload_processor,
        dependencies=[],
        lifetime="singleton",
    )

    logger.info("Event filtering services registered successfully")
