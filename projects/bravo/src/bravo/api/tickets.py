"""Tickets API endpoints.

This module provides CRUD endpoints for watched tickets.
"""

import structlog
from fastapi import APIRouter, HTTPException, Response

from bravo.db import queries
from bravo.models import (
    EvaluationResponse,
    GateResults,
    LLMScores,
    TicketListResponse,
    TicketResponse,
    TicketStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def _row_to_ticket(row: dict) -> TicketResponse:
    """Convert database row to TicketResponse.

    Args:
        row: Database record dict.

    Returns:
        TicketResponse model instance.
    """
    return TicketResponse(
        ticket_key=row["ticket_key"],
        jira_id=row["jira_id"],
        project=row["project"],
        summary=row["summary"],
        assignee_jira_id=row["assignee_jira_id"],
        assignee_name=row["assignee_name"],
        status=TicketStatus(row["status"]),
        jira_status=row["jira_status"],
        first_seen_at=row["first_seen_at"],
        last_polled_at=row["last_polled_at"],
        last_assignee_comment_at=row["last_assignee_comment_at"],
        snoozed_until=row["snoozed_until"],
        gate_results=GateResults(
            g1_passed=row["g1_passed"],
            g2_passed=row["g2_passed"],
            g3_passed=row["g3_passed"],
            g4_passed=row["g4_passed"],
        ),
        llm_scores=LLMScores(
            clarity=row["llm_clarity"],
            completeness=row["llm_completeness"],
            root_cause=row["llm_root_cause"],
            actionability=row["llm_actionability"],
            average=row["llm_average"],
        ) if row["llm_average"] else None,
    )


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    status: TicketStatus | None = None,
    assignee: str | None = None,
    project: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TicketListResponse:
    """List watched tickets.

    Args:
        status: Filter by ticket status.
        assignee: Filter by assignee Jira ID.
        project: Filter by project key.
        limit: Maximum results to return.
        offset: Number of results to skip.

    Returns:
        TicketListResponse with tickets and pagination info.
    """
    rows, total = await queries.list_tickets(
        status=status.value if status else None,
        assignee=assignee,
        project=project,
        limit=limit,
        offset=offset,
    )
    tickets = [_row_to_ticket(row) for row in rows]
    return TicketListResponse(
        tickets=tickets,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{ticket_key}", response_model=TicketResponse)
async def get_ticket(ticket_key: str) -> TicketResponse:
    """Get ticket details.

    Args:
        ticket_key: The Jira ticket key.

    Returns:
        TicketResponse with full ticket details.

    Raises:
        HTTPException: 404 if ticket not found.
    """
    row = await queries.get_ticket(ticket_key)
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _row_to_ticket(row)


@router.delete("/{ticket_key}", status_code=204)
async def delete_ticket(ticket_key: str) -> Response:
    """Stop watching a ticket.

    Args:
        ticket_key: The Jira ticket key.

    Returns:
        Empty 204 response on success.

    Raises:
        HTTPException: 404 if ticket not found.
    """
    deleted = await queries.delete_ticket(ticket_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return Response(status_code=204)


@router.post("/{ticket_key}/evaluate", response_model=EvaluationResponse)
async def evaluate_ticket(ticket_key: str) -> EvaluationResponse:
    """Manually evaluate ticket for nudge.

    Args:
        ticket_key: The Jira ticket key.

    Returns:
        EvaluationResponse with gate and LLM results.

    Raises:
        HTTPException: 404 if ticket not found.
    """
    row = await queries.get_ticket(ticket_key)
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # TODO: Implement actual gate and LLM evaluation
    logger.info("manual_evaluation_requested", ticket_key=ticket_key)

    return EvaluationResponse(
        ticket_key=ticket_key,
        gate_results=GateResults(
            g1_passed=row["g1_passed"],
            g2_passed=row["g2_passed"],
            g3_passed=row["g3_passed"],
            g4_passed=row["g4_passed"],
        ),
        llm_scores=LLMScores(
            clarity=row["llm_clarity"],
            completeness=row["llm_completeness"],
            root_cause=row["llm_root_cause"],
            actionability=row["llm_actionability"],
            average=row["llm_average"],
        ) if row["llm_average"] else None,
        nudge_triggered=False,
        nudge_reason=None,
    )
