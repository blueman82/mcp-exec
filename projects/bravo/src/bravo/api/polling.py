"""Polling API endpoints.

This module provides endpoints for viewing polling state and history.
"""

import structlog
from fastapi import APIRouter

from bravo.db import queries
from bravo.models import (
    PollHistoryEntry,
    PollHistoryResponse,
    PollStateResponse,
    PollStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/state", response_model=PollStateResponse)
async def get_poll_state() -> PollStateResponse:
    """Get current poll state.

    Returns:
        PollStateResponse with cursor position and next poll time.
    """
    state = await queries.get_poll_state()
    if not state:
        return PollStateResponse()
    return PollStateResponse(
        last_cursor=state["last_cursor"],
        last_poll_at=state["last_poll_at"],
        tickets_fetched=state["tickets_fetched"],
        next_poll_at=state["next_poll_at"],
    )


@router.get("/history", response_model=PollHistoryResponse)
async def get_poll_history(limit: int = 10) -> PollHistoryResponse:
    """Get poll history.

    Args:
        limit: Maximum number of poll entries to return.

    Returns:
        PollHistoryResponse with list of recent polls.
    """
    rows = await queries.get_poll_history(limit=limit)
    polls = [
        PollHistoryEntry(
            poll_id=row["id"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            tickets_fetched=row["tickets_fetched"],
            tickets_new=row["tickets_new"],
            tickets_updated=row["tickets_updated"],
            nudges_triggered=row["nudges_triggered"],
            status=PollStatus(row["status"]),
        )
        for row in rows
    ]
    return PollHistoryResponse(polls=polls)
