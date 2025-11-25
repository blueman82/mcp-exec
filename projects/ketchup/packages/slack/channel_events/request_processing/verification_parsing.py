"""
verification_parsing.py

Handles Slack request signature verification and body parsing.
"""

import base64
from typing import Any, Dict, List, Optional, Tuple

from packages.core.event_parsing_utils import parse_event_body
from packages.core.logging import setup_logger
from packages.slack.authorisation.auth import SlackAuth

logger = setup_logger(__name__)


async def verify_and_parse_body(
    event: Dict[str, Any], slack_auth: SlackAuth
) -> Tuple[Optional[bytes], Optional[Dict[str, Any]], Optional[Dict[str, List[str]]]]:
    """
    Verifies Slack signature using raw body and then parses the request body.

    Returns:
        - raw_body_bytes: Raw request body as bytes (used for signature verification).
        - parsed_body_dict: Parsed single-value dict (JSON or form).
        - parsed_body_multivalue: Parsed multi-value dict.
    """
    # --- Extract raw body as bytes (before any parsing) ---
    try:
        if event.get("isBase64Encoded", False):
            raw_body_bytes = base64.b64decode(event["body"])
        else:
            body = event.get("body")
            if body is None:
                # Missing body - use empty bytes
                raw_body_bytes = b""
            elif isinstance(body, bytes):
                # Body is already bytes
                raw_body_bytes = body
            elif isinstance(body, str):
                # Body is string - encode it
                raw_body_bytes = body.encode("utf-8")
            else:
                # Unexpected type - raise error to be caught below
                raise TypeError(f"Unsupported body type: {type(body)}")
    except Exception as e:
        logger.warning(
            "Unable to extract raw_body_bytes for signature verification: %s", e
        )
        return None, None, None

    # --- Verify Slack signature using raw bytes ---
    if not await slack_auth.verify_slack_signature(
        raw_body_bytes=raw_body_bytes,
        headers=event.get("headers", {}),
    ):
        logger.warning("Slack signature verification failed")
        return None, None, None

    # --- Now it's safe to parse the body ---
    raw_body_bytes, parsed_body_dict, parsed_body_multivalue = parse_event_body(event)

    return raw_body_bytes, parsed_body_dict, parsed_body_multivalue
