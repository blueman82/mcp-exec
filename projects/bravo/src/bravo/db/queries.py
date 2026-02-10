"""Raw SQL queries for Bravo database operations.

This module provides async database query functions using asyncpg.
All queries use parameterized SQL to prevent injection.
"""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
import structlog

from bravo.db.pool import get_pool

logger = structlog.get_logger(__name__)


# ============ TICKETS ============


async def get_ticket(ticket_key: str) -> asyncpg.Record | None:
    """Get a watched ticket by key.

    Args:
        ticket_key: The Jira ticket key.

    Returns:
        The ticket record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        "SELECT * FROM watched_tickets WHERE ticket_key = $1",
        ticket_key,
    )


async def list_tickets(
    status: str | None = None,
    assignee: str | None = None,
    project: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    """List watched tickets with filters.

    Args:
        status: Filter by ticket status.
        assignee: Filter by assignee Jira ID.
        project: Filter by project key.
        limit: Maximum results to return.
        offset: Number of results to skip.

    Returns:
        Tuple of (list of ticket records, total count).
    """
    pool = get_pool()

    conditions = []
    params: list[Any] = []
    param_idx = 1

    if status:
        conditions.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1

    if assignee:
        conditions.append(f"assignee_jira_id = ${param_idx}")
        params.append(assignee)
        param_idx += 1

    if project:
        conditions.append(f"project = ${param_idx}")
        params.append(project)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    count_query = f"SELECT COUNT(*) FROM watched_tickets WHERE {where_clause}"
    total = await pool.fetchval(count_query, *params)

    params.extend([limit, offset])
    query = f"""
        SELECT * FROM watched_tickets
        WHERE {where_clause}
        ORDER BY last_polled_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """

    rows = await pool.fetch(query, *params)
    return rows, total or 0


async def upsert_ticket(
    ticket_key: str,
    jira_id: str,
    project: str,
    summary: str | None,
    assignee_jira_id: str | None,
    assignee_name: str | None,
    jira_status: str | None,
) -> asyncpg.Record:
    """Insert or update a watched ticket.

    Args:
        ticket_key: The Jira ticket key.
        jira_id: The internal Jira ticket ID.
        project: The project key.
        summary: The ticket summary.
        assignee_jira_id: The assignee's Jira account ID.
        assignee_name: The assignee's display name.
        jira_status: The current Jira status.

    Returns:
        The upserted ticket record.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        INSERT INTO watched_tickets (
            ticket_key, jira_id, project, summary,
            assignee_jira_id, assignee_name, jira_status, last_polled_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (ticket_key) DO UPDATE SET
            summary = EXCLUDED.summary,
            assignee_jira_id = EXCLUDED.assignee_jira_id,
            assignee_name = EXCLUDED.assignee_name,
            jira_status = EXCLUDED.jira_status,
            last_polled_at = NOW()
        RETURNING *
        """,
        ticket_key,
        jira_id,
        project,
        summary,
        assignee_jira_id,
        assignee_name,
        jira_status,
    )


async def update_ticket_status(ticket_key: str, status: str) -> asyncpg.Record | None:
    """Update ticket watch status.

    Args:
        ticket_key: The Jira ticket key.
        status: The new status (ACQUIRED, ACTIVE, SNOOZED, RESOLVED).

    Returns:
        The updated ticket record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        "UPDATE watched_tickets SET status = $2 WHERE ticket_key = $1 RETURNING *",
        ticket_key,
        status,
    )


async def update_ticket_gates(
    ticket_key: str,
    g1: bool | None,
    g2: bool | None,
    g3: bool | None,
    g4: bool | None,
) -> asyncpg.Record | None:
    """Update ticket gate results.

    Args:
        ticket_key: The Jira ticket key.
        g1: G1 gate result (comment exists).
        g2: G2 gate result (not stale).
        g3: G3 gate result (response time).
        g4: G4 gate result (resolution time).

    Returns:
        The updated ticket record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        UPDATE watched_tickets
        SET g1_passed = $2, g2_passed = $3, g3_passed = $4, g4_passed = $5
        WHERE ticket_key = $1
        RETURNING *
        """,
        ticket_key,
        g1,
        g2,
        g3,
        g4,
    )


