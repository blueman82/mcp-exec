"""
Safe extraction of response_text from AI JSON responses.

Single source of truth for parsing structured JSON output from OpenAI.
All callers that need to extract response_text from AI responses should
use safe_extract_response_text() instead of inline orjson.loads() + .get().
"""

from __future__ import annotations

import orjson

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def safe_extract_response_text(raw_content: str, fallback: str = "") -> str:
    """Extract response_text from an AI JSON response, safely.

    Handles three failure modes:
    1. JSON parse failure → returns fallback
    2. Missing response_text key → returns fallback
    3. response_text value looks like JSON → returns fallback

    Args:
        raw_content: Raw string from AI response (may be JSON or prose)
        fallback: Value to return on any failure

    Returns:
        The extracted response_text string, or fallback on failure.
    """
    try:
        data = orjson.loads(raw_content)
    except (orjson.JSONDecodeError, TypeError):
        logger.warning("Failed to parse AI JSON response, using fallback")
        return fallback

    if not isinstance(data, dict):
        logger.warning("AI JSON response is not a dict (got %s), using fallback", type(data).__name__)
        return fallback

    # Case-insensitive key lookup (AI sometimes returns RESPONSE_TEXT)
    lower_data = {k.lower(): v for k, v in data.items()}
    text = lower_data.get("response_text")

    if text is None:
        logger.warning(
            "AI JSON response missing 'response_text' key (keys: %s), using fallback",
            list(data.keys()),
        )
        return fallback

    if not isinstance(text, str):
        logger.warning("response_text is not a string (got %s), using fallback", type(text).__name__)
        return fallback

    # Guard: reject if extracted text still looks like raw JSON
    if text.lstrip().startswith("{"):
        logger.warning("response_text appears to be nested JSON, using fallback: %.100s", text)
        return fallback

    return text
