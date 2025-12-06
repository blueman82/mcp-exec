"""Fast JSON parsing utilities using orjson."""

from typing import Any

import aiohttp
import orjson

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def parse_json_response(response) -> Any:
    """Parse JSON from aiohttp response using orjson for better performance.

    Args:
        response: aiohttp ClientResponse object

    Returns:
        Parsed JSON data (dict, list, or primitive types)

    Raises:
        aiohttp.ClientConnectionError: Re-raised with more context if connection is closed
        orjson.JSONDecodeError: If the response contains invalid JSON

    Note:
        orjson is significantly faster than standard json library,
        especially for large payloads like Slack channel histories.
    """
    try:
        content = await response.read()
        return orjson.loads(content)
    except aiohttp.ClientConnectionError as e:
        # Log additional context about the connection error
        logger.error(
            "Connection closed while reading response body. " "Status: %s, URL: %s, Headers: %s",
            getattr(response, "status", "unknown"),
            getattr(response, "url", "unknown"),
            dict(getattr(response, "headers", {})),
        )
        # Re-raise with more context
        raise aiohttp.ClientConnectionError(
            f"Connection closed after receiving {getattr(response, 'status', 'unknown')} response. "
            "The server may have closed the connection before we could read the response body."
        ) from e
