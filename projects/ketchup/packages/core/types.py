"""
Core type definitions and re-exports.

This module provides centralized type definitions and re-exports
commonly used types from other packages for backward compatibility.
"""

from typing import Any, Dict, List

# Re-export from db package
from packages.db.models.channel_metadata import ChannelMetadata

# Additional type definitions
MessageBlocks = List[Dict[str, Any]]
JiraReportStatus = str  # One of: PENDING, PROCESSING, PROCESSED, FAILED, SKIPPED

# Re-export all types
__all__ = [
    "ChannelMetadata",
    "MessageBlocks",
    "JiraReportStatus",
]
