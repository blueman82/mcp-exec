"""
ServiceDependencyResolver for Ketchup

Automatic dependency resolution for service initialization order.
Eliminates manual phase management brittleness when adding new services.

Based on the right-sized DI solution, adapted for Ketchup's modular client factory system.
"""

from collections import defaultdict, deque
from typing import Dict, List, Set

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class ServiceDependencyResolver:
    """
    Automatic dependency resolution using topological sorting.

    Solves the brittleness of manual initialization phase management by
    automatically determining the correct service initialization order
    based on declared dependencies.
    """

    def __init__(self):
        """Initialize the dependency resolver."""
        self._dependencies: Dict[str, List[str]] = {}
        self._services: Set[str] = set()

    def register_service_deps(self, service: str, dependencies: List[str]) -> None:
        """
        Register service dependencies for automatic ordering.

        Args:
            service: Service name (matches CLIENT_MAP keys)
            dependencies: List of services this service depends on

        Example:
            resolver.register_service_deps("dynamodb_store", ["dynamodb_async_client"])
            resolver.register_service_deps("user_store", ["dynamodb_async_client"])
            resolver.register_service_deps("slack_posting", ["secrets_manager"])
        """
        logger.debug("Registering service dependencies: %s -> %s", service, dependencies)
        self._dependencies[service] = dependencies
        self._services.add(service)
        for dep in dependencies:
            self._services.add(dep)

    def get_initialization_order(self) -> List[str]:
        """
        Calculate safe initialization order using topological sorting.

        Uses Kahn's algorithm to detect circular dependencies and provide
        a valid initialization sequence.

        Returns:
            List of service names in dependency-safe initialization order

        Raises:
            ValueError: If circular dependencies are detected
        """
        logger.info("Calculating initialization order for %d services", len(self._services))

        # Kahn's algorithm for topological sorting
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        # Initialize in-degree counter for all services
        for service in self._services:
            in_degree[service] = 0

        # Build dependency graph and calculate in-degrees
        for service, deps in self._dependencies.items():
            for dep in deps:
                graph[dep].append(service)
                in_degree[service] += 1

        # Find services with no dependencies (can initialize first)
        queue = deque([service for service in self._services if in_degree[service] == 0])
        result = []

        # Process services in topological order
        while queue:
            current = queue.popleft()
            result.append(current)
            logger.debug("Adding %s to initialization order", current)

            # Remove current service from dependency graph
            for dependent in graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for circular dependencies
        if len(result) != len(self._services):
            remaining = [s for s in self._services if s not in result]
            error_msg = f"Circular dependency detected among services: {remaining}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Initialization order calculated: %s", result)
        return result

    def get_services(self) -> Set[str]:
        """Get all registered services."""
        return self._services.copy()

    def get_dependencies(self, service: str) -> List[str]:
        """Get dependencies for a specific service."""
        return self._dependencies.get(service, []).copy()


def create_ketchup_dependency_resolver() -> ServiceDependencyResolver:
    """
    Create and configure ServiceDependencyResolver with Ketchup service dependencies.

    This configuration reflects the current Ketchup service architecture:
    - Secrets services have no dependencies
    - DB services depend on secrets and each other
    - Integration services depend on DB
    - Cloud services depend on secrets and DB
    - Slack services depend on secrets, DB, and cloud
    - AI services depend on secrets and slack

    Returns:
        Configured ServiceDependencyResolver with Ketchup services
    """
    logger.info("Creating Ketchup dependency resolver configuration")
    resolver = ServiceDependencyResolver()

    # Secrets domain - no dependencies
    resolver.register_service_deps("secrets_manager", [])

    # DB domain - depends on secrets
    resolver.register_service_deps("dynamodb_config", [])
    resolver.register_service_deps("dynamodb_async_client", ["dynamodb_config"])
    resolver.register_service_deps("dynamodb_store", ["dynamodb_async_client"])
    resolver.register_service_deps("user_store", ["dynamodb_async_client"])
    resolver.register_service_deps("command_tracking_ops", ["dynamodb_async_client"])
    resolver.register_service_deps("channel_operations", ["dynamodb_async_client"])

    # Integration domain - depends on DB
    resolver.register_service_deps("jira_client", ["secrets_manager"])

    # Cloud domain - depends on secrets
    resolver.register_service_deps("aws_client", ["secrets_manager"])
    resolver.register_service_deps("elasticsearch_client", ["secrets_manager"])

    # Slack domain - depends on secrets, DB, and cloud
    resolver.register_service_deps("slack_auth", ["secrets_manager"])
    resolver.register_service_deps("slack_posting", ["secrets_manager"])
    resolver.register_service_deps("slack_web_client", ["slack_auth"])
    resolver.register_service_deps("slack_socket_client", ["slack_auth"])

    # AI domain - depends on secrets and slack
    resolver.register_service_deps("openai_client", ["secrets_manager"])
    resolver.register_service_deps("azure_openai_client", ["secrets_manager"])

    logger.info(
        "Ketchup dependency resolver configured with %d services",
        len(resolver.get_services()),
    )
    return resolver
