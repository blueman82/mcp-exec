"""Admin API endpoints.

This module provides administrative endpoints for system stats,
configuration, poll triggering, and log access.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends

from bravo.api.deps import get_poller_service
from bravo.config import LOG_FILE, get_settings
from bravo.models import (
    ConfigResponse,
    ConfigUpdateRequest,
    GateConfig,
    LLMConfig,
    LogEntry,
    LogLevel,
    LogsResponse,
    PollStatus,
    PollTriggerResponse,
    StatsResponse,
)
from bravo.protocols import PollerServiceProto

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
    """
    settings = get_settings()
    updates = request.model_dump(exclude_none=True)
    logger.info("config_update_requested", updates=updates)

    if "poll_interval_minutes" in updates:
        settings.poll_interval_minutes = updates["poll_interval_minutes"]

    if "gates" in updates:
        for key, value in updates["gates"].items():
            setattr(settings.gates, key, value)

    if "llm" in updates:
        for key, value in updates["llm"].items():
            setattr(settings.llm, key, value)

    return await get_config()


@router.post("/poll/trigger", response_model=PollTriggerResponse, status_code=202)
async def trigger_poll(
    background_tasks: BackgroundTasks,
    poller: PollerServiceProto = Depends(get_poller_service),
) -> PollTriggerResponse:
    """Manually trigger a poll cycle.

    Args:
        background_tasks: FastAPI background task queue.
        poller: Injected poller service.

    Returns:
        PollTriggerResponse with poll ID and queued status.
    """
    poll_id = uuid4()
    logger.info("manual_poll_triggered", poll_id=str(poll_id))
    background_tasks.add_task(poller.run_poll)
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
    if not LOG_FILE.exists():
        return LogsResponse(logs=[])

    entries: list[LogEntry] = []
    lines = LOG_FILE.read_text().strip().splitlines()

    for line in reversed(lines):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        entry_level = data.get("level", "info").upper()
        if level and entry_level != level.value:
            continue

        entries.append(
            LogEntry(
                timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
                level=entry_level,
                message=data.get("event", ""),
                context={
                    k: v
                    for k, v in data.items()
                    if k not in ("timestamp", "level", "event")
                },
            )
        )

        if len(entries) >= limit:
            break

    return LogsResponse(logs=entries)
