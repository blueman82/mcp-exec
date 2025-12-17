"""
PAT Rotation Task for the unified scheduler.

Migrates the ketchup_jira_pat_rotator service to run within the unified scheduler.
Uses 24-hour (1440 minute) interval for JIRA PAT rotation checks.
"""

from typing import Optional

from ketchup_unified_scheduler.services.pat_rotator import PATRotator
from ketchup_unified_scheduler.task_config import TaskConfig
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry

logger = setup_logger(__name__)


async def pat_rotation_task(container: Optional[TypedServiceRegistry] = None) -> None:
    """
    Execute the PAT rotation task.

    Checks if JIRA PAT rotation is needed and performs the rotation if required.
    The PATRotator handles the full rotation flow:
    1. Check expiry (return early if not needed)
    2. Create new PAT via MCP
    3. Validate new PAT works
    4. Update secrets in AWS Secrets Manager
    5. Revoke old PAT
    6. Alert on Slack (success/failure)

    Args:
        container: TypedServiceRegistry for dependency injection.
                  Passed to PATRotator for resolving MCP client via DI.
    """
    logger.info("Starting PAT rotation task")

    try:
        rotator = PATRotator(container=container)
        result = await rotator.rotate()

        status = result.get("status", "unknown")
        if status == "success":
            logger.info("PAT rotation task completed successfully: %s", result)
        elif status == "skipped":
            logger.info("PAT rotation not needed: %s", result)
        elif status == "partial_success":
            logger.warning("PAT rotation partially succeeded: %s", result)
        else:
            logger.error("PAT rotation task failed: %s", result)

    except Exception as e:
        logger.error("PAT rotation task failed: %s", str(e), exc_info=True)
        raise


def get_pat_rotation_task_config() -> TaskConfig:
    """
    Get the TaskConfig for the PAT rotation task.

    Returns:
        TaskConfig configured for 24-hour (1440 minute) interval execution.
    """
    return TaskConfig(
        name="pat_rotator",
        handler=pat_rotation_task,
        interval_minutes=1440,  # 24 hours
        feature_flag="KETCHUP_JIRA_PAT_ROTATOR_FEATURE",
        enabled=True,
    )
