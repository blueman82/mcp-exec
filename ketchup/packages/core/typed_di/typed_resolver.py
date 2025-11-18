"""
Typed DI Resolver - Convenience functions for resolving typed dependencies.

This module provides simplified async functions for resolving services
from the TypedDI registry without requiring direct registry access.
"""

from typing import TypeVar, Type

from packages.core.typed_di.resolver import TypedResolver
from packages.core.typed_di_integration import get_typed_registry

T = TypeVar("T")


async def resolve_typed(protocol: Type[T]) -> T:
    """
    Resolve a service by its protocol type.

    Args:
        protocol: The protocol/interface type to resolve

    Returns:
        Instance implementing the protocol

    Raises:
        MissingDependencyError: If no service registered for protocol
        NotInitializedError: If registry not initialized
    """
    registry = get_typed_registry()
    resolver = TypedResolver(registry)
    return await resolver.aget(protocol)


async def resolve_typed_optional(protocol: Type[T]) -> T | None:
    """
    Resolve a service by its protocol type, returning None if not found.

    Args:
        protocol: The protocol/interface type to resolve

    Returns:
        Instance implementing the protocol or None if not registered
    """
    try:
        return await resolve_typed(protocol)
    except Exception:
        return None
