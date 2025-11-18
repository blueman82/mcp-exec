"""
Command Service Protocols

Protocol definitions for command-related services.
"""

from typing import Any, Dict, Protocol, runtime_checkable


__all__ = [
    "AccessCommandProtocol",
    "ListCommandProtocol",
    "QueryCommandProtocol",
    "VerifyCommandProtocol",
    "StatusReportCommandProtocol",
    "ShortLongCommandProtocol",
    "SlackArchiveCommandProtocol",
    "SlackListCommandProtocol",
    "SlackQueryHandlerProtocol",
    "SlackSummaryHandlerProtocol",
    "CommandRouterProtocol",
    "CommandTrackingOperationsProtocol",
    "CommandUsageCSVGeneratorProtocol",
    "FeatureCommandProtocol",
    "FeatureServiceProtocol",
]


@runtime_checkable
class AccessCommandProtocol(Protocol):
    """Protocol for access command operations."""

    pass


@runtime_checkable
class ListCommandProtocol(Protocol):
    """Protocol for list command operations."""

    pass


@runtime_checkable
class QueryCommandProtocol(Protocol):
    """Protocol for query command operations."""

    pass


@runtime_checkable
class VerifyCommandProtocol(Protocol):
    """Protocol for verify command operations."""

    pass


@runtime_checkable
class StatusReportCommandProtocol(Protocol):
    """Protocol for status report command operations."""

    pass


@runtime_checkable
class ShortLongCommandProtocol(Protocol):
    """Protocol for short/long command operations."""

    pass


@runtime_checkable
class SlackArchiveCommandProtocol(Protocol):
    """Protocol for Slack archive command operations."""

    pass


@runtime_checkable
class SlackListCommandProtocol(Protocol):
    """Protocol for Slack list command operations."""

    pass


@runtime_checkable
class SlackQueryHandlerProtocol(Protocol):
    """Protocol for Slack query handler operations."""

    pass


@runtime_checkable
class SlackSummaryHandlerProtocol(Protocol):
    """Protocol for Slack summary handler operations."""

    pass


@runtime_checkable
class CommandRouterProtocol(Protocol):
    """Protocol for command router operations."""

    async def route_command(
        self, body: dict[str, any], response_url: str = ""
    ) -> dict[str, any]:
        """
        Route a Slack command to the appropriate handler.

        Args:
            body: The parsed Slack command payload
            response_url: The response URL from Slack (optional, defaults to empty string)

        Returns:
            A dictionary representing the result or an error
        """
        ...


@runtime_checkable
class CommandTrackingOperationsProtocol(Protocol):
    """Protocol for command tracking operations."""

    pass


@runtime_checkable
class CommandUsageCSVGeneratorProtocol(Protocol):
    """Protocol for command usage CSV generator operations."""

    pass


@runtime_checkable
class FeatureCommandProtocol(Protocol):
    """Protocol for feature command operations."""

    pass


@runtime_checkable
class FeatureServiceProtocol(Protocol):
    """Protocol for FeatureService."""

    async def handle_feature_command(self, params: Any) -> Dict[str, Any]:
        """Handle feature command with given parameters."""
        ...

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled."""
        ...

    def get_feature_config(self, feature_name: str) -> Dict[str, Any]:
        """Get configuration for a specific feature."""
        ...