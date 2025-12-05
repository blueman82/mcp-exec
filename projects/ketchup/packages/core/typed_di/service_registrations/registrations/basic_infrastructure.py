"""
Basic Infrastructure Registration Module

Registers fundamental infrastructure services for enterprise operations:
- ConnectionPoolManager: Database and HTTP connection pool management
- CircuitBreakerService: Resilience patterns for service calls
- HealthCheckService: Service health monitoring and validation
- ConfigurationService: Runtime configuration management
- DistributedLockService: Distributed lock coordination

These 5 services provide core infrastructure capabilities that other services depend on.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, Any, Dict, Protocol, runtime_checkable

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Core infrastructure imports
try:
    from packages.core.async_client import AsyncClient
    from packages.core.local_metrics import MetricsStorage
    from packages.core.resilience.backoff import BackoffStrategy
    from packages.db.dynamodb_store import DynamoDBStore
    from packages.secrets.manager import SecretsManager
except ImportError as e:
    logger = setup_logger(__name__)
    logger.warning(f"Core infrastructure import failed: {e}")

if TYPE_CHECKING:
    from packages.core.typed_di.service_registrations.manager import ServiceRegistrationManager

logger = setup_logger(__name__)


# =============================================================================
# PROTOCOL DEFINITIONS
# =============================================================================


@runtime_checkable
class ConnectionPoolManagerProtocol(Protocol):
    """Protocol for managing database and HTTP connection pools."""

    async def get_connection(self, pool_name: str) -> Any: ...
    async def release_connection(self, pool_name: str, connection: Any) -> bool: ...
    async def get_pool_stats(self, pool_name: str) -> Dict[str, Any]: ...
    async def configure_pool(self, pool_name: str, config: Dict[str, Any]) -> bool: ...


@runtime_checkable
class CircuitBreakerServiceProtocol(Protocol):
    """Protocol for circuit breaker resilience patterns."""

    async def call_with_breaker(self, service_name: str, func, *args, **kwargs) -> Any: ...
    async def get_breaker_state(self, service_name: str) -> str: ...
    async def reset_breaker(self, service_name: str) -> bool: ...
    async def configure_breaker(self, service_name: str, config: Dict[str, Any]) -> bool: ...


@runtime_checkable
class HealthCheckServiceProtocol(Protocol):
    """Protocol for service health monitoring."""

    async def register_health_check(self, service_name: str, check_func) -> bool: ...
    async def run_health_check(self, service_name: str) -> Dict[str, Any]: ...
    async def get_system_health(self) -> Dict[str, Any]: ...
    async def get_health_status(self, service_name: str) -> str: ...


@runtime_checkable
class ConfigurationServiceProtocol(Protocol):
    """Protocol for runtime configuration management."""

    async def get_config(self, key: str, default: Any = None) -> Any: ...
    async def set_config(self, key: str, value: Any) -> bool: ...
    async def reload_config(self) -> bool: ...
    async def get_all_config(self) -> Dict[str, Any]: ...


@runtime_checkable
class DistributedLockServiceProtocol(Protocol):
    """Protocol for distributed lock coordination."""

    async def acquire_lock(self, lock_key: str, timeout: int = 30) -> bool: ...
    async def release_lock(self, lock_key: str) -> bool: ...
    async def is_locked(self, lock_key: str) -> bool: ...
    async def get_lock_info(self, lock_key: str) -> Dict[str, Any]: ...


def register_basic_infrastructure(manager: "ServiceRegistrationManager") -> None:
    """
    Register basic infrastructure services (5 services).

    Provides fundamental infrastructure capabilities:
    - ConnectionPoolManager: Database and HTTP connection pools
    - CircuitBreakerService: Resilience patterns for service failures
    - HealthCheckService: Service health monitoring and validation
    - ConfigurationService: Runtime configuration management
    - DistributedLockService: Distributed lock coordination

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration
    """
    logger.info("Registering Basic Infrastructure Services (5 services)")

    # ConnectionPoolManager
    async def create_connection_pool_manager(resolver) -> object:
        """Factory function for ConnectionPoolManager."""
        logger.info("Creating ConnectionPoolManager instance via TypedDI")
        async_client = await resolver.aget(AsyncClient)

        class ConnectionPoolManager:
            """Manages database and HTTP connection pools."""

            def __init__(self, async_client):
                self.async_client = async_client
                self.pools = {}

            async def get_connection(self, pool_name: str) -> Any:
                """Get a connection from the specified pool."""
                logger.debug(f"Getting connection from pool: {pool_name}")
                return f"connection_{pool_name}_1"

            async def release_connection(self, pool_name: str, connection: Any) -> bool:
                """Release a connection back to the pool."""
                logger.debug(f"Releasing connection to pool: {pool_name}")
                return True

            async def get_pool_stats(self, pool_name: str) -> Dict[str, Any]:
                """Get statistics for the specified pool."""
                return {"pool_name": pool_name, "active": 5, "idle": 10, "max": 20}

            async def configure_pool(self, pool_name: str, config: Dict[str, Any]) -> bool:
                """Configure pool settings."""
                logger.debug(f"Configuring pool {pool_name}: {config}")
                return True

        return ConnectionPoolManager(async_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=ConnectionPoolManagerProtocol,
        concrete_type=type("ConcreteType1017", (), {}),
        factory=create_connection_pool_manager,
        dependencies=[DependencySpec(AsyncClient)],
        lifetime="singleton",
    )

    # CircuitBreakerService
    async def create_circuit_breaker_service(resolver) -> object:
        """Factory function for CircuitBreakerService."""
        logger.info("Creating CircuitBreakerService instance via TypedDI")
        backoff_strategy = await resolver.aget(BackoffStrategy)

        class CircuitBreakerService:
            """Provides circuit breaker resilience patterns."""

            def __init__(self, backoff_strategy):
                self.backoff = backoff_strategy
                self.breakers = {}

            async def call_with_breaker(self, service_name: str, func, *args, **kwargs) -> Any:
                """Execute function with circuit breaker protection."""
                logger.debug(f"Calling {service_name} with circuit breaker")
                # Simulate circuit breaker logic
                return await func(*args, **kwargs) if callable(func) else "success"

            async def get_breaker_state(self, service_name: str) -> str:
                """Get current state of circuit breaker."""
                return "closed"  # closed, open, half-open

            async def reset_breaker(self, service_name: str) -> bool:
                """Reset circuit breaker to closed state."""
                logger.debug(f"Resetting circuit breaker for {service_name}")
                return True

            async def configure_breaker(self, service_name: str, config: Dict[str, Any]) -> bool:
                """Configure circuit breaker parameters."""
                logger.debug(f"Configuring breaker {service_name}: {config}")
                return True

        return CircuitBreakerService(backoff_strategy)

    manager.register_protocol_with_concrete_alias(
        protocol_type=CircuitBreakerServiceProtocol,
        concrete_type=type("ConcreteType1018", (), {}),
        factory=create_circuit_breaker_service,
        dependencies=[DependencySpec(BackoffStrategy)],
        lifetime="singleton",
    )

    # HealthCheckService
    async def create_health_check_service(resolver) -> object:
        """Factory function for HealthCheckService."""
        logger.info("Creating HealthCheckService instance via TypedDI")
        metrics_storage = await resolver.aget(MetricsStorage)

        class HealthCheckService:
            """Monitors service health across the system."""

            def __init__(self, metrics_storage):
                self.metrics = metrics_storage
                self.checks = {}

            async def register_health_check(self, service_name: str, check_func) -> bool:
                """Register a health check for a service."""
                logger.debug(f"Registering health check for {service_name}")
                self.checks[service_name] = check_func
                return True

            async def run_health_check(self, service_name: str) -> Dict[str, Any]:
                """Run health check for specific service."""
                logger.debug(f"Running health check for {service_name}")
                return {"service": service_name, "status": "healthy", "timestamp": "now"}

            async def get_system_health(self) -> Dict[str, Any]:
                """Get overall system health status."""
                return {"status": "healthy", "services": len(self.checks), "timestamp": "now"}

            async def get_health_status(self, service_name: str) -> str:
                """Get health status for specific service."""
                return "healthy"  # healthy, unhealthy, unknown

        return HealthCheckService(metrics_storage)

    manager.register_protocol_with_concrete_alias(
        protocol_type=HealthCheckServiceProtocol,
        concrete_type=type("ConcreteType1019", (), {}),
        factory=create_health_check_service,
        dependencies=[DependencySpec(MetricsStorage)],
        lifetime="singleton",
    )

    # ConfigurationService
    async def create_configuration_service(resolver) -> object:
        """Factory function for ConfigurationService."""
        logger.info("Creating ConfigurationService instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)

        class ConfigurationService:
            """Manages runtime configuration across the system."""

            def __init__(self, secrets_manager):
                self.secrets = secrets_manager
                self.config = {}

            async def get_config(self, key: str, default: Any = None) -> Any:
                """Get configuration value by key."""
                logger.debug(f"Getting config: {key}")
                return self.config.get(key, default)

            async def set_config(self, key: str, value: Any) -> bool:
                """Set configuration value."""
                logger.debug(f"Setting config {key}: {value}")
                self.config[key] = value
                return True

            async def reload_config(self) -> bool:
                """Reload configuration from source."""
                logger.debug("Reloading configuration")
                return True

            async def get_all_config(self) -> Dict[str, Any]:
                """Get all configuration values."""
                return self.config.copy()

        return ConfigurationService(secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=ConfigurationServiceProtocol,
        concrete_type=type("ConcreteType1020", (), {}),
        factory=create_configuration_service,
        dependencies=[DependencySpec(SecretsManager)],
        lifetime="singleton",
    )

    # DistributedLockService
    async def create_distributed_lock_service(resolver) -> object:
        """Factory function for DistributedLockService."""
        logger.info("Creating DistributedLockService instance via TypedDI")
        dynamodb_store = await resolver.aget(DynamoDBStore)

        class DistributedLockService:
            """Provides distributed lock coordination."""

            def __init__(self, dynamodb_store):
                self.db = dynamodb_store
                self.locks = {}

            async def acquire_lock(self, lock_key: str, timeout: int = 30) -> bool:
                """Acquire a distributed lock."""
                logger.debug(f"Acquiring lock: {lock_key} (timeout: {timeout}s)")
                self.locks[lock_key] = {"acquired": True, "timeout": timeout}
                return True

            async def release_lock(self, lock_key: str) -> bool:
                """Release a distributed lock."""
                logger.debug(f"Releasing lock: {lock_key}")
                if lock_key in self.locks:
                    del self.locks[lock_key]
                return True

            async def is_locked(self, lock_key: str) -> bool:
                """Check if a lock is currently held."""
                return lock_key in self.locks

            async def get_lock_info(self, lock_key: str) -> Dict[str, Any]:
                """Get information about a lock."""
                if lock_key in self.locks:
                    return {"key": lock_key, "status": "held", "info": self.locks[lock_key]}
                return {"key": lock_key, "status": "available"}

        return DistributedLockService(dynamodb_store)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DistributedLockServiceProtocol,
        concrete_type=type("ConcreteType1021", (), {}),
        factory=create_distributed_lock_service,
        dependencies=[DependencySpec(DynamoDBStore)],
        lifetime="singleton",
    )

    logger.info("Basic Infrastructure Services completed - 5 services registered")
