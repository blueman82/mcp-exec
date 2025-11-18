"""
Provides backoff strategies and decorators for resilient operations.
"""

import asyncio
import random
from typing import Any, Awaitable, Callable, List, Optional, Tuple, Type, TypeVar

import aiohttp

from packages.core.constants import MAX_RETRIES
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Type variable for the return type of functions decorated with exponential backoff
T = TypeVar("T")


class BackoffStrategy:
    """Interface for backoff strategies."""

    async def execute(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Execute a function with backoff strategy.

        Args:
            func: The function to execute with backoff
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Backoff strategies must implement execute")


class ExponentialBackoffStrategy(BackoffStrategy):
    """Exponential backoff implementation."""

    def __init__(
        self,
        max_retries: int = MAX_RETRIES,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        retryable_errors: Optional[List[str]] = None,
        retryable_exception_types: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        """Initialize exponential backoff strategy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay time in seconds
            max_delay: Maximum delay time in seconds
            jitter: Whether to add random jitter to delay times
            retryable_errors: List of error strings to retry on
            retryable_exception_types: Tuple of Exception types to retry on
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_errors = retryable_errors or [
            "ratelimited",
            "timeout",
            "socket",
            "connection",
            "server disconnected",
            "connection reset by peer",
            "not_in_channel",
        ]
        self.retryable_exception_types = retryable_exception_types or (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        )

    async def execute(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Execute function with exponential backoff.

        Args:
            func: The function to execute with backoff
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            Exception: The last exception encountered after max retries
        """
        retry_count = 0
        last_exception = None

        while retry_count <= self.max_retries:  # Include initial attempt
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                last_exception = e
                retry_count += 1

                # Check if the error is retryable based on type OR message string
                is_retryable_type = isinstance(e, self.retryable_exception_types)
                error_str = str(e).lower()
                is_retryable_string = any(
                    err in error_str for err in self.retryable_errors
                )

                is_retryable = is_retryable_type or is_retryable_string

                # If not retryable or we've used all retries, raise the exception
                if not is_retryable or retry_count > self.max_retries:
                    logger.error(
                        "Non-retryable error ('%s' type: %s, string: %s) or max retries (%s) exceeded: %s",
                        type(e).__name__,
                        is_retryable_type,
                        is_retryable_string,
                        self.max_retries,
                        str(e),
                    )
                    raise

                # Calculate delay with exponential backoff
                delay = min(self.base_delay * (2 ** (retry_count - 1)), self.max_delay)

                # Add jitter if enabled (±15%)
                if self.jitter:
                    jitter_factor = random.uniform(0.85, 1.15)
                    delay *= jitter_factor

                logger.warning(
                    "Request failed with %s. Retry %s/%s after %.2f seconds",
                    str(e),
                    retry_count,
                    self.max_retries,
                    delay,
                )

                await asyncio.sleep(delay)

        # We should never reach here due to the raise in the loop,
        # but just in case...
        raise last_exception if last_exception else RuntimeError("Max retries exceeded")


def with_exponential_backoff(
    max_retries: int = MAX_RETRIES,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable_errors: Optional[List[str]] = None,
    retryable_exception_types: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for applying exponential backoff to async functions.

    Uses ExponentialBackoffStrategy internally.

    Args:
        max_retries: Maximum number of retry attempts before giving up
        base_delay: Base delay time for the internal strategy
        max_delay: Maximum delay time for the internal strategy
        jitter: Whether to add jitter for the internal strategy
        retryable_errors: Error strings for the internal strategy
        retryable_exception_types: Exception types for the internal strategy

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        # Create a default strategy instance using decorator args
        # Note: This creates a new strategy instance *per decorated function*
        strategy = ExponentialBackoffStrategy(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            jitter=jitter,
            retryable_errors=retryable_errors,
            retryable_exception_types=retryable_exception_types,
        )

        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Delegate execution to the strategy instance
            return await strategy.execute(func, *args, **kwargs)

        return wrapper

    return decorator
