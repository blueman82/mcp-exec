"""
Manages the creation of resilient HTTP client sessions.

Supports both aiohttp and httpx based on feature flags.
When httpx is enabled, provides HTTP/2 support for improved performance.
"""

import asyncio
import logging
from typing import Optional, Tuple, Union

import aiohttp
import httpx

from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class SessionCreationError(Exception):
    """Custom exception for session creation failures after retries."""

    def __init__(self, message: str, last_exception: Optional[Exception]):
        self.message = message
        self.last_exception = last_exception
        super().__init__(message)


async def create_session_with_retries(
    client_name: str,
    semaphore_limit: int,
    request_timeout_total: Optional[float] = 60.0,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    log_level: int = logging.INFO,
) -> Tuple[
    Optional[Union[aiohttp.ClientSession, httpx.AsyncClient]], Optional[Exception]
]:
    """Create an HTTP client session with retries and exponential backoff.

    Supports both aiohttp and httpx based on KETCHUP_USE_HTTPX feature flag.
    When httpx is enabled, creates an AsyncClient with HTTP/2 support for
    improved performance through connection multiplexing.

    Args:
        client_name: Name of the client for logger purposes.
        semaphore_limit: Limit for the TCPConnector (aiohttp) or max_connections (httpx).
        request_timeout_total: Total request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay for backoff in seconds.
        log_level: logger level to use for this function.

    Returns:
        Tuple[Optional[Union[aiohttp.ClientSession, httpx.AsyncClient]], Optional[Exception]]:
            A tuple containing the created session (or None on failure)
            and the last exception encountered (or None on success).

    Raises:
        SessionCreationError: If session creation fails after all retries.
    """
    retry_count = 0
    last_exception = None
    current_logger = logging.getLogger(client_name)  # Get logger specific to client
    current_logger.setLevel(log_level)

    # Check which HTTP library to use
    use_httpx = FeatureFlags.is_httpx_enabled()
    library_name = "httpx" if use_httpx else "aiohttp"

    while retry_count < max_retries:
        current_logger.info(
            "Session creation attempt %d/%d using %s",
            retry_count + 1,
            max_retries,
            library_name,
        )
        try:
            if use_httpx:
                # Create httpx.AsyncClient with HTTP/2 support
                limits = httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=FeatureFlags.get_httpx_pool_limits(),
                    keepalive_expiry=60,
                )
                session = httpx.AsyncClient(
                    http2=FeatureFlags.is_http2_enabled(),
                    limits=limits,
                    timeout=httpx.Timeout(request_timeout_total),
                )
                session_state = session.is_closed
                current_logger.info(
                    "httpx AsyncClient created (attempt %d/%d). HTTP/2: %s, Closed: %s",
                    retry_count + 1,
                    max_retries,
                    FeatureFlags.is_http2_enabled(),
                    session_state,
                )
            else:
                # Create aiohttp.ClientSession with optional keep-alive tuning
                if FeatureFlags.is_keepalive_tuning_enabled():
                    keepalive_timeout = FeatureFlags.get_keepalive_timeout()
                    dns_cache_ttl = FeatureFlags.get_dns_cache_ttl()
                    connector = aiohttp.TCPConnector(
                        limit=semaphore_limit,
                        ttl_dns_cache=dns_cache_ttl,
                        enable_cleanup_closed=True,
                        force_close=False,
                        keepalive_timeout=keepalive_timeout,
                    )
                    current_logger.info(
                        "Keep-alive tuning enabled: timeout=%ds, DNS cache=%ds",
                        keepalive_timeout,
                        dns_cache_ttl,
                    )
                else:
                    connector = aiohttp.TCPConnector(limit=semaphore_limit)
                    current_logger.debug("Using legacy TCPConnector configuration")

                timeout = aiohttp.ClientTimeout(total=request_timeout_total)
                session = aiohttp.ClientSession(connector=connector, timeout=timeout)
                session_state = session.closed if session else "None"
                current_logger.info(
                    "aiohttp ClientSession created (attempt %d/%d). Closed: %s",
                    retry_count + 1,
                    max_retries,
                    session_state,
                )

            return session, None  # Return the created session and None for exception

        except Exception as e:
            last_exception = e  # Store the last exception
            retry_count += 1
            current_logger.error(
                "Failed to create session (attempt %d/%d): %s",
                retry_count,
                max_retries,
                e,
                exc_info=True,
            )
            if retry_count >= max_retries:
                break  # Exit loop if max retries reached

            # Basic exponential backoff
            wait_time = initial_delay * (2 ** (retry_count - 1))
            current_logger.info(
                "Retrying session creation after %.2f seconds", wait_time
            )
            await asyncio.sleep(wait_time)

    # If loop finishes without returning a session, log critical error and raise
    error_message = (
        f"Max retries ({max_retries}) reached for {client_name} session creation. "
        f"Last error: {last_exception}"
    )
    current_logger.critical(error_message)
    raise SessionCreationError(error_message, last_exception)  # Raise custom error
