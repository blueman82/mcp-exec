"""
event_parsing_utils.py

Centralized utility for event parsing logic (moved from utils.py).
"""

import base64
import json
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def parse_event_body(
    event: Dict[str, Any],
) -> Tuple[Optional[bytes], Dict[str, Any], Dict[str, Any]]:
    """
    Parses the request body from a Lambda event, handling JSON, form data,
    and Slack's nested 'payload' within form data. Also handles base64 decoding.

    Args:
        event: The Lambda event dictionary.

    Returns:
        A tuple containing:
        - raw_body_bytes: The raw bytes of the request body (after base64 decoding if needed).
        - parsed_body_dict: Dictionary of parsed body (single value per key, including nested payload if applicable).
        - parsed_body_multivalue: Dictionary of parsed body (list of values per key).
    """
    raw_body_bytes: Optional[bytes] = None
    parsed_body_dict: Dict[str, Any] = {}
    parsed_body_multivalue: Dict[str, Any] = {}
    headers = event.get("headers", {}) or {}
    mv_headers = event.get("multiValueHeaders", {}) or {}
    merged_headers = {k.lower(): v for k, v in headers.items()}
    for k, v in mv_headers.items():
        if isinstance(v, list) and v:
            merged_headers[k.lower()] = v[0]
        elif isinstance(v, str):
            merged_headers[k.lower()] = v
    # logger.info("Merged headers for event: %s", merged_headers)
    content_type = merged_headers.get("content-type", "")
    is_json = "application/json" in content_type
    decoded_body_str: Optional[str] = None

    # --- Body Decoding (including base64) ---
    if event.get("body"):
        if event.get("isBase64Encoded", False):
            try:
                raw_body_bytes = base64.b64decode(event.get("body"))
                logger.info("Successfully base64 decoded request body.")
            except (TypeError, ValueError) as e:
                logger.error("Failed to base64 decode body: %s", e)
                raw_body_bytes = b""  # Indicate failure to decode
        elif isinstance(event.get("body"), str):
            raw_body_bytes = event.get("body").encode("utf-8")
            # logger.info("Encoded string body to bytes.")
        elif isinstance(event.get("body"), bytes):
            raw_body_bytes = event.get("body")
            logger.info("Body is already bytes.")
        else:
            logger.error("Unexpected body type: %s.", type(event.get("body")))
            raw_body_bytes = b""

        # --- Attempt to get string version after decoding bytes ---
        if raw_body_bytes:
            try:
                decoded_body_str = raw_body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning("Failed to decode body as UTF-8. Attempting ISO-8859-1.")
                try:
                    decoded_body_str = raw_body_bytes.decode("iso-8859-1")
                except UnicodeDecodeError:
                    logger.error("Failed to decode body with UTF-8 and ISO-8859-1.")
                    decoded_body_str = ""  # Unable to decode
    else:
        logger.warning("Request body is missing or empty.")
        raw_body_bytes = b""
        decoded_body_str = ""

    # --- Parsing Logic ---
    if is_json and decoded_body_str:
        try:
            parsed_body_dict = json.loads(decoded_body_str)
            # Simulate multivalue for JSON (assuming single value)
            parsed_body_multivalue = {k: [v] for k, v in parsed_body_dict.items()}
            # logger.info(
            #     "Successfully parsed JSON body. Keys: %s", list(parsed_body_dict.keys())
            # )
        except json.JSONDecodeError:
            logger.warning(
                "Content-Type is JSON, but failed to parse body: %s...",
                decoded_body_str[:200],
            )
            # Reset in case of partial parsing or error
            parsed_body_dict = {}
            parsed_body_multivalue = {}

    # If not JSON or JSON parsing failed, try form-urlencoded
    elif decoded_body_str and (
        "application/x-www-form-urlencoded" in content_type
        or ("=" in decoded_body_str and "&" in decoded_body_str)  # Heuristic check
    ):
        logger.info("Attempting to parse body as application/x-www-form-urlencoded.")
        try:
            parsed_body_multivalue = parse_qs(decoded_body_str)
            # Create a single-value version, taking the first value for each key
            parsed_body_dict = {k: v[0] for k, v in parsed_body_multivalue.items() if v}

            # --- Incorporate Slack nested payload logic ---
            if "payload" in parsed_body_dict:
                try:
                    # Replace the string payload with the parsed dict
                    payload_dict = json.loads(parsed_body_dict["payload"])
                    parsed_body_dict["payload"] = payload_dict
                    logger.info("Successfully parsed nested Slack payload JSON.")
                except json.JSONDecodeError:
                    logger.error("Failed to parse nested Slack payload JSON string.")
            # --- End Slack logic ---

            logger.info(  # Changed to info for successful form parse
                "Successfully parsed form data. Keys: %s", list(parsed_body_dict.keys())
            )
        except Exception as e:
            logger.error(
                "Failed to parse form data: %s. Body: %s...",
                e,
                decoded_body_str[:200],
                exc_info=True,
            )
            # Reset in case of partial parsing or error
            parsed_body_dict = {}
            parsed_body_multivalue = {}

    # Fallback if it's not JSON and doesn't look like form data or failed parsing
    elif decoded_body_str:  # Check if there was a body string at all
        logger.warning(
            "Could not parse body as JSON or form data. Content-Type: '%s'. Body: %s...",
            content_type,
            decoded_body_str[:200],
        )

    # Final check for debugging
    # logger.info(
    #     "Final parsed body keys (single value): %s", list(parsed_body_dict.keys())
    # )
    # logger.info(
    #     "Final parsed body keys (multi value): %s", list(parsed_body_multivalue.keys())
    # )

    # Return raw bytes (might be needed for signature verification), single-value, and multi-value dicts
    return raw_body_bytes, parsed_body_dict, parsed_body_multivalue
