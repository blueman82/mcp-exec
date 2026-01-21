"""
Services module for ketchup_unified_scheduler.

This module contains business logic services that have been consolidated
from legacy scheduler services into the unified scheduler.
"""

from ketchup_unified_scheduler.services.maintenance import (
    fetch_and_store_maintenance_data,
)
from ketchup_unified_scheduler.services.maintenance import main as maintenance_main
from ketchup_unified_scheduler.services.status import (
    AutoStatusGenerator,
    AutoStatusProcessor,
    run_auto_status,
)

__all__ = [
    "AutoStatusGenerator",
    "AutoStatusProcessor",
    "run_auto_status",
    "fetch_and_store_maintenance_data",
    "maintenance_main",
]
