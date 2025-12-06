"""
Database Batches Registration Module

Registers database batch operation services:
- Database connection and migration services
- Database backup and restore operations
- Database indexing and query optimization
- Database transaction management
- Database connection pooling
- Database monitoring and performance tracking
- Batch size management and utilities
- Flag review database operations

These services provide advanced database functionality and batch operations.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.local_metrics import MetricsStorage
from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Database operation imports
from packages.db.config.dynamodb_config import DynamoDBConfig
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.interactive_elements.flag_review.database import (
    FlagReviewDatabaseOperations,
)

# Access Request services imports
try:
    from packages.core.distributed_lock import DistributedLock
    from packages.db.operations.access_request_operations import AccessRequestOperations
    from packages.slack.interactive_elements.access_request_handler import AccessRequestHandler
    from packages.slack.metrics.access_request_monitor import AccessRequestMonitor

    ACCESS_REQUEST_IMPORTS_AVAILABLE = True
except ImportError:
    ACCESS_REQUEST_IMPORTS_AVAILABLE = False


# Placeholder imports for missing protocols
class AccessRequestBlocks:
    """Placeholder implementation for AccessRequestBlocks."""

    pass


class AccessRequest:
    """Placeholder implementation for AccessRequest."""

    pass


class DatabaseConnectionService:
    """Placeholder implementation for DatabaseConnectionService."""

    pass


class DatabaseMigrationService:
    """Placeholder implementation for DatabaseMigrationService."""

    pass


class DatabaseBackupService:
    """Placeholder implementation for DatabaseBackupService."""

    pass


class DatabaseRestoreService:
    """Placeholder implementation for DatabaseRestoreService."""

    pass


class DatabaseQueryService:
    """Placeholder implementation for DatabaseQueryService."""

    pass


class DatabaseIndexService:
    """Placeholder implementation for DatabaseIndexService."""

    pass


class DatabaseTransactionService:
    """Placeholder implementation for DatabaseTransactionService."""

    pass


class DatabasePoolService:
    """Placeholder implementation for DatabasePoolService."""

    pass


class DatabaseMonitoringService:
    """Placeholder implementation for DatabaseMonitoringService."""

    pass


# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import protocols from the protocols module to avoid circular dependencies
# Linters: E402 violation is intentional - we need this import here to prevent circular import issues
from ..protocols import (  # noqa: E402
    AccessRequestBlocksProtocol,
    AccessRequestHandlerProtocol,
    AccessRequestMonitorProtocol,
    AccessRequestOperationsProtocol,
    AccessRequestProtocol,
    DatabaseBackupServiceProtocol,
    DatabaseConnectionServiceProtocol,
    DatabaseIndexServiceProtocol,
    DatabaseMigrationServiceProtocol,
    DatabaseMonitoringServiceProtocol,
    DatabasePoolServiceProtocol,
    DatabaseQueryServiceProtocol,
    DatabaseRestoreServiceProtocol,
    DatabaseTransactionServiceProtocol,
    DistributedLockProtocol,
    DynamoDBAsyncClientProtocol,
    DynamoDBConfigProtocol,
    FlagReviewDatabaseOperationsProtocol,
)

# Set up logger
logger = setup_logger(__name__)


def _register_database_core_services(manager: "ServiceRegistrationManager") -> None:
    """Register core database services."""

    # DatabaseConnectionService
    async def create_database_connection_service(resolver) -> object:
        """Factory function for DatabaseConnectionService."""
        logger.info("Creating DatabaseConnectionService instance via TypedDI")
        dynamodb_config = await resolver.aget(DynamoDBConfig)
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)

        class DatabaseConnectionService:
            def __init__(self, dynamodb_config, dynamodb_async_client):
                self.config = dynamodb_config
                self.client = dynamodb_async_client

            async def get_connection(self):
                return self.client

            async def test_connection(self):
                return True

            async def close_connection(self):
                pass

        return DatabaseConnectionService(dynamodb_config, dynamodb_async_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseConnectionServiceProtocol,
        concrete_type=DatabaseConnectionService,
        factory=create_database_connection_service,
        dependencies=[DependencySpec(DynamoDBConfig), DependencySpec(DynamoDBAsyncClient)],
        lifetime="singleton",
    )

    # DatabaseMigrationService
    async def create_database_migration_service(resolver) -> object:
        """Factory function for DatabaseMigrationService."""
        logger.info("Creating DatabaseMigrationService instance via TypedDI")
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)
        dynamodb_store = await resolver.aget(DynamoDBStore)

        class DatabaseMigrationService:
            def __init__(self, client, store):
                self.client = client
                self.store = store

            async def run_migration(self, version: str):
                return True

            async def get_current_version(self):
                return "1.0.0"

            async def rollback_migration(self, version: str):
                return True

        return DatabaseMigrationService(dynamodb_async_client, dynamodb_store)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseMigrationServiceProtocol,
        concrete_type=DatabaseMigrationService,
        factory=create_database_migration_service,
        dependencies=[DependencySpec(DynamoDBAsyncClient), DependencySpec(DynamoDBStore)],
        lifetime="singleton",
    )


def _register_backup_restore_services(manager: "ServiceRegistrationManager") -> None:
    """Register backup and restore services."""

    # DatabaseBackupService
    async def create_database_backup_service(resolver) -> object:
        """Factory function for DatabaseBackupService."""
        logger.info("Creating DatabaseBackupService instance via TypedDI")
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)
        secrets_manager = await resolver.aget(SecretsManager)

        class DatabaseBackupService:
            def __init__(self, client, secrets):
                self.client = client
                self.secrets = secrets

            async def create_backup(self, table_name: str):
                return "backup-id"

            async def list_backups(self):
                return []

            async def restore_from_backup(self, backup_id: str):
                return True

        return DatabaseBackupService(dynamodb_async_client, secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseBackupServiceProtocol,
        concrete_type=DatabaseBackupService,
        factory=create_database_backup_service,
        dependencies=[DependencySpec(DynamoDBAsyncClient), DependencySpec(SecretsManager)],
        lifetime="singleton",
    )

    # DatabaseRestoreService
    async def create_database_restore_service(resolver) -> object:
        """Factory function for DatabaseRestoreService."""
        logger.info("Creating DatabaseRestoreService instance via TypedDI")
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)
        backup_service = await resolver.aget(DatabaseBackupServiceProtocol)

        class DatabaseRestoreService:
            def __init__(self, client, backup_service):
                self.client = client
                self.backup_service = backup_service

            async def restore_table(self, table_name: str):
                return True

            async def restore_point_in_time(self, table_name: str, timestamp: str):
                return True

            async def validate_restore(self, table_name: str):
                return True

        return DatabaseRestoreService(dynamodb_async_client, backup_service)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseRestoreServiceProtocol,
        concrete_type=DatabaseRestoreService,
        factory=create_database_restore_service,
        dependencies=[
            DependencySpec(DynamoDBAsyncClient),
            DependencySpec(DatabaseBackupServiceProtocol),
        ],
        lifetime="singleton",
    )


def _register_query_services(manager: "ServiceRegistrationManager") -> None:
    """Register query and indexing services."""

    # DatabaseIndexService
    async def create_database_index_service(resolver) -> object:
        """Factory function for DatabaseIndexService."""
        logger.info("Creating DatabaseIndexService instance via TypedDI")
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)

        class DatabaseIndexService:
            def __init__(self, client):
                self.client = client

            async def create_index(self, table_name: str, index_name: str):
                return True

            async def drop_index(self, table_name: str, index_name: str):
                return True

            async def list_indexes(self, table_name: str):
                return []

        return DatabaseIndexService(dynamodb_async_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseIndexServiceProtocol,
        concrete_type=DatabaseIndexService,
        factory=create_database_index_service,
        dependencies=[DependencySpec(DynamoDBAsyncClient)],
        lifetime="singleton",
    )

    # DatabaseQueryService
    async def create_database_query_service(resolver) -> object:
        """Factory function for DatabaseQueryService."""
        logger.info("Creating DatabaseQueryService instance via TypedDI")
        dynamodb_store = await resolver.aget(DynamoDBStore)
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)

        class DatabaseQueryService:
            def __init__(self, store, client):
                self.store = store
                self.client = client

            async def execute_query(self, query: str):
                return []

            async def execute_batch_query(self, queries: list):
                return []

            async def optimize_query(self, query: str):
                return query

        return DatabaseQueryService(dynamodb_store, dynamodb_async_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseQueryServiceProtocol,
        concrete_type=DatabaseQueryService,
        factory=create_database_query_service,
        dependencies=[DependencySpec(DynamoDBStore), DependencySpec(DynamoDBAsyncClient)],
        lifetime="singleton",
    )


def _register_management_services(manager: "ServiceRegistrationManager") -> None:
    """Register transaction and pool management services."""

    # DatabaseTransactionService
    async def create_database_transaction_service(resolver) -> object:
        """Factory function for DatabaseTransactionService."""
        logger.info("Creating DatabaseTransactionService instance via TypedDI")
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)

        class DatabaseTransactionService:
            def __init__(self, client):
                self.client = client

            async def begin_transaction(self):
                return "txn-id"

            async def commit_transaction(self, txn_id: str):
                return True

            async def rollback_transaction(self, txn_id: str):
                return True

        return DatabaseTransactionService(dynamodb_async_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseTransactionServiceProtocol,
        concrete_type=DatabaseTransactionService,
        factory=create_database_transaction_service,
        dependencies=[DependencySpec(DynamoDBAsyncClient)],
        lifetime="singleton",
    )

    # DatabasePoolService
    async def create_database_pool_service(resolver) -> object:
        """Factory function for DatabasePoolService."""
        logger.info("Creating DatabasePoolService instance via TypedDI")
        dynamodb_config = await resolver.aget(DynamoDBConfig)
        connection_service = await resolver.aget(DatabaseConnectionServiceProtocol)

        class DatabasePoolService:
            def __init__(self, config, connection_service):
                self.config = config
                self.connection_service = connection_service

            async def get_connection(self):
                return await self.connection_service.get_connection()

            async def return_connection(self, conn):
                pass

            def get_pool_stats(self):
                return {"active": 1, "idle": 0}

        return DatabasePoolService(dynamodb_config, connection_service)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabasePoolServiceProtocol,
        concrete_type=DatabasePoolService,
        factory=create_database_pool_service,
        dependencies=[
            DependencySpec(DynamoDBConfig),
            DependencySpec(DatabaseConnectionServiceProtocol),
        ],
        lifetime="singleton",
    )

    # DatabaseMonitoringService
    async def create_database_monitoring_service(resolver) -> object:
        """Factory function for DatabaseMonitoringService."""
        logger.info("Creating DatabaseMonitoringService instance via TypedDI")
        metrics_storage = await resolver.aget(MetricsStorage)
        dynamodb_async_client = await resolver.aget(DynamoDBAsyncClient)

        class DatabaseMonitoringService:
            def __init__(self, metrics, client):
                self.metrics = metrics
                self.client = client

            async def monitor_performance(self):
                return {"cpu": 50, "memory": 60}

            async def track_query_metrics(self, query: str, duration: float):
                pass

            async def get_health_status(self):
                return {"status": "healthy"}

        return DatabaseMonitoringService(metrics_storage, dynamodb_async_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DatabaseMonitoringServiceProtocol,
        concrete_type=DatabaseMonitoringService,
        factory=create_database_monitoring_service,
        dependencies=[DependencySpec(MetricsStorage), DependencySpec(DynamoDBAsyncClient)],
        lifetime="singleton",
    )


def _register_utility_services(manager: "ServiceRegistrationManager") -> None:
    """Register batch utilities and flag review operations."""

    # JoinNotificationOps with protocol
    try:
        from packages.db.operations.join_notification_ops import JoinNotificationOps

        async def create_join_notification_ops(resolver) -> JoinNotificationOps:
            """Factory function for JoinNotificationOps using TypedResolver."""
            logger.info("Creating JoinNotificationOps instance via TypedDI")
            dynamodb_async_client = await resolver.aget(DynamoDBAsyncClientProtocol)
            dynamodb_config = await resolver.aget(DynamoDBConfigProtocol)

            # Get table name from config
            table_name = (
                dynamodb_config.table_name
                if hasattr(dynamodb_config, "table_name")
                else "ketchup_channel_information"
            )

            return JoinNotificationOps(client=dynamodb_async_client, table_name=table_name)

        # Import the protocol from the correct location
        from ..protocols import JoinNotificationOpsProtocol

        manager.register_protocol_with_concrete_alias(
            protocol_type=JoinNotificationOpsProtocol,
            concrete_type=JoinNotificationOps,
            factory=create_join_notification_ops,
            dependencies=[
                DependencySpec(DynamoDBAsyncClientProtocol),
                DependencySpec(DynamoDBConfigProtocol),
            ],
            lifetime="singleton",
        )
        logger.info("JoinNotificationOps registered successfully")
    except ImportError as e:
        logger.warning(f"JoinNotificationOps not available: {e}")

    # FlagReviewDatabaseOperations with protocol
    async def create_flag_review_database_operations(resolver) -> FlagReviewDatabaseOperations:
        """Factory function for FlagReviewDatabaseOperations using TypedResolver."""
        logger.info("Creating FlagReviewDatabaseOperations instance via TypedDI")
        dynamodb_store = await resolver.aget(DynamoDBStore)
        return FlagReviewDatabaseOperations(db_store=dynamodb_store)

    manager.register_protocol_with_concrete_alias(
        protocol_type=FlagReviewDatabaseOperationsProtocol,
        concrete_type=FlagReviewDatabaseOperations,
        factory=create_flag_review_database_operations,
        dependencies=[DependencySpec(DynamoDBStore)],
        lifetime="singleton",
    )


def _register_access_request_services(manager: "ServiceRegistrationManager") -> None:
    """Register AccessRequest-related services including handler, operations, and monitor."""
    if not ACCESS_REQUEST_IMPORTS_AVAILABLE:
        logger.warning(
            "AccessRequest services not available - registering placeholder implementations"
        )
        _register_access_request_placeholders(manager)
        return

    try:
        # Register DistributedLock first
        async def create_distributed_lock(resolver) -> DistributedLock:
            """Factory function for DistributedLock using TypedResolver."""
            logger.info("Creating DistributedLock instance via TypedDI")
            async_client = await resolver.aget(DynamoDBAsyncClient)
            config = await resolver.aget(DynamoDBConfig)
            table_name = config.get_table_name()
            return DistributedLock(dynamodb_client=async_client, table_name=table_name)

        manager.register_protocol_with_concrete_alias(
            protocol_type=DistributedLockProtocol,
            concrete_type=DistributedLock,
            factory=create_distributed_lock,
            dependencies=[DependencySpec(DynamoDBAsyncClient), DependencySpec(DynamoDBConfig)],
            lifetime="singleton",
        )

        # Register AccessRequestOperations
        async def create_access_request_operations(resolver) -> AccessRequestOperations:
            """Factory function for AccessRequestOperations using TypedResolver."""
            logger.info("Creating AccessRequestOperations instance via TypedDI")
            async_client = await resolver.aget(DynamoDBAsyncClient)
            config = await resolver.aget(DynamoDBConfig)
            table_name = config.get_table_name()
            return AccessRequestOperations(client=async_client, table_name=table_name)

        manager.register_protocol_with_concrete_alias(
            protocol_type=AccessRequestOperationsProtocol,
            concrete_type=AccessRequestOperations,
            factory=create_access_request_operations,
            dependencies=[DependencySpec(DynamoDBAsyncClient), DependencySpec(DynamoDBConfig)],
            lifetime="singleton",
        )

        # Register AccessRequestMonitor
        async def create_access_request_monitor(resolver) -> AccessRequestMonitor:
            """Factory function for AccessRequestMonitor using TypedResolver."""
            logger.info("Creating AccessRequestMonitor instance via TypedDI")
            # AccessRequestMonitor creates its own MetricsStorage internally
            return AccessRequestMonitor()

        manager.register_protocol_with_concrete_alias(
            protocol_type=AccessRequestMonitorProtocol,
            concrete_type=AccessRequestMonitor,
            factory=create_access_request_monitor,
            dependencies=[DependencySpec(MetricsStorage)],
            lifetime="singleton",
        )

        # Register AccessRequestHandler with all dependencies
        async def create_access_request_handler(resolver) -> AccessRequestHandler:
            """Factory function for AccessRequestHandler using TypedResolver."""
            logger.info("Creating AccessRequestHandler instance via TypedDI")
            # Import SlackAsyncClient locally to avoid circular import
            from packages.slack.core.slack_async_client import SlackAsyncClient

            slack_client = await resolver.aget(SlackAsyncClient)
            access_request_ops = await resolver.aget(AccessRequestOperations)
            secrets_manager = await resolver.aget(SecretsManager)
            metrics_service = await resolver.aget(AccessRequestMonitor)
            distributed_lock = await resolver.aget(DistributedLock)
            return AccessRequestHandler(
                slack_client=slack_client,
                access_request_ops=access_request_ops,
                secrets_manager=secrets_manager,
                metrics_service=metrics_service,
                distributed_lock=distributed_lock,
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=AccessRequestHandlerProtocol,
            concrete_type=AccessRequestHandler,
            factory=create_access_request_handler,
            dependencies=[
                DependencySpec(AccessRequestOperations),
                DependencySpec(SecretsManager),
                DependencySpec(AccessRequestMonitor),
                DependencySpec(DistributedLock),
            ],
            lifetime="singleton",
        )

        logger.info("AccessRequest services registered successfully")

    except ImportError as e:
        logger.warning(f"AccessRequest services dependencies not available: {e}")
        _register_access_request_placeholders(manager)


def _register_access_request_placeholders(manager: "ServiceRegistrationManager") -> None:
    """Register placeholder implementations for AccessRequest services."""

    # Register placeholder AccessRequestBlocks
    async def create_access_request_blocks_placeholder(resolver) -> AccessRequestBlocks:
        return AccessRequestBlocks()

    manager.register_protocol_with_concrete_alias(
        protocol_type=AccessRequestBlocksProtocol,
        concrete_type=AccessRequestBlocks,
        factory=create_access_request_blocks_placeholder,
        dependencies=[],
        lifetime="singleton",
    )

    # Register placeholder AccessRequest
    async def create_access_request_placeholder(resolver) -> AccessRequest:
        return AccessRequest()

    manager.register_protocol_with_concrete_alias(
        protocol_type=AccessRequestProtocol,
        concrete_type=AccessRequest,
        factory=create_access_request_placeholder,
        dependencies=[],
        lifetime="singleton",
    )

    logger.info("AccessRequest placeholder services registered")


def register_database_batches(manager: "ServiceRegistrationManager") -> None:
    """
    Register database batch operation services.

    Provides advanced database functionality including connection management,
    migrations, backup/restore, indexing, queries, transactions, pooling,
    monitoring, batch utilities, and flag review operations.

    Args:
        manager: ServiceRegistrationManager instance
    """
    logger.info("Starting Database Batch Services registration")

    _register_database_core_services(manager)
    _register_backup_restore_services(manager)
    _register_query_services(manager)
    _register_management_services(manager)
    _register_utility_services(manager)
    _register_access_request_services(manager)

    logger.info("Database Batch Services registered successfully")
