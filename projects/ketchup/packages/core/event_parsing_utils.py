"""
event_parsing_utils.py

Centralized utility for event parsing logic.
"""

import json
from typing import Any, Dict, List
from urllib.parse import parse_qs

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def parse_slack_body(
    raw_body: bytes, content_type: str
) -> tuple[Dict[str, Any], Dict[str, List[Any]]]:
    """Parse raw body bytes into single-value and multi-value dicts.

    Handles JSON (application/json) and form-encoded
    (application/x-www-form-urlencoded) payloads including
    Slack's nested 'payload' JSON within form data.

    Args:
        raw_body: Raw request body as bytes.
        content_type: Content-Type header value.

    Returns:
        A tuple of (parsed_body_dict, parsed_body_multivalue) where:
        - parsed_body_dict: Single-value dict (JSON or form first-value)
        - parsed_body_multivalue: Multi-value dict (form: all values; JSON: [v])
    """
    parsed_body_dict: Dict[str, Any] = {}
    parsed_body_multivalue: Dict[str, List[Any]] = {}

    is_json = "application/json" in content_type
    decoded_body_str: str = ""

    if raw_body:
        try:
            decoded_body_str = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("Failed to decode body as UTF-8. Attempting ISO-8859-1.")
            try:
                decoded_body_str = raw_body.decode("iso-8859-1")
            except UnicodeDecodeError:
                logger.error("Failed to decode body with UTF-8 and ISO-8859-1.")
                return parsed_body_dict, parsed_body_multivalue
    else:
        logger.warning("Request body is missing or empty.")
        return parsed_body_dict, parsed_body_multivalue

    if is_json and decoded_body_str:
        try:
            parsed_body_dict = json.loads(decoded_body_str)
            parsed_body_multivalue = {k: [v] for k, v in parsed_body_dict.items()}
        except json.JSONDecodeError:
            logger.warning(
                "Content-Type is JSON, but failed to parse body: %s...",
                decoded_body_str[:200],
            )
            parsed_body_dict = {}
            parsed_body_multivalue = {}
    elif decoded_body_str and (
        "application/x-www-form-urlencoded" in content_type
        or ("=" in decoded_body_str and "&" in decoded_body_str)
    ):
        logger.info("Attempting to parse body as application/x-www-form-urlencoded.")
        try:
            parsed_body_multivalue = parse_qs(decoded_body_str)
            parsed_body_dict = {k: v[0] for k, v in parsed_body_multivalue.items() if v}
            if "payload" in parsed_body_dict:
                try:
                    payload_dict = json.loads(parsed_body_dict["payload"])
                    parsed_body_dict["payload"] = payload_dict
                    logger.info("Successfully parsed nested Slack payload JSON.")
                except json.JSONDecodeError:
                    logger.error("Failed to parse nested Slack payload JSON string.")
            logger.info("Successfully parsed form data. Keys: %s", list(parsed_body_dict.keys()))
        except Exception as e:
            logger.error(
                "Failed to parse form data: %s. Body: %s...",
                e,
                decoded_body_str[:200],
                exc_info=True,
            )
            parsed_body_dict = {}
            parsed_body_multivalue = {}
    elif decoded_body_str:
        logger.warning(
            "Could not parse body as JSON or form data. Content-Type: '%s'. Body: %s...",
            content_type,
            decoded_body_str[:200],
        )

    return parsed_body_dict, parsed_body_multivalue
