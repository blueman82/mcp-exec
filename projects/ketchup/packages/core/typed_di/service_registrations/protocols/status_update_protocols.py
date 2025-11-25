"""
Status Update Service Protocols.

This module defines the protocols for status update and processing services
used throughout the Ketchup application for managing status information,
validation, reporting, and analytics.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class StatusUpdateProcessorProtocol(Protocol):
    """Protocol for status update processor operations."""

    async def process_status_update(
        self, channel_id: str, status_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a status update for a channel."""
        ...

    async def validate_status_data(self, status_data: Dict[str, Any]) -> bool:
        """Validate status update data."""
        ...

    async def queue_status_update(
        self, channel_id: str, status_data: Dict[str, Any]
    ) -> str:
        """Queue a status update for processing."""
        ...

    async def get_processing_status(self, update_id: str) -> Dict[str, Any]:
        """Get the processing status of an update."""
        ...


@runtime_checkable
class StatusGeneratorProtocol(Protocol):
    """Protocol for status generator operations."""

    async def generate_channel_status(self, channel_id: str) -> Dict[str, Any]:
        """Generate status information for a channel."""
        ...

    async def generate_user_status(self, user_id: str) -> Dict[str, Any]:
        """Generate status information for a user."""
        ...

    async def generate_system_status(self) -> Dict[str, Any]:
        """Generate overall system status information."""
        ...

    async def generate_custom_status(
        self, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate status based on custom criteria."""
        ...


@runtime_checkable
class StatusValidationServiceProtocol(Protocol):
    """Protocol for status validation service operations."""

    async def validate_status_format(self, status_data: Dict[str, Any]) -> bool:
        """Validate status data format and structure."""
        ...

    async def validate_status_permissions(
        self, user_id: str, channel_id: str, action: str
    ) -> bool:
        """Validate user permissions for status operations."""
        ...

    async def validate_status_content(self, content: str) -> Dict[str, Any]:
        """Validate status content for policy compliance."""
        ...

    async def get_validation_rules(self) -> List[Dict[str, Any]]:
        """Get current validation rules."""
        ...


@runtime_checkable
class StatusReportingServiceProtocol(Protocol):
    """Protocol for status reporting service operations."""

    async def generate_status_report(
        self, report_type: str, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a status report based on criteria."""
        ...

    async def export_status_data(
        self, format_type: str, date_range: Dict[str, Any]
    ) -> str:
        """Export status data in specified format."""
        ...

    async def schedule_report(
        self, report_config: Dict[str, Any]
    ) -> str:
        """Schedule a recurring status report."""
        ...

    async def get_report_history(
        self, report_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get history of status reports."""
        ...


@runtime_checkable
class StatusAnalyticsServiceProtocol(Protocol):
    """Protocol for status analytics service operations."""

    async def analyze_status_trends(
        self, channel_id: str, time_period: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze status trends for a channel over time."""
        ...

    async def generate_status_metrics(
        self, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate status metrics based on criteria."""
        ...

    async def compare_status_performance(
        self, comparison_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare status performance across different criteria."""
        ...

    async def get_analytics_dashboard_data(
        self, dashboard_type: str
    ) -> Dict[str, Any]:
        """Get data for status analytics dashboards."""
        ...


__all__ = [
    "StatusUpdateProcessorProtocol",
    "StatusGeneratorProtocol",
    "StatusValidationServiceProtocol",
    "StatusReportingServiceProtocol",
    "StatusAnalyticsServiceProtocol",
]