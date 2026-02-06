"""Dependency injection type definitions."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DependencySpec:
    """Specification for a service dependency.

    Attributes:
        name: Unique service identifier.
        factory: Async callable that creates the service instance.
        depends_on: Names of services this one requires.
    """

    name: str
    factory: Callable[..., Coroutine[Any, Any, Any]]
    depends_on: list[str] = field(default_factory=list)


@dataclass
class ServiceRegistration:
    """Internal registration record for a service.

    Attributes:
        spec: The dependency specification.
        instance: The created service instance, or None if not yet initialized.
    """

    spec: DependencySpec
    instance: Any = None
