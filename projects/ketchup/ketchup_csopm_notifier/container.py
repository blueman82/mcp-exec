"""
CSOPM Notifier Container.

This module provides the TypedDI container for the CSOPM notification system.
It follows the async initialization pattern established in typed_di_integration.py
and registers all CSOPM services with their dependencies.

Architectural Note:
This container is designed to be used by the CSOPM notifier scheduler task.
It can either be initialized standalone or integrated with the main Ketchup
container by resolving shared dependencies (DynamoDBAsyncClient, AsyncMCPClient,
SlackPostingHandler, SlackUserOps) from the parent registry.

Service Registration Order (topological sort):
1. CSOPMStateTracker - No CSOPM dependencies (only DynamoDB)
2. CSOPMJIRAPoller - No CSOPM dependencies (only AsyncMCPClient)
3. CSOPMSlackNotifier - Depends on StateTracker, SlackPostingHandler, SlackUserOps, AsyncMCPClient
4. CSOPMReminderService - Depends on StateTracker, JIRAPoller, AsyncMCPClient

This ordering ensures all dependencies are resolved before their dependents.
"""

from typing import Optional

from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry
from packages.core.typed_di.protocols import (
    CSOPMJIRAPollerProtocol,
    CSOPMReminderServiceProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
)
from packages.core.typed_di.types import DependencySpec
from packages.db.config.dynamodb_config import DynamoDBConfig
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller
from ketchup_csopm_notifier.services.reminder_service import CSOPMReminderService
from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier
from ketchup_csopm_notifier.services.state_tracker import CSOPMStateTracker

logger = setup_logger(__name__)


async def get_csopm_container(
    parent_registry: Optional[TypedServiceRegistry] = None,
) -> TypedServiceRegistry:
    """
    Get a TypedServiceRegistry configured with CSOPM notifier services.

    This function creates and initializes a container for the CSOPM notification
    system. It can work in two modes:

    1. Standalone mode (parent_registry=None): Creates all dependencies internally.
       Useful for testing or isolated execution.

    2. Integrated mode (parent_registry provided): Resolves shared dependencies
       (DynamoDB, MCP, Slack) from the parent registry. This is the production
       pattern when running as part of the unified scheduler.

    Args:
        parent_registry: Optional parent TypedServiceRegistry to resolve shared
            dependencies from. If None, dependencies must be registered separately.

    Returns:
        TypedServiceRegistry configured with CSOPM services.

    Raises:
        RuntimeError: If initialization fails or required dependencies are missing.

    Example:
        # Standalone usage for testing
        container = await get_csopm_container()

        # Integrated usage with main container
        main_container = await get_unified_container()
        csopm_container = await get_csopm_container(parent_registry=main_container)
    """
    logger.info("Initializing CSOPM notifier container")

    # Create registry instance
    registry = TypedServiceRegistry()

    # Register CSOPM services
    _register_csopm_services(registry, parent_registry)

    # Initialize all services
    logger.info("Running CSOPM container initialize_all()")
    await registry.initialize_all()

    # Freeze registry after initialization
    registry.freeze_after_init()
    logger.info("CSOPM notifier container initialized and frozen")

    return registry


