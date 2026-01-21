"""
Status service module for auto-status generation and processing.

This module contains the business logic for generating and posting
automated status updates to Slack channels.
"""

from ketchup_unified_scheduler.services.status.generator import AutoStatusGenerator
from ketchup_unified_scheduler.services.status.processor import (
    AutoStatusProcessor,
    run_auto_status,
)

__all__ = [
    "AutoStatusGenerator",
    "AutoStatusProcessor",
    "run_auto_status",
]
