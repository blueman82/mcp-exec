#!/usr/bin/env python3
"""
Unified Scheduler Main Entry Point.

Single container running all scheduled tasks:
- maintenance_fetcher (daily at 01:30 UTC)
- pat_rotator (24-hour interval)
- metadata_updater (15-minute interval)
- status_updater (55-minute interval)
- jira_reporter (15-minute interval)
- handover_summary (configurable times, default: 09:00 and 17:00 UTC)

Container is created once at startup and shared across all tasks for
efficient resource utilization (shared HTTP connection pools).
"""

import asyncio
import sys

from ketchup_unified_scheduler.engine import UnifiedSchedulerEngine
from ketchup_unified_scheduler.task_registry import TaskRegistry
from ketchup_unified_scheduler.tasks.jira_report_task import get_jira_report_task_config
from ketchup_unified_scheduler.tasks.maintenance_fetch_task import (
    get_maintenance_fetch_task_config,
)
from ketchup_unified_scheduler.tasks.metadata_update_task import (
    get_metadata_update_task_config,
)
from ketchup_unified_scheduler.tasks.pat_rotation_task import get_pat_rotation_task_config
from ketchup_unified_scheduler.tasks.status_update_task import get_status_update_task_config
from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.container_roles import ContainerRole
from packages.core.typed_di_integration import get_unified_container

logger = setup_logger(__name__)


def create_task_registry() -> TaskRegistry:
    """
    Create and populate the task registry with all scheduled tasks.

    Returns:
        TaskRegistry with all 5 tasks registered.
    """
    registry = TaskRegistry()

    # Register all tasks
    registry.register(get_maintenance_fetch_task_config())
    registry.register(get_pat_rotation_task_config())
    registry.register(get_metadata_update_task_config())
    registry.register(get_status_update_task_config())
    registry.register(get_jira_report_task_config())

    logger.info(f"Registered {len(registry)} tasks: {[t.name for t in registry.list_tasks()]}")

    return registry


async def main() -> None:
    """
    Main entry point for the unified scheduler.

    Creates a single DI container at startup and passes it to the engine
    so all tasks share the same container (efficient connection pooling).
    """
    logger.info("Unified Scheduler starting...")

    try:
        # Create task registry with all scheduled tasks
        registry = create_task_registry()

        # Create DI container ONCE at startup - shared by all tasks
        logger.info("Initializing shared DI container...")
        container = await get_unified_container(ContainerRole.SCHEDULER)
        logger.info("DI container initialized successfully")

        # Create engine with shared container
        engine = UnifiedSchedulerEngine(
            registry=registry,
            container=container,
            health_file_path="/tmp/unified_scheduler_health",
        )

        # Start the engine (blocks until shutdown signal)
        await engine.start()

        logger.info("Unified Scheduler stopped gracefully")

    except Exception as e:
        logger.error(f"Unified Scheduler failed: {e}", exc_info=True)
        raise


def run() -> None:
    """Run the unified scheduler."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Unified Scheduler interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in Unified Scheduler: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