async def update_ticket_llm_scores(
    ticket_key: str,
    clarity: float,
    completeness: float,
    root_cause: float,
    actionability: float,
) -> asyncpg.Record | None:
    """Update ticket LLM scores.

    Args:
        ticket_key: The Jira ticket key.
        clarity: Clarity score (1-5).
        completeness: Completeness score (1-5).
        root_cause: Root cause score (1-5).
        actionability: Actionability score (1-5).

    Returns:
        The updated ticket record or None if not found.
    """
    pool = get_pool()
    average = (clarity + completeness + root_cause + actionability) / 4
    return await pool.fetchrow(
        """
        UPDATE watched_tickets
        SET llm_clarity = $2, llm_completeness = $3, llm_root_cause = $4,
            llm_actionability = $5, llm_average = $6, llm_scored_at = NOW()
        WHERE ticket_key = $1
        RETURNING *
        """,
        ticket_key,
        clarity,
        completeness,
        root_cause,
        actionability,
        average,
    )


async def delete_ticket(ticket_key: str) -> bool:
    """Delete a watched ticket.

    Args:
        ticket_key: The Jira ticket key.

    Returns:
        True if the ticket was deleted, False if not found.
    """
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM watched_tickets WHERE ticket_key = $1",
        ticket_key,
    )
    return cast(str, result) == "DELETE 1"


# ============ NUDGE EVENTS ============


async def create_nudge(
    ticket_key: str,
    assignee_jira_id: str,
    trigger_reason: str,
    slack_channel: str,
    message_content: str,
) -> asyncpg.Record:
    """Create a new nudge event.

    Args:
        ticket_key: The Jira ticket key.
        assignee_jira_id: The assignee's Jira account ID.
        trigger_reason: Why the nudge was triggered.
        slack_channel: The Slack channel/user ID.
        message_content: The message content sent.

    Returns:
        The created nudge record.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        INSERT INTO nudge_events (
            ticket_key, assignee_jira_id, trigger_reason,
            slack_channel, message_content
        ) VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        ticket_key,
        assignee_jira_id,
        trigger_reason,
        slack_channel,
        message_content,
    )


async def get_nudge(nudge_id: UUID) -> asyncpg.Record | None:
    """Get a nudge event by ID.

    Args:
        nudge_id: The nudge event UUID.

    Returns:
        The nudge record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        "SELECT * FROM nudge_events WHERE id = $1",
        nudge_id,
    )


async def list_nudges(
    ticket_key: str | None = None,
    assignee: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> tuple[list[asyncpg.Record], int]:
    """List nudge events with filters.

    Args:
        ticket_key: Filter by ticket key.
        assignee: Filter by assignee Jira ID.
        status: Filter by nudge status.
        limit: Maximum results to return.

    Returns:
        Tuple of (list of nudge records, total count).
    """
    pool = get_pool()

    conditions = []
    params: list[Any] = []
    param_idx = 1

    if ticket_key:
        conditions.append(f"ticket_key = ${param_idx}")
        params.append(ticket_key)
        param_idx += 1

    if assignee:
        conditions.append(f"assignee_jira_id = ${param_idx}")
        params.append(assignee)
        param_idx += 1

    if status:
        conditions.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    count_query = f"SELECT COUNT(*) FROM nudge_events WHERE {where_clause}"
    total = await pool.fetchval(count_query, *params)

    params.append(limit)
    query = f"""
        SELECT * FROM nudge_events
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ${param_idx}
    """

    rows = await pool.fetch(query, *params)
    return rows, total or 0


async def update_nudge_status(
    nudge_id: UUID,
    status: str,
    slack_ts: str | None = None,
) -> asyncpg.Record | None:
    """Update nudge event status.

    Args:
        nudge_id: The nudge event UUID.
        status: The new status.
        slack_ts: Optional Slack message timestamp.

    Returns:
        The updated nudge record or None if not found.
    """
    pool = get_pool()
    if slack_ts:
        return await pool.fetchrow(
            "UPDATE nudge_events SET status = $2, slack_ts = $3 WHERE id = $1 RETURNING *",
            nudge_id,
            status,
            slack_ts,
        )
    return await pool.fetchrow(
        "UPDATE nudge_events SET status = $2 WHERE id = $1 RETURNING *",
        nudge_id,
        status,
    )


async def update_nudge_response(
    nudge_id: UUID,
    jira_comment: str,
) -> asyncpg.Record | None:
    """Update nudge with Jira comment response.

    Args:
        nudge_id: The nudge event UUID.
        jira_comment: The comment text posted to Jira.

    Returns:
        The updated nudge record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        UPDATE nudge_events
        SET status = 'POSTED', responded_at = NOW(),
            jira_comment_posted = $2, posted_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        nudge_id,
        jira_comment,
    )


async def get_nudge_by_slack_ts(slack_ts: str) -> asyncpg.Record | None:
    """Get an active nudge event by Slack message timestamp.

    Args:
        slack_ts: The Slack message timestamp identifier.

    Returns:
        The nudge record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        "SELECT * FROM nudge_events WHERE slack_ts = $1 AND status = 'SENT'",
        slack_ts,
    )


