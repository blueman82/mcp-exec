"""
CSOPM Services Registration Module.

Registers CSOPM (Customer Success Operations Project Management) notification services:
- CSOPMStateTracker: DynamoDB-backed notification state persistence
- CSOPMJIRAPoller: JIRA ticket polling for new assignments
- CSOPMSlackNotifier: Slack DM notifications for assignees
- CSOPMReminderService: RCA and closure reminder management

These services form the core of the CSOPM notification system, which monitors
JIRA tickets and sends proactive notifications to assignees.

All registrations use protocol-first pattern with concrete class aliasing
for backward compatibility and type-safe dependency injection.

Architectural Note:
This module integrates CSOPM services into the main Ketchup TypedDI container.
Services are registered in topological order to ensure proper dependency resolution:
1. CSOPMStateTracker (depends on DynamoDB infrastructure)
2. CSOPMJIRAPoller (depends on AsyncMCPClient)
3. CSOPMSlackNotifier (depends on StateTracker, Slack infrastructure)
4. CSOPMReminderService (depends on StateTracker, JIRAPoller, MCP)
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec
from packages.db.config.dynamodb_config import DynamoDBConfig
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

# Conditional imports to avoid circular dependencies
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

logger = setup_logger(__name__)


def register_csopm_services(manager: "ServiceRegistrationManager") -> None:
    """
    Register CSOPM notification services.

    Provides the core services for the CSOPM notification system:
    - State tracking in DynamoDB
    - JIRA ticket polling
    - Slack DM notifications
    - RCA and closure reminders

    Services are registered in dependency order to ensure proper initialization.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration.
    """
    logger.info("Starting CSOPM Services registration")

    # Import protocols inside function to avoid circular dependency
    # protocols.py -> csopm_protocols.py -> registrations/__init__.py -> csopm_services.py
    from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
        CSOPMJIRAPollerProtocol,
        CSOPMReminderServiceProtocol,
        CSOPMSlackNotifierProtocol,
        CSOPMStateTrackerProtocol,
    )

    # Import concrete implementations
    try:
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier
        from ketchup_csopm_notifier.services.state_tracker import CSOPMStateTracker
        from packages.integrations.async_mcp_client import AsyncMCPClient
        from packages.slack.messages.posting import SlackPostingHandler
        from packages.slack.user_operations.user_ops import SlackUserOps
    except ImportError as e:
        logger.warning(f"CSOPM services not available: {e}")
        return

    # Service 1: CSOPMStateTracker
    try:

        async def create_state_tracker(resolver) -> CSOPMStateTracker:
            """Factory function for CSOPMStateTracker using TypedResolver."""
            logger.info("Creating CSOPMStateTracker instance via TypedDI")
            async_client = await resolver.aget(DynamoDBAsyncClient)
            config = await resolver.aget(DynamoDBConfig)
            table_name = config.get_table_name()
            return CSOPMStateTracker(client=async_client, table_name=table_name)

        manager.register_protocol_with_concrete_alias(
            protocol_type=CSOPMStateTrackerProtocol,
            concrete_type=CSOPMStateTracker,
            factory=create_state_tracker,
            dependencies=[
                DependencySpec(DynamoDBAsyncClient),
                DependencySpec(DynamoDBConfig),
            ],
            lifetime="singleton",
        )
        logger.info("CSOPMStateTracker registered successfully")
    except Exception as e:
        logger.warning(f"CSOPMStateTracker registration failed: {e}")

    # Service 2: CSOPMJIRAPoller
    try:

        async def create_jira_poller(resolver) -> CSOPMJIRAPoller:
            """Factory function for CSOPMJIRAPoller using TypedResolver."""
            logger.info("Creating CSOPMJIRAPoller instance via TypedDI")
            mcp_client = await resolver.aget(AsyncMCPClient)
            return CSOPMJIRAPoller(mcp_client=mcp_client)

        manager.register_protocol_with_concrete_alias(
            protocol_type=CSOPMJIRAPollerProtocol,
            concrete_type=CSOPMJIRAPoller,
            factory=create_jira_poller,
            dependencies=[DependencySpec(AsyncMCPClient)],
            lifetime="singleton",
        )
        logger.info("CSOPMJIRAPoller registered successfully")
    except Exception as e:
        logger.warning(f"CSOPMJIRAPoller registration failed: {e}")

    # Service 3: CSOPMSlackNotifier (depends on StateTracker)
    try:

        async def create_slack_notifier(resolver) -> CSOPMSlackNotifier:
            """Factory function for CSOPMSlackNotifier using TypedResolver."""
            logger.info("Creating CSOPMSlackNotifier instance via TypedDI")
            posting_handler = await resolver.aget(SlackPostingHandler)
            user_ops = await resolver.aget(SlackUserOps)
            mcp_client = await resolver.aget(AsyncMCPClient)
            state_tracker = await resolver.aget(CSOPMStateTrackerProtocol)
            return CSOPMSlackNotifier(
                posting_handler=posting_handler,
                user_ops=user_ops,
                mcp_client=mcp_client,
                state_tracker=state_tracker,
                metrics=None,  # Metrics can be added later
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=CSOPMSlackNotifierProtocol,
            concrete_type=CSOPMSlackNotifier,
            factory=create_slack_notifier,
            dependencies=[
                DependencySpec(SlackPostingHandler),
                DependencySpec(SlackUserOps),
                DependencySpec(AsyncMCPClient),
                DependencySpec(CSOPMStateTrackerProtocol),
            ],
            lifetime="singleton",
        )
        logger.info("CSOPMSlackNotifier registered successfully")
    except Exception as e:
        logger.warning(f"CSOPMSlackNotifier registration failed: {e}")

    # Service 4: CSOPMReminderService (depends on StateTracker and JIRAPoller)
    try:

        async def create_reminder_service(resolver) -> CSOPMReminderService:
            """Factory function for CSOPMReminderService using TypedResolver."""
            logger.info("Creating CSOPMReminderService instance via TypedDI")
            state_tracker = await resolver.aget(CSOPMStateTrackerProtocol)
            mcp_client = await resolver.aget(AsyncMCPClient)
            jira_poller = await resolver.aget(CSOPMJIRAPollerProtocol)
            return CSOPMReminderService(
                state_tracker=state_tracker,
                mcp_client=mcp_client,
                jira_poller=jira_poller,
                metrics=None,  # Metrics can be added later
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=CSOPMReminderServiceProtocol,
            concrete_type=CSOPMReminderService,
            factory=create_reminder_service,
            dependencies=[
                DependencySpec(CSOPMStateTrackerProtocol),
                DependencySpec(AsyncMCPClient),
                DependencySpec(CSOPMJIRAPollerProtocol),
            ],
            lifetime="singleton",
        )
        logger.info("CSOPMReminderService registered successfully")
    except Exception as e:
        logger.warning(f"CSOPMReminderService registration failed: {e}")

    logger.info("CSOPM Services registration completed (4 services)")
