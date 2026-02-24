"""Handover Summary Configuration."""

import os
from typing import List

HANDOVER_SCHEDULE_TIMES: List[str] = [
    t.strip() for t in os.environ.get("KETCHUP_HANDOVER_SCHEDULE_TIMES", "09:00,17:00").split(",")
]
HANDOVER_TARGET_CHANNEL: str = os.environ.get("KETCHUP_HANDOVER_TARGET_CHANNEL", "C03PWLW9P5H")
HANDOVER_MESSAGE_WINDOW_HOURS: int = int(os.environ.get("KETCHUP_HANDOVER_MESSAGE_WINDOW_HOURS", "12"))