async def get_snoozed_nudge_by_slack_ts(slack_ts: str) -> asyncpg.Record | None:
    """Get a snoozed nudge event by Slack message timestamp.

    Args:
        slack_ts: The Slack message timestamp identifier.

    Returns:
        The nudge record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        "SELECT * FROM nudge_events WHERE slack_ts = $1 AND status = 'SNOOZED'",
        slack_ts,
    )


async def update_nudge_snooze(
    nudge_id: UUID,
    snoozed_until: datetime,
) -> asyncpg.Record | None:
    """Set a nudge to snoozed status with expiry time.

    Args:
        nudge_id: The nudge event UUID.
        snoozed_until: When the snooze expires.

    Returns:
        The updated nudge record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        UPDATE nudge_events
        SET status = 'SNOOZED', snoozed_until = $2
        WHERE id = $1
        RETURNING *
        """,
        nudge_id,
        snoozed_until,
    )


async def clear_nudge_snooze(nudge_id: UUID) -> asyncpg.Record | None:
    """Clear snooze and restore nudge to sent status.

    Args:
        nudge_id: The nudge event UUID.

    Returns:
        The updated nudge record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        UPDATE nudge_events
        SET status = 'SENT', snoozed_until = NULL
        WHERE id = $1
        RETURNING *
        """,
        nudge_id,
    )


async def get_latest_nudge_for_ticket(ticket_key: str) -> asyncpg.Record | None:
    """Get the most recent SENT nudge for a ticket.

    Args:
        ticket_key: The Jira ticket key.

    Returns:
        The most recent sent nudge record or None if none found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        SELECT * FROM nudge_events
        WHERE ticket_key = $1 AND status = 'SENT'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        ticket_key,
    )


# ============ ASSIGNEES ============


