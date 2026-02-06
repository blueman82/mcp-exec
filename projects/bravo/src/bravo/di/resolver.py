"""Dependency resolution via topological sort."""

from collections import deque

from bravo.di.types import DependencySpec


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected.

    Attributes:
        remaining: Service names involved in the cycle.
    """

    def __init__(self, remaining: list[str]) -> None:
        self.remaining = remaining
        super().__init__(f"Circular dependency detected among: {remaining}")


def topological_sort(specs: dict[str, DependencySpec]) -> list[str]:
    """Sort services in dependency order using Kahn's algorithm.

    Produces a linear ordering where each service appears after all of
    its dependencies.  Runs in O(V+E) time.

    Args:
        specs: Mapping of service name to its dependency spec.

    Returns:
        Service names in valid initialization order.

    Raises:
        ValueError: If a dependency references an unregistered service.
        CircularDependencyError: If a cycle exists in the dependency graph.
    """
    # Validate all dependencies reference known services.
    for name, spec in specs.items():
        for dep in spec.depends_on:
            if dep not in specs:
                raise ValueError(
                    f"Service {name!r} depends on unknown service {dep!r}"
                )

    # Build in-degree map.
    in_degree: dict[str, int] = {name: 0 for name in specs}
    for name, spec in specs.items():
        for dep in spec.depends_on:
            in_degree[name] += 1

    # Seed queue with zero-dependency services.
    queue: deque[str] = deque(
        name for name, degree in in_degree.items() if degree == 0
    )

    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)

        # Reduce in-degree for dependents of the current service.
        for name, spec in specs.items():
            if current in spec.depends_on:
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)

    if len(order) != len(specs):
        remaining = [name for name in specs if name not in order]
        raise CircularDependencyError(remaining)

    return order
