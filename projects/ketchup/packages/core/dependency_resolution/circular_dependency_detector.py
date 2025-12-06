"""
Circular dependency detection and resolution system.

Implements static analysis and runtime detection of circular dependencies
to prevent issues during DI system migration and operation.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass
class DependencyEdge:
    """Represents a dependency relationship between two services."""

    source: str
    target: str
    dependency_type: str  # 'import', 'injection', 'inheritance', 'factory'
    location: str  # File:line where dependency is defined


@dataclass
class CircularDependencyIssue:
    """Detected circular dependency issue."""

    cycle_path: List[str]
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'
    issue_type: str
    description: str
    resolution_strategy: str


class CircularDependencyDetector:
    """Detects and analyzes circular dependencies in the DI system."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.dependency_edges: List[DependencyEdge] = []
        self.detected_cycles: List[List[str]] = []

    def add_dependency(self, source: str, target: str, dep_type: str, location: str) -> None:
        """Add a dependency edge to the graph."""
        self.dependency_graph[source].add(target)
        edge = DependencyEdge(source, target, dep_type, location)
        self.dependency_edges.append(edge)

    def detect_cycles(self) -> List[List[str]]:
        """Detect all cycles in the dependency graph using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs_cycle_detection(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Found a cycle - extract the cycle path
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.dependency_graph.get(node, set()):
                dfs_cycle_detection(neighbor, path.copy())

            rec_stack.remove(node)

        for node in self.dependency_graph:
            if node not in visited:
                dfs_cycle_detection(node, [])

        self.detected_cycles = cycles
        return cycles

    def analyze_cycle_severity(self, cycle: List[str]) -> Tuple[str, str]:
        """Analyze the severity and type of a detected cycle."""
        # Count different types of dependencies in the cycle
        inheritance_count = 0
        factory_count = 0
        injection_count = 0

        for i in range(len(cycle) - 1):
            source, target = cycle[i], cycle[i + 1]
            edges = [e for e in self.dependency_edges if e.source == source and e.target == target]

            for edge in edges:
                if edge.dependency_type == "inheritance":
                    inheritance_count += 1
                elif edge.dependency_type == "factory":
                    factory_count += 1
                elif edge.dependency_type == "injection":
                    injection_count += 1

        # Determine severity based on dependency types and cycle length
        if inheritance_count > 0:
            severity = "HIGH"  # Inheritance cycles are most problematic
            issue_type = "inheritance_cycle"
        elif factory_count >= 2:
            severity = "HIGH"  # Multiple factory dependencies in cycle
            issue_type = "factory_cycle"
        elif len(cycle) > 5:
            severity = "MEDIUM"  # Long cycles are complex to resolve
            issue_type = "complex_cycle"
        else:
            severity = "MEDIUM"
            issue_type = "injection_cycle"

        return severity, issue_type

    def generate_resolution_strategy(self, cycle: List[str], issue_type: str) -> str:
        """Generate resolution strategy for a specific cycle."""
        strategies = {
            "inheritance_cycle": (
                "Break inheritance chain using composition pattern. "
                "Create interfaces and use dependency injection instead."
            ),
            "factory_cycle": (
                "Implement lazy initialization with dependency ordering. "
                "Move factory creation to appropriate package boundaries."
            ),
            "complex_cycle": (
                "Refactor package boundaries and use facade pattern. "
                "Implement proper layered architecture."
            ),
            "injection_cycle": (
                "Use interfaces/protocols to break coupling. "
                "Implement dependency inversion principle."
            ),
        }
        return strategies.get(issue_type, "Analyze dependency structure and refactor.")

    def analyze_issues(self) -> List[CircularDependencyIssue]:
        """Analyze all detected cycles and generate issue reports."""
        cycles = self.detect_cycles()
        issues = []

        for cycle in cycles:
            severity, issue_type = self.analyze_cycle_severity(cycle)
            resolution_strategy = self.generate_resolution_strategy(cycle, issue_type)

            description = (
                f"Circular dependency detected: {' -> '.join(cycle)}. "
                f"Cycle length: {len(cycle) - 1} dependencies."
            )

            issue = CircularDependencyIssue(
                cycle_path=cycle,
                severity=severity,
                issue_type=issue_type,
                description=description,
                resolution_strategy=resolution_strategy,
            )
            issues.append(issue)

        return issues


class RuntimeDependencyValidator:
    """Runtime validation of dependency initialization order."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.initialization_order: List[str] = []
        self.pending_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.initialized_services: Set[str] = set()

    def register_dependency(self, service: str, dependencies: List[str]) -> None:
        """Register service dependencies for validation."""
        self.pending_dependencies[service] = set(dependencies)

    def validate_initialization(self, service: str) -> bool:
        """Validate that all dependencies are initialized before service."""
        dependencies = self.pending_dependencies.get(service, set())
        missing_deps = dependencies - self.initialized_services

        if missing_deps:
            self.logger.error(
                f"Service '{service}' cannot be initialized. "
                f"Missing dependencies: {missing_deps}"
            )
            return False

        return True

    def mark_initialized(self, service: str) -> None:
        """Mark a service as successfully initialized."""
        self.initialized_services.add(service)
        self.initialization_order.append(service)
        self.logger.info(f"Service '{service}' initialized successfully")

    def get_safe_initialization_order(self) -> List[str]:
        """Calculate safe initialization order using topological sort."""
        # Build reverse dependency graph
        graph = defaultdict(set)
        in_degree = defaultdict(int)

        for service, deps in self.pending_dependencies.items():
            for dep in deps:
                graph[dep].add(service)
                in_degree[service] += 1

        # Topological sort using Kahn's algorithm
        queue = deque([service for service in self.pending_dependencies if in_degree[service] == 0])
        result = []

        while queue:
            service = queue.popleft()
            result.append(service)

            for dependent in graph[service]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(result) != len(self.pending_dependencies):
            remaining = set(self.pending_dependencies.keys()) - set(result)
            self.logger.error(f"Circular dependencies detected in: {remaining}")

        return result


def create_dependency_detector() -> CircularDependencyDetector:
    """Factory function to create and configure dependency detector."""
    return CircularDependencyDetector()


def create_runtime_validator() -> RuntimeDependencyValidator:
    """Factory function to create runtime dependency validator."""
    return RuntimeDependencyValidator()
