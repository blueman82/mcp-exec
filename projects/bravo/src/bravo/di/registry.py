"""Service registry for dependency injection."""

import structlog

from bravo.di.resolver import topological_sort
from bravo.di.types import DependencySpec, ServiceRegistration

logger = structlog.get_logger(__name__)


class ServiceRegistry:
    """Container that manages service lifecycle via dependency injection.

    Services are registered with a DependencySpec, then initialized in
    topological order so each factory receives its resolved dependencies
    as keyword arguments.

    Attributes:
        _services: Internal mapping of service name to registration.
        _initialized: Whether initialize_all has been called.
        _init_order: Service names in the order they were initialized.
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceRegistration] = {}
        self._initialized: bool = False
        self._init_order: list[str] = []

    def register(self, spec: DependencySpec) -> None:
        """Register a service specification.

        Args:
            spec: The dependency specification to register.

        Raises:
            RuntimeError: If the registry has already been initialized.
            ValueError: If a service with the same name is already registered.
        """
        if self._initialized:
            raise RuntimeError("Cannot register services after initialization")
        if spec.name in self._services:
            raise ValueError(f"Service {spec.name!r} is already registered")

        self._services[spec.name] = ServiceRegistration(spec=spec)
        logger.debug("service_registered", service=spec.name)

    def get(self, name: str) -> object:
        """Retrieve an initialized service instance by name.

        Args:
            name: The service name.

        Returns:
            The initialized service instance.

        Raises:
            RuntimeError: If the registry has not been initialized.
            KeyError: If no service with the given name exists.
        """
        if not self._initialized:
            raise RuntimeError(
                "Registry has not been initialized; call initialize_all() first"
            )
        if name not in self._services:
            raise KeyError(f"Unknown service {name!r}")
        return self._services[name].instance

    async def initialize_all(self) -> None:
        """Initialize all registered services in dependency order.

        Resolves the dependency graph via topological sort, then calls
        each factory with its resolved dependencies as keyword arguments.

        Raises:
            CircularDependencyError: If a dependency cycle is detected.
            ValueError: If a dependency references an unknown service.
        """
        specs = {name: reg.spec for name, reg in self._services.items()}
        order = topological_sort(specs)

        for name in order:
            reg = self._services[name]
            deps = {dep: self._services[dep].instance for dep in reg.spec.depends_on}
            logger.debug("initializing_service", service=name, deps=list(deps))
            reg.instance = await reg.spec.factory(**deps)

        self._init_order = order
        self._initialized = True
        logger.info(
            "all_services_initialized",
            count=len(order),
            order=order,
        )

    async def shutdown_all(self) -> None:
        """Shut down all services in reverse initialization order.

        Calls ``close()`` on each service that exposes it (EAFP pattern).
        """
        for name in reversed(self._init_order):
            instance = self._services[name].instance
            if hasattr(instance, "close"):
                logger.debug("closing_service", service=name)
                await instance.close()

        self._initialized = False
        self._init_order = []
        logger.info("all_services_shut_down")
