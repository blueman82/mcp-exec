"""
models.py

Data models for Slack request processing.
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class SlackRequest:
    """Parsed Slack request — replaces the Lambda event dict.

    This immutable dataclass represents a fully parsed Slack webhook request,
    eliminating the need to pass around Lambda event dicts and allowing for
    cleaner, type-safe request handling across the pipeline.

    Attributes:
        raw_body: Raw request body as bytes (used for signature verification).
        body_str: Decoded body as string (for logging and debugging).
        headers: Request headers with lowercase keys for case-insensitive access.
        path: Request path (e.g., "/slack/events", "/slack/commands").
        parsed_body: Single-value dict of parsed body (JSON or form first-value).
        parsed_body_multivalue: Multi-value dict of parsed body (form: all values; JSON: [v]).
    """

    raw_body: bytes
    body_str: str
    headers: Dict[str, str]
    path: str
    parsed_body: Dict[str, Any]
    parsed_body_multivalue: Dict[str, List[Any]]


@dataclass(frozen=True)
class ProcessingResult:
    """Result of processing a Slack request — replaces {statusCode, body} dicts.

    Attributes:
        status_code: HTTP status code (e.g., 200, 400, 500).
        body: Response body string (plain text or JSON-encoded).
        feedback_sent: Whether feedback was already sent to the user (command handlers).
    """

    status_code: int
    body: str = ""
    feedback_sent: bool = False
