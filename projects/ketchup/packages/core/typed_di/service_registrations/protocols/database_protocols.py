"""
Database Service Protocols

Protocol definitions for database-related services including connection management,
migrations, backups, monitoring, and optimization operations.
"""

from typing import Protocol, runtime_checkable

__all__ = [
    "DatabaseConnectionServiceProtocol",
    "DatabaseMigrationServiceProtocol",
    "DatabaseBackupServiceProtocol",
    "DatabaseRestoreServiceProtocol",
    "DatabaseIndexServiceProtocol",
    "DatabaseQueryServiceProtocol",
    "DatabaseTransactionServiceProtocol",
    "DatabasePoolServiceProtocol",
    "DatabaseMonitoringServiceProtocol",
    "DatabaseOptimizationServiceProtocol",
    "DatabaseSchemaServiceProtocol",
    "DatabaseReplicationServiceProtocol",
    "DatabaseShardingServiceProtocol",
    "DatabaseCacheServiceProtocol",
    "DatabaseAuditServiceProtocol",
    "DatabaseSecurityServiceProtocol",
    "DatabaseMetricsServiceProtocol",
    "DatabaseHealthServiceProtocol",
    "DatabaseCleanupServiceProtocol",
    "DatabaseArchiveServiceProtocol",
]


@runtime_checkable
class DatabaseConnectionServiceProtocol(Protocol):
    """Protocol for database connection management."""

    async def get_connection(self):
        """Get database connection."""
        pass

    async def test_connection(self) -> bool:
        """Test database connection."""
        pass


@runtime_checkable
class DatabaseMigrationServiceProtocol(Protocol):
    """Protocol for database migration operations."""

    async def run_migration(self, version: str) -> bool:
        """Run database migration."""
        pass


@runtime_checkable
class DatabaseBackupServiceProtocol(Protocol):
    """Protocol for database backup operations."""

    async def create_backup(self, table_name: str) -> str:
        """Create database backup."""
        pass


@runtime_checkable
class DatabaseRestoreServiceProtocol(Protocol):
    """Protocol for database restore operations."""

    async def restore_table(self, table_name: str) -> bool:
        """Restore database table."""
        pass


@runtime_checkable
class DatabaseIndexServiceProtocol(Protocol):
    """Protocol for database index management."""

    async def create_index(self, table_name: str, index_name: str) -> bool:
        """Create database index."""
        pass


@runtime_checkable
class DatabaseQueryServiceProtocol(Protocol):
    """Protocol for advanced query operations."""

    async def execute_query(self, query: str) -> list:
        """Execute database query."""
        pass


@runtime_checkable
class DatabaseTransactionServiceProtocol(Protocol):
    """Protocol for transaction management."""

    async def begin_transaction(self) -> str:
        """Begin database transaction."""
        pass


@runtime_checkable
class DatabasePoolServiceProtocol(Protocol):
    """Protocol for connection pool management."""

    async def get_connection(self):
        """Get connection from pool."""
        pass


@runtime_checkable
class DatabaseMonitoringServiceProtocol(Protocol):
    """Protocol for database monitoring."""

    async def monitor_performance(self) -> dict:
        """Monitor database performance."""
        pass


@runtime_checkable
class DatabaseOptimizationServiceProtocol(Protocol):
    """Protocol for database optimization."""

    async def analyze_performance(self) -> dict:
        """Analyze database performance."""
        pass


@runtime_checkable
class DatabaseSchemaServiceProtocol(Protocol):
    """Protocol for schema management."""

    async def create_table(self, table_name: str, schema: dict) -> bool:
        """Create database table."""
        pass


@runtime_checkable
class DatabaseReplicationServiceProtocol(Protocol):
    """Protocol for database replication."""

    async def setup_replication(self, source: str, target: str) -> bool:
        """Setup database replication."""
        pass


@runtime_checkable
class DatabaseShardingServiceProtocol(Protocol):
    """Protocol for database sharding."""

    async def create_shard(self, shard_key: str) -> bool:
        """Create database shard."""
        pass


@runtime_checkable
class DatabaseCacheServiceProtocol(Protocol):
    """Protocol for database caching layer."""

    async def get(self, key: str):
        """Get cached value."""
        pass


@runtime_checkable
class DatabaseAuditServiceProtocol(Protocol):
    """Protocol for database audit logging."""

    async def log_operation(self, operation: str, details: dict):
        """Log database operation."""
        pass


@runtime_checkable
class DatabaseSecurityServiceProtocol(Protocol):
    """Protocol for database security."""

    async def encrypt_data(self, data: str) -> str:
        """Encrypt database data."""
        pass


@runtime_checkable
class DatabaseMetricsServiceProtocol(Protocol):
    """Protocol for database metrics."""

    async def collect_metrics(self) -> dict:
        """Collect database metrics."""
        pass


@runtime_checkable
class DatabaseHealthServiceProtocol(Protocol):
    """Protocol for database health checks."""

    async def check_health(self) -> dict:
        """Check database health."""
        pass


@runtime_checkable
class DatabaseCleanupServiceProtocol(Protocol):
    """Protocol for database cleanup operations."""

    async def cleanup_old_data(self, retention_days: int) -> bool:
        """Cleanup old database data."""
        pass


@runtime_checkable
class DatabaseArchiveServiceProtocol(Protocol):
    """Protocol for database archival."""

    async def archive_data(self, table_name: str, criteria: dict) -> bool:
        """Archive database data."""
        pass
