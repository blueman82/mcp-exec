"""
Integration Management Registration Module

Registers integration management and operational services for enterprise systems:
- Data & Config Services (196-197): Data synchronization, integration configuration
- Monitoring Services (198-199): Health monitoring, retry policies
- Management Services (200-204): Caching, logging, metrics, security, versioning

This module handles Services 196-204 (9 services) with enterprise integration management.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Core infrastructure imports
try:
    from packages.core.local_metrics import MetricsStorage
    from packages.core.resilience.backoff import BackoffStrategy
    from packages.secrets.manager import SecretsManager
except ImportError as e:
    logger = setup_logger(__name__)
    logger.warning(f"Core infrastructure import failed: {e}")

if TYPE_CHECKING:
    from packages.core.typed_di.service_registrations.manager import ServiceRegistrationManager

logger = setup_logger(__name__)


# Module-level protocols for cross-function access
@runtime_checkable
class IntegrationConfigServiceProtocol(Protocol):
    """Protocol for integration configuration."""

    async def get_config(self, integration_name: str) -> dict: ...
    async def update_config(self, integration_name: str, config: dict) -> bool: ...


@runtime_checkable
class ExternalAPIServiceProtocol(Protocol):
    """Protocol for external API management."""

    async def call_api(self, endpoint: str, data: dict) -> dict: ...
    async def get_api_status(self, api_name: str) -> dict: ...


def register_integration_management(manager: "ServiceRegistrationManager") -> None:
    """
    Register integration management services.

    Covers Services 196-204 (9 services):
    - Data & configuration services (2 services)
    - Monitoring & retry services (2 services)
    - Management services (5 services)

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration
    """
    logger.info("Registering Integration Management Services (196-204)")

    # Data & Configuration Services (196-197)
    _register_data_config_services(manager)

    # Monitoring & Retry Services (198-199)
    _register_monitoring_services(manager)

    # Management Services (200-204)
    _register_management_services(manager)

    logger.info("Integration Management Services completed - 9 services registered (196-204)")


def _register_data_config_services(manager: "ServiceRegistrationManager") -> None:
    """Register data and configuration services (196-197)."""

    # ExternalAPIService - Prerequisite for DataSyncService
    async def create_external_api_service(resolver) -> object:
        """Factory function for ExternalAPIService."""
        logger.info("Creating ExternalAPIService instance via TypedDI")

        class ExternalAPIService:
            async def call_api(self, endpoint: str, data: dict):
                return {"status": "success"}

            async def get_api_status(self, api_name: str):
                return {"status": "available"}

        return ExternalAPIService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=ExternalAPIServiceProtocol,
        concrete_type=type("ConcreteExternalAPIService", (), {}),
        factory=create_external_api_service,
        dependencies=[],
        lifetime="singleton",
    )

    # DataSyncService (Service 196)
    @runtime_checkable
    class DataSyncServiceProtocol(Protocol):
        """Protocol for data synchronization."""

        async def sync_data(self, source: str, target: str) -> bool: ...
        async def get_sync_status(self, sync_id: str) -> dict: ...

    async def create_data_sync_service(resolver) -> object:
        """Factory function for DataSyncService."""
        logger.info("Creating DataSyncService instance via TypedDI")
        external_api = await resolver.aget(ExternalAPIServiceProtocol)

        class DataSyncService:
            def __init__(self, external_api):
                self.api = external_api

            async def sync_data(self, source: str, target: str):
                return True

            async def get_sync_status(self, sync_id: str):
                return {"status": "synced"}

        return DataSyncService(external_api)

    manager.register_protocol_with_concrete_alias(
        protocol_type=DataSyncServiceProtocol,
        concrete_type=type("ConcreteType1004", (), {}),
        factory=create_data_sync_service,
        dependencies=[DependencySpec(ExternalAPIServiceProtocol)],
        lifetime="singleton",
    )

    # IntegrationConfigService (Service 197)
    async def create_integration_config_service(resolver) -> object:
        """Factory function for IntegrationConfigService."""
        logger.info("Creating IntegrationConfigService instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)

        class IntegrationConfigService:
            def __init__(self, secrets_manager):
                self.secrets = secrets_manager

            async def get_config(self, integration_name: str):
                return {"config": "value"}

            async def update_config(self, integration_name: str, config: dict):
                return True

        return IntegrationConfigService(secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationConfigServiceProtocol,
        concrete_type=type("ConcreteType1005", (), {}),
        factory=create_integration_config_service,
        dependencies=[DependencySpec(SecretsManager)],
        lifetime="singleton",
    )


def _register_monitoring_services(manager: "ServiceRegistrationManager") -> None:
    """Register monitoring and retry services (198-199)."""

    # IntegrationHealthService (Service 198)
    @runtime_checkable
    class IntegrationHealthServiceProtocol(Protocol):
        """Protocol for integration health monitoring."""

        async def check_health(self, integration_name: str) -> dict: ...
        async def get_health_metrics(self) -> dict: ...

    async def create_integration_health_service(resolver) -> object:
        """Factory function for IntegrationHealthService."""
        logger.info("Creating IntegrationHealthService instance via TypedDI")
        metrics_storage = await resolver.aget(MetricsStorage)

        class IntegrationHealthService:
            def __init__(self, metrics_storage):
                self.metrics = metrics_storage

            async def check_health(self, integration_name: str):
                return {"status": "healthy"}

            async def get_health_metrics(self):
                return {"uptime": "99.9%"}

        return IntegrationHealthService(metrics_storage)

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationHealthServiceProtocol,
        concrete_type=type("ConcreteType1006", (), {}),
        factory=create_integration_health_service,
        dependencies=[DependencySpec(MetricsStorage)],
        lifetime="singleton",
    )

    # IntegrationRetryService (Service 199)
    @runtime_checkable
    class IntegrationRetryServiceProtocol(Protocol):
        """Protocol for integration retry logic."""

        async def retry_operation(self, operation_id: str) -> bool: ...
        async def configure_retry_policy(self, policy: dict) -> bool: ...

    async def create_integration_retry_service(resolver) -> object:
        """Factory function for IntegrationRetryService."""
        logger.info("Creating IntegrationRetryService instance via TypedDI")
        backoff_strategy = await resolver.aget(BackoffStrategy)

        class IntegrationRetryService:
            def __init__(self, backoff_strategy):
                self.backoff = backoff_strategy

            async def retry_operation(self, operation_id: str):
                return True

            async def configure_retry_policy(self, policy: dict):
                return True

        return IntegrationRetryService(backoff_strategy)

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationRetryServiceProtocol,
        concrete_type=type("ConcreteType1007", (), {}),
        factory=create_integration_retry_service,
        dependencies=[DependencySpec(BackoffStrategy)],
        lifetime="singleton",
    )


def _register_management_services(manager: "ServiceRegistrationManager") -> None:
    """Register management services (200-204)."""

    # IntegrationCacheService (Service 200)
    @runtime_checkable
    class IntegrationCacheServiceProtocol(Protocol):
        """Protocol for integration response caching."""

        async def get_cached_response(self, key: str) -> dict: ...
        async def cache_response(self, key: str, response: dict) -> bool: ...

    async def create_integration_cache_service(resolver) -> object:
        """Factory function for IntegrationCacheService."""
        logger.info("Creating IntegrationCacheService instance via TypedDI")

        class IntegrationCacheService:
            async def get_cached_response(self, key: str):
                return {"cached": True}

            async def cache_response(self, key: str, response: dict):
                return True

        return IntegrationCacheService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationCacheServiceProtocol,
        concrete_type=type("ConcreteType1008", (), {}),
        factory=create_integration_cache_service,
        dependencies=[],
        lifetime="singleton",
    )

    # IntegrationLogService (Service 201)
    @runtime_checkable
    class IntegrationLogServiceProtocol(Protocol):
        """Protocol for integration logging."""

        async def log_integration_event(self, event: dict) -> bool: ...
        async def get_integration_logs(self, integration_name: str) -> list: ...

    async def create_integration_log_service(resolver) -> object:
        """Factory function for IntegrationLogService."""
        logger.info("Creating IntegrationLogService instance via TypedDI")

        class IntegrationLogService:
            async def log_integration_event(self, event: dict):
                return True

            async def get_integration_logs(self, integration_name: str):
                return []

        return IntegrationLogService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationLogServiceProtocol,
        concrete_type=type("ConcreteType1009", (), {}),
        factory=create_integration_log_service,
        dependencies=[],
        lifetime="singleton",
    )

    # IntegrationMetricsService (Service 202)
    @runtime_checkable
    class IntegrationMetricsServiceProtocol(Protocol):
        """Protocol for integration metrics."""

        async def record_metric(self, metric_name: str, value: float) -> bool: ...
        async def get_metrics(self, integration_name: str) -> dict: ...

    async def create_integration_metrics_service(resolver) -> object:
        """Factory function for IntegrationMetricsService."""
        logger.info("Creating IntegrationMetricsService instance via TypedDI")
        metrics_storage = await resolver.aget(MetricsStorage)

        class IntegrationMetricsService:
            def __init__(self, metrics_storage):
                self.storage = metrics_storage

            async def record_metric(self, metric_name: str, value: float):
                return True

            async def get_metrics(self, integration_name: str):
                return {"metrics": []}

        return IntegrationMetricsService(metrics_storage)

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationMetricsServiceProtocol,
        concrete_type=type("ConcreteType1010", (), {}),
        factory=create_integration_metrics_service,
        dependencies=[DependencySpec(MetricsStorage)],
        lifetime="singleton",
    )

    # IntegrationSecurityService (Service 203)
    @runtime_checkable
    class IntegrationSecurityServiceProtocol(Protocol):
        """Protocol for integration security."""

        async def validate_request(self, request: dict) -> bool: ...
        async def encrypt_payload(self, payload: dict) -> dict: ...

    async def create_integration_security_service(resolver) -> object:
        """Factory function for IntegrationSecurityService."""
        logger.info("Creating IntegrationSecurityService instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)

        class IntegrationSecurityService:
            def __init__(self, secrets_manager):
                self.secrets = secrets_manager

            async def validate_request(self, request: dict):
                return True

            async def encrypt_payload(self, payload: dict):
                return {"encrypted": True}

        return IntegrationSecurityService(secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationSecurityServiceProtocol,
        concrete_type=type("ConcreteType1011", (), {}),
        factory=create_integration_security_service,
        dependencies=[DependencySpec(SecretsManager)],
        lifetime="singleton",
    )

    # IntegrationVersioningService (Service 204)
    @runtime_checkable
    class IntegrationVersioningServiceProtocol(Protocol):
        """Protocol for integration versioning."""

        async def get_version(self, integration_name: str) -> str: ...
        async def upgrade_integration(self, integration_name: str, version: str) -> bool: ...

    async def create_integration_versioning_service(resolver) -> object:
        """Factory function for IntegrationVersioningService."""
        logger.info("Creating IntegrationVersioningService instance via TypedDI")
        integration_config = await resolver.aget(IntegrationConfigServiceProtocol)

        class IntegrationVersioningService:
            def __init__(self, integration_config):
                self.config = integration_config

            async def get_version(self, integration_name: str):
                return "1.0.0"

            async def upgrade_integration(self, integration_name: str, version: str):
                return True

        return IntegrationVersioningService(integration_config)

    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationVersioningServiceProtocol,
        concrete_type=type("ConcreteType1012", (), {}),
        factory=create_integration_versioning_service,
        dependencies=[DependencySpec(IntegrationConfigServiceProtocol)],
        lifetime="singleton",
    )


# Protocol imports for cross-module dependencies
# ExternalAPIServiceProtocol already defined at module level
