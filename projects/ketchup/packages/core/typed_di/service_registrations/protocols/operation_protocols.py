"""
Operation Service Protocols

Protocol definitions for operational services including base operations,
restore state operations, trust operations, and join notification operations.
"""

from typing import List, Protocol, runtime_checkable

__all__ = [
    "BaseOperationsProtocol",
    "RestoreStateOperationsProtocol",
    "TrustOperationsProtocol",
    "JoinNotificationOpsProtocol",
    "RestoreStateManagerProtocol",
    "AccessRequestOperationsProtocol",
    "AccessRequestProtocol",
]


@runtime_checkable
class BaseOperationsProtocol(Protocol):
    """Protocol for base database operations."""

    pass


@runtime_checkable
class RestoreStateOperationsProtocol(Protocol):
    """Protocol for restore state operations."""

    pass


@runtime_checkable
class TrustOperationsProtocol(Protocol):
    """Protocol for trust operations."""

    pass


@runtime_checkable
class JoinNotificationOpsProtocol(Protocol):
    """Protocol for join notification operations."""

    pass


@runtime_checkable
class RestoreStateManagerProtocol(Protocol):
    """Protocol for RestoreStateManager operations."""

    pass


@runtime_checkable
class AccessRequestOperationsProtocol(Protocol):
    """Protocol for access request operations."""

    async def get_user_request_history(self, user_id: str, limit: int = 10) -> List[object]: ...


@runtime_checkable
class AccessRequestProtocol(Protocol):
    """Protocol for access request operations."""

    pass
