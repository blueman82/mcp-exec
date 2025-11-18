"""
Base class providing optimized async functionality for API operations.

This module provides a foundational client with improved connection management,
concurrency control, and retry logic for API interactions.
"""

import asyncio
import os
from typing import Any, Awaitable, Callable, Dict, Generic, Optional, TypedDict, TypeVar, Union

import aiohttp
import httpx

from packages.core.constants import BATCH_SIZE

# Import the unified ClientError
from packages.core.exceptions import ClientError

# Import session management utility
from packages.core.http.session_management import (
    SessionCreationError,
    create_session_with_retries,
)
from packages.core.logging import setup_logger

# Import resilience components
from packages.core.resilience.backoff import BackoffStrategy, ExponentialBackoffStrategy

logger = setup_logger(__name__)

# Default maximum concurrent requests (configurable via environment variable)
DEFAULT_MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '10'))

# Type variable for the return type of functions decorated with exponential backoff
T = TypeVar("T")
ConfigType = TypeVar("ConfigType")
ResponseType = TypeVar("ResponseType")


class SafeResponse(TypedDict):
    """A dictionary containing response data that is safe to access outside of a context manager."""

    status: int
    headers: Dict[str, str]
    body: bytes
    content_type: str
    url: str


class _AdaptiveBatcher:
    """Dynamically adjusts batch sizes based on response times and errors."""

    def __init__(
        self,
        initial_size: int = BATCH_SIZE,
        min_size: int = 10,
        max_size: int = 200,
    ) -> None:
        """Initialize the adaptive batcher.

        Args:
            initial_size: Starting batch size (defaults to 100)
            min_size: Minimum allowable batch size (defaults to 10)
            max_size: Maximum allowable batch size (defaults to 200)
        """
        # Default values are aligned with BATCH_SIZE constant but can be overridden
        self.current_size: int = initial_size
        self.min_size: int = min_size
        self.max_size: int = max_size

    def increase_size(self) -> None:
        """Increase batch size after successful operations."""
        pass

    def decrease_size(self) -> None:
        """Decrease batch size after failures."""
        pass

    def get_size(self) -> int:
        """Get the current recommended batch size."""
        return self.current_size


