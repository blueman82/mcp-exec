"""
Ketchup Unified Scheduler - Multi-task scheduling system.

This module provides a unified scheduler that can run multiple scheduled tasks
within a single container, reducing infrastructure complexity and costs.

Key components:
- TaskConfig: Configuration dataclass for scheduled tasks
- TaskRegistry: Registry for managing task configurations
"""

from ketchup_unified_scheduler.task_config import TaskConfig
from ketchup_unified_scheduler.task_registry import TaskRegistry

__all__ = ["TaskConfig", "TaskRegistry"]
