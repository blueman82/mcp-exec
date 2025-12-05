"""
Typed DI System Types

Core type definitions for the TypedServiceRegistry system.
"""

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

if TYPE_CHECKING:
    from .resolver import TypedResolver

# Core type variables
T = TypeVar("T")

# Factory function types
Factory = Callable[["TypedResolver"], T]
AsyncFactory = Callable[["TypedResolver"], Awaitable[T]]

# Provider types for circular dependency resolution
Provider = Callable[[], T]
AsyncProvider = Callable[[], Awaitable[T]]


@dataclass
class DependencySpec:
    """Structured dependency specification for qualifiers and optionals."""

    type: Type
    qualifier: Optional[str] = None
    optional: bool = False
    provider: bool = False  # True = inject Provider[T] for cycle-breaking


@dataclass(frozen=True)
class InitializationStats:
    """Statistics captured during registry initialization."""

    service_order: List[Type]  # Actual initialization order (topological + tie-breaking)
    timings: Dict[Type, float]  # Per-service initialization duration in seconds
    failures: List[Tuple[Type, Exception]]  # Services that failed to initialize
    retries: Dict[Type, int]  # Retry attempts per service (always 0 in v1)
    total_duration: float  # Total initialization time in seconds
    deterministic_tie_breaks: List[Tuple[Type, Type]]  # Registration-order tie-breaks applied


@dataclass
class ServiceRegistration:
    """Internal service registration record."""

    service_type: Type[Any]
    factory: Callable[["TypedResolver"], Any]  # Can be sync or async
    dependencies: List[DependencySpec]
    lifetime: Literal["singleton"]
    qualifier: Optional[str]
    registration_index: int  # For deterministic tie-breaking
    is_async: bool


@dataclass
class ServiceInstance:
    """Internal service instance record."""

    instance: Any
    initialization_time: float
    dependencies_resolved: List[str]  # For debugging/tracing