class AsyncClient(Generic[ConfigType, ResponseType]):
    """Base class providing optimized async functionality for API operations."""

    def __init__(
        self,
        config: Optional[ConfigType] = None,
        max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        request_timeout: int = 60,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ) -> None:
        """Initialize the async client.

        Args:
            config: Configuration for the API
            max_concurrent_requests: Maximum number of concurrent requests
            request_timeout: Request timeout in seconds
            backoff_strategy: Strategy for handling retries and backoff (optional)
        """
        if config is None:
            # Handle the case where config is None, maybe raise an error
            # or initialize with a default config if applicable.
            # For now, we'll raise an error as config seems essential.
            raise ValueError("Configuration (config) cannot be None for AsyncClient")
        self.config: ConfigType = config
        self._session: Optional[Union[aiohttp.ClientSession, httpx.AsyncClient]] = None
        self._request_semaphore: asyncio.Semaphore = asyncio.Semaphore(
            max_concurrent_requests
        )
        self._batch_sizer: _AdaptiveBatcher = _AdaptiveBatcher(initial_size=BATCH_SIZE)
        self._request_timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._backoff_strategy: BackoffStrategy = (
            backoff_strategy or ExponentialBackoffStrategy()
        )

    async def execute_with_backoff(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Execute an async function with the configured backoff strategy.

        Args:
            func: The function to execute with backoff
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function

        Returns:
            The result of the function call
        """
        try:
            return await self._backoff_strategy.execute(func, *args, **kwargs)
        except asyncio.TimeoutError as e:
            raise ClientError("Request timed out during backoff execution") from e

    async def setup(self) -> "AsyncClient":
        """Initialize the aiohttp client session if not already done."""
        client_name = self.__class__.__name__  # Get class name for logging

        # Helper to check if session is closed (handles both types)
        def is_session_closed(session):
            if isinstance(session, httpx.AsyncClient):
                return session.is_closed
            elif isinstance(session, aiohttp.ClientSession):
                return session.closed
            return True  # If unknown type, consider it closed

        logger.info(
            "Entering setup() for %s. Current session: %s, Closed: %s",
            client_name,
            self._session,
            is_session_closed(self._session) if self._session else "N/A",
        )
        if self._session and not is_session_closed(self._session):
            logger.info("Session already exists and is open for %s.", client_name)
            return self

        # If session exists but is closed, clean it up first
        if self._session and is_session_closed(self._session):
            logger.warning(
                "Existing session was closed for %s. Cleaning up before creating new one.",
                client_name,
            )
            self._session = None
            await asyncio.sleep(0.1)  # Short pause before recreating

        # Attempt to create a new session using the imported function
        try:
            new_session, last_error = await create_session_with_retries(
                client_name=client_name,
                semaphore_limit=self._request_semaphore._value,
                request_timeout_total=self._request_timeout.total,
                # Pass other parameters if needed, e.g., max_retries
                log_level=logger.level,  # Pass client's logger level
            )
            self._session = new_session
            logger.info(
                "Successfully established session in setup() for %s.",
                client_name,
            )
        except SessionCreationError as e:
            # Store the final error from the session creation attempt
            logger.critical(
                "Failed to establish client session after multiple attempts for %s. Last error: %s",
                client_name,
                e.last_exception,
            )
            # Re-raise as a ClientError for consistency in the client's error handling
            raise ClientError(
                f"Failed to establish client session for {client_name}. Last error: {e.last_exception}"
            ) from e

        return self

    async def cleanup(self) -> None:
        """Clean up shared resources."""
        if self._session:
            # Detect session type and use appropriate cleanup method
            if isinstance(self._session, httpx.AsyncClient):
                # httpx: use is_closed property and aclose() method
                if not self._session.is_closed:
                    logger.info(
                        "Closing httpx session in %s.cleanup()",
                        self.__class__.__name__
                    )
                    try:
                        await self._session.aclose()
                        logger.info(
                            "Successfully closed httpx session in %s",
                            self.__class__.__name__
                        )
                    except Exception as e:
                        logger.error(
                            "Error closing httpx session in %s: %s",
                            self.__class__.__name__,
                            str(e)
                        )
                    finally:
                        self._session = None
            elif isinstance(self._session, aiohttp.ClientSession):
                # aiohttp: use closed property and close() method
                if not self._session.closed:
                    logger.info(
                        "Closing aiohttp session in %s.cleanup()",
                        self.__class__.__name__
                    )
                    try:
                        await self._session.close()
                        logger.info(
                            "Successfully closed aiohttp session in %s",
                            self.__class__.__name__
                        )
                    except Exception as e:
                        logger.error(
                            "Error closing aiohttp session in %s: %s",
                            self.__class__.__name__,
                            str(e)
                        )
                    finally:
                        self._session = None

    async def __aenter__(self) -> "AsyncClient":
        """Support for async context manager.

        Returns:
            Self for use in async with statements
        """
        await self.setup()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[Any],
    ) -> None:
        """Clean up resources on exit."""
        await self.cleanup()

    async def _make_api_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> SafeResponse:
        """Internal helper to make API requests with semaphore and session management.

        Args:
            url: The API endpoint URL
            method: HTTP method (GET or POST)
            headers: Request headers
            params: Query parameters for GET
            json_data: JSON body for POST requests
            data: Form data for POST requests

        Returns:
            A SafeResponse dictionary containing the response status, headers, and body.

        Raises:
            ClientError: For API-specific errors or if session cannot be guaranteed
            aiohttp.ClientError: For HTTP or connection errors
            asyncio.TimeoutError: If the request times out
        """
        async with self._request_semaphore:

            async def perform_request() -> SafeResponse:
                # Ensure we have a valid session by calling setup if needed.
                # setup() handles the logic of checking if session exists/is open.
                await self.setup()

                # After calling setup, we expect self._session to be valid.
                # If it's not, setup() would have raised an error.
                # Helper to check if session is closed (handles both types)
                def is_session_closed(session):
                    if isinstance(session, httpx.AsyncClient):
                        return session.is_closed
                    elif isinstance(session, aiohttp.ClientSession):
                        return session.closed
                    return True

                if not self._session or is_session_closed(self._session):
                    # This should theoretically not happen if setup() works correctly,
                    # but added as a safeguard.
                    error_msg = (
                        f"Critical error: Session for {self.__class__.__name__} is invalid "
                        "even after calling setup(). Lifecycle issue?"
                    )
                    logger.critical(error_msg)
                    raise ClientError(error_msg)

                # Proceed with the actual request using the guaranteed valid session
                logger.info(
                    "Making %s request to %s for %s (params=%s)",
                    method,
                    url,
                    self.__class__.__name__,
                    params,
                )
                try:
                    # httpx and aiohttp have different request APIs
                    if isinstance(self._session, httpx.AsyncClient):
                        # httpx: request() returns Response directly (not a context manager)
                        response = await self._session.request(
                            method,
                            url,
                            headers=headers,
                            params=params,
                            json=json_data,
                            data=data,
                            # timeout already set at client level in session_management.py
                        )
                        logger.info(
                            "Request for %s to %s completed with status %d",
                            self.__class__.__name__,
                            url,
                            response.status_code,
                        )
                        body = response.content

                        # Basic check for successful status codes before returning
                        if response.status_code >= 400:
                            logger.warning(
                                "%s request to %s failed with status %d. Response: %s",
                                method,
                                url,
                                response.status_code,
                                body.decode(errors="ignore"),
                            )
                        # Return a dictionary that is safe to use outside the context manager
                        return {
                            "status": response.status_code,
                            "headers": dict(response.headers),
                            "body": body,
                            "content_type": response.headers.get("content-type", ""),
                            "url": str(response.url),
                        }
                    else:
                        # aiohttp: request() returns a context manager
                        async with self._session.request(
                            method,
                            url,
                            headers=headers,
                            params=params,
                            json=json_data,
                            data=data,
                            timeout=self._request_timeout,  # Use configured timeout
                        ) as response:
                            logger.info(
                                "Request for %s to %s completed with status %d",
                                self.__class__.__name__,
                                url,
                                response.status,
                            )
                            # Read the body while the connection is guaranteed to be open
                            body = await response.read()

                            # Basic check for successful status codes before returning
                            if not response.ok:
                                logger.warning(
                                    "%s request to %s failed with status %d. Response: %s",
                                    method,
                                    url,
                                    response.status,
                                    body.decode(errors="ignore"),
                                )
                            # Return a dictionary that is safe to use outside the context manager
                            return {
                                "status": response.status,
                                "headers": dict(response.headers),
                                "body": body,
                                "content_type": response.content_type,
                                "url": str(response.url),
                            }
                except asyncio.TimeoutError as e:
                    logger.error(
                        "Request timed out for %s to %s: %s",
                        self.__class__.__name__,
                        url,
                        e,
                    )
                    raise ClientError(f"Request timed out: {url}") from e
                except aiohttp.ClientError as e:
                    logger.error(
                        "aiohttp client error for %s to %s: %s",
                        self.__class__.__name__,
                        url,
                        e,
                        exc_info=True,
                    )
                    raise ClientError(f"HTTP Client error: {e}") from e
                except Exception as e:
                    logger.error(
                        "Unexpected error during request for %s to %s: %s",
                        self.__class__.__name__,
                        url,
                        e,
                        exc_info=True,
                    )
                    raise ClientError(f"Unexpected request error: {e}") from e

            # Execute the request logic with backoff strategy
            return await self.execute_with_backoff(perform_request)
