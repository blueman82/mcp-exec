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

from typing import TYPE_CHECKING, List

from packages.core.logging import setup_logger
from packages.core.typed_di.service_spec import ServiceSpec, register_from_specs

# Channel Management service imports
from packages.slack.channel_operations.channel_analytics_service import ChannelAnalyticsService
from packages.slack.channel_operations.channel_eligibility import ChannelEligibilityService
from packages.slack.channel_operations.channel_metrics_service import ChannelMetricsService
from packages.slack.channel_operations.channel_policy_service import ChannelPolicyService
from packages.slack.channel_operations.channel_validation_service import ChannelValidationService

# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import required dependencies
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.messages.posting import SlackPostingHandler

from ..protocols import (
    ChannelAnalyticsServiceProtocol,
    ChannelEligibilityServiceProtocol,
    ChannelMetricsServiceProtocol,
    ChannelPolicyServiceProtocol,
    ChannelValidationServiceProtocol,
)

logger = setup_logger(__name__)


# =============================================================================
# ServiceSpec Declarations (declarative registration - minimal boilerplate)
# =============================================================================


def _get_channel_management_specs() -> List[ServiceSpec]:
    """Return specs for all channel management services."""
    return [
        ServiceSpec(
            protocol=ChannelEligibilityServiceProtocol,
            concrete=ChannelEligibilityService,
            deps={
                "channel_info_ops": ChannelInfoOps,
                "posting_handler": SlackPostingHandler,
                "dynamodb_store": DynamoDBStore,
            },
        ),
        ServiceSpec(
            protocol=ChannelPolicyServiceProtocol,
            concrete=ChannelPolicyService,
            deps={
                "channel_info_ops": ChannelInfoOps,
                "dynamodb_store": DynamoDBStore,
            },
        ),
        ServiceSpec(
            protocol=ChannelMetricsServiceProtocol,
            concrete=ChannelMetricsService,
            deps={
                "channel_info_ops": ChannelInfoOps,
                "dynamodb_store": DynamoDBStore,
            },
        ),
        ServiceSpec(
            protocol=ChannelAnalyticsServiceProtocol,
            concrete=ChannelAnalyticsService,
            deps={
                "channel_info_ops": ChannelInfoOps,
                "dynamodb_store": DynamoDBStore,
            },
        ),
        ServiceSpec(
            protocol=ChannelValidationServiceProtocol,
            concrete=ChannelValidationService,
            deps={
                "channel_info_ops": ChannelInfoOps,
                "dynamodb_store": DynamoDBStore,
            },
        ),
    ]


# =============================================================================
# Main Registration Entry Point
# =============================================================================


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

    register_from_specs(manager, _get_channel_management_specs(), "channel_management")

    logger.info("Channel Management services registered successfully (5 services)")
