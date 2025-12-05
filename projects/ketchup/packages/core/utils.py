"""
utils.py

This module contains various utility functions used across the application.
"""

import re
from typing import Any, Dict, Optional, Union

import aiohttp
import httpx

from packages.core.constants import SLACK_API_TIMEOUT
from packages.core.http.session_management import create_session_with_retries
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


async def invite_ketchup_to_channel(
    channel_id: str,
    user_id: str,
    channel_name: str,
    secrets_manager: SecretsManager,
    http_session: Optional[Union[aiohttp.ClientSession, httpx.AsyncClient]] = None,
) -> Dict[str, Any]:
    """
    Adds Ketchup (the bot) to a Slack channel by calling the Slack API. This is the main function used by other parts of the code to invite the bot to a channel. It handles all the details like authentication and making the web request.

    Args:
        channel_id: The Slack channel ID where the invitation should be sent
        user_id: The Slack user ID to invite
        channel_name: The name of the channel (used for logging purposes)
        secrets_manager: Instance of SecretsManager for retrieving secrets
        http_session: Optional pre-configured HTTP session (aiohttp.ClientSession or httpx.AsyncClient). If None, a new session will be created.

    Returns:
        The JSON response from the Slack API
    """
    logger.info(
        "Starting invite_ketchup_to_channel function for user %s in channel %s (ID: %s).",
        user_id,
        channel_name,
        channel_id,
    )

    # Get slack api token from secrets manager
    slack_api_token = await secrets_manager.get_slack_api_token_async()

    # Configure API request headers with auth token
    headers = {
        "Authorization": f"Bearer {slack_api_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    logger.info(
        "Sending invitation request to Slack API for user %s to join channel %s (ID: %s).",
        user_id,
        channel_name,
        channel_id,
    )

    # Create a new session if one wasn't provided
    session_created = False
    session_to_use = http_session

    try:
        if session_to_use is None:
            logger.info("No session provided, creating a new one")
            new_session, last_error = await create_session_with_retries(
                client_name="invite_ketchup_to_channel",
                request_timeout_total=SLACK_API_TIMEOUT.total,
                semaphore_limit=10,  # Use a reasonable default limit for concurrent requests
            )
            if new_session is None:
                raise RuntimeError(f"Failed to create session: {last_error}")
            session_to_use = new_session
            session_created = True

        # Use the session (either provided or newly created)
        # httpx and aiohttp have different .post() APIs
        if isinstance(session_to_use, httpx.AsyncClient):
            # httpx: post() returns Response directly (not a context manager)
            response = await session_to_use.post(
                "https://slack.com/api/conversations.join",
                headers=headers,
                json={"channel": channel_id, "users": user_id},
            )
            logger.info(
                "Received response with status code: %s from Slack API.",
                response.status_code,
            )

            # Parse response and handle success/failure
            invite_data = response.json()
            if invite_data.get("ok"):
                logger.info(
                    "Successfully invited user %s to channel %s (ID: %s).",
                    user_id,
                    channel_name,
                    channel_id,
                )
            else:
                logger.error(
                    "Failed to invite user %s to channel %s (ID: %s): %s.",
                    user_id,
                    channel_name,
                    channel_id,
                    invite_data.get("error"),
                )

            logger.info("Response from conversations.join: %s.", invite_data)
            return invite_data
        else:
            # aiohttp: post() returns a context manager
            async with session_to_use.post(
                "https://slack.com/api/conversations.join",
                headers=headers,
                json={"channel": channel_id, "users": user_id},
            ) as response:
                logger.info(
                    "Received response with status code: %s from Slack API.",
                    response.status,
                )

                # Parse response and handle success/failure
                invite_data = await response.json()
                if invite_data.get("ok"):
                    logger.info(
                        "Successfully invited user %s to channel %s (ID: %s).",
                        user_id,
                        channel_name,
                        channel_id,
                    )
                else:
                    logger.error(
                        "Failed to invite user %s to channel %s (ID: %s): %s.",
                        user_id,
                        channel_name,
                        channel_id,
                        invite_data.get("error"),
                    )

                logger.info("Response from conversations.join: %s.", invite_data)
                return invite_data

    except (
        aiohttp.ClientError,
        httpx.HTTPError,
    ) as e:  # Handle network/client errors for both libraries
        logger.error(
            "Request error while inviting user %s to channel %s (ID: %s): %s.",
            user_id,
            channel_name,
            channel_id,
            str(e),
        )
        return {"ok": False, "error": str(e)}
    except Exception as e:  # Handle unexpected errors
        logger.error(
            "Unexpected error while inviting user %s to channel %s (ID: %s): %s.",
            user_id,
            channel_name,
            channel_id,
            str(e),
        )
        return {"ok": False, "error": str(e)}
    finally:
        # Clean up the session if we created it
        if session_created and session_to_use is not None:
            if isinstance(session_to_use, httpx.AsyncClient):
                await session_to_use.aclose()
                logger.info("Closed created httpx session")
            else:
                await session_to_use.close()
                logger.info("Closed created aiohttp session")


def normalize_prompt_for_agent(text: str) -> str:
    """
    Normalize user prompts to prevent interpretation issues.

    This function addresses the issue where multi-line prompts cause the agent to
    execute fragments of the original query as separate tasks.

    Args:
        text: The raw user input text

    Returns:
        Normalized text safe for agent processing
    """
    if not text:
        return text

    # Remove leading/trailing whitespace
    text = text.strip()

    # Replace multiple consecutive newlines (with or without spaces) with a single space
    # This regex matches 2 or more newlines with optional whitespace between them
    text = re.sub(r"\n\s*\n+", " ", text)

    # Replace remaining single newlines with spaces (but preserve intentional line breaks in structured data)
    # Only replace if not part of a list or structured format (e.g., "1. item" or "- item")
    text = re.sub(r"(?<![:\-\d\.])\n(?![:\-\d\.])", " ", text)

    # Normalize multiple spaces to single space
    text = re.sub(r"\s+", " ", text)

    return text
