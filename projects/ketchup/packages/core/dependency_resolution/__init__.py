"""
Dependency resolution utilities for TypedDI migration.

Provides circular dependency detection and resolution tools to ensure
safe migration from legacy DI system to TypedDI system.
"""

from .circular_dependency_detector import (
    CircularDependencyDetector,
    RuntimeDependencyValidator,
    create_dependency_detector,
    create_runtime_validator,
)

__all__ = [
    "CircularDependencyDetector",
    "RuntimeDependencyValidator",
    "create_dependency_detector",
    "create_runtime_validator",
]
