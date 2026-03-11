"""
Azure Async Client

This module provides a base class for asynchronous interactions with Azure OpenAI services
with improved connection management, concurrency control, and error handling.
"""

import json
from typing import Any, Dict, Optional, TypeVar

import orjson

from packages.core.async_client import (
    AsyncClient,
    BackoffStrategy,
    ExponentialBackoffStrategy,
    SafeResponse,
)
from packages.core.constants import MAX_RETRIES
from packages.core.exceptions import ClientError
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Type variable for function return types
T = TypeVar("T")


class AzureClientError(ClientError):
    """Exception for Azure-specific client errors.

    Attributes:
        message: Error message
        status_code: HTTP status code (optional)
        response_data: Response data from the API (optional)
        request_id: Azure request ID for tracking (optional)
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Initialize the AzureClientError.

        Args:
            message: Error message
            status_code: HTTP status code (optional)
            response_data: Response data from the API (optional)
            request_id: Azure request ID for tracking (optional)
        """
        super().__init__(message, status_code, response_data)
        self.request_id = request_id

    def __str__(self) -> str:
        """Return string representation of the error."""
        error_msg = self.message
        if self.status_code:
            error_msg += f" (Status: {self.status_code})"
        if self.request_id:
            error_msg += f" (Request ID: {self.request_id})"
        return error_msg


class AzureConfig:
    """Configuration for Azure OpenAI services."""

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None) -> None:
        """Initialize Azure configuration.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
        """
        self.api_key = api_key
        self.endpoint = endpoint

    def get_headers(self, content_type: str = "application/json") -> Dict[str, str]:
        """Get headers for Azure API requests.

        Args:
            content_type: Content type header value

        Returns:
            Dict containing necessary headers for API requests
        """
        headers = {
            "Content-Type": content_type,
        }
        if self.api_key:
            headers["api-key"] = self.api_key  # type: ignore[dict-item] # Only add if not None (ignore likely false positive)
        return headers


class AzureAsyncClient(AsyncClient[AzureConfig, Dict[str, Any]]):
    """Base class for asynchronous interactions with Azure OpenAI services.

    Provides improved connection management, concurrency control, and retry logic.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        max_concurrent_requests: int = 5,
        request_timeout: int = 180,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ) -> None:
        """Initialize the Azure async client.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            max_concurrent_requests: Maximum number of concurrent requests
            request_timeout: Request timeout in seconds
            backoff_strategy: Strategy for handling retries and backoff (optional)
        """
        self._config = AzureConfig(api_key=api_key, endpoint=endpoint)

        # Explicitly store the strategy that will be used by this class instance
        # This ensures self.backoff_strategy is set with the correct strategy
        # before calling super().__init__ and for use in _make_azure_api_request.
        self.backoff_strategy = backoff_strategy or ExponentialBackoffStrategy(
            max_retries=MAX_RETRIES
        )

        super().__init__(
            config=self._config,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout,
            backoff_strategy=self.backoff_strategy,  # Pass the now definite strategy
        )
        self._endpoint = endpoint
        self._api_key = api_key
        logger.info(f"AzureAsyncClient initialized with endpoint: {self._endpoint}")

    async def _make_azure_api_request(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request to Azure OpenAI with error handling and retry logic.

        This method orchestrates the request by:
        1. Defining the core request logic (making the HTTP call, processing response).
        2. Executing this core logic using the instance's configured `backoff_strategy`,
           which handles retries for retryable errors.

        Args:
            url: The API endpoint URL.
            method: HTTP method (e.g., "POST", "GET").
            headers: Optional request headers.
            json_data: Optional JSON payload for the request (used as params for GET).

        Returns:
            A dictionary containing the parsed JSON response from the API.

        Raises:
            AzureClientError: For API-specific errors after exhausting retries.
            aiohttp.ClientError: For network/connection errors after exhausting retries.
            asyncio.TimeoutError: If the request times out after exhausting retries.
            Exception: For other unexpected errors during the process.
        """

        async def _core_request_logic() -> Dict[str, Any]:
            current_headers = headers
            # Use self._api_key which is set in __init__
            if not current_headers and self._api_key:
                current_headers = self._config.get_headers()

            try:
                # self._make_api_request is from the parent AsyncClient
                if method.upper() == "GET":
                    safe_response = await self._make_api_request(  # From AsyncClient
                        url, method, current_headers, params=json_data
                    )
                else:
                    safe_response = await self._make_api_request(  # From AsyncClient
                        url, method, current_headers, json_data=json_data
                    )

                return await self._process_response(safe_response)
            except Exception:
                # The backoff_strategy will handle logging.
                raise  # Re-raise for the backoff strategy to catch

        # Ensure backoff_strategy is available (should be set by AsyncClient.__init__)
        if not hasattr(self, "backoff_strategy") or not self.backoff_strategy:
            logger.error(
                "CRITICAL: backoff_strategy not found on AzureAsyncClient instance. This should not happen."
            )
            # Fallback to direct call, though this bypasses configured retries
            return await _core_request_logic()

        return await self.backoff_strategy.execute(_core_request_logic)

    async def _process_response(self, response: SafeResponse) -> Dict[str, Any]:
        """Process the API response and handle errors.

        Args:
            response: The SafeResponse dictionary from the base client

        Returns:
            Dict containing the parsed JSON response

        Raises:
            AzureClientError: For API errors or non-2xx status codes
        """
        request_id = response["headers"].get("x-request-id", "unknown")

        if response["status"] == 429:
            retry_after = response["headers"].get("retry-after", "60")
            # This error will be caught and retried by the backoff_strategy
            raise AzureClientError(
                f"Rate limit exceeded. Retry after {retry_after} seconds.",
                status_code=429,
                request_id=request_id,
            )

        if response["status"] >= 400:
            error_text = response["body"].decode(errors="ignore")
            try:
                # Try to parse the error text as JSON
                error_json = orjson.loads(response["body"])
                error_message = error_json.get("error", {}).get("message", error_text)
            except (orjson.JSONDecodeError, json.JSONDecodeError):
                error_message = error_text

            # This error will be caught and retried by the backoff_strategy if applicable
            raise AzureClientError(
                f"API request failed: {error_message}",
                status_code=response["status"],
                response_data={"body": error_text},
                request_id=request_id,
            )

        # For successful responses, try to parse JSON
        try:
            # Use orjson for performance, with a fallback to standard json if needed
            return orjson.loads(response["body"])
        except (orjson.JSONDecodeError, json.JSONDecodeError):
            body_text = response["body"].decode(errors="ignore")
            logger.warning("Failed to parse JSON response: %s...", body_text[:200])
            # Return a dict indicating non-JSON response, or raise specific error
            return {"text_response": body_text}
