"""
TypedServiceRegistry

Core implementation of the typed dependency injection registry with async support,
topological dependency resolution, and compatibility with existing DI container.
"""

import asyncio
import inspect
import os
import time
from typing import Dict, List, Literal, Optional, Type, TypeVar, Union

from packages.core.logging import setup_logger

from .exceptions import (
    DuplicateRegistrationError,
    FrozenRegistryError,
    MissingDependencyError,
    NotInitializedError,
)
from .resolver import ServiceDependencyResolver, TypedResolver
from .types import (
    AsyncFactory,
    DependencySpec,
    Factory,
    InitializationStats,
    ServiceInstance,
    ServiceRegistration,
)

T = TypeVar("T")


class TypedServiceRegistry:
    """
    Typed service registry with automatic dependency resolution and lifecycle management.

    Features:
    - Type-safe service resolution with IDE support
    - Automatic topological dependency ordering
    - Async factory support with singleton lifetimes
    - Circular dependency detection and resolution via Providers
    - Deterministic initialization with registration-order tie-breaking
    - Test override support with environment detection
    """

    def __init__(self):
        self._logger = setup_logger(__name__)
        self._registrations: Dict[str, ServiceRegistration] = {}
        self._instances: Dict[str, ServiceInstance] = {}
        self._original_instances: Dict[str, ServiceInstance] = (
            {}
        )  # Backup for overrides
        self._resolver = ServiceDependencyResolver()
        self._typed_resolver = TypedResolver(self)
        self._initialization_order: List[ServiceRegistration] = []
        self._initialization_stats: Optional[InitializationStats] = None
        self._initialized = False
        self._frozen = False
        self._lock = asyncio.Lock()
        self._registration_counter = 0
        self._lazy_services: set[str] = set()  # Track services that support lazy initialization
        self._essential_services: set[str] = set()  # Track essential services that need immediate init

    def register(
        self,
        service_type: Type[T],
        factory: Union[Factory[T], AsyncFactory[T]],
        dependencies: Optional[List[DependencySpec]] = None,
        lifetime: Literal["singleton"] = "singleton",
        qualifier: Optional[str] = None,
        lazy: bool = True,  # Default to lazy initialization
        essential: bool = False,  # Mark as essential for immediate initialization
    ) -> None:
        """
        Register a service with the registry.

        Args:
            service_type: Protocol interface to register
            factory: Factory function that creates the service
            dependencies: List of dependency specifications
            lifetime: Service lifetime (only 'singleton' supported)
            qualifier: Optional qualifier for multiple implementations
        """
        if self._frozen and not self._is_test_environment():
            raise FrozenRegistryError(
                "Cannot register services after registry is frozen"
            )

        service_key = self._get_service_key(service_type, qualifier)

        if service_key in self._registrations:
            raise DuplicateRegistrationError(
                f"Service {service_key} is already registered"
            )

        # Determine if factory is async
        is_async = inspect.iscoroutinefunction(factory)

        # Create registration
        registration = ServiceRegistration(
            service_type=service_type,
            factory=factory,
            dependencies=dependencies or [],
            lifetime=lifetime,
            qualifier=qualifier,
            registration_index=self._registration_counter,
            is_async=is_async,
        )

        self._registrations[service_key] = registration
        self._resolver.add_service(registration)
        self._registration_counter += 1

        # Track service initialization behavior
        if lazy:
            self._lazy_services.add(service_key)
        if essential:
            self._essential_services.add(service_key)

    async def initialize_all(self) -> None:
        """
        Initialize all registered services in correct dependency order.

        Uses Kahn's algorithm for topological sorting with deterministic tie-breaking
        based on registration order.
        """
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:  # Double-check pattern
                return

            start_time = time.time()

            try:
                # Validate all dependencies can be resolved
                validation_errors = self._resolver.validate_dependencies()
                if validation_errors:
                    raise MissingDependencyError(
                        f"Dependency validation failed: {validation_errors}"
                    )

                # Get initialization order
                self._initialization_order = self._resolver.get_initialization_order()

                # Initialize services in order
                timings: Dict[Type, float] = {}
                failures: List[tuple[Type, Exception]] = []

                for registration in self._initialization_order:
                    service_start = time.time()
                    try:
                        self._logger.info(
                            "Initializing service %s",
                            registration.service_type.__name__,
                        )
                        await self._initialize_service(registration)
                        timings[registration.service_type] = time.time() - service_start
                        self._logger.info(
                            "Initialized service %s in %.2fs",
                            registration.service_type.__name__,
                            timings[registration.service_type],
                        )
                    except Exception as e:
                        self._logger.error(
                            "Service %s failed to initialize: %s",
                            registration.service_type.__name__,
                            e,
                        )
                        failures.append((registration.service_type, e))
                        raise

                # Calculate tie-breaks that occurred during ordering
                tie_breaks = []  # Will be populated by resolver if needed

                total_duration = time.time() - start_time

                self._initialization_stats = InitializationStats(
                    service_order=[
                        reg.service_type for reg in self._initialization_order
                    ],
                    timings=timings,
                    failures=failures,
                    retries={},  # No retry logic in v1
                    total_duration=total_duration,
                    deterministic_tie_breaks=tie_breaks,
                )

                self._initialized = True

            except Exception:
                # Clear any partially initialized services
                self._instances.clear()
                raise

    async def initialize(self, targets: Optional[List[Type]] = None) -> None:
        """
        Initialize specific service targets and their dependencies.

        Args:
            targets: List of service types to initialize, or None for all services
        """
        if targets is None:
            await self.initialize_all()
            return

        # For partial initialization, we still need full dependency resolution
        # to ensure proper ordering of the subset
        if not self._initialized:
            await self.initialize_all()

        # If already fully initialized, partial init is a no-op

    def get(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """
        Get an initialized singleton service synchronously.

        Args:
            service_type: Service type to retrieve
            qualifier: Optional qualifier for disambiguation

        Returns:
            The service instance

        Raises:
            NotInitializedError: If called before initialize_all()
            MissingDependencyError: If service is not registered
        """
        service_key = self._get_service_key(service_type, qualifier)

        # If service is already initialized, return it
        if service_key in self._instances:
            return self._instances[service_key].instance

        # Registry must be initialized before accessing services
        if not self._initialized:
            raise NotInitializedError(
                "Registry not initialized. Call initialize_all() first."
            )

        return self._get_initialized_singleton(service_type, qualifier)

    async def aget(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """
        Get an initialized singleton service asynchronously.

        This method is async-safe and can be used during async initialization
        or when accessing services that were created by async factories.

        Args:
            service_type: Service type to retrieve
            qualifier: Optional qualifier for disambiguation

        Returns:
            The service instance

        Raises:
            NotInitializedError: If called before initialize_all()
            MissingDependencyError: If service is not registered
        """
        service_key = self._get_service_key(service_type, qualifier)

        # If service is already initialized, return it
        if service_key in self._instances:
            return self._instances[service_key].instance

        # Registry must be initialized before accessing services
        if not self._initialized:
            raise NotInitializedError(
                "Registry not initialized. Call initialize_all() first."
            )

        return self._get_initialized_singleton(service_type, qualifier)

    def try_get(
        self, service_type: Type[T], qualifier: Optional[str] = None
    ) -> Optional[T]:
        """
        Try to get an initialized singleton service.

        Returns None if service not initialized or not registered.
        """
        if not self._initialized:
            return None

        try:
            return self._get_initialized_singleton(service_type, qualifier)
        except (MissingDependencyError, RuntimeError):
            return None

    def override(
        self, service_type: Type[T], instance: T, qualifier: Optional[str] = None
    ) -> None:
        """
        Override a service instance for testing.

        Allowed only before freeze or in test environments.
        """
        if self._frozen and not self._is_test_environment():
            raise FrozenRegistryError(
                "Cannot override services after freeze in production mode"
            )

        service_key = self._get_service_key(service_type, qualifier)

        # Backup original instance before overriding
        if (
            service_key in self._instances
            and service_key not in self._original_instances
        ):
            self._original_instances[service_key] = self._instances[service_key]

        # Create a mock service instance record
        self._instances[service_key] = ServiceInstance(
            instance=instance,
            initialization_time=0.0,
            dependencies_resolved=["[override]"],
        )

    def clear_overrides(self) -> None:
        """Clear all service overrides and restore original instances."""
        if self._frozen and not self._is_test_environment():
            raise FrozenRegistryError(
                "Cannot clear overrides after freeze in production mode"
            )

        # Remove override instances and restore originals
        override_keys = [
            key
            for key, instance in self._instances.items()
            if instance.dependencies_resolved == ["[override]"]
        ]
        for key in override_keys:
            del self._instances[key]
            # Restore original instance if backed up
            if key in self._original_instances:
                self._instances[key] = self._original_instances[key]
                del self._original_instances[key]

    def freeze_after_init(self) -> None:
        """Freeze the registry to prevent further modifications."""
        self._frozen = True

    def get_initialization_order(self) -> List[Type]:
        """Get the actual initialization order used."""
        return [reg.service_type for reg in self._initialization_order]

    def get_initialization_stats(self) -> InitializationStats:
        """Get initialization statistics."""
        if self._initialization_stats is None:
            raise NotInitializedError(
                "No initialization stats available. Call initialize_all() first."
            )
        return self._initialization_stats

    # Internal methods

    async def _initialize_service(self, registration: ServiceRegistration) -> None:
        """Initialize a single service with two-phase initialization support."""
        service_key = self._get_service_key(
            registration.service_type, registration.qualifier
        )

        # Skip if already initialized (could happen with overrides)
        if service_key in self._instances:
            return

        try:
            # Phase 1: Factory creates instance
            if registration.is_async:
                instance = await registration.factory(self._typed_resolver)
            else:
                # Handle sync factory
                result = registration.factory(self._typed_resolver)
                if inspect.isawaitable(result):
                    instance = await result
                else:
                    instance = result

            # Phase 2: Call async initialize() if service supports it
            from .initialization_lifecycle import initialize_if_needed
            instance = await initialize_if_needed(instance)

            # Store instance
            self._instances[service_key] = ServiceInstance(
                instance=instance,
                initialization_time=time.time(),
                dependencies_resolved=[
                    dep.type.__name__ for dep in registration.dependencies
                ],
            )

        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize service {service_key}: {e}"
            ) from e

    def _get_initialized_singleton(
        self, service_type: Type[T], qualifier: Optional[str] = None
    ) -> T:
        """Get an already initialized singleton."""
        service_key = self._get_service_key(service_type, qualifier)

        if service_key not in self._instances:
            raise MissingDependencyError(
                f"Service {service_key} not found or not initialized"
            )

        return self._instances[service_key].instance

    async def _resolve_service(
        self,
        service_type: Type[T],
        qualifier: Optional[str] = None,
        async_context: bool = False,
    ) -> T:
        """Internal service resolution for async contexts."""
        # For now, delegate to sync resolution since we use eager singleton model
        return self._get_initialized_singleton(service_type, qualifier)

    def _get_service_key(
        self, service_type: Type, qualifier: Optional[str] = None
    ) -> str:
        """Generate unique service key."""
        base_key = f"{service_type.__module__}.{service_type.__qualname__}"
        if qualifier:
            return f"{base_key}#{qualifier}"
        return base_key

    def _lazy_initialize_service(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """Synchronously lazy-initialize a single service."""
        service_key = self._get_service_key(service_type, qualifier)

        if service_key not in self._registrations:
            raise MissingDependencyError(
                f"Service {service_key} not registered"
            )

        registration = self._registrations[service_key]

        # For sync lazy initialization, we need to handle async factories differently
        if registration.is_async:
            # Cannot lazy initialize async factories synchronously
            raise RuntimeError(
                f"Cannot synchronously initialize async service {service_key}. Use aget() instead."
            )

        # Initialize synchronously
        try:
            instance = registration.factory(self._typed_resolver)

            # Store instance
            self._instances[service_key] = ServiceInstance(
                instance=instance,
                initialization_time=time.time(),
                dependencies_resolved=[
                    dep.type.__name__ for dep in registration.dependencies
                ],
            )

            return instance
        except Exception as e:
            raise RuntimeError(
                f"Failed to lazy initialize service {service_key}: {e}"
            ) from e

    async def _async_lazy_initialize_service(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """Asynchronously lazy-initialize a single service."""
        service_key = self._get_service_key(service_type, qualifier)

        if service_key not in self._registrations:
            raise MissingDependencyError(
                f"Service {service_key} not registered"
            )

        registration = self._registrations[service_key]

        # Use existing _initialize_service method for proper async handling
        try:
            await self._initialize_service(registration)
            return self._instances[service_key].instance
        except Exception as e:
            raise RuntimeError(
                f"Failed to async lazy initialize service {service_key}: {e}"
            ) from e

    def _is_test_environment(self) -> bool:
        """Detect if running in test mode."""
        return os.getenv("KETCHUP_TEST_MODE", "false").lower() in {"1", "true", "yes"}

    def is_initialized(self) -> bool:
        """Check if the registry has been initialized."""
        return self._initialized

    def _lazy_initialize_service(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """
        Lazy initialization is disabled - use initialize_all() first.

        This stub method exists for backward compatibility with tests that expect it.
        """
        raise NotInitializedError("Lazy initialization disabled. Call initialize_all() first.")

    async def _async_lazy_initialize_service(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """
        Lazy initialization is disabled - use initialize_all() first.

        This stub method exists for backward compatibility with tests that expect it.
        """
        raise NotInitializedError("Lazy initialization disabled. Call initialize_all() first.")
