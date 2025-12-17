"""
JIRA Reporter Service Module.

This module provides JIRA reporting functionality including:
- Report generation for incident channels
- Channel monitoring for reporting eligibility
- Archive handling for accessing archived channels
- JIRA ticket discovery and linking
- JIRA API interaction via MCP
"""

from .archive_handler import JiraReporterArchiveHandler
from .channel_monitor import ChannelMonitor
from .constants import (
    BASE_RETRY_DELAY,
    MAX_RETRY_ATTEMPTS,
    MAX_RETRY_DELAY,
    RETRYABLE_ERROR_PATTERNS,
    JiraReportStatus,
)
from .orchestration import (
    process_channel,
    process_sqs_messages,
    run_reporting_cycle,
    write_health_status,
    write_last_successful_run,
)
from .report_generator import ReportGenerator
from .service import JiraService
from .ticket_discovery import JiraTicketDiscovery

__all__ = [
    # Main service
    "JiraService",
    # Orchestration functions
    "run_reporting_cycle",
    "process_channel",
    "process_sqs_messages",
    "write_health_status",
    "write_last_successful_run",
    # Report generation
    "ReportGenerator",
    # Channel monitoring
    "ChannelMonitor",
    # Archive handling
    "JiraReporterArchiveHandler",
    # Ticket discovery
    "JiraTicketDiscovery",
    # Constants
    "JiraReportStatus",
    "MAX_RETRY_ATTEMPTS",
    "BASE_RETRY_DELAY",
    "MAX_RETRY_DELAY",
    "RETRYABLE_ERROR_PATTERNS",
]
