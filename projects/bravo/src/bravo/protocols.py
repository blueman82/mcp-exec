"""Protocol interfaces for Bravo services.

Defines runtime-checkable Protocol classes for dependency injection,
enabling loose coupling between services and their consumers.
"""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from bravo.services.gates import GateEvaluation
from bravo.services.llm import LLMScore


@runtime_checkable
class SlackServiceProto(Protocol):
    """Protocol for Slack messaging operations."""

    async def send_dm(
        self,
        user_id: str,
        text: str,
        blocks: list[dict] | None = None,
    ) -> str | None: ...

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict] | None = None,
    ) -> bool: ...

    async def lookup_user_by_email(self, email: str) -> Any: ...

    async def close(self) -> None: ...


@runtime_checkable
class JiraClientProto(Protocol):
    """Protocol for Jira API operations."""

    async def search_tickets(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 100,
    ) -> list: ...

    async def add_comment(self, ticket_key: str, body: str) -> None: ...

    async def transition_status(
        self,
        ticket_key: str,
        transition_id: str,
        resolution: dict | None = None,
    ) -> None: ...

    async def get_transitions(self, ticket_key: str) -> list[dict]: ...

    async def create_issue(self, fields: dict) -> dict: ...

    async def update_issue(self, ticket_key: str, fields: dict) -> None: ...

    async def download_attachment(
        self,
        ticket_key: str,
        attachment_id: str,
        destination_path: str,
    ) -> dict: ...

    async def close(self) -> None: ...


@runtime_checkable
class GateServiceProto(Protocol):
    """Protocol for heuristic gate evaluation."""

    def evaluate(
        self,
        has_assignee_comment: bool,
        last_assignee_comment_at: datetime | None,
        first_seen_at: datetime,
        jira_status: str,
    ) -> GateEvaluation: ...


@runtime_checkable
class LLMServiceProto(Protocol):
    """Protocol for LLM-based ticket scoring."""

    async def score_ticket(
        self,
        ticket_key: str,
        summary: str,
        comments: list[str],
    ) -> LLMScore: ...

    def build_prompt(self, summary: str, comments: list[str]) -> str: ...

    async def close(self) -> None: ...

@runtime_checkable
class PollerServiceProto(Protocol):
    """Protocol for Jira polling operations."""

    async def run_poll(self) -> dict: ...


@runtime_checkable
class NudgeServiceProto(Protocol):
    """Protocol for nudge orchestration."""

    async def evaluate_ticket(self, ticket_key: str) -> dict: ...
