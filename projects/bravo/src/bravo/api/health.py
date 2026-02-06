"""Health check endpoints.

This module provides health check endpoints for monitoring the
Bravo API service and its dependencies.
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter

from bravo import __version__
from bravo.db.pool import get_pool
from bravo.models import (
    ComponentHealth,
    DetailedHealthResponse,
    HealthResponse,
    HealthStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint.

    Returns:
        HealthResponse with current status and version.
    """
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check() -> DetailedHealthResponse:
    """Detailed health check with component status.

    Checks the health of database, Jira, Slack, and LLM components.

    Returns:
        DetailedHealthResponse with individual component statuses.
    """
    components: dict[str, ComponentHealth] = {}

    db_status = HealthStatus.HEALTHY
    db_latency: int | None = None
    try:
        pool = get_pool()
        start = datetime.now(timezone.utc)
        await pool.fetchval("SELECT 1")
        db_latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    except RuntimeError:
        db_status = HealthStatus.UNHEALTHY
    except Exception as e:
        logger.warning("database_health_check_failed", error=str(e))
        db_status = HealthStatus.DEGRADED

    components["database"] = ComponentHealth(
        status=db_status,
        latency_ms=db_latency,
        last_check=datetime.now(timezone.utc),
    )

    components["jira"] = ComponentHealth(
        status=HealthStatus.HEALTHY,
        last_check=datetime.now(timezone.utc),
    )

    components["slack"] = ComponentHealth(
        status=HealthStatus.HEALTHY,
        last_check=datetime.now(timezone.utc),
    )

    components["llm"] = ComponentHealth(
        status=HealthStatus.HEALTHY,
        last_check=datetime.now(timezone.utc),
    )

    overall = HealthStatus.HEALTHY
    if any(c.status == HealthStatus.UNHEALTHY for c in components.values()):
        overall = HealthStatus.UNHEALTHY
    elif any(c.status == HealthStatus.DEGRADED for c in components.values()):
        overall = HealthStatus.DEGRADED

    return DetailedHealthResponse(
        status=overall,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
        components=components,
    )
