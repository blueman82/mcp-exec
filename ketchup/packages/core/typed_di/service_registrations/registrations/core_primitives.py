"""
Core Primitives Registration Module

Registers fundamental services that form the foundation of the dependency system:
- SecretsManager (no dependencies)
- SlackConfig (depends on SecretsManager)
- DynamoDB trio (DynamoDBConfig, DynamoDBAsyncClient, DynamoDBStore)
- UserStore (depends on DynamoDB trio)
- SlackAuth and SlackAsyncClient (depends on SlackConfig/SecretsManager)
- RestoreStateManager (depends on DynamoDBStore)

These are production-critical services that must be available for the system to function.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Essential imports for core primitives (with try/except for optional modules)
try:
    from packages.db.config.dynamodb_config import DynamoDBConfig
    from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
    from packages.db.dynamodb_store import DynamoDBStore
    from packages.db.user_store import UserStore
    from packages.secrets.manager import SecretsManager
    from packages.slack.authorisation.auth import SlackAuth
    from packages.slack.channel_operations.restore_state_manager import RestoreStateManager
    from packages.slack.config.slack_config import SlackConfig
    from packages.slack.core.slack_async_client import SlackAsyncClient
    from packages.slack.messages.posting import SlackPostingHandler
except ImportError:
    # Allow module to load even with missing imports for testing
    pass

# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import protocols from the protocols module to avoid circular dependencies
from ..protocols import (
    DynamoDBAsyncClientProtocol,
    DynamoDBConfigProtocol,
    DynamoDBStoreProtocol,
    RestoreStateManagerProtocol,
    SecretsManagerProtocol,
    SlackAsyncClientProtocol,
    SlackAuthProtocol,
    SlackConfigProtocol,
    SlackPostingHandlerProtocol,
    UserStoreProtocol,
)

logger = setup_logger(__name__)


def register_core_primitives(manager: "ServiceRegistrationManager") -> None:
    """
    Register core primitive services that form the foundation of the system.

    These services are production-critical and must be available for the system
    to function. Registration order is important due to dependencies.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical service registration fails
    """
    logger.info("Registering core primitive services")

    # Register services in dependency order
    _register_secrets_and_config(manager)
    _register_dynamodb_trio(manager)
    _register_slack_auth_services(manager)
    _register_utility_services(manager)

    logger.info("Core primitive services registered successfully (9 essential services)")


def _register_secrets_and_config(manager: "ServiceRegistrationManager") -> None:
    """Register SecretsManager, SlackConfig, and SlackPostingHandler."""
    # SecretsManager (no dependencies) - foundation service
    manager.register_protocol_with_concrete_alias(
        protocol_type=SecretsManagerProtocol,
        concrete_type=SecretsManager,
        factory=lambda resolver: SecretsManager(),
        dependencies=[],
        lifetime="singleton",
        essential=True,
    )

    # SlackConfig factory using TypedResolver
    async def create_slack_config(resolver) -> SlackConfig:
        """Factory function for SlackConfig using TypedResolver."""
        logger.info("Creating SlackConfig instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)
        return await SlackConfig.create(secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackConfigProtocol,
        concrete_type=SlackConfig,
        factory=create_slack_config,
        dependencies=[DependencySpec(SecretsManager)],
        lifetime="singleton",
        essential=True,
    )

    # SlackPostingHandler (critical service causing production errors)
    async def create_slack_posting_handler(resolver) -> SlackPostingHandler:
        """Factory function for SlackPostingHandler using TypedResolver."""
        logger.info("Creating SlackPostingHandler instance via TypedDI")
        slack_config = await resolver.aget(SlackConfig)
        secrets_manager = await resolver.aget(SecretsManager)

        if slack_config is None:
            msg = "Slack config missing for SlackPostingHandler"
            logger.error(msg)
            raise RuntimeError(msg)
        if secrets_manager is None:
            msg = "Secrets manager missing for SlackPostingHandler"
            logger.error(msg)
            raise RuntimeError(msg)

        instance = SlackPostingHandler(
            slack_config=slack_config,
            secrets_manager=secrets_manager,
        )
        logger.info("SlackPostingHandler instance created successfully via TypedDI")
        return instance

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackPostingHandlerProtocol,
        concrete_type=SlackPostingHandler,
        factory=create_slack_posting_handler,
        dependencies=[DependencySpec(SlackConfig), DependencySpec(SecretsManager)],
        lifetime="singleton",
        essential=True,
    )


def _register_dynamodb_trio(manager: "ServiceRegistrationManager") -> None:
    """Register DynamoDBConfig, DynamoDBAsyncClient, DynamoDBStore, and UserStore."""
    # DynamoDBConfig (no dependencies) - Critical for DB operations
    async def create_dynamodb_config(resolver) -> DynamoDBConfig:
        """Factory function for DynamoDBConfig using TypedResolver."""
        logger.info("Creating DynamoDBConfig instance via TypedDI")
        return DynamoDBConfig()

    manager.register_protocol_with_concrete_alias(
        protocol_type=DynamoDBConfigProtocol,
        concrete_type=DynamoDBConfig,
        factory=create_dynamodb_config,
        dependencies=[],
        lifetime="singleton",
        essential=True,
    )

    # DynamoDBAsyncClient (depends on DynamoDBConfig)
    async def create_dynamodb_async_client(resolver) -> DynamoDBAsyncClient:
        """Factory function for DynamoDBAsyncClient using TypedResolver."""
        logger.info("Creating DynamoDBAsyncClient instance via TypedDI")
        config = await resolver.aget(DynamoDBConfig)
        return DynamoDBAsyncClient(config=config)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DynamoDBAsyncClientProtocol,
        concrete_type=DynamoDBAsyncClient,
        factory=create_dynamodb_async_client,
        dependencies=[DependencySpec(DynamoDBConfig)],
        lifetime="singleton",
        essential=True,
    )

    # DynamoDBStore (depends on DynamoDBAsyncClient and DynamoDBConfig)
    async def create_dynamodb_store(resolver) -> DynamoDBStore:
        """Factory function for DynamoDBStore - PRODUCTION CRITICAL."""
        logger.info("Creating DynamoDBStore instance via TypedDI")
        async_client = await resolver.aget(DynamoDBAsyncClient)
        config = await resolver.aget(DynamoDBConfig)
        table_name = config.get_table_name()
        return DynamoDBStore(client=async_client, table_name=table_name)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DynamoDBStoreProtocol,
        concrete_type=DynamoDBStore,
        factory=create_dynamodb_store,
        dependencies=[
            DependencySpec(DynamoDBAsyncClient),
            DependencySpec(DynamoDBConfig),
        ],
        lifetime="singleton",
        essential=True,
    )

    # UserStore with protocol - High-traffic service
    async def create_user_store(resolver) -> UserStore:
        """Factory function for UserStore using TypedResolver."""
        logger.info("Creating UserStore instance via TypedDI")
        async_client = await resolver.aget(DynamoDBAsyncClient)
        config = await resolver.aget(DynamoDBConfig)
        table_name = config.get_table_name()
        return UserStore(client=async_client, table_name=table_name)

    manager.register_protocol_with_concrete_alias(
        protocol_type=UserStoreProtocol,
        concrete_type=UserStore,
        factory=create_user_store,
        dependencies=[
            DependencySpec(DynamoDBAsyncClient),
            DependencySpec(DynamoDBConfig),
        ],
        lifetime="singleton",
        essential=True,
    )


def _register_slack_auth_services(manager: "ServiceRegistrationManager") -> None:
    """Register SlackAuth and SlackAsyncClient services."""
    # SlackAuth with protocol - High-traffic service
    async def create_slack_auth(resolver) -> SlackAuth:
        """Factory function for SlackAuth using TypedResolver."""
        logger.info("Creating SlackAuth instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)
        return SlackAuth(secrets_manager=secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackAuthProtocol,
        concrete_type=SlackAuth,
        factory=create_slack_auth,
        dependencies=[DependencySpec(SlackConfig), DependencySpec(SecretsManager)],
        lifetime="singleton",
        essential=True,
    )

    # SlackAsyncClient with protocol - High-traffic service
    async def create_slack_async_client(resolver) -> SlackAsyncClient:
        """Factory function for SlackAsyncClient using TypedResolver."""
        logger.info("Creating SlackAsyncClient instance via TypedDI")
        slack_config = await resolver.aget(SlackConfig)
        return SlackAsyncClient(slack_config=slack_config)

    manager.register_protocol_with_concrete_alias(
        protocol_type=SlackAsyncClientProtocol,
        concrete_type=SlackAsyncClient,
        factory=create_slack_async_client,
        dependencies=[DependencySpec(SlackConfig)],
        lifetime="singleton",
        essential=True,
    )


def _register_utility_services(manager: "ServiceRegistrationManager") -> None:
    """Register utility services like RestoreStateManager."""
    # RestoreStateManager with protocol
    async def create_restore_state_manager(resolver) -> RestoreStateManager:
        """Factory function for RestoreStateManager using TypedResolver."""
        logger.info("Creating RestoreStateManager instance via TypedDI")
        dynamodb_store = await resolver.aget(DynamoDBStore)
        return RestoreStateManager(dynamodb_store=dynamodb_store)

    manager.register_protocol_with_concrete_alias(
        protocol_type=RestoreStateManagerProtocol,
        concrete_type=RestoreStateManager,
        factory=create_restore_state_manager,
        dependencies=[DependencySpec(DynamoDBStore)],
        lifetime="singleton",
        essential=True,
    )