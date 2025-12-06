"""Performance testing utilities for TypedDI testing."""

import random
import time
from dataclasses import dataclass
from typing import List, Tuple, Type


@dataclass
class PerformanceMetrics:
    """Performance metrics for TypedDI operations."""

    startup_time: float
    memory_usage_mb: float
    avg_resolution_ms: float
    total_services: int


@dataclass
class LoadTestMetrics:
    """Load testing metrics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    requests_per_second: float


def create_mock_service(name: str, dependencies: List[Type] = None) -> Type:
    """Create a mock service class with optional dependencies."""
    dependencies = dependencies or []

    # Create a unique class using type()
    attrs = {
        "__init__": lambda self, **kwargs: (
            setattr(self, "name", name),
            setattr(self, "dependencies", dependencies),
            setattr(self, "initialized_at", time.time()),
        )[-1]
        or None,
        "__repr__": lambda self: f"MockService({name})",
        "__module__": "__main__",
    }

    # Use type() to create a truly unique class
    MockService = type(f"MockService_{name}", (object,), attrs)
    return MockService


def create_service_factory(service_type: Type, dependencies: List[Type] = None):
    """Create a factory function for a service."""
    dependencies = dependencies or []

    def factory(resolver=None):
        """Factory function for service creation."""
        # Resolve dependencies if resolver is provided
        deps = {}
        if resolver and dependencies:
            for dep in dependencies:
                # Use get method from TypedResolver
                dep_instance = resolver.get(dep)
                # Use a simplified key name for the dependency
                dep_name = dep.__name__.replace("MockService_", "").lower()
                deps[dep_name] = dep_instance

        return service_type(**deps)

    return factory


def generate_271_service_graph() -> List[Tuple[Type, List[Type]]]:
    """Generate a realistic service dependency graph with 271 services."""
    services = []
    service_types = []

    # Create base services with no dependencies (leaf nodes)
    for i in range(50):
        service = create_mock_service(f"BaseService_{i}")
        services.append((service, []))
        service_types.append(service)

    # Create middle-tier services with dependencies on base services
    for i in range(100):
        # Each service depends on 1-3 base services
        num_deps = random.randint(1, 3)
        deps = random.sample(service_types[:50], min(num_deps, 50))
        service = create_mock_service(f"MiddleService_{i}", deps)
        services.append((service, deps))
        service_types.append(service)

    # Create top-tier services with dependencies on middle-tier services
    for i in range(121):
        # Each service depends on 1-5 previous services (base + middle)
        available_services = service_types[:150]  # Only base + middle services
        num_deps = random.randint(1, min(5, len(available_services)))
        deps = random.sample(available_services, num_deps)
        service = create_mock_service(f"TopService_{i}", deps)
        services.append((service, deps))
        service_types.append(service)

    return services
