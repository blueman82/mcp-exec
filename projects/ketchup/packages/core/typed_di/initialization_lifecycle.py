"""
Two-Phase Initialization Lifecycle Support

Provides patterns and utilities for services that require post-construction
async initialization (Pattern 1 from bug analysis).

Example services:
- OpenAIHandler: needs async initialize() to fetch API keys and setup client
- Any service with async resource setup (connections, auth, etc.)

Solution:
1. Factory functions can be async and handle initialization
2. Registry detects services with initialize() method
3. Automatic initialization orchestration during resolve
"""

import inspect
from typing import Any, Callable, Optional, Protocol, Type, TypeVar


class InitializableProtocol(Protocol):
    """Protocol for services that support async initialization."""

    async def initialize(self) -> Any:
        """Initialize the service asynchronously.

        Returns:
            Self for method chaining, or None.
        """
        ...


T = TypeVar("T")


def has_async_initialize(obj: Any) -> bool:
    """Check if an object has an async initialize() method.

    Args:
        obj: Object to check (can be instance or class)

    Returns:
        True if object has async initialize() method
    """
    if inspect.isclass(obj):
        # Check class for method
        return hasattr(obj, "initialize") and inspect.iscoroutinefunction(obj.initialize)
    else:
        # Check instance for method
        return hasattr(obj, "initialize") and inspect.iscoroutinefunction(obj.initialize)


async def initialize_if_needed(instance: T) -> T:
    """Initialize instance if it has an async initialize() method.

    This is the core utility that enables Pattern 1 support.

    Args:
        instance: Service instance to potentially initialize

    Returns:
        Initialized instance (or original if no initialize method)

    Example:
        ```python
        # Factory that creates and initializes
        async def create_openai_handler(resolver) -> OpenAIHandler:
            deps = await resolver.aget_multi([TokenTracker, SecretsManager, ...])
            handler = OpenAIHandler(*deps)
            return await initialize_if_needed(handler)
        ```
    """
    if has_async_initialize(instance):
        # Avoid recursive initialization for the registry itself
        from packages.core.typed_di.registry import TypedServiceRegistry

        if isinstance(instance, TypedServiceRegistry):
            return instance

        from packages.core.logging import setup_logger

        logger = setup_logger(__name__)

        logger.debug(f"Initializing {type(instance).__name__} via async initialize()")
        result = await instance.initialize()

        # Some services return self, others return None
        return result if result is not None else instance

    return instance


def make_two_phase_factory(factory: Callable, auto_initialize: bool = True) -> Callable:
    """Wrap a factory function to support two-phase initialization.

    This decorator/wrapper automatically calls initialize() on services
    that support it, converting a simple factory into a two-phase factory.

    Args:
        factory: Original factory function (sync or async)
        auto_initialize: Whether to automatically call initialize()

    Returns:
        Wrapped factory that handles initialization

    Example:
        ```python
        # Original factory just constructs
        def create_handler(resolver) -> OpenAIHandler:
            deps = resolver.get_multi([TokenTracker, SecretsManager])
            return OpenAIHandler(*deps)

        # Wrapped factory constructs AND initializes
        two_phase_factory = make_two_phase_factory(create_handler)
        registry.register(OpenAIHandler, two_phase_factory, ...)
        ```
    """
    if not auto_initialize:
        return factory

    if inspect.iscoroutinefunction(factory):
        # Async factory
        async def async_wrapper(*args, **kwargs):
            instance = await factory(*args, **kwargs)
            return await initialize_if_needed(instance)

        return async_wrapper
    else:
        # Sync factory - need to make it async to call initialize
        async def sync_to_async_wrapper(*args, **kwargs):
            instance = factory(*args, **kwargs)
            return await initialize_if_needed(instance)

        return sync_to_async_wrapper


class InitializationLifecycleManager:
    """Manages service initialization lifecycle.

    Provides utilities for:
    - Detecting services needing initialization
    - Tracking initialization state
    - Orchestrating initialization order
    """

    def __init__(self):
        self._initialized_services: set[Any] = set()
        self._initialization_in_progress: set[Any] = set()

    async def ensure_initialized(self, instance: T, service_key: str) -> T:
        """Ensure service is initialized, avoiding duplicate initialization.

        Args:
            instance: Service instance
            service_key: Unique key for tracking

        Returns:
            Initialized instance
        """
        # Use id() for tracking since instances might not be hashable
        instance_id = id(instance)

        # Already initialized
        if instance_id in self._initialized_services:
            return instance

        # Initialization in progress (circular dependency protection)
        if instance_id in self._initialization_in_progress:
            from packages.core.logging import setup_logger

            logger = setup_logger(__name__)
            logger.warning(
                f"Circular initialization detected for {service_key}, "
                f"returning partially initialized instance"
            )
            return instance

        # Mark as in progress
        self._initialization_in_progress.add(instance_id)

        try:
            # Initialize if needed
            result = await initialize_if_needed(instance)

            # Mark as complete
            self._initialized_services.add(instance_id)

            return result
        finally:
            # Always remove from in-progress
            self._initialization_in_progress.discard(instance_id)

    def is_initialized(self, instance: Any) -> bool:
        """Check if service instance has been initialized.

        Args:
            instance: Service instance to check

        Returns:
            True if instance has been initialized
        """
        return id(instance) in self._initialized_services

    def reset(self) -> None:
        """Reset initialization tracking (for testing)."""
        self._initialized_services.clear()
        self._initialization_in_progress.clear()


# Global lifecycle manager
_lifecycle_manager: Optional[InitializationLifecycleManager] = None


def get_lifecycle_manager() -> InitializationLifecycleManager:
    """Get global initialization lifecycle manager."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = InitializationLifecycleManager()
    return _lifecycle_manager


# Convenience functions for common patterns
async def create_and_initialize(service_class: Type[T], *args, **kwargs) -> T:
    """Create service instance and initialize it.

    Args:
        service_class: Service class to instantiate
        *args: Constructor arguments
        **kwargs: Constructor keyword arguments

    Returns:
        Initialized service instance

    Example:
        ```python
        # Instead of:
        handler = OpenAIHandler(tracker, secrets, ...)
        await handler.initialize()

        # Use:
        handler = await create_and_initialize(
            OpenAIHandler, tracker, secrets, ...
        )
        ```
    """
    instance = service_class(*args, **kwargs)
    return await initialize_if_needed(instance)
