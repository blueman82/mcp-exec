"""
posting.py

This module provides functions for posting messages to Slack channels and users.
"""

from typing import Any, Dict, Optional

import aiohttp
import orjson

from packages.core.constants import FEEDBACK_CHANNEL
from packages.core.exceptions import ClientError, InvalidBlocksForResponseUrlError
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager
from packages.slack.config.slack_config import SlackConfig
from packages.slack.core.slack_async_client import SlackAsyncClient

logger = setup_logger(__name__)


class SlackPostingHandler(SlackAsyncClient):
    """
    A class for posting messages to Slack channels and users.
    """

    def __init__(
        self,
        slack_config: SlackConfig,
        secrets_manager: SecretsManager,
        max_concurrent_requests: int = 10,
    ):
        """
        Initialize the SlackPostingHandler.

        Args:
            slack_config: Pre-initialized SlackConfig instance (required).
            secrets_manager: Pre-initialized SecretsManager instance (required).
            max_concurrent_requests: Maximum number of concurrent requests
        """
        super().__init__(slack_config, max_concurrent_requests)
        self._secrets_manager = secrets_manager

        # Define the instance variable to fix linter error
        self._slack_token: Optional[str] = None

        # Session management handled by parent AsyncClient
        self._session = None

    async def _init_slack_token(self):
        """Initialize and cache the Slack API token."""
        if not self._slack_token:
            secrets = await self._secrets_manager.get_app_secrets()
            self._slack_token = secrets["SLACK_API_TOKEN"]

    async def post_message(
        self,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        message: Optional[str] = None,
        response_url: Optional[str] = None,
        blocks: Optional[list] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post a message to Slack using a hierarchical approach:
        1. Try to post as ephemeral message (if user_id and channel_id provided)
        2. Try to post via response_url (if provided)
        3. Fall back to chat.postMessage (if channel_id provided)

        Args:
            user_id: Slack user ID for ephemeral messages
            channel_id: Slack channel ID to post to
            message: Message content to post
            response_url: Slack response URL for interactive message responses
            blocks: Optional Block Kit blocks to include in the message

        Returns:
            Response data from the Slack API

        Raises:
            ValueError: If insufficient information is provided to post the message
            Exception: If all posting methods fail
        """
        # We now rely on the client factory to provide a setup session
        # and the lambda handler to manage cleanup.

        logger.info("Starting post_message with hierarchical approach")

        # Attempt ephemeral posting first (only if we have BOTH user_id and channel_id)
        if user_id and channel_id:
            try:
                # Ensure message is a string, provide empty string as fallback
                message_text = message if message is not None else ""
                logger.info(
                    "Attempting ephemeral message. User: %s, Channel: %s",
                    user_id,
                    channel_id,
                )
                response = await self._post_ephemeral(user_id, channel_id, message_text, blocks)

                # Check if the ephemeral message was successful (ok: True or not present)
                # If ok: False, log warning and try next method.
                if isinstance(response, dict) and response.get("ok") is False:
                    error_type = response.get("error", "unknown_error")
                    logger.warning(
                        "Ephemeral post returned ok:False with error: %s. Trying next method.",
                        error_type,
                    )
                else:
                    # Assume success if ok is True or not present
                    logger.info("Ephemeral post successful (or non-failure response).")
                    return response  # Return successful response

            except Exception as e:
                # Log generic error and try next method. Backoff handled by decorator.
                logger.warning("Ephemeral post failed: %s. Trying next method.", str(e))

        # Next try response_url if provided
        if response_url:
            try:
                # Ensure message is a string, provide empty string as fallback
                message_text = message if message is not None else ""
                logger.info("Attempting to post via response_url: %s", response_url)
                response = await self._post_response_url(response_url, message_text, blocks)
                # If response indicates a structured error (not ok), try fallback to channel_id
                if isinstance(response, dict) and not response.get("ok", True):
                    logger.warning("Response_url post failed with error: %s", response.get("error"))
                    return response
                logger.info("Response URL post successful.")
                return response  # Return successful response
            except Exception as e:  # Catch any exception from _post_response_url
                # Check if it's the specific block error
                if isinstance(e, InvalidBlocksForResponseUrlError):
                    logger.warning(
                        "InvalidBlocks error caught by post_message: %s. Re-raising for handler.",
                        str(e),
                    )
                    raise e  # Re-raise for the calling handler (e.g., ArchiveMessageHandler) to catch
                else:
                    # For OTHER errors from _post_response_url, log and try chat.postMessage
                    logger.warning(
                        "Response URL post failed (non-block error): %s. Trying next method.",
                        str(e),
                    )

        # Fallback to chat.postMessage if channel_id is provided
        # Keep the original logic for DMs and feedback channel, but also allow regular channels
        if channel_id == FEEDBACK_CHANNEL or (
            channel_id
            and (
                channel_id.startswith("U")
                or channel_id.startswith("W")
                or channel_id.startswith("D")
                or channel_id.startswith("C")
                or channel_id.startswith("G")
            )
        ):
            try:
                message_text = message if message is not None else ""
                logger.info("Attempting to post to channel via chat.postMessage: %s", channel_id)
                response = await self._post_channel_message(
                    channel_id, message_text, blocks, thread_ts=thread_ts
                )
                logger.info("chat.postMessage successful.")
                return response
            except Exception as e:
                logger.error("chat.postMessage failed: %s", str(e))
                raise

        # If we reach here, no valid method could be used
        error_msg = "Insufficient information to post message (need user/channel, response_url, or channel_id)."
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Backoff handled by inherited _make_api_request
    async def _post_ephemeral(
        self, user_id: str, channel_id: str, message: str, blocks: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Post an ephemeral message only visible to the specified user.

        Args:
            user_id: The Slack user ID to send the message to
            channel_id: The Slack channel ID to post in
            message: The message content
            blocks: Optional Block Kit blocks to include in the message

        Returns:
            The response from the Slack API
        """
        await self._init_slack_token()

        logger.info("Posting ephemeral message. User: %s, Channel: %s", user_id, channel_id)

        url = f"{self.config.get_api_base_url()}/chat.postEphemeral"
        headers = self.config.get_headers()

        # Prepare basic payload
        payload: Dict[str, Any] = {
            "channel": channel_id,
            "user": user_id,
            "text": message,
        }

        # Add blocks if provided
        if blocks:
            payload["blocks"] = blocks

        response = await self._make_api_request(url, "POST", headers, None, payload)
        # Response is now a SafeResponse dict, parse the body
        response_data = orjson.loads(response["body"])
        logger.info("Slack ephemeral response: %s", response_data)
        return response_data

    async def _post_response_url(
        self, response_url: str, message: str, blocks: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Post a message to a response_url from a Slack interaction.
        Uses a temporary session for resilience against main session closure.

        Args:
            response_url: The Slack response URL to post to
            message: The message content
            blocks: Optional Block Kit blocks to include in the message

        Returns:
            The response from the Slack API
        """
        logger.info("Sending message using response_url: %s", response_url)
        timeout = aiohttp.ClientTimeout(total=30)  # Short timeout for response URLs
        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Try sending with blocks first
            if blocks:
                payload = {
                    "blocks": blocks,
                    "text": message,  # Fallback text
                    "replace_original": False,
                    "response_type": "ephemeral",
                }
                logger.info("Attempting POST via response_url (blocks).")
                try:
                    # This inner try specifically handles exceptions *during* the post call and response processing
                    async with session.post(
                        response_url, headers=headers, json=payload
                    ) as response:
                        # --- Check for invalid_blocks error START --- ##
                        response_text_for_error = ""  # Initialize
                        try:
                            # Try reading text first in case it's not JSON or for error check
                            response_text_for_error = await response.text()
                            # Check status and content for invalid_blocks indication
                            is_invalid_block_error = (
                                response.status >= 400  # Check for client/server errors
                                and (
                                    "invalid_blocks" in response_text_for_error.lower()
                                    or "block is too large" in response_text_for_error.lower()
                                    or "invalid view" in response_text_for_error.lower()
                                )  # Added other common block errors
                            ) or (
                                response.status == 500
                                and "invalid_blocks" in response_text_for_error.lower()
                            )

                            if is_invalid_block_error:
                                logger.error(
                                    "Block-based response_url returned error indicating invalid blocks (Status %s): %s",
                                    response.status,
                                    response_text_for_error[:200],  # Log snippet
                                )
                                # Raise the specific error to be caught by post_message
                                raise InvalidBlocksForResponseUrlError(
                                    f"Blocks invalid for response_url (Status: {response.status}) - {response_text_for_error[:100]}",  # Add snippet
                                    response_data=response_text_for_error,  # Pass text as data
                                )

                            # If not invalid_blocks, try parsing as JSON
                            if response.content_type == "application/json":
                                import json

                                response_data = json.loads(response_text_for_error)
                            else:  # Fallback to standard json() which might raise ContentTypeError
                                # This is a regular aiohttp response, not SafeResponse
                                response_data = await response.json()

                            logger.info("Response URL response (blocks): %s", response_data)
                            if isinstance(response_data, dict) and response_data.get("ok") is False:
                                logger.warning(
                                    "Slack API indicated failure for response_url with blocks: %s",
                                    response_data.get("error"),
                                )
                                # Fall through to text-only retry for other 'ok: False' errors
                            else:
                                return response_data  # Success with blocks

                        except aiohttp.ContentTypeError:
                            text = await response.text()
                            if response.status == 200 and text.strip().lower() in (
                                "",
                                "ok",
                            ):
                                return {
                                    "ok": True,
                                    "assumed_success": True,
                                    "fallback_type": "mimetype_mismatch",
                                    "content_type": response.headers.get("Content-Type"),
                                    "raw_body": text[:100],  # safely truncated
                                }
                            logger.warning(
                                "Block-based response_url returned unexpected response %s: %s",
                                response.status,
                                response_text_for_error,
                            )
                            # Fall through to text-only retry
                        # --- Check for invalid_blocks error END --- ##
                except InvalidBlocksForResponseUrlError:  # Catch the specific error if raised above
                    raise  # Re-raise immediately for post_message to handle
                except Exception as e:  # Catch *other* exceptions from the block post attempt
                    logger.warning(
                        "Failed response_url post with blocks (non-block error): %s. Trying text-only.",
                        e,
                    )
                    # Fall through to text-only for other errors

            # Text-only attempt (either fallback or if no blocks provided)
            # This try block now correctly follows the 'if blocks:' block or runs if blocks=None
            try:
                payload = {
                    "text": message,
                    "replace_original": False,
                    "response_type": "ephemeral",
                }
                logger.info("Attempting POST via response_url (text-only).")
                async with session.post(response_url, headers=headers, json=payload) as response:
                    try:
                        # This is a regular aiohttp response, not SafeResponse
                        response_data = await response.json()
                        logger.info("Response URL response (text-only): %s", response_data)
                        if isinstance(response_data, dict) and response_data.get("ok") is False:
                            logger.error(
                                "Slack API indicated failure for response_url (text-only): %s",
                                response_data.get("error"),
                            )
                            # Raise the correct ClientError
                            raise ClientError(
                                f"Slack response_url failed: {response_data.get('error')}",
                                response_data=response_data,
                            )
                        return response_data  # Success with text
                    except aiohttp.ContentTypeError:
                        text = await response.text()
                        logger.info(
                            "Response URL raw body (text-only, content-type error): %s",
                            text,
                        )
                        if response.status == 200:
                            logger.info(
                                "Assuming text-only Slack response_url post succeeded despite invalid mimetype."
                            )
                            return {"ok": True, "assumed_success": True}
                        # If 404 or other error, log and return error response instead of raising
                        logger.error(
                            "Slack response_url returned unexpected mimetype and status %s: %s. Returning error response.",
                            response.status,
                            text,
                        )
                        return {
                            "ok": False,
                            "error": f"Unexpected mimetype and status {response.status}",
                            "status": response.status,
                            "body": text[:200],
                            "response_url": response_url,
                        }
                    except Exception as exc:
                        # If status was 200 but json decoding failed or other issue
                        logger.error(
                            "Unexpected error processing text-only response_url: %s",
                            exc,
                            exc_info=True,
                        )
                        return {
                            "ok": False,
                            "error": f"Unexpected error processing text-only response_url: {exc}",
                            "response_url": response_url,
                        }

            except Exception as e:
                logger.error("Text-only attempt failed for response_url: %s", e, exc_info=True)
                # If we fall through after blocks failed (non-invalid_blocks error), or text fails directly, raise
                raise Exception(f"Failed to post to response_url {response_url}") from e

    # Backoff handled by inherited _make_api_request
    async def _post_channel_message(
        self,
        channel_id: str,
        message: str,
        blocks: Optional[list] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post a message visible to the entire channel.

        Args:
            channel_id: The Slack channel ID to post in
            message: The message content
            blocks: Optional Block Kit blocks to include in the message

        Returns:
            The response from the Slack API
        """
        await self._init_slack_token()

        logger.info(
            "Sending message using chat.postMessage: channel=%s thread_ts=%s",
            channel_id,
            thread_ts,
        )
        headers = self.config.get_headers()

        # Prepare basic payload
        payload: Dict[str, Any] = {
            "channel": channel_id,
            "text": message,
        }

        # Add thread_ts for threaded replies
        if thread_ts:
            payload["thread_ts"] = thread_ts

        # Add blocks if provided
        if blocks:
            payload["blocks"] = blocks

        url = f"{self.config.get_api_base_url()}/chat.postMessage"

        response = await self._make_api_request(url, "POST", headers, None, payload)
        # Response is now a SafeResponse dict, parse the body
        response_data = orjson.loads(response["body"])
        logger.info("Response: %s", response_data)

        # Check for invalid_blocks error
        if isinstance(response_data, dict) and response_data.get("ok") is False:
            error = response_data.get("error", "")
            if error == "invalid_blocks":
                logger.error(
                    "chat.postMessage returned invalid_blocks error: %s",
                    response_data.get("errors", []),
                )
                # Raise the specific error to be caught by calling handlers
                raise InvalidBlocksForResponseUrlError(
                    f"Blocks invalid for chat.postMessage: {response_data.get('errors', [])}",
                    response_data=response_data,
                )

        return response_data

    async def update_message(
        self, channel_id: str, ts: str, message: str, blocks: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Update an existing Slack message.

        Args:
            channel_id: The Slack channel ID where the message exists
            ts: The timestamp of the message to update
            message: The new message content
            blocks: Optional Block Kit blocks to include in the message

        Returns:
            The response from the Slack API
        """
        await self._init_slack_token()

        logger.info("Updating message in channel %s with ts %s", channel_id, ts)
        headers = self.config.get_headers()

        # Prepare payload
        payload: Dict[str, Any] = {
            "channel": channel_id,
            "ts": ts,
            "text": message,
        }

        # Add blocks if provided
        if blocks:
            payload["blocks"] = blocks

        url = f"{self.config.get_api_base_url()}/chat.update"

        response = await self._make_api_request(url, "POST", headers, None, payload)
        # Response is now a SafeResponse dict, parse the body
        response_data = orjson.loads(response["body"])

        if not response_data.get("ok"):
            logger.error(
                "Failed to update message: %s",
                response_data.get("error", "Unknown error"),
            )
        else:
            logger.info("Message updated successfully")

        return response_data

    async def delete_message(self, channel_id: str, message_ts: str) -> Dict[str, Any]:
        """
        Delete a message from a Slack channel.

        Args:
            channel_id: The ID of the channel containing the message
            message_ts: The timestamp of the message to delete

        Returns:
            Dict containing the response from Slack API
        """
        await self._init_slack_token()

        payload = {"channel": channel_id, "ts": message_ts, "token": self._slack_token}

        headers = self.config.get_headers()
        url = f"{self.config.get_api_base_url()}/chat.delete"

        response = await self._make_api_request(url, "POST", headers, None, payload)
        # Response is now a SafeResponse dict, parse the body
        response_data = orjson.loads(response["body"])

        if not response_data.get("ok"):
            logger.error(
                "Failed to delete message %s from channel %s: %s",
                message_ts,
                channel_id,
                response_data.get("error", "Unknown error"),
            )
        else:
            logger.info("Message %s deleted successfully from channel %s", message_ts, channel_id)

        return response_data

    async def pin_message(self, channel_id: str, message_ts: str) -> Dict[str, Any]:
        """
        Pin a message in a Slack channel.

        Args:
            channel_id: The ID of the channel containing the message
            message_ts: The timestamp of the message to pin

        Returns:
            Dict containing the response from Slack API
        """
        await self._init_slack_token()

        payload = {"channel": channel_id, "timestamp": message_ts}

        headers = self.config.get_headers()
        url = f"{self.config.get_api_base_url()}/pins.add"

        response = await self._make_api_request(url, "POST", headers, None, payload)
        # Response is now a SafeResponse dict, parse the body
        response_data = orjson.loads(response["body"])

        if not response_data.get("ok"):
            logger.error(
                "Failed to pin message %s in channel %s: %s",
                message_ts,
                channel_id,
                response_data.get("error", "Unknown error"),
            )
        else:
            logger.info("Message %s pinned successfully in channel %s", message_ts, channel_id)

        return response_data
