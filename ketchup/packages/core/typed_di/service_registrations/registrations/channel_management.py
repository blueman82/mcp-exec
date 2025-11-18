"""
Channel Management Services Registration Module

Registers channel management services that handle channel operations, analytics,
policy enforcement, metrics collection, and validation:
- ChannelEligibilityService for channel eligibility checks
- ChannelPolicyService for policy management and enforcement
- ChannelMetricsService for metrics collection and analysis
- ChannelAnalyticsService for advanced analytics and insights
- ChannelValidationService for validation and integrity checks

These services provide comprehensive channel management capabilities for the Slack application.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Channel Management service imports
from packages.slack.channel_operations.channel_analytics_service import ChannelAnalyticsService
from packages.slack.channel_operations.channel_eligibility import ChannelEligibilityService
from packages.slack.channel_operations.channel_metrics_service import ChannelMetricsService
from packages.slack.channel_operations.channel_policy_service import ChannelPolicyService
from packages.slack.channel_operations.channel_validation_service import ChannelValidationService

# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import protocols from the protocols module to avoid circular dependencies
from ..protocols import (
    ChannelAnalyticsServiceProtocol,
    ChannelEligibilityServiceProtocol,
    ChannelMetricsServiceProtocol,
    ChannelPolicyServiceProtocol,
    ChannelValidationServiceProtocol,
)

# Import required dependencies
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


def register_channel_management(manager: "ServiceRegistrationManager") -> None:
    """
    Register Channel Management services.

    These services handle comprehensive channel management operations including
    eligibility checks, policy enforcement, metrics collection, analytics,
    and validation operations.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any channel management service registration fails
    """
    logger.info("Registering Channel Management services")

    # Register core channel management services
    _register_core_channel_services(manager)

    # Register analytics and validation services
    _register_analytics_validation_services(manager)

    logger.info("Channel Management services registered successfully")


def _register_core_channel_services(manager: "ServiceRegistrationManager") -> None:
    """Register core channel management services: eligibility, policy, metrics."""

    # ChannelEligibilityService with protocol
    async def create_channel_eligibility_service(resolver) -> ChannelEligibilityService:
        """Factory function for ChannelEligibilityService using TypedResolver."""
        logger.info("Creating ChannelEligibilityService instance via TypedDI")
        channel_info_ops = await resolver.aget(ChannelInfoOps)
        posting_handler = await resolver.aget(SlackPostingHandler)
        dynamodb_store = await resolver.aget(DynamoDBStore)
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
            DependencySpec(ChannelInfoOps),
            DependencySpec(SlackPostingHandler),
            DependencySpec(DynamoDBStore),
        ],
        lifetime="singleton",
    )

    # ChannelPolicyService with protocol
    async def create_channel_policy_service(resolver) -> ChannelPolicyService:
        """Factory function for ChannelPolicyService using TypedResolver."""
        logger.info("Creating ChannelPolicyService instance via TypedDI")
        channel_info_ops = await resolver.aget(ChannelInfoOps)
        dynamodb_store = await resolver.aget(DynamoDBStore)
        return ChannelPolicyService(
            channel_info_ops=channel_info_ops,
            dynamodb_store=dynamodb_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelPolicyServiceProtocol,
        concrete_type=ChannelPolicyService,
        factory=create_channel_policy_service,
        dependencies=[
            DependencySpec(ChannelInfoOps),
            DependencySpec(DynamoDBStore),
        ],
        lifetime="singleton",
    )

    # ChannelMetricsService with protocol
    async def create_channel_metrics_service(resolver) -> ChannelMetricsService:
        """Factory function for ChannelMetricsService using TypedResolver."""
        logger.info("Creating ChannelMetricsService instance via TypedDI")
        channel_info_ops = await resolver.aget(ChannelInfoOps)
        dynamodb_store = await resolver.aget(DynamoDBStore)
        return ChannelMetricsService(
            channel_info_ops=channel_info_ops,
            dynamodb_store=dynamodb_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelMetricsServiceProtocol,
        concrete_type=ChannelMetricsService,
        factory=create_channel_metrics_service,
        dependencies=[
            DependencySpec(ChannelInfoOps),
            DependencySpec(DynamoDBStore),
        ],
        lifetime="singleton",
    )


def _register_analytics_validation_services(manager: "ServiceRegistrationManager") -> None:
    """Register analytics and validation services."""

    # ChannelAnalyticsService with protocol
    async def create_channel_analytics_service(resolver) -> ChannelAnalyticsService:
        """Factory function for ChannelAnalyticsService using TypedResolver."""
        logger.info("Creating ChannelAnalyticsService instance via TypedDI")
        channel_info_ops = await resolver.aget(ChannelInfoOps)
        dynamodb_store = await resolver.aget(DynamoDBStore)
        return ChannelAnalyticsService(
            channel_info_ops=channel_info_ops,
            dynamodb_store=dynamodb_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelAnalyticsServiceProtocol,
        concrete_type=ChannelAnalyticsService,
        factory=create_channel_analytics_service,
        dependencies=[
            DependencySpec(ChannelInfoOps),
            DependencySpec(DynamoDBStore),
        ],
        lifetime="singleton",
    )

    # ChannelValidationService with protocol
    async def create_channel_validation_service(resolver) -> ChannelValidationService:
        """Factory function for ChannelValidationService using TypedResolver."""
        logger.info("Creating ChannelValidationService instance via TypedDI")
        channel_info_ops = await resolver.aget(ChannelInfoOps)
        dynamodb_store = await resolver.aget(DynamoDBStore)
        return ChannelValidationService(
            channel_info_ops=channel_info_ops,
            dynamodb_store=dynamodb_store,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=ChannelValidationServiceProtocol,
        concrete_type=ChannelValidationService,
        factory=create_channel_validation_service,
        dependencies=[
            DependencySpec(ChannelInfoOps),
            DependencySpec(DynamoDBStore),
        ],
        lifetime="singleton",
    )