"""
Status Update Task for the unified scheduler.

Migrates the ketchup_status_updater service to run within the unified scheduler.
Uses 55-minute interval with distributed locking and AI-powered status generation.
"""

from typing import Optional

from ketchup_status_updater.main import run_auto_status
from ketchup_unified_scheduler.task_config import TaskConfig
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry

logger = setup_logger(__name__)


async def status_update_task(container: Optional[TypedServiceRegistry] = None) -> None:
    """
    Execute the status update task.

    Generates AI-powered status updates for eligible channels.
    The run_auto_status function handles distributed locking internally
    to prevent duplicate runs across servers.

    Args:
        container: TypedServiceRegistry for dependency injection.
                  If None, run_auto_status will create its own container.
    """
    logger.info("Starting status update task")

    try:
        await run_auto_status(container=container)
        logger.info("Status update task completed successfully")

    except Exception as e:
        logger.error("Status update task failed: %s", str(e), exc_info=True)
        raise


def get_status_update_task_config() -> TaskConfig:
    """
    Get the TaskConfig for the status update task.

    Returns:
        TaskConfig configured for 55-minute interval execution.
    """
    return TaskConfig(
        name="status_updater",
        handler=status_update_task,
        interval_minutes=55,
        feature_flag="KETCHUP_STATUS_UPDATER_FEATURE",
        enabled=True,
    )
