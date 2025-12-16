"""
JIRA Report Task for the unified scheduler.

Migrates the jira_reporter service to run within the unified scheduler.
Uses 15-minute interval with dual-mode support: both polling channels
AND processing SQS events for archived channels.
"""

from typing import Optional

from ketchup_unified_scheduler.services.jira_reporter import run_reporting_cycle
from ketchup_unified_scheduler.task_config import TaskConfig
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry

logger = setup_logger(__name__)


async def jira_report_task(container: Optional[TypedServiceRegistry] = None) -> None:
    """
    Execute the JIRA report task.

    Runs a single JIRA reporting cycle that handles:
    1. Processing SQS messages for archived channels (priority)
    2. Polling DynamoDB for channels needing reports
    3. Generating AI summaries and posting to JIRA tickets
    4. CSOPM ticket discovery and posting

    Args:
        container: TypedServiceRegistry for dependency injection.
                  If None, creates its own container.
    """
    logger.info("Starting JIRA report task")

    try:
        await run_reporting_cycle(container=container)
        logger.info("JIRA report task completed successfully")

    except Exception as e:
        logger.error("JIRA report task failed: %s", str(e), exc_info=True)
        raise


def get_jira_report_task_config() -> TaskConfig:
    """
    Get the TaskConfig for the JIRA report task.

    Returns:
        TaskConfig configured for 15-minute interval execution.
    """
    return TaskConfig(
        name="jira_reporter",
        handler=jira_report_task,
        interval_minutes=15,
        feature_flag="KETCHUP_JIRA_REPORTER_FEATURE",
        enabled=True,
    )
