"""
Registry Service Protocols

Protocol definitions for TypedDI registry-related services.
"""

from typing import Protocol, runtime_checkable

__all__ = [
    "TypedServiceRegistryProtocol",
]


@runtime_checkable
class TypedServiceRegistryProtocol(Protocol):
    """Protocol for typed service registry operations."""

    pass