async def get_assignee(jira_id: str) -> asyncpg.Record | None:
    """Get an assignee by Jira ID.

    Args:
        jira_id: The Jira account ID.

    Returns:
        The assignee record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        "SELECT * FROM watched_assignees WHERE jira_id = $1",
        jira_id,
    )


async def list_assignees() -> tuple[list[asyncpg.Record], int]:
    """List all watched assignees.

    Returns:
        Tuple of (list of assignee records, total count).
    """
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT * FROM watched_assignees ORDER BY jira_display_name"
    )
    return rows, len(rows)


async def upsert_assignee(
    jira_id: str,
    display_name: str | None,
    slack_user_id: str | None,
    email: str | None,
) -> asyncpg.Record:
    """Insert or update an assignee.

    Args:
        jira_id: The Jira account ID.
        display_name: The user's display name.
        slack_user_id: The Slack user ID.
        email: The user's email address.

    Returns:
        The upserted assignee record.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        INSERT INTO watched_assignees (jira_id, jira_display_name, slack_user_id, email)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (jira_id) DO UPDATE SET
            jira_display_name = COALESCE(EXCLUDED.jira_display_name, watched_assignees.jira_display_name),
            slack_user_id = COALESCE(EXCLUDED.slack_user_id, watched_assignees.slack_user_id),
            email = COALESCE(EXCLUDED.email, watched_assignees.email)
        RETURNING *
        """,
        jira_id,
        display_name,
        slack_user_id,
        email,
    )


async def update_assignee_preferences(
    jira_id: str,
    quiet_hours_start: str | None = None,
    quiet_hours_end: str | None = None,
    default_snooze_minutes: int | None = None,
    timezone: str | None = None,
) -> asyncpg.Record | None:
    """Update assignee preferences.

    Args:
        jira_id: The Jira account ID.
        quiet_hours_start: Start of quiet hours (HH:MM format).
        quiet_hours_end: End of quiet hours (HH:MM format).
        default_snooze_minutes: Default snooze duration.
        timezone: User's timezone (e.g., Europe/London).

    Returns:
        The updated assignee record or None if not found.
    """
    pool = get_pool()

    updates = []
    params: list[Any] = [jira_id]
    param_idx = 2

    if quiet_hours_start is not None:
        updates.append(f"quiet_hours_start = ${param_idx}::time")
        params.append(quiet_hours_start)
        param_idx += 1

    if quiet_hours_end is not None:
        updates.append(f"quiet_hours_end = ${param_idx}::time")
        params.append(quiet_hours_end)
        param_idx += 1

    if default_snooze_minutes is not None:
        updates.append(f"default_snooze_minutes = ${param_idx}")
        params.append(default_snooze_minutes)
        param_idx += 1

    if timezone is not None:
        updates.append(f"timezone = ${param_idx}")
        params.append(timezone)
        param_idx += 1

    if not updates:
        return await get_assignee(jira_id)

    query = f"""
        UPDATE watched_assignees
        SET {', '.join(updates)}
        WHERE jira_id = $1
        RETURNING *
    """
    return await pool.fetchrow(query, *params)


async def increment_assignee_nudge_count(jira_id: str) -> asyncpg.Record | None:
    """Increment assignee nudge count and update last nudge time.

    Args:
        jira_id: The Jira account ID.

    Returns:
        The updated assignee record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        UPDATE watched_assignees
        SET nudge_count = nudge_count + 1, last_nudge_at = NOW()
        WHERE jira_id = $1
        RETURNING *
        """,
        jira_id,
    )


# ============ POLLING STATE ============


async def get_poll_state() -> asyncpg.Record | None:
    """Get current polling state.

    Returns:
        The polling state record or None if not initialized.
    """
    pool = get_pool()
    return await pool.fetchrow("SELECT * FROM polling_state WHERE id = 1")


async def update_poll_state(
    last_cursor: datetime,
    tickets_fetched: int,
    next_poll_at: datetime,
) -> asyncpg.Record:
    """Update polling state.

    Args:
        last_cursor: The timestamp cursor for incremental polling.
        tickets_fetched: Number of tickets fetched in last poll.
        next_poll_at: When the next poll should run.

    Returns:
        The updated polling state record.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        UPDATE polling_state
        SET last_cursor = $1, last_poll_at = NOW(),
            tickets_fetched = $2, next_poll_at = $3
        WHERE id = 1
        RETURNING *
        """,
        last_cursor,
        tickets_fetched,
        next_poll_at,
    )


async def create_poll_history() -> asyncpg.Record:
    """Create a new poll history entry.

    Returns:
        The created poll history record with generated ID.
    """
    pool = get_pool()
    return await pool.fetchrow("INSERT INTO poll_history DEFAULT VALUES RETURNING *")


async def complete_poll_history(
    poll_id: UUID,
    tickets_fetched: int,
    tickets_new: int,
    tickets_updated: int,
    nudges_triggered: int,
    status: str = "completed",
    error_message: str | None = None,
) -> asyncpg.Record | None:
    """Complete a poll history entry.

    Args:
        poll_id: The poll history UUID.
        tickets_fetched: Total tickets fetched.
        tickets_new: Number of new tickets.
        tickets_updated: Number of updated tickets.
        nudges_triggered: Number of nudges triggered.
        status: Final status (completed, failed, partial).
        error_message: Error message if failed.

    Returns:
        The updated poll history record or None if not found.
    """
    pool = get_pool()
    return await pool.fetchrow(
        """
        UPDATE poll_history
        SET completed_at = NOW(), tickets_fetched = $2, tickets_new = $3,
            tickets_updated = $4, nudges_triggered = $5, status = $6, error_message = $7
        WHERE id = $1
        RETURNING *
        """,
        poll_id,
        tickets_fetched,
        tickets_new,
        tickets_updated,
        nudges_triggered,
        status,
        error_message,
    )


async def get_poll_history(limit: int = 10) -> list[asyncpg.Record]:
    """Get recent poll history.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of poll history records, most recent first.
    """
    pool = get_pool()
    rows: list[Any] = await pool.fetch(
        "SELECT * FROM poll_history ORDER BY started_at DESC LIMIT $1",
        limit,
    )
    return rows
