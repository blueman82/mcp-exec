"""
Core Infrastructure Registration Module

Registers infrastructure services that provide foundational capabilities:
- SQSClient for message queuing
- MetricsStorage for application metrics
- AsyncClient for HTTP operations
- TypedServiceRegistry for dependency injection
- TypedResolver for service resolution
- BackoffStrategy services for resilience patterns

These services form the infrastructure backbone supporting all application functionality.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING

from packages.core.async_client import AsyncClient
from packages.core.local_metrics import MetricsStorage
from packages.core.logging import setup_logger
from packages.core.sqs_client import SQSClient
from packages.core.typed_di.types import DependencySpec
from packages.core.typed_di.registry import TypedServiceRegistry

# Type hint imports
if TYPE_CHECKING:
    from packages.core.typed_di.resolver import TypedResolver

# Protocol imports (conditional to avoid circular dependencies)
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

# Import protocols from the protocols module to avoid circular dependencies
from ..protocols import (
    AsyncClientProtocol,
    ExponentialBackoffStrategyProtocol,
    MetricsStorageProtocol,
    SQSClientProtocol,
    TypedResolverProtocol,
    TypedServiceRegistryProtocol,
)

logger = setup_logger(__name__)


def register_core_infrastructure(manager: "ServiceRegistrationManager") -> None:
    """
    Register core infrastructure services for messaging, metrics, and DI framework.

    Infrastructure services provide foundational capabilities like message queuing,
    metrics collection, HTTP clients, and dependency injection framework components.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        ImportError: If optional infrastructure components are not available
    """
    logger.info("Registering core infrastructure services")

    # Register messaging and metrics infrastructure
    _register_messaging_and_metrics(manager)

    # Register HTTP client infrastructure
    _register_http_infrastructure(manager)

    # Register dependency injection infrastructure
    _register_di_infrastructure(manager)

    # Register resilience infrastructure (optional)
    _register_resilience_infrastructure(manager)

    logger.info("Core infrastructure services registered successfully")


def _register_messaging_and_metrics(manager: "ServiceRegistrationManager") -> None:
    """Register SQSClient and MetricsStorage infrastructure services."""
    # SQSClient with protocol - messaging infrastructure
    async def create_sqs_client(resolver) -> SQSClient:
        """Factory function for SQSClient using TypedResolver."""
        logger.info("Creating SQSClient instance via TypedDI")
        # SQSClient requires queue_url and region from environment or config
        # For now, using default values - this should be configured via environment
        return SQSClient(queue_url="", region="eu-west-1")

    manager.register_protocol_with_concrete_alias(
        protocol_type=SQSClientProtocol,
        concrete_type=SQSClient,
        factory=create_sqs_client,
        dependencies=[],
        lifetime="singleton",
    )

    # MetricsStorage with protocol - metrics infrastructure
    async def create_metrics_storage(resolver) -> MetricsStorage:
        """Factory function for MetricsStorage using TypedResolver."""
        logger.info("Creating MetricsStorage instance via TypedDI")
        return MetricsStorage(namespace="ketchup")

    manager.register_protocol_with_concrete_alias(
        protocol_type=MetricsStorageProtocol,
        concrete_type=MetricsStorage,
        factory=create_metrics_storage,
        dependencies=[],
        lifetime="singleton",
    )


def _register_http_infrastructure(manager: "ServiceRegistrationManager") -> None:
    """Register AsyncClient HTTP infrastructure service."""
    # AsyncClient with protocol - HTTP client infrastructure
    async def create_async_client(resolver) -> AsyncClient:
        """Factory function for AsyncClient."""
        # Import locally to avoid circular dependencies
        from packages.core.resilience.backoff import ExponentialBackoffStrategy

        # Create backoff strategy locally to avoid circular dependency
        backoff_strategy = ExponentialBackoffStrategy()

        # Create minimal config object for AsyncClient
        class MinimalConfig:
            pass

        return AsyncClient(
            config=MinimalConfig(),
            max_concurrent_requests=10,
            request_timeout=60,
            backoff_strategy=backoff_strategy,
        )

    manager.register_protocol_with_concrete_alias(
        protocol_type=AsyncClientProtocol,
        concrete_type=AsyncClient,
        factory=create_async_client,
        dependencies=[],
        lifetime="singleton",
    )


def _register_di_infrastructure(manager: "ServiceRegistrationManager") -> None:
    """Register TypedDI framework infrastructure services."""
    _register_typed_service_registry(manager)
    _register_typed_resolver(manager)


def _register_typed_service_registry(manager: "ServiceRegistrationManager") -> None:
    """Register TypedServiceRegistry - self-registration for dependency injection."""
    try:
        from packages.core.typed_di.registry import TypedServiceRegistry

        async def create_typed_service_registry(resolver) -> TypedServiceRegistry:
            """Factory function for TypedServiceRegistry - returns current instance."""
            # Return the current registry instance being used
            return (
                resolver._registry
                if hasattr(resolver, "_registry")
                else TypedServiceRegistry()
            )

        manager.register_protocol_with_concrete_alias(
            protocol_type=TypedServiceRegistryProtocol,
            concrete_type=TypedServiceRegistry,
            factory=create_typed_service_registry,
            dependencies=[],
            lifetime="singleton",
        )
        logger.info("TypedServiceRegistry self-registration completed")
    except ImportError as e:
        logger.warning(f"TypedServiceRegistry not available: {e}")


def _register_typed_resolver(manager: "ServiceRegistrationManager") -> None:
    """Register TypedResolver - resolution infrastructure."""
    async def create_typed_resolver(resolver) -> "TypedResolver":
        """Factory function for TypedResolver."""
        from packages.core.typed_di.resolver import TypedResolver

        # Get the current registry from the resolver instead of passing None
        registry = await resolver.aget(TypedServiceRegistry)
        return TypedResolver(registry=registry)

    # Import for registration only - avoid module-level circular import
    try:
        from packages.core.typed_di.resolver import TypedResolver as _TypedResolver

        manager.register_protocol_with_concrete_alias(
            protocol_type=TypedResolverProtocol,
            concrete_type=_TypedResolver,
            factory=create_typed_resolver,
            dependencies=[DependencySpec(TypedServiceRegistryProtocol)],
            lifetime="singleton",
        )
    except ImportError as e:
        logger.warning(f"TypedResolver not available: {e}")


def _register_resilience_infrastructure(manager: "ServiceRegistrationManager") -> None:
    """Register resilience pattern infrastructure services (optional)."""
    try:
        from packages.core.resilience.backoff import BackoffStrategy, ExponentialBackoffStrategy

        # BackoffStrategy with protocol
        async def create_backoff_strategy(resolver) -> BackoffStrategy:
            """Factory function for BackoffStrategy using TypedResolver."""
            logger.info("Creating BackoffStrategy instance via TypedDI")
            return BackoffStrategy()

        manager.register_protocol_with_concrete_alias(
            protocol_type=BackoffStrategy,  # Use concrete as protocol
            concrete_type=BackoffStrategy,
            factory=create_backoff_strategy,
            dependencies=[],
            lifetime="singleton",
        )

        # ExponentialBackoffStrategy with protocol
        async def create_exponential_backoff_strategy(resolver) -> ExponentialBackoffStrategy:
            """Factory function for ExponentialBackoffStrategy using TypedResolver."""
            logger.info("Creating ExponentialBackoffStrategy instance via TypedDI")
            return ExponentialBackoffStrategy()

        manager.register_protocol_with_concrete_alias(
            protocol_type=ExponentialBackoffStrategyProtocol,
            concrete_type=ExponentialBackoffStrategy,
            factory=create_exponential_backoff_strategy,
            dependencies=[],
            lifetime="singleton",
        )
        logger.info("BackoffStrategy services registered successfully")
    except ImportError as e:
        logger.warning(f"BackoffStrategy services not available: {e}")