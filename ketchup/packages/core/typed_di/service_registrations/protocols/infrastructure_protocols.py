"""Infrastructure Protocol Definitions.

This module contains protocol definitions for infrastructure services
including HTTP clients, backoff strategies, and async operations.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class AsyncClientProtocol(Protocol):
    """Protocol for async HTTP client operations."""

    pass


@runtime_checkable
class TypedResolverProtocol(Protocol):
    """Protocol for typed dependency resolution."""

    pass


@runtime_checkable
class ExponentialBackoffStrategyProtocol(Protocol):
    """Protocol for backoff strategy."""

    pass


@runtime_checkable
class EventProcessorProtocol(Protocol):
    """Protocol for event processing."""

    async def process_request(self, event: dict) -> dict:
        """
        Process an incoming request event.

        Args:
            event: The raw event dictionary from Slack or other sources

        Returns:
            A dictionary suitable for returning from a Lambda function
            with statusCode and body fields
        """
        ...


@runtime_checkable
class BatchSizeManagerProtocol(Protocol):
    """Protocol for batch size management."""

    pass


@runtime_checkable
class iPaaSRateLimiterProtocol(Protocol):
    """Protocol for iPaaS rate limiting."""

    pass


@runtime_checkable
class MetricsStorageProtocol(Protocol):
    """Protocol for metrics storage operations."""

    pass


@runtime_checkable
class DistributedLockProtocol(Protocol):
    """Protocol for distributed lock operations."""

    pass


@runtime_checkable
class IMSTokenManagerProtocol(Protocol):
    """Protocol for IMS token manager operations."""

    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        ...

    def get_cached_token(self) -> str:
        """Get cached token if available and valid."""
        ...


@runtime_checkable
class TokenTrackerProtocol(Protocol):
    """Protocol for token tracker operations."""

    pass


__all__ = [
    "AsyncClientProtocol",
    "TypedResolverProtocol",
    "ExponentialBackoffStrategyProtocol",
    "EventProcessorProtocol",
    "BatchSizeManagerProtocol",
    "iPaaSRateLimiterProtocol",
    "MetricsStorageProtocol",
    "DistributedLockProtocol",
    "IMSTokenManagerProtocol",
    "TokenTrackerProtocol",
]
