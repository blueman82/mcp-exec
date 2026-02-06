"""Assignees API endpoints.

This module provides endpoints for listing and managing watched assignees.
"""

import structlog
from fastapi import APIRouter, HTTPException

from bravo.db import queries
from bravo.models import (
    AssigneeListResponse,
    AssigneeResponse,
    AssigneeUpdateRequest,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def _row_to_assignee(row: dict) -> AssigneeResponse:
    """Convert database row to AssigneeResponse.

    Args:
        row: Database record dict.

    Returns:
        AssigneeResponse model instance.
    """
    return AssigneeResponse(
        jira_id=row["jira_id"],
        jira_display_name=row["jira_display_name"],
        slack_user_id=row["slack_user_id"],
        email=row["email"],
        quiet_hours_start=str(row["quiet_hours_start"]) if row["quiet_hours_start"] else None,
        quiet_hours_end=str(row["quiet_hours_end"]) if row["quiet_hours_end"] else None,
        default_snooze_minutes=row["default_snooze_minutes"],
        timezone=row["timezone"],
        nudge_count=row["nudge_count"],
        last_nudge_at=row["last_nudge_at"],
    )


@router.get("", response_model=AssigneeListResponse)
async def list_assignees() -> AssigneeListResponse:
    """List watched assignees.

    Returns:
        AssigneeListResponse with all assignees and total count.
    """
    rows, total = await queries.list_assignees()
    assignees = [_row_to_assignee(row) for row in rows]
    return AssigneeListResponse(assignees=assignees, total=total)


@router.get("/{jira_id}", response_model=AssigneeResponse)
async def get_assignee(jira_id: str) -> AssigneeResponse:
    """Get assignee details.

    Args:
        jira_id: The Jira account ID.

    Returns:
        AssigneeResponse with full assignee details.

    Raises:
        HTTPException: 404 if assignee not found.
    """
    row = await queries.get_assignee(jira_id)
    if not row:
        raise HTTPException(status_code=404, detail="Assignee not found")
    return _row_to_assignee(row)


@router.patch("/{jira_id}", response_model=AssigneeResponse)
async def update_assignee(
    jira_id: str,
    request: AssigneeUpdateRequest,
) -> AssigneeResponse:
    """Update assignee preferences.

    Args:
        jira_id: The Jira account ID.
        request: AssigneeUpdateRequest with fields to update.

    Returns:
        AssigneeResponse with updated assignee details.

    Raises:
        HTTPException: 404 if assignee not found, 500 if update fails.
    """
    existing = await queries.get_assignee(jira_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Assignee not found")

    row = await queries.update_assignee_preferences(
        jira_id=jira_id,
        quiet_hours_start=request.quiet_hours_start,
        quiet_hours_end=request.quiet_hours_end,
        default_snooze_minutes=request.default_snooze_minutes,
        timezone=request.timezone,
    )

    if not row:
        raise HTTPException(status_code=500, detail="Failed to update assignee")

    return _row_to_assignee(row)