def _register_csopm_services(
    registry: TypedServiceRegistry,
    parent_registry: Optional[TypedServiceRegistry] = None,
) -> None:
    """
    Register all CSOPM notifier services in the provided registry.

    Follows the factory registration pattern with proper dependency specifications.
    Services are registered in topological order to ensure dependencies are
    resolved before their dependents.

    Args:
        registry: The TypedServiceRegistry to register services in.
        parent_registry: Optional parent registry to resolve shared dependencies from.
    """
    logger.info("Registering CSOPM notifier services")

    # Service 1: CSOPMStateTracker (no CSOPM dependencies)
    async def create_state_tracker(resolver) -> CSOPMStateTracker:
        """Factory function for CSOPMStateTracker."""
        logger.info("Creating CSOPMStateTracker via TypedDI")

        if parent_registry:
            async_client = await parent_registry.aget(DynamoDBAsyncClient)
            config = await parent_registry.aget(DynamoDBConfig)
        else:
            async_client = await resolver.aget(DynamoDBAsyncClient)
            config = await resolver.aget(DynamoDBConfig)

        table_name = config.get_table_name()
        return CSOPMStateTracker(client=async_client, table_name=table_name)

    registry.register(
        service_type=CSOPMStateTrackerProtocol,
        factory=create_state_tracker,
        dependencies=[
            DependencySpec(DynamoDBAsyncClient),
            DependencySpec(DynamoDBConfig),
        ],
        lifetime="singleton",
    )
    # Also register concrete type for direct resolution
    registry.register(
        service_type=CSOPMStateTracker,
        factory=create_state_tracker,
        dependencies=[
            DependencySpec(DynamoDBAsyncClient),
            DependencySpec(DynamoDBConfig),
        ],
        lifetime="singleton",
    )
    logger.info("CSOPMStateTracker registered")

    # Service 2: CSOPMJIRAPoller (no CSOPM dependencies)
    async def create_jira_poller(resolver) -> CSOPMJIRAPoller:
        """Factory function for CSOPMJIRAPoller."""
        logger.info("Creating CSOPMJIRAPoller via TypedDI")

        if parent_registry:
            mcp_client = await parent_registry.aget(AsyncMCPClient)
        else:
            mcp_client = await resolver.aget(AsyncMCPClient)

        return CSOPMJIRAPoller(mcp_client=mcp_client)

    registry.register(
        service_type=CSOPMJIRAPollerProtocol,
        factory=create_jira_poller,
        dependencies=[DependencySpec(AsyncMCPClient)],
        lifetime="singleton",
    )
    registry.register(
        service_type=CSOPMJIRAPoller,
        factory=create_jira_poller,
        dependencies=[DependencySpec(AsyncMCPClient)],
        lifetime="singleton",
    )
    logger.info("CSOPMJIRAPoller registered")

    # Service 3: CSOPMSlackNotifier (depends on StateTracker)
    async def create_slack_notifier(resolver) -> CSOPMSlackNotifier:
        """Factory function for CSOPMSlackNotifier."""
        logger.info("Creating CSOPMSlackNotifier via TypedDI")

        # Resolve Slack dependencies from parent or local registry
        if parent_registry:
            posting_handler = await parent_registry.aget(SlackPostingHandler)
            user_ops = await parent_registry.aget(SlackUserOps)
            mcp_client = await parent_registry.aget(AsyncMCPClient)
        else:
            posting_handler = await resolver.aget(SlackPostingHandler)
            user_ops = await resolver.aget(SlackUserOps)
            mcp_client = await resolver.aget(AsyncMCPClient)

        # StateTracker is always resolved from local registry
        state_tracker = await resolver.aget(CSOPMStateTrackerProtocol)

        return CSOPMSlackNotifier(
            posting_handler=posting_handler,
            user_ops=user_ops,
            mcp_client=mcp_client,
            state_tracker=state_tracker,
            metrics=None,  # Metrics can be added later if needed
        )

    registry.register(
        service_type=CSOPMSlackNotifierProtocol,
        factory=create_slack_notifier,
        dependencies=[
            DependencySpec(SlackPostingHandler),
            DependencySpec(SlackUserOps),
            DependencySpec(AsyncMCPClient),
            DependencySpec(CSOPMStateTrackerProtocol),
        ],
        lifetime="singleton",
    )
    registry.register(
        service_type=CSOPMSlackNotifier,
        factory=create_slack_notifier,
        dependencies=[
            DependencySpec(SlackPostingHandler),
            DependencySpec(SlackUserOps),
            DependencySpec(AsyncMCPClient),
            DependencySpec(CSOPMStateTrackerProtocol),
        ],
        lifetime="singleton",
    )
    logger.info("CSOPMSlackNotifier registered")

    # Service 4: CSOPMReminderService (depends on StateTracker and JIRAPoller)
    async def create_reminder_service(resolver) -> CSOPMReminderService:
        """Factory function for CSOPMReminderService."""
        logger.info("Creating CSOPMReminderService via TypedDI")

        # Resolve StateTracker and JIRAPoller from local registry
        state_tracker = await resolver.aget(CSOPMStateTrackerProtocol)
        jira_poller = await resolver.aget(CSOPMJIRAPollerProtocol)

        # Resolve MCP client from parent or local
        if parent_registry:
            mcp_client = await parent_registry.aget(AsyncMCPClient)
        else:
            mcp_client = await resolver.aget(AsyncMCPClient)

        return CSOPMReminderService(
            state_tracker=state_tracker,
            mcp_client=mcp_client,
            jira_poller=jira_poller,
            metrics=None,  # Metrics can be added later if needed
        )

    registry.register(
        service_type=CSOPMReminderServiceProtocol,
        factory=create_reminder_service,
        dependencies=[
            DependencySpec(CSOPMStateTrackerProtocol),
            DependencySpec(CSOPMJIRAPollerProtocol),
            DependencySpec(AsyncMCPClient),
        ],
        lifetime="singleton",
    )
    registry.register(
        service_type=CSOPMReminderService,
        factory=create_reminder_service,
        dependencies=[
            DependencySpec(CSOPMStateTrackerProtocol),
            DependencySpec(CSOPMJIRAPollerProtocol),
            DependencySpec(AsyncMCPClient),
        ],
        lifetime="singleton",
    )
    logger.info("CSOPMReminderService registered")

    logger.info("All CSOPM notifier services registered (4 services)")


async def get_csopm_state_tracker(
    registry: TypedServiceRegistry,
) -> CSOPMStateTrackerProtocol:
    """
    Convenience function to get the CSOPMStateTracker from a container.

    Args:
        registry: The TypedServiceRegistry containing CSOPM services.

    Returns:
        The resolved CSOPMStateTrackerProtocol instance.
    """
    return await registry.aget(CSOPMStateTrackerProtocol)


async def get_csopm_jira_poller(
    registry: TypedServiceRegistry,
) -> CSOPMJIRAPollerProtocol:
    """
    Convenience function to get the CSOPMJIRAPoller from a container.

    Args:
        registry: The TypedServiceRegistry containing CSOPM services.

    Returns:
        The resolved CSOPMJIRAPollerProtocol instance.
    """
    return await registry.aget(CSOPMJIRAPollerProtocol)


async def get_csopm_slack_notifier(
    registry: TypedServiceRegistry,
) -> CSOPMSlackNotifierProtocol:
    """
    Convenience function to get the CSOPMSlackNotifier from a container.

    Args:
        registry: The TypedServiceRegistry containing CSOPM services.

    Returns:
        The resolved CSOPMSlackNotifierProtocol instance.
    """
    return await registry.aget(CSOPMSlackNotifierProtocol)


async def get_csopm_reminder_service(
    registry: TypedServiceRegistry,
) -> CSOPMReminderServiceProtocol:
    """
    Convenience function to get the CSOPMReminderService from a container.

    Args:
        registry: The TypedServiceRegistry containing CSOPM services.

    Returns:
        The resolved CSOPMReminderServiceProtocol instance.
    """
    return await registry.aget(CSOPMReminderServiceProtocol)
