"""
aiohttp_helpers.py

Helper utilities for mocking aiohttp in tests.
"""

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import orjson


class MockAiohttpResponse:
    """Mock aiohttp response that supports async context manager protocol."""

    def __init__(
        self,
        status: int = 200,
        json_data: Optional[Dict[str, Any]] = None,
        text_data: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        self.headers = headers or {}

    async def json(self):
        """Mock json() method."""
        return self._json_data

    async def text(self):
        """Mock text() method."""
        return self._text_data

    async def __aenter__(self):
        """Support async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async context manager."""
        return None

    async def read(self):
        """Mock read() method for orjson compatibility."""
        if self._json_data is not None:
            return orjson.dumps(self._json_data)
        elif self._text_data is not None:
            return (
                self._text_data.encode()
                if isinstance(self._text_data, str)
                else self._text_data
            )
        return b"{}"


def create_mock_session(method_responses: Dict[str, MockAiohttpResponse]):
    """
    Create a mock aiohttp ClientSession with specified responses.

    Args:
        method_responses: Dict mapping HTTP methods to their mock responses
                         e.g., {'get': MockAiohttpResponse(200), 'post': MockAiohttpResponse(201)}

    Returns:
        Mock ClientSession
    """
    mock_session = MagicMock()
    mock_session_instance = MagicMock()

    # Set up the context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Set up HTTP methods to return the response directly (not as a coroutine)
    for method, response in method_responses.items():
        setattr(mock_session_instance, method, MagicMock(return_value=response))

    return mock_session


def create_mock_session_class(method_responses: Dict[str, MockAiohttpResponse]):
    """
    Create a mock ClientSession class that can be used with patch.

    Args:
        method_responses: Dict mapping HTTP methods to their mock responses

    Returns:
        Mock ClientSession class
    """
    mock_session_class = MagicMock()
    mock_session_class.return_value = create_mock_session(method_responses)
    return mock_session_class
