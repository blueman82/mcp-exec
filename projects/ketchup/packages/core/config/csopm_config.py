"""
CSOPM Notifier Configuration.

Environment-driven configuration for CSOPM notification thresholds,
JIRA project settings, and scheduling parameters.

This module centralizes all CSOPM-specific configuration, allowing
easy override via docker-compose environment variables for testing
or production tuning without code changes.

Environment Variables:
    CSOPM_JIRA_PROJECT: JIRA project key for CSOPM tickets (default: "CSOPM")
    CSOPM_RCA_REMINDER_DAYS: Days before RCA reminder is sent (default: 7)
    CSOPM_CLOSURE_REMINDER_DAYS: Days before closure reminder is sent (default: 45)
    CSOPM_MAX_PING_COUNT: Maximum reminder pings before escalation (default: 3)
    CSOPM_SCHEDULE_TIMES: Comma-separated schedule times in UTC (default: "08:00,16:00")

Example docker-compose.yml:
    environment:
      - CSOPM_JIRA_PROJECT=CSOPM
      - CSOPM_RCA_REMINDER_DAYS=7
      - CSOPM_CLOSURE_REMINDER_DAYS=45
      - CSOPM_MAX_PING_COUNT=3
      - CSOPM_SCHEDULE_TIMES=08:00,16:00
"""

import os
from typing import List

# JIRA Project Configuration
# The JIRA project key used in JQL queries for CSOPM ticket discovery
CSOPM_JIRA_PROJECT: str = os.environ.get("CSOPM_JIRA_PROJECT", "CSOPM")

# Reminder Thresholds (in days)
# RCA reminder sent after this many days since ticket creation
CSOPM_RCA_REMINDER_DAYS: int = int(os.environ.get("CSOPM_RCA_REMINDER_DAYS", "7"))

# Closure reminder sent after this many days since ticket creation
CSOPM_CLOSURE_REMINDER_DAYS: int = int(os.environ.get("CSOPM_CLOSURE_REMINDER_DAYS", "45"))

# Maximum reminder pings before escalation
# After this many pings, the system may escalate or stop reminding
CSOPM_MAX_PING_COUNT: int = int(os.environ.get("CSOPM_MAX_PING_COUNT", "3"))

# Schedule Configuration
# Comma-separated times in 24-hour UTC format when the poll cycle runs
_schedule_times_str: str = os.environ.get("CSOPM_SCHEDULE_TIMES", "08:00,16:00")
CSOPM_SCHEDULE_TIMES: List[str] = [t.strip() for t in _schedule_times_str.split(",")]
