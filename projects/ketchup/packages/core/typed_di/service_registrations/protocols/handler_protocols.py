"""
Handler Service Protocols

Protocol definitions for various handler services including flag review handlers,
access request handlers, and other interactive element handlers.
"""

from typing import Protocol, runtime_checkable


__all__ = [
    "BaseCommandHandlerProtocol",
    "FlagReviewDatabaseOperationsProtocol",
    "FlagReviewDMHandlerProtocol",
    "FlagReviewMessageHandlerProtocol",
    "FlagReviewModalManagerProtocol",
    "AccessRequestHandlerProtocol",
    "AccessRequestBlocksProtocol",
    "AccessRequestMonitorProtocol",
    "FlagReviewHandlerProtocol",
    "HomeTabHandlerProtocol",
    "OpenAIHandlerProtocol",
    "ShortcutHandlerProtocol",
    "TrustEndorsementHandlerProtocol",
    "UsageExportHandlerProtocol",
]


@runtime_checkable
class BaseCommandHandlerProtocol(Protocol):
    """Protocol for base command handling."""

    pass


@runtime_checkable
class FlagReviewDatabaseOperationsProtocol(Protocol):
    """Protocol for flag review database operations."""

    pass


@runtime_checkable
class FlagReviewDMHandlerProtocol(Protocol):
    """Protocol for flag review DM handling."""

    pass


@runtime_checkable
class FlagReviewMessageHandlerProtocol(Protocol):
    """Protocol for flag review message handling."""

    pass


@runtime_checkable
class FlagReviewModalManagerProtocol(Protocol):
    """Protocol for flag review modal management."""

    pass


@runtime_checkable
class AccessRequestHandlerProtocol(Protocol):
    """Protocol for access request handler operations."""

    pass


@runtime_checkable
class AccessRequestBlocksProtocol(Protocol):
    """Protocol for access request blocks operations."""

    pass


@runtime_checkable
class AccessRequestMonitorProtocol(Protocol):
    """Protocol for access request monitoring operations."""

    pass


@runtime_checkable
class FlagReviewHandlerProtocol(Protocol):
    """Protocol for flag review handler operations."""

    pass


@runtime_checkable
class HomeTabHandlerProtocol(Protocol):
    """Protocol for home tab handler operations."""

    pass


@runtime_checkable
class OpenAIHandlerProtocol(Protocol):
    """Protocol for OpenAI handler operations."""

    pass


@runtime_checkable
class ShortcutHandlerProtocol(Protocol):
    """Protocol for shortcut handler operations."""

    pass


@runtime_checkable
class TrustEndorsementHandlerProtocol(Protocol):
    """Protocol for trust endorsement handler operations."""

    pass


@runtime_checkable
class UsageExportHandlerProtocol(Protocol):
    """Protocol for usage export handler operations."""

    pass