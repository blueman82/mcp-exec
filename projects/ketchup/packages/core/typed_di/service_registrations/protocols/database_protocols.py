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


