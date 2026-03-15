"""
base_command_handler.py

This module contains the BaseCommandHandler class, which serves as the base class
for all command handlers in the system.
"""

from typing import Any

from packages.core.logging import setup_logger
from packages.slack.channel_events.models import ProcessingResult

logger = setup_logger(__name__)


class BaseCommandHandler:
    """
    Base class for all command handlers.
    Provides common functionality, response formatting, and shared dependency injection logic.

    Subclasses should call super().__init__(...) and pass dependencies as keyword arguments.
    All provided dependencies will be set as instance attributes.
    Optionally, subclasses can enforce required dependencies by checking for None.
    """

    def __init__(self, **dependencies: Any) -> None:
        """
        Shared constructor for command handlers.
        Sets all provided dependencies as instance attributes.

        Args:
            **dependencies: Arbitrary keyword arguments for dependencies (e.g., services, handlers)
        """
        for name, value in dependencies.items():
            setattr(self, name, value)
        logger.info(
            "BaseCommandHandler initialized with dependencies: %s",
            list(dependencies.keys()),
        )

    def create_success_response(self, message: str) -> ProcessingResult:
        """
        Create a standardized success response.

        Args:
            message: The success message to include

        Returns:
            A ProcessingResult containing the success response
        """
        return ProcessingResult(status_code=200, body=message, feedback_sent=True)

    def create_error_response(self, message: str, status_code: int = 500) -> ProcessingResult:
        """
        Create a standardized error response.

        Args:
            message: The error message to include
            status_code: The HTTP status code (default: 500)

        Returns:
            A ProcessingResult containing the error response
        """
        return ProcessingResult(status_code=status_code, body=message, feedback_sent=True)

    def create_validation_error_response(self, message: str) -> ProcessingResult:
        """
        Create a standardized validation error response.

        Args:
            message: The validation error message to include

        Returns:
            A ProcessingResult containing the validation error response
        """
        return ProcessingResult(status_code=400, body=message, feedback_sent=True)
