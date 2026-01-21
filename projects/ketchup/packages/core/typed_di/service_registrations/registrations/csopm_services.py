"""
CSOPM Services Registration Module.

Registers CSOPM (Customer Success Operations Project Management) notification services.

Core Services (always registered from packages/slack/csopm/ and interactive_elements/):
- CSOPMStateTracker: DynamoDB-backed notification state persistence
- CSOPMButtonActionHandler: Handler for interactive button actions from Slack DMs
- CSOPMHandler: Interactive element handler for CSOPM block actions and modals

Scheduler Services (only in ketchup_csopm_notifier, optional with ImportError handling):
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

Core services (always available from packages/slack/csopm/ and interactive_elements/):
1. CSOPMStateTracker (depends on DynamoDB infrastructure)
2. CSOPMButtonActionHandler (depends on StateTracker, Slack posting, MCP client)
3. CSOPMHandler (depends on ButtonActionHandler, MCP client, Slack posting)

Scheduler services (only in ketchup_csopm_notifier container):
4. CSOPMJIRAPoller (depends on AsyncMCPClient)
5. CSOPMSlackNotifier (depends on StateTracker, Slack infrastructure)
6. CSOPMReminderService (depends on StateTracker, JIRAPoller, MCP)
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
    - Button action handling for interactive Slack DMs
    - JIRA ticket polling (scheduler only)
    - Slack DM notifications (scheduler only)
    - RCA and closure reminders (scheduler only)

    Services are registered in dependency order to ensure proper initialization.

    Core services are imported from packages/slack/csopm/ and are always available.
    Scheduler services are imported from ketchup_csopm_notifier/ and are only
    available in the notifier container (registered with ImportError handling).

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration.
    """
    logger.info("Starting CSOPM Services registration")

    # Import protocols inside function to avoid circular dependency
    # protocols.py -> csopm_protocols.py -> registrations/__init__.py -> csopm_services.py
    from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
        CSOPMButtonActionHandlerProtocol,
        CSOPMHandlerProtocol,
        CSOPMJIRAPollerProtocol,
        CSOPMReminderServiceProtocol,
        CSOPMSlackNotifierProtocol,
        CSOPMStateTrackerProtocol,
        UserPATOperationsProtocol,
    )

    # ===========================================================================
    # Core Services (always available from packages/slack/csopm/)
    # These are shared components used by both ketchup-app and ketchup_csopm_notifier
    # ===========================================================================
    # Import core implementations from packages/slack/csopm/ and interactive_elements/
    # These imports should always succeed as they're part of the main packages
    from packages.db.operations.user_pat_operations import UserPATOperations
    from packages.integrations.async_mcp_client import AsyncMCPClient
    from packages.slack.csopm.actions import CSOPMButtonActionHandler
    from packages.slack.csopm.state import CSOPMStateTracker
    from packages.slack.interactive_elements.csopm_handler import CSOPMHandler
    from packages.slack.messages.posting import SlackPostingHandler

    # Service 1: CSOPMStateTracker (core service - always register)
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

    # Service 1b: UserPATOperations (core service - always register)
    # Stores user JIRA PATs with 1-hour TTL for authenticating JIRA operations
    try:

        async def create_user_pat_operations(resolver) -> UserPATOperations:
            """Factory function for UserPATOperations using TypedResolver."""
            logger.info("Creating UserPATOperations instance via TypedDI")
            async_client = await resolver.aget(DynamoDBAsyncClient)
            config = await resolver.aget(DynamoDBConfig)
            table_name = config.get_table_name()
            return UserPATOperations(client=async_client, table_name=table_name)

        manager.register_protocol_with_concrete_alias(
            protocol_type=UserPATOperationsProtocol,
            concrete_type=UserPATOperations,
            factory=create_user_pat_operations,
            dependencies=[
                DependencySpec(DynamoDBAsyncClient),
                DependencySpec(DynamoDBConfig),
            ],
            lifetime="singleton",
        )
        logger.info("UserPATOperations registered successfully")
    except Exception as e:
        logger.warning(f"UserPATOperations registration failed: {e}")

    # Service 2: CSOPMButtonActionHandler (core service - always register)
    # Depends on CSOPMStateTrackerProtocol and UserPATOperationsProtocol
    try:

        async def create_button_action_handler(resolver) -> CSOPMButtonActionHandler:
            """Factory function for CSOPMButtonActionHandler using TypedResolver."""
            logger.info("Creating CSOPMButtonActionHandler instance via TypedDI")
            posting_handler = await resolver.aget(SlackPostingHandler)
            mcp_client = await resolver.aget(AsyncMCPClient)
            state_tracker = await resolver.aget(CSOPMStateTrackerProtocol)
            user_pat_ops = await resolver.aget(UserPATOperationsProtocol)
            return CSOPMButtonActionHandler(
                posting_handler=posting_handler,
                mcp_client=mcp_client,
                state_tracker=state_tracker,
                user_pat_ops=user_pat_ops,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=CSOPMButtonActionHandlerProtocol,
            concrete_type=CSOPMButtonActionHandler,
            factory=create_button_action_handler,
            dependencies=[
                DependencySpec(SlackPostingHandler),
                DependencySpec(AsyncMCPClient),
                DependencySpec(CSOPMStateTrackerProtocol),
                DependencySpec(UserPATOperationsProtocol),
            ],
            lifetime="singleton",
        )
        logger.info("CSOPMButtonActionHandler registered successfully")
    except Exception as e:
        logger.warning(f"CSOPMButtonActionHandler registration failed: {e}")

    # Service 3: CSOPMHandler (core service - always register)
    # Depends on CSOPMButtonActionHandlerProtocol and UserPATOperationsProtocol
    try:

        async def create_csopm_handler(resolver) -> CSOPMHandler:
            """Factory function for CSOPMHandler using TypedResolver."""
            logger.info("Creating CSOPMHandler instance via TypedDI")
            button_handler = await resolver.aget(CSOPMButtonActionHandlerProtocol)
            mcp_client = await resolver.aget(AsyncMCPClient)
            posting_handler = await resolver.aget(SlackPostingHandler)
            user_pat_ops = await resolver.aget(UserPATOperationsProtocol)
            return CSOPMHandler(
                button_handler=button_handler,
                mcp_client=mcp_client,
                posting_handler=posting_handler,
                user_pat_ops=user_pat_ops,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=CSOPMHandlerProtocol,
            concrete_type=CSOPMHandler,
            factory=create_csopm_handler,
            dependencies=[
                DependencySpec(CSOPMButtonActionHandlerProtocol),
                DependencySpec(AsyncMCPClient),
                DependencySpec(SlackPostingHandler),
                DependencySpec(UserPATOperationsProtocol),
            ],
            lifetime="singleton",
        )
        logger.info("CSOPMHandler registered successfully")
    except Exception as e:
        logger.warning(f"CSOPMHandler registration failed: {e}")

    # ===========================================================================
    # Scheduler Services (only in ketchup_csopm_notifier container)
    # These are only available when running in the CSOPM notifier service
    # ===========================================================================

    # Try to import scheduler services from ketchup_csopm_notifier/
    # These may not be available in ketchup-app or other containers
    try:
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier
        from packages.slack.user_operations.user_ops import SlackUserOps
    except ImportError as e:
        logger.info(f"Scheduler services not available (not in ketchup_csopm_notifier): {e}")
        logger.info("CSOPM Core Services registration completed (3 services)")
        return

    # Service 4: CSOPMJIRAPoller (scheduler service)
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

    # Service 5: CSOPMSlackNotifier (scheduler service, depends on StateTracker)
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

    # Service 6: CSOPMReminderService (scheduler service, depends on StateTracker and JIRAPoller)
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

    logger.info("CSOPM Services registration completed (6 services)")
