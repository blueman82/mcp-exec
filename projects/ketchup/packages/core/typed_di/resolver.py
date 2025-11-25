"""
Typed DI System Resolver

Dependency resolver and service dependency resolution components.
"""

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Type, TypeVar

from .exceptions import CircularDependencyError, MissingDependencyError
from .types import AsyncProvider, Provider, ServiceRegistration

T = TypeVar("T")


class TypedResolver:
    """Dependency resolver passed to factory functions for clean injection.

    This class provides the dependency injection interface for factory functions,
    allowing them to resolve their dependencies through the TypedServiceRegistry
    without direct registry access.

    Attributes:
        _registry: The TypedServiceRegistry instance for service resolution.
    """

    def __init__(self, registry):
        """Initialize the TypedResolver.

        Args:
            registry: The TypedServiceRegistry instance to use for service resolution.
        """
        self._registry = registry

    async def aget(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """Get service asynchronously with full resolution support.

        Args:
            service_type: The protocol/type of service to resolve.
            qualifier: Optional service qualifier for disambiguation.

        Returns:
            The resolved service instance.

        Raises:
            MissingDependencyError: If the service is not registered.
            CircularDependencyError: If circular dependencies are detected.
        """
        return await self._registry._resolve_service(
            service_type, qualifier, async_context=True
        )

    def get(self, service_type: Type[T], qualifier: Optional[str] = None) -> T:
        """Get service synchronously - only for already-initialized singletons.

        Args:
            service_type: The protocol/type of service to resolve.
            qualifier: Optional service qualifier for disambiguation.

        Returns:
            The resolved service instance.

        Raises:
            MissingDependencyError: If the service is not registered or initialized.
            NotInitializedError: If called before initialize_all().
        """
        return self._registry._get_initialized_singleton(service_type, qualifier)

    def try_get(
        self, service_type: Type[T], qualifier: Optional[str] = None
    ) -> Optional[T]:
        """Get service synchronously, returns None if not initialized.

        Args:
            service_type: The protocol/type of service to resolve.
            qualifier: Optional service qualifier for disambiguation.

        Returns:
            The resolved service instance or None if not available.
        """
        try:
            return self.get(service_type, qualifier)
        except (MissingDependencyError, RuntimeError):
            return None

    def build_provider(
        self, service_type: Type[T], qualifier: Optional[str] = None
    ) -> Provider[T]:
        """Build sync provider for cycle-breaking dependencies.

        Args:
            service_type: The protocol/type of service to provide.
            qualifier: Optional service qualifier for disambiguation.

        Returns:
            A provider function that returns the service when called.
        """

        def provider() -> T:
            return self._registry._get_initialized_singleton(service_type, qualifier)

        return provider

    def build_async_provider(
        self, service_type: Type[T], qualifier: Optional[str] = None
    ) -> AsyncProvider[T]:
        """Build async provider for cycle-breaking dependencies.

        Args:
            service_type: The protocol/type of service to provide.
            qualifier: Optional service qualifier for disambiguation.

        Returns:
            An async provider function that returns the service when awaited.
        """

        async def async_provider() -> T:
            return await self._registry._resolve_service(
                service_type, qualifier, async_context=True
            )

        return async_provider


class ServiceDependencyResolver:
    """Handles topological sorting and dependency resolution using Kahn's Algorithm.

    This class maintains dependency graphs and provides deterministic initialization
    ordering for services with automatic circular dependency detection.

    Attributes:
        dependency_graph: Forward dependency mapping (service -> dependents).
        reverse_graph: Reverse dependency mapping (service -> dependencies).
        in_degree: Count of dependencies for each service.
        registrations: Registry of all service registrations by key.
    """

    def __init__(self):
        """Initialize the dependency resolver with empty graphs."""
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self.in_degree: Dict[str, int] = defaultdict(int)
        self.registrations: Dict[str, ServiceRegistration] = {}

    def add_service(self, registration: ServiceRegistration) -> None:
        """Add a service registration to the resolver.

        Args:
            registration: The service registration containing type, factory, and dependencies.

        Note:
            Ensures all services have entries in dependency graphs, even those without
            dependencies, to prevent KeyError during topological sorting.
        """
        service_key = self._get_service_key(
            registration.service_type, registration.qualifier
        )
        self.registrations[service_key] = registration

        # ALWAYS ensure service exists in dependency graph (even with empty set)
        if service_key not in self.dependency_graph:
            self.dependency_graph[service_key] = set()

        # ALWAYS ensure service exists in reverse graph
        if service_key not in self.reverse_graph:
            self.reverse_graph[service_key] = set()

        # Initialize in-degree if not present
        if service_key not in self.in_degree:
            self.in_degree[service_key] = 0

        # Process dependencies
        for dep_spec in registration.dependencies:
            dep_key = self._get_service_key(dep_spec.type, dep_spec.qualifier)

            # Skip provider dependencies for topological sort (they break cycles)
            if dep_spec.provider:
                continue

            # Add dependency edge
            self.dependency_graph[dep_key].add(service_key)
            self.reverse_graph[service_key].add(dep_key)
            self.in_degree[service_key] += 1

            # Ensure dependency is in in_degree dict
            if dep_key not in self.in_degree:
                self.in_degree[dep_key] = 0

    def get_initialization_order(self) -> List[ServiceRegistration]:
        """Get deterministic initialization order using Kahn's algorithm with tie-breaking."""
        # Create working copies
        in_degree = self.in_degree.copy()
        graph = {k: v.copy() for k, v in self.dependency_graph.items()}

        # Find all nodes with no incoming edges, sorted by registration order for determinism
        queue: deque[str] = deque()
        ready_services = [
            (self.registrations[key].registration_index, key)
            for key, degree in in_degree.items()
            if degree == 0 and key in self.registrations
        ]
        ready_services.sort()  # Sort by registration index for deterministic tie-breaking
        queue.extend(key for _, key in ready_services)

        result = []
        tie_breaks = []

        while queue:
            # Process the next service (already sorted by registration order)
            current = queue.popleft()
            if current not in self.registrations:
                continue

            result.append(self.registrations[current])

            # Remove this node and update in-degrees
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    # Find insertion point to maintain registration order
                    neighbor_reg_idx = self.registrations[neighbor].registration_index

                    # Check for tie-breaking situation
                    existing_indices = [
                        self.registrations[key].registration_index
                        for key in queue
                        if key in self.registrations
                    ]

                    if existing_indices and any(
                        idx == neighbor_reg_idx for idx in existing_indices
                    ):
                        # Find the service with same registration order for tie-break recording
                        for key in queue:
                            if (
                                key in self.registrations
                                and self.registrations[key].registration_index
                                == neighbor_reg_idx
                            ):
                                tie_breaks.append(
                                    (
                                        self.registrations[key].service_type,
                                        self.registrations[neighbor].service_type,
                                    )
                                )
                                break

                    # Insert in correct position to maintain order
                    inserted = False
                    for i, key in enumerate(queue):
                        if (
                            key in self.registrations
                            and self.registrations[key].registration_index
                            > neighbor_reg_idx
                        ):
                            queue.insert(i, neighbor)
                            inserted = True
                            break
                    if not inserted:
                        queue.append(neighbor)

        # Check for circular dependencies
        if len(result) != len([k for k in self.registrations.keys() if k in in_degree]):
            remaining = [
                k for k, v in in_degree.items() if v > 0 and k in self.registrations
            ]
            cycles = self._find_cycles(remaining)
            raise CircularDependencyError(f"Circular dependencies detected: {cycles}")

        return result

    def _find_cycles(self, remaining_nodes: List[str]) -> List[List[str]]:
        """Find cycles in remaining nodes after topological sort."""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Found cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.reverse_graph.get(node, []):
                if neighbor in remaining_nodes:
                    dfs(neighbor, path.copy())

            rec_stack.remove(node)

        for node in remaining_nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def validate_dependencies(self) -> List[str]:
        """Validate that all dependencies can be resolved."""
        errors = []

        for service_key, registration in self.registrations.items():
            for dep_spec in registration.dependencies:
                if dep_spec.optional:
                    continue

                dep_key = self._get_service_key(dep_spec.type, dep_spec.qualifier)
                if dep_key not in self.registrations:
                    errors.append(
                        f"Service {service_key} depends on {dep_key} which is not registered"
                    )

        return errors

    def _get_service_key(
        self, service_type, qualifier: Optional[str] = None
    ) -> str:
        """Generate unique service key."""
        # Handle both Type objects and string dependencies
        if isinstance(service_type, str):
            base_key = service_type
        else:
            # Type object with __module__ and __qualname__
            base_key = f"{service_type.__module__}.{service_type.__qualname__}"

        if qualifier:
            return f"{base_key}#{qualifier}"
        return base_key
