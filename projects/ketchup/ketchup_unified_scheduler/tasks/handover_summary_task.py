"""Handover Summary Task for the unified scheduler."""

from typing import Optional

from ketchup_unified_scheduler.services.handover import generate_and_post_handover
from ketchup_unified_scheduler.task_config import TaskConfig
from packages.core.config.handover_config import HANDOVER_SCHEDULE_TIMES
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry

logger = setup_logger(__name__)


async def handover_summary_task(container: Optional[TypedServiceRegistry] = None) -> None:
    logger.info("Starting handover summary task")
    try:
        result = await generate_and_post_handover(container=container)
        logger.info("Handover summary task completed with result: %s", result)
        if result.get("status") == "error":
            raise RuntimeError(
                f"Handover summary generation failed: {result.get('error', 'Unknown error')}"
            )
    except Exception as e:
        logger.error("Handover summary task failed: %s", str(e), exc_info=True)
        raise


def get_handover_task_configs() -> list[TaskConfig]:
    configs = [
        TaskConfig(
            name=f"handover_{i}",
            handler=handover_summary_task,
            schedule_time=time_str,
            feature_flag="KETCHUP_HANDOVER_SUMMARY_ENABLED",
            enabled=True,
        )
        for i, time_str in enumerate(HANDOVER_SCHEDULE_TIMES)
    ]
    logger.info(
        f"Created {len(configs)} handover task configs for times: {HANDOVER_SCHEDULE_TIMES}"
    )
    return configs
