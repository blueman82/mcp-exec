"""
Maintenance Fetch Task for the unified scheduler.

Migrates the ketchup_maintenance_fetcher service to run within the unified scheduler.
Uses time-based scheduling at 01:30 UTC daily to fetch maintenance data from SOAP API
and store in DynamoDB.
"""

from typing import Optional

from ketchup_unified_scheduler.services.maintenance import fetch_and_store_maintenance_data
from ketchup_unified_scheduler.task_config import TaskConfig
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry

logger = setup_logger(__name__)


async def maintenance_fetch_task(container: Optional[TypedServiceRegistry] = None) -> None:
    """
    Execute the maintenance fetch task.

    Fetches maintenance data from the Raven SOAP API and stores it in DynamoDB.
    The fetch_and_store_maintenance_data function handles feature flag checks
    and container management internally.

    Args:
        container: TypedServiceRegistry for dependency injection.
                  If None, fetch_and_store_maintenance_data will create its own container.
    """
    logger.info("Starting maintenance fetch task")

    try:
        result = await fetch_and_store_maintenance_data(container=container)
        logger.info("Maintenance fetch task completed with result: %s", result)

        if result.get("status") == "error":
            raise RuntimeError(
                f"Maintenance fetch failed: {result.get('message', 'Unknown error')}"
            )

    except Exception as e:
        logger.error("Maintenance fetch task failed: %s", str(e), exc_info=True)
        raise


def get_maintenance_fetch_task_config() -> TaskConfig:
    """
    Get the TaskConfig for the maintenance fetch task.

    Returns:
        TaskConfig configured for daily execution at 01:30 UTC.
    """
    return TaskConfig(
        name="maintenance_fetcher",
        handler=maintenance_fetch_task,
        schedule_time="01:30",
        feature_flag="KETCHUP_MAINTENANCE_FETCHER_ENABLED",
        enabled=True,
    )
