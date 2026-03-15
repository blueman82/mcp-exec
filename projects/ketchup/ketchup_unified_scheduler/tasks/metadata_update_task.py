"""
Metadata Update Task for the unified scheduler.

Migrates the channel_metadata_updater service to run within the unified scheduler.
Uses 15-minute interval for metadata extraction using AI.
"""

from typing import Optional

from ketchup_unified_scheduler.services.metadata import process_channels
from ketchup_unified_scheduler.task_config import TaskConfig
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry

logger = setup_logger(__name__)


async def metadata_update_task(container: Optional[TypedServiceRegistry] = None) -> None:
    """
    Execute the metadata update task.

    Scans channels for incomplete metadata and uses AI to extract
    and update missing channel information.

    Args:
        container: TypedServiceRegistry for dependency injection.
                  If None, process_channels will create its own container.
    """
    logger.info("Starting metadata update task")

    try:
        result = await process_channels(container=container)

        status_code = result.get("statusCode", 500)
        if status_code == 200:
            logger.info("Metadata update task completed successfully: %s", result)
        else:
            logger.warning("Metadata update task completed with issues: %s", result)

    except Exception as e:
        logger.error("Metadata update task failed: %s", str(e), exc_info=True)
        raise


def get_metadata_update_task_config() -> TaskConfig:
    """
    Get the TaskConfig for the metadata update task.

    Returns:
        TaskConfig configured for 15-minute interval execution.
    """
    return TaskConfig(
        name="metadata_updater",
        handler=metadata_update_task,
        interval_minutes=15,
        feature_flag="KETCHUP_METADATA_UPDATER_FEATURE",
        enabled=True,
    )
