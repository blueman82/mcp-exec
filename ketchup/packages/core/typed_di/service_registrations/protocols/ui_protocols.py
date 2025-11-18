"""
UI Service Protocols

Protocol definitions for UI-related services including Block Kit builders,
message formatters, and feedback operations.
"""

from typing import Optional, Protocol, runtime_checkable


__all__ = [
    "BlockKitBuilderProtocol",
    "SlackMessageFormatterProtocol",
    "FeedbackOperationsProtocol",
    "BlockBuilderProtocol",
    "FeedbackReactionsHandlerProtocol",
    "FeedbackReportHandlerProtocol",
    "ArchiveMessageHandlerProtocol",
    "LookupMessageHandlerProtocol",
    "QueryMessageHandlerProtocol",
    "ReportMessageHandlerProtocol",
    "StatusMessageHandlerProtocol",
    "SummaryMessageHandlerProtocol",
    "ParameterMessageHandlerProtocol",
]


@runtime_checkable
class BlockKitBuilderProtocol(Protocol):
    """Protocol for Block Kit builder operations."""

    pass


@runtime_checkable
class SlackMessageFormatterProtocol(Protocol):
    """Protocol for Slack message formatter operations."""

    pass


@runtime_checkable
class FeedbackOperationsProtocol(Protocol):
    """Protocol for feedback operations."""

    pass


@runtime_checkable
class BlockBuilderProtocol(Protocol):
    """Protocol for block builder operations."""

    pass


@runtime_checkable
class FeedbackReactionsHandlerProtocol(Protocol):
    """Protocol for feedback reactions handler operations."""

    pass


@runtime_checkable
class FeedbackReportHandlerProtocol(Protocol):
    """Protocol for feedback report handler operations."""

    pass


@runtime_checkable
class ArchiveMessageHandlerProtocol(Protocol):
    """Protocol for archive message handler operations."""

    pass


@runtime_checkable
class LookupMessageHandlerProtocol(Protocol):
    """Protocol for lookup message handler operations."""

    pass


@runtime_checkable
class QueryMessageHandlerProtocol(Protocol):
    """Protocol for query message handler operations."""

    pass


@runtime_checkable
class ReportMessageHandlerProtocol(Protocol):
    """Protocol for report message handler operations."""

    async def send_message(
        self,
        combined_command: str,
        response_url: str,
        response_text: str,
        query: Optional[str] = None,
        target_channel: Optional[str] = None,
        execution_channel: Optional[str] = None,
    ) -> None:
        """Send a formatted report message to Slack."""
        ...


@runtime_checkable
class StatusMessageHandlerProtocol(Protocol):
    """Protocol for status message handler operations."""

    async def send_message(
        self,
        combined_command: str,
        response_url: str,
        response_text: str,
        query: Optional[str] = None,
        target_channel: Optional[str] = None,
        execution_channel: Optional[str] = None,
    ) -> None:
        """Send a formatted status message to Slack."""
        ...


@runtime_checkable
class SummaryMessageHandlerProtocol(Protocol):
    """Protocol for summary message handler operations."""

    pass


@runtime_checkable
class ParameterMessageHandlerProtocol(Protocol):
    """Protocol for parameter message handler operations."""

    pass