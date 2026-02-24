"""
Handover Summary Configuration.

Environment-driven configuration for handover summary scheduling,
target channel, and message window parameters.

This module centralizes all handover-specific configuration, allowing
easy override via docker-compose environment variables for testing
or production tuning without code changes.

Environment Variables:
    KETCHUP_HANDOVER_SCHEDULE_TIMES: Comma-separated schedule times in UTC (default: "09:00,17:00")
    KETCHUP_HANDOVER_TARGET_CHANNEL: Slack channel ID for handover summaries (default: "C03PWLW9P5H")
    KETCHUP_HANDOVER_MESSAGE_WINDOW_HOURS: Hours to look back for messages (default: 12)

Example docker-compose.yml:
    environment:
      - KETCHUP_HANDOVER_SCHEDULE_TIMES=09:00,17:00
      - KETCHUP_HANDOVER_TARGET_CHANNEL=C03PWLW9P5H
      - KETCHUP_HANDOVER_MESSAGE_WINDOW_HOURS=12
"""

import os
from typing import List

# Schedule Configuration
# Comma-separated times in 24-hour UTC format when the handover summary runs
_schedule_times_str: str = os.environ.get("KETCHUP_HANDOVER_SCHEDULE_TIMES", "09:00,17:00")
HANDOVER_SCHEDULE_TIMES: List[str] = [t.strip() for t in _schedule_times_str.split(",")]

# Target Channel Configuration
# The Slack channel ID where handover summaries will be posted
HANDOVER_TARGET_CHANNEL: str = os.environ.get("KETCHUP_HANDOVER_TARGET_CHANNEL", "C03PWLW9P5H")

# Message Window Configuration
# Number of hours to look back when collecting messages for summary
HANDOVER_MESSAGE_WINDOW_HOURS: int = int(
    os.environ.get("KETCHUP_HANDOVER_MESSAGE_WINDOW_HOURS", "12")
)
