"""Pydantic schemas matching OpenAPI specification."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ============ ENUMS ============


class TicketStatus(str, Enum):
    """Ticket watch status."""

    ACQUIRED = "ACQUIRED"
    ACTIVE = "ACTIVE"
    SNOOZED = "SNOOZED"
    RESOLVED = "RESOLVED"


class NudgeStatus(str, Enum):
    """Nudge event status."""

    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SNOOZED = "SNOOZED"
    RESPONDED = "RESPONDED"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class PollStatus(str, Enum):
    """Poll execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class LogLevel(str, Enum):
    """Log level filter."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ============ HEALTH ============


class ComponentHealth(BaseModel):
    """Health status of a component."""

    status: HealthStatus = HealthStatus.HEALTHY
    latency_ms: int | None = None
    last_check: datetime | None = None


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: HealthStatus
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DetailedHealthResponse(HealthResponse):
    """Detailed health check with component status."""

    components: dict[str, ComponentHealth] | None = None


# ============ STATS ============


class TicketStats(BaseModel):
    """Ticket statistics."""

    total_watched: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_project: dict[str, int] = Field(default_factory=dict)


class NudgeStats(BaseModel):
    """Nudge statistics."""

    total_sent: int = 0
    today: int = 0
    response_rate: float = 0.0


class PollingStats(BaseModel):
    """Polling statistics."""

    last_poll: datetime | None = None
    polls_today: int = 0
    avg_tickets_per_poll: float = 0.0


class StatsResponse(BaseModel):
    """System statistics response."""

    tickets: TicketStats = Field(default_factory=TicketStats)
    nudges: NudgeStats = Field(default_factory=NudgeStats)
    polling: PollingStats = Field(default_factory=PollingStats)


# ============ CONFIG ============


class GateConfig(BaseModel):
    """Gate configuration."""

    g1_enabled: bool = True
    g2_stale_hours: int = 4
    g3_response_hours: int = 24
    g4_resolution_hours: int = 24


class LLMConfig(BaseModel):
    """LLM configuration."""

    threshold: float = 3.0
    model: str = "gpt-4"


class ConfigResponse(BaseModel):
    """Configuration response."""

    poll_interval_minutes: int = 60
    projects: list[str] = Field(default_factory=list)
    org_groups: list[str] = Field(default_factory=list)
    gates: GateConfig = Field(default_factory=GateConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""

    poll_interval_minutes: int | None = None
    gates: GateConfig | None = None
    llm: LLMConfig | None = None


# ============ POLLING ============


class PollTriggerResponse(BaseModel):
    """Poll trigger response."""

    poll_id: UUID
    status: PollStatus = PollStatus.QUEUED
    message: str | None = None


class PollStateResponse(BaseModel):
    """Current poll state."""

    last_cursor: datetime | None = None
    last_poll_at: datetime | None = None
    tickets_fetched: int = 0
    next_poll_at: datetime | None = None


class PollHistoryEntry(BaseModel):
    """Single poll history entry."""

    poll_id: UUID
    started_at: datetime
    completed_at: datetime | None = None
    tickets_fetched: int = 0
    tickets_new: int = 0
    tickets_updated: int = 0
    nudges_triggered: int = 0
    status: PollStatus = PollStatus.COMPLETED


class PollHistoryResponse(BaseModel):
    """Poll history response."""

    polls: list[PollHistoryEntry] = Field(default_factory=list)


# ============ TICKETS ============


class GateResults(BaseModel):
    """Gate evaluation results."""

    g1_passed: bool | None = None
    g2_passed: bool | None = None
    g3_passed: bool | None = None
    g4_passed: bool | None = None


class LLMScores(BaseModel):
    """LLM scoring results."""

    clarity: float | None = None
    completeness: float | None = None
    root_cause: float | None = None
    actionability: float | None = None
    average: float | None = None


class TicketResponse(BaseModel):
    """Ticket details response."""

    ticket_key: str
    jira_id: str | None = None
    project: str | None = None
    summary: str | None = None
    assignee_jira_id: str | None = None
    assignee_name: str | None = None
    status: TicketStatus
    jira_status: str | None = None
    first_seen_at: datetime | None = None
    last_polled_at: datetime | None = None
    last_assignee_comment_at: datetime | None = None
    snoozed_until: datetime | None = None
    gate_results: GateResults | None = None
    llm_scores: LLMScores | None = None


class TicketListResponse(BaseModel):
    """Ticket list response."""

    tickets: list[TicketResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class EvaluationResponse(BaseModel):
    """Ticket evaluation response."""

    ticket_key: str
    gate_results: GateResults | None = None
    llm_scores: LLMScores | None = None
    nudge_triggered: bool = False
    nudge_reason: str | None = None


# ============ NUDGE ============


class NudgeResponse(BaseModel):
    """Nudge event details."""

    nudge_id: UUID
    ticket_key: str
    assignee_jira_id: str
    status: NudgeStatus
    trigger_reason: str | None = None
    slack_channel: str | None = None
    slack_ts: str | None = None
    message_content: str | None = None
    created_at: datetime
    responded_at: datetime | None = None
    jira_comment_posted: str | None = None


class NudgeListResponse(BaseModel):
    """Nudge list response."""

    nudges: list[NudgeResponse] = Field(default_factory=list)
    total: int = 0


class SendNudgeRequest(BaseModel):
    """Manual nudge send request."""

    ticket_key: str
    reason: str | None = None


# ============ ASSIGNEES ============


class AssigneeResponse(BaseModel):
    """Assignee details."""

    jira_id: str
    jira_display_name: str | None = None
    slack_user_id: str | None = None
    email: str | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    default_snooze_minutes: int = 240
    timezone: str = "Europe/London"
    nudge_count: int = 0
    last_nudge_at: datetime | None = None


class AssigneeListResponse(BaseModel):
    """Assignee list response."""

    assignees: list[AssigneeResponse] = Field(default_factory=list)
    total: int = 0


class AssigneeUpdateRequest(BaseModel):
    """Assignee update request."""

    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    default_snooze_minutes: int | None = None
    timezone: str | None = None


# ============ LOGS ============


class LogEntry(BaseModel):
    """Single log entry."""

    timestamp: datetime
    level: str
    message: str
    context: dict[str, Any] | None = None


class LogsResponse(BaseModel):
    """Logs response."""

    logs: list[LogEntry] = Field(default_factory=list)
