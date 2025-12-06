"""
Maintenance Detection Service Registrations.

Registers maintenance detection services using protocol-first pattern:
- Raven SOAP client for maintenance data
- Maintenance checker for instance matching
- JIRA prompt handler for workflow orchestration
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Import protocols
from ..protocols import (
    DynamoDBStoreProtocol,
    JiraPromptHandlerProtocol,
    MaintenanceCheckerProtocol,
    MCPClientProtocol,
    RavenMaintenanceClientProtocol,
    SecretsManagerProtocol,
    SlackChannelMessageOpsProtocol,
    SlackPostingHandlerProtocol,
)

if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

logger = setup_logger(__name__)


def register_maintenance_services(manager: "ServiceRegistrationManager") -> None:
    """
    Register maintenance detection services.

    Args:
        manager: ServiceRegistrationManager instance
    """
    logger.info("Starting Maintenance Detection Services registration")

    # RavenMaintenanceClient
    try:
        from packages.integrations.raven_maintenance import RavenMaintenanceClient

        async def create_raven_client(resolver) -> RavenMaintenanceClient:
            """Factory function for RavenMaintenanceClient using TypedResolver."""
            logger.info("Creating RavenMaintenanceClient instance via TypedDI")
            secrets_manager = await resolver.aget(SecretsManagerProtocol)
            secrets = await secrets_manager.get_secret_async("Ketchup_Token_Secrets")

            # Get endpoint from secrets and ensure it has Adobe Campaign SOAP path
            endpoint = secrets.get(
                "raven_maintenance_endpoint", "https://raven-rt-prod2.campaign.adobe.com"
            )
            # Append Adobe Campaign SOAP router path if not already present
            if not endpoint.endswith("/nl/jsp/soaprouter.jsp"):
                endpoint = f"{endpoint}/nl/jsp/soaprouter.jsp"

            return RavenMaintenanceClient(
                endpoint=endpoint,
                username=secrets.get("raven_maintenance_email_username"),
                password=secrets.get("raven_maintenance_email_password"),
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=RavenMaintenanceClientProtocol,
            concrete_type=RavenMaintenanceClient,
            factory=create_raven_client,
            dependencies=[DependencySpec(SecretsManagerProtocol)],
            lifetime="singleton",
        )
        logger.info("RavenMaintenanceClient registered successfully")
    except ImportError as e:
        logger.warning(f"RavenMaintenanceClient not available: {e}")

    # MaintenanceChecker
    try:
        from packages.ai.maintenance_checker import MaintenanceChecker

        async def create_maintenance_checker(resolver) -> MaintenanceChecker:
            """Factory function for MaintenanceChecker using TypedResolver."""
            logger.info("Creating MaintenanceChecker instance via TypedDI")
            db_store = await resolver.aget(DynamoDBStoreProtocol)

            return MaintenanceChecker(dynamodb_store=db_store)

        manager.register_protocol_with_concrete_alias(
            protocol_type=MaintenanceCheckerProtocol,
            concrete_type=MaintenanceChecker,
            factory=create_maintenance_checker,
            dependencies=[
                DependencySpec(DynamoDBStoreProtocol),
            ],
            lifetime="singleton",
        )
        logger.info("MaintenanceChecker registered successfully")
    except ImportError as e:
        logger.warning(f"MaintenanceChecker not available: {e}")

    # JiraPromptHandler
    try:
        from packages.slack.maintenance.jira_prompt_handler import JiraPromptHandler

        async def create_jira_prompt_handler(resolver) -> JiraPromptHandler:
            """Factory function for JiraPromptHandler using TypedResolver."""
            logger.info("Creating JiraPromptHandler instance via TypedDI")
            posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
            maintenance_checker = await resolver.aget(MaintenanceCheckerProtocol)
            db_store = await resolver.aget(DynamoDBStoreProtocol)
            mcp_client = await resolver.aget(MCPClientProtocol)
            channel_msg_ops = await resolver.aget(SlackChannelMessageOpsProtocol)
            secrets_manager = await resolver.aget(SecretsManagerProtocol)

            return JiraPromptHandler(
                posting_handler=posting_handler,
                maintenance_checker=maintenance_checker,
                db_store=db_store,
                mcp_client=mcp_client,
                channel_msg_ops=channel_msg_ops,
                secrets_manager=secrets_manager,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=JiraPromptHandlerProtocol,
            concrete_type=JiraPromptHandler,
            factory=create_jira_prompt_handler,
            dependencies=[
                DependencySpec(SlackPostingHandlerProtocol),
                DependencySpec(MaintenanceCheckerProtocol),
                DependencySpec(DynamoDBStoreProtocol),
                DependencySpec(MCPClientProtocol),
                DependencySpec(SlackChannelMessageOpsProtocol),
                DependencySpec(SecretsManagerProtocol),
            ],
            lifetime="singleton",
        )
        logger.info("JiraPromptHandler registered successfully")
    except ImportError as e:
        logger.warning(f"JiraPromptHandler not available: {e}")

    logger.info("Maintenance Detection Services registration completed")
