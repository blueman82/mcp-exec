"""
Archive Processing Service Protocols.

This module defines the protocols for archive processing services
used throughout the Ketchup application for managing channel archival,
validation, reporting, analytics, and cleanup operations.
"""

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class ArchiveValidationServiceProtocol(Protocol):
    """Protocol for archive validation service operations."""

    async def validate_archive_eligibility(self, channel_id: str) -> Dict[str, Any]:
        """Validate if a channel is eligible for archiving."""
        ...

    async def validate_archive_permissions(
        self, user_id: str, channel_id: str
    ) -> bool:
        """Validate user permissions for archive operations."""
        ...

    async def validate_archive_conditions(self, channel_id: str) -> Dict[str, Any]:
        """Validate archive conditions like activity thresholds."""
        ...

    async def check_archive_dependencies(self, channel_id: str) -> List[str]:
        """Check for dependencies that might prevent archiving."""
        ...

    async def get_validation_report(self, channel_id: str) -> Dict[str, Any]:
        """Generate comprehensive validation report for archiving."""
        ...


@runtime_checkable
class ArchiveReportingServiceProtocol(Protocol):
    """Protocol for archive reporting service operations."""

    async def generate_archive_report(
        self, report_type: str, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate archive reports based on specified criteria."""
        ...

    async def export_archive_data(
        self, format_type: str, date_range: Dict[str, Any]
    ) -> str:
        """Export archive data in specified format (CSV, JSON, etc)."""
        ...

    async def schedule_archive_report(
        self, report_config: Dict[str, Any]
    ) -> str:
        """Schedule recurring archive reports."""
        ...

    async def get_archive_statistics(
        self, time_period: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get archive statistics for specified time period."""
        ...

    async def generate_compliance_report(
        self, compliance_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate compliance reports for archived channels."""
        ...


@runtime_checkable
class ArchiveAnalyticsServiceProtocol(Protocol):
    """Protocol for archive analytics service operations."""

    async def analyze_archive_trends(
        self, time_period: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze archiving trends over specified time period."""
        ...

    async def generate_archive_metrics(
        self, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate archive metrics based on criteria."""
        ...

    async def predict_archive_candidates(
        self, prediction_criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Predict channels that may need archiving."""
        ...

    async def analyze_archive_impact(self, channel_ids: List[str]) -> Dict[str, Any]:
        """Analyze the impact of archiving specific channels."""
        ...

    async def get_analytics_dashboard_data(
        self, dashboard_type: str
    ) -> Dict[str, Any]:
        """Get data for archive analytics dashboards."""
        ...


@runtime_checkable
class ArchiveCleanupServiceProtocol(Protocol):
    """Protocol for archive cleanup service operations."""

    async def cleanup_archived_channel_data(self, channel_id: str) -> Dict[str, Any]:
        """Clean up data associated with archived channels."""
        ...

    async def purge_old_archive_data(
        self, retention_policy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Purge old archive data based on retention policies."""
        ...

    async def cleanup_archive_metadata(self, channel_id: str) -> bool:
        """Clean up metadata for archived channels."""
        ...

    async def optimize_archive_storage(
        self, optimization_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize storage for archived data."""
        ...

    async def get_cleanup_status(self, cleanup_job_id: str) -> Dict[str, Any]:
        """Get status of cleanup operations."""
        ...

    async def schedule_cleanup_job(
        self, cleanup_config: Dict[str, Any]
    ) -> str:
        """Schedule cleanup jobs for archive maintenance."""
        ...


__all__ = [
    "ArchiveValidationServiceProtocol",
    "ArchiveReportingServiceProtocol",
    "ArchiveAnalyticsServiceProtocol",
    "ArchiveCleanupServiceProtocol",
]