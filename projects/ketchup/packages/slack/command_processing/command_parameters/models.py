"""
Command parameter models.

This module contains the dataclasses and enums for command parameters.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Optional


class CommandType(Enum):
    """Types of supported Ketchup commands."""

    SHORT = "short"  # Deprecated: redirects to STATUS
    LONG = "long"  # Deprecated: redirects to REPORT
    QUERY = "query"
    STATUS = "status"
    REPORT = "report"
    ARCHIVE = "archive"
    LIST = "list"
    FEATURE = "feature"
    ACCESS = "access"
    METRICS = "metrics"

    def __str__(self) -> str:
        return self.value


class CommandContext(Enum):
    """Context in which a command is executed."""

    DIRECT_MESSAGE = "directmessage"
    PUBLIC_CHANNEL = "public_channel"

    def __str__(self) -> str:
        return self.value


@dataclass
class CommandParams:
    """Base class for all command parameters."""

    user_id: str
    user_name: str
    channel_id: str
    command_text: str
    response_url: str
    original_command: str
    command_type: CommandType
    context: CommandContext = CommandContext.DIRECT_MESSAGE
    trigger_id: Optional[str] = None


@dataclass
class ReportCommandParams(CommandParams):
    """
    Parameters for report commands (status, short, long, archive).

    These commands generate different types of reports about a channel.
    """

    # Non-default fields first (must come before inherited default fields)
    request_type: Literal["status", "short", "long", "archive"] = "status"


@dataclass
class QueryCommandParams(CommandParams):
    """
    Parameters for query commands.

    Query commands allow users to ask questions about channel content.
    """

    query_text: Optional[str] = None  # Required field, must be set
    target_channel_id: Optional[str] = None  # Channel to query about


@dataclass
class ChannelListCommandParams(CommandParams):
    """
    Parameters for list commands.

    List commands show all eligible channels or user's channels.
    """

    list_type: Optional[Literal["all", "my"]] = None  # Required field, must be set


@dataclass
class FeatureCommandParams(CommandParams):
    """
    Parameters for feature commands.

    The feature command manages feature flags for beta users and channels.
    Format: /ketchup feature <feature_name> <action> [user_mention|channel_id]
    Available actions: enable, disable, list, status
    """

    feature_name: Optional[str] = None  # Required field, must be set
    action: Optional[str] = None  # Required field, must be set
    target_user_id: Optional[str] = None  # User to enable/disable (for NLP feature)
    target_channel_id: Optional[str] = (
        None  # Channel to enable/disable (for status_updater feature)
    )


@dataclass
class AccessCommandParams(CommandParams):
    """
    Parameters for access command.

    The access command creates access requests for sensitive channels or resources.
    Format: /ketchup access <resource> <justification>
    """

    resource: Optional[str] = None  # Required field, must be set
    justification: Optional[str] = None  # Required field, must be set
    request_type: Literal["channel_access", "resource_access"] = "channel_access"


@dataclass
class ArchiveCommandParams(CommandParams):
    """
    Parameters for archive command.

    Archive commands provide archive reports and management for channels.
    """

    archive_days: Optional[int] = 30  # Number of days to look back for archive
    include_metadata: bool = True  # Whether to include channel metadata in archive report


@dataclass
class StatusReportCommandParams(CommandParams):
    """
    Parameters for status report commands.

    Status report commands generate status reports about channel activity.
    """

    report_type: Optional[str] = None  # Required field, must be set (status, report)
    target_channel_id: Optional[str] = None  # Required field, must be set


@dataclass
class ListCommandParams(CommandParams):
    """
    Parameters for list commands.

    List commands show all eligible channels or user's channels.
    """

    list_type: Optional[Literal["all", "my"]] = None  # Required field, must be set


@dataclass
class MetricsCommandParams(CommandParams):
    """
    Parameters for metrics commands.

    The metrics command generates comprehensive HTML dashboard covering:
    - Executive CSO Management metrics
    - Technical System Health monitoring

    Format:
    - /ketchup metrics (last 7 days)
    - /ketchup metrics september 25 (monthly)
    - /ketchup metrics q1 25 (quarterly)
    """

    # Time period specification
    time_period_type: str = "7_days"  # "7_days", "monthly", "quarterly"
    month: Optional[int] = None  # 1-12
    quarter: Optional[int] = None  # 1-4
    year: Optional[int] = None  # 2024, 2025, etc.
    start_date: Optional[datetime] = None  # Calculated start
    end_date: Optional[datetime] = None  # Calculated end
    is_partial: bool = False  # True if ongoing period
