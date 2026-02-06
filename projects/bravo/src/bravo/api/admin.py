"""Admin API endpoints.

This module provides administrative endpoints for system stats,
configuration, poll triggering, and log access.
"""

from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException

from bravo.config import get_settings
from bravo.models import (
    ConfigResponse,
    ConfigUpdateRequest,
    GateConfig,
    LLMConfig,
    LogLevel,
    LogsResponse,
    PollStatus,
    PollTriggerResponse,
    StatsResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get system statistics.

    Returns:
        StatsResponse with ticket, nudge, and polling statistics.
    """
    # TODO: Implement actual stats from database
    return StatsResponse()


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Get current configuration.

    Returns:
        ConfigResponse with current poll interval, projects, gates, and LLM settings.
    """
    settings = get_settings()
    return ConfigResponse(
        poll_interval_minutes=settings.poll_interval_minutes,
        projects=settings.jira.projects,
        org_groups=settings.jira.org_groups,
        gates=GateConfig(
            g1_enabled=settings.gates.g1_enabled,
            g2_stale_hours=settings.gates.g2_stale_hours,
            g3_response_hours=settings.gates.g3_response_hours,
            g4_resolution_hours=settings.gates.g4_resolution_hours,
        ),
        llm=LLMConfig(
            threshold=settings.llm.threshold,
            model=settings.llm.model,
        ),
    )


@router.patch("/config", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
    """Update configuration (runtime only, not persisted).

    Args:
        request: Configuration update request with fields to change.

    Returns:
        ConfigResponse with updated configuration.

    Raises:
        HTTPException: 501 if not yet implemented.
    """
    # TODO: Implement runtime config updates
    logger.info(
        "config_update_requested", updates=request.model_dump(exclude_none=True)
    )
    raise HTTPException(
        status_code=501,
        detail="Runtime config updates not yet implemented",
    )


@router.post("/poll/trigger", response_model=PollTriggerResponse, status_code=202)
async def trigger_poll() -> PollTriggerResponse:
    """Manually trigger a poll cycle.

    Returns:
        PollTriggerResponse with poll ID and queued status.
    """
    poll_id = uuid4()
    logger.info("manual_poll_triggered", poll_id=str(poll_id))
    # TODO: Queue the poll job
    return PollTriggerResponse(
        poll_id=poll_id,
        status=PollStatus.QUEUED,
        message="Poll cycle queued for execution",
    )


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    level: LogLevel | None = None,
    limit: int = 100,
) -> LogsResponse:
    """Get recent logs.

    Args:
        level: Filter logs by level (DEBUG, INFO, WARNING, ERROR).
        limit: Maximum number of log entries to return.

    Returns:
        LogsResponse with list of log entries.
    """
    # TODO: Implement log retrieval
    _ = level, limit
    return LogsResponse(logs=[])
