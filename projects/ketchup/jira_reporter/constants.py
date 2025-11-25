"""
constants.py

Constants for JIRA reporter service.
"""


# JIRA report status values
class JiraReportStatus:
    """Status values for JIRA report processing."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    # New retry-aware states
    RETRY_PENDING = "RETRY_PENDING"
    MAX_RETRIES_EXCEEDED = "MAX_RETRIES_EXCEEDED"
    CSOPM_PARTIAL = "CSOPM_PARTIAL"  # Posted to JIRA but CSOPM failed


# Retry configuration
MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY = 60  # 1 minute base delay
MAX_RETRY_DELAY = 3600  # 1 hour max delay

# Retryable error patterns
RETRYABLE_ERROR_PATTERNS = [
    "timeout",
    "connection",
    "server disconnected",
    "ratelimited",
    "temporarily unavailable",
    "service unavailable",
    "500",  # HTTP 500 server errors
    "502",  # HTTP 502 bad gateway
    "503",  # HTTP 503 service unavailable
    "504",  # HTTP 504 gateway timeout
    "mcp tool call failed",  # MCP tool failures
]
