"""
Custom exceptions for the core package.
"""

from typing import Any, Dict, Optional


class ClientError(Exception):
    """Exception raised for API client errors.

    Attributes:
        message: Error message
        status_code: HTTP status code (optional)
        response_data: Response data from the API (optional)
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the ClientError.

        Args:
            message: Error message
            status_code: HTTP status code (optional)
            response_data: Response data from the API (optional)
        """
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        return self.message


class InvalidBlocksForResponseUrlError(ClientError):
    """Indicates blocks were invalid specifically for a Slack response_url."""

    # This class inherits all necessary functionality (__init__, __str__, attributes)
    # from the parent ClientError class.
    # Its primary purpose is to provide a distinct exception type that can be
    # caught specifically in try...except blocks to trigger different error
    # handling logic (e.g., changing fallback behavior in posting.py) when
    # blocks are invalid for a response_url.
    # No additional methods or attributes are needed here, so 'pass' is used.
    pass


class MessagePreparationError(Exception):
    """Exception raised for errors during message preparation for AI models."""

    # No custom attributes or methods needed; inherits all from Exception.
    # 'pass' is used as a syntactic placeholder because the class body cannot be empty.
    pass
