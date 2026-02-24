"""
Handover Summary Task for the unified scheduler.

Generates and posts AI-powered handover summaries to Slack at scheduled times.
Uses time-based scheduling from HANDOVER_SCHEDULE_TIMES environment variable
(default: 09:00 and 17:00 UTC).
"""

from typing import Optional

from ketchup_unified_scheduler.services.handover import generate_and_post_handover
from ketchup_unified_scheduler.task_config import TaskConfig
from packages.core.config.handover_config import HANDOVER_SCHEDULE_TIMES
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry

logger = setup_logger(__name__)


async def handover_summary_task(container: Optional[TypedServiceRegistry] = None) -> None:
    """
    Execute the handover summary task.

    Generates an AI-powered summary of recent Slack messages and posts it
    to the configured handover channel. The generate_and_post_handover function
    handles feature flag checks and container management internally.

    Args:
        container: TypedServiceRegistry for dependency injection.
                  If None, generate_and_post_handover will create its own container.
    """
    logger.info("Starting handover summary task")

    try:
        result = await generate_and_post_handover(container=container)
        logger.info("Handover summary task completed with result: %s", result)

        if result.get("status") == "error":
            raise RuntimeError(
                f"Handover summary generation failed: {result.get('message', 'Unknown error')}"
            )

    except Exception as e:
        logger.error("Handover summary task failed: %s", str(e), exc_info=True)
        raise


def get_handover_task_configs() -> list[TaskConfig]:
    """
    Generate TaskConfig instances for all handover schedule times.

    Reads HANDOVER_SCHEDULE_TIMES from environment configuration and creates
    one TaskConfig per schedule time. This allows dynamic configuration via
    docker-compose environment variables.

    Returns:
        List of TaskConfig instances, one per schedule time.

    Example:
        With HANDOVER_SCHEDULE_TIMES="09:00,17:00", returns:
        - handover_0: 09:00 UTC
        - handover_1: 17:00 UTC
    """
    configs = []

    for i, time_str in enumerate(HANDOVER_SCHEDULE_TIMES):
        configs.append(
            TaskConfig(
                name=f"handover_{i}",
                handler=handover_summary_task,
                schedule_time=time_str,
                feature_flag="KETCHUP_HANDOVER_SUMMARY_ENABLED",
                enabled=True,
            )
        )

    logger.info(
        f"Created {len(configs)} handover task configs for times: {HANDOVER_SCHEDULE_TIMES}"
    )

    return configs
