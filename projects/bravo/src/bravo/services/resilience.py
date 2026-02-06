"""Generic async retry with exponential backoff."""

import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx
import structlog

logger = structlog.get_logger(__name__)


def _calc_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Calculate backoff delay with jitter.

    Args:
        attempt: 1-based attempt number.
        base_delay: Base delay in seconds.
        max_delay: Maximum delay cap in seconds.

    Returns:
        Delay in seconds with jitter applied.
    """
    delay: float = min(base_delay * 2 ** (attempt - 1), max_delay)
    return delay * random.uniform(0.8, 1.2)


async def retry_with_backoff(
    fn: Callable[[], Awaitable[httpx.Response]],
    *,
    max_retries: int,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    operation: str = "",
) -> httpx.Response:
    """Retry an async HTTP call with exponential backoff.

    Retries on transport errors, timeouts, and retryable HTTP status codes
    (429, 502, 503, 504). Non-retryable HTTP errors are raised immediately.

    Args:
        fn: Async callable that returns an httpx.Response.
        max_retries: Maximum number of attempts.
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum backoff delay cap in seconds.
        operation: Description of the operation for logging.

    Returns:
        The successful httpx.Response.

    Raises:
        httpx.TransportError: If all retries exhausted on transport errors.
        httpx.TimeoutException: If all retries exhausted on timeouts.
        httpx.HTTPStatusError: If a non-retryable HTTP error occurs, or
            all retries exhausted on retryable status codes.
    """
    last_exc: Exception | None = None
    retryable_statuses = {429, 502, 503, 504}

    for attempt in range(1, max_retries + 1):
        try:
            resp = await fn()
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt == max_retries:
                logger.error(
                    "retry_exhausted",
                    operation=operation,
                    attempt=attempt,
                    error=str(exc),
                )
                raise
            delay = _calc_delay(attempt, base_delay, max_delay)
            logger.warning(
                "retry_transport_error",
                operation=operation,
                attempt=attempt,
                max_retries=max_retries,
                delay=delay,
                error=str(exc),
            )
            await asyncio.sleep(delay)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in retryable_statuses:
                raise
            last_exc = exc
            if attempt == max_retries:
                logger.error(
                    "retry_exhausted",
                    operation=operation,
                    attempt=attempt,
                    status_code=exc.response.status_code,
                )
                raise
            delay = _calc_delay(attempt, base_delay, max_delay)
            logger.warning(
                "retry_http_error",
                operation=operation,
                attempt=attempt,
                max_retries=max_retries,
                status_code=exc.response.status_code,
                delay=delay,
            )
            await asyncio.sleep(delay)

    # Should never reach here, but satisfy type checker
    raise last_exc  # type: ignore[misc]
