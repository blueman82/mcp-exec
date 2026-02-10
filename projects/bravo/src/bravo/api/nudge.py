"""Nudge API endpoints.

This module provides endpoints for listing and viewing nudges.
"""

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException

from bravo.db import queries
from bravo.models import (
    NudgeListResponse,
    NudgeResponse,
    NudgeStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def _row_to_nudge(row: dict[str, Any]) -> NudgeResponse:
    """Convert database row to NudgeResponse.

    Args:
        row: Database record dict.

    Returns:
        NudgeResponse model instance.
    """
    return NudgeResponse(
        nudge_id=row["id"],
        ticket_key=row["ticket_key"],
        assignee_jira_id=row["assignee_jira_id"],
        status=NudgeStatus(row["status"]),
        trigger_reason=row["trigger_reason"],
        slack_channel=row["slack_channel"],
        slack_ts=row["slack_ts"],
        message_content=row["message_content"],
        created_at=row["created_at"],
        responded_at=row["responded_at"],
        jira_comment_posted=row["jira_comment_posted"],
    )


@router.get("", response_model=NudgeListResponse)
async def list_nudges(
    ticket_key: str | None = None,
    assignee: str | None = None,
    status: NudgeStatus | None = None,
    limit: int = 50,
) -> NudgeListResponse:
    """List nudge events.

    Args:
        ticket_key: Filter by ticket key.
        assignee: Filter by assignee Jira ID.
        status: Filter by nudge status.
        limit: Maximum results to return.

    Returns:
        NudgeListResponse with nudges and total count.
    """
    rows, total = await queries.list_nudges(
        ticket_key=ticket_key,
        assignee=assignee,
        status=status.value if status else None,
        limit=limit,
    )
    nudges = [_row_to_nudge(row) for row in rows]
    return NudgeListResponse(nudges=nudges, total=total)


@router.get("/{nudge_id}", response_model=NudgeResponse)
async def get_nudge(nudge_id: UUID) -> NudgeResponse:
    """Get nudge event details.

    Args:
        nudge_id: The nudge event UUID.

    Returns:
        NudgeResponse with full nudge details.

    Raises:
        HTTPException: 404 if nudge not found.
    """
    row = await queries.get_nudge(nudge_id)
    if not row:
        raise HTTPException(status_code=404, detail="Nudge not found")
    return _row_to_nudge(row)


