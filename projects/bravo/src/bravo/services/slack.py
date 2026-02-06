"""Slack Socket Mode client service.

This module provides async Slack integration using Socket Mode for
receiving events and the Web API for sending messages.
"""

import asyncio
from dataclasses import dataclass

import structlog
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web.async_client import AsyncWebClient

from bravo.config import SlackSettings

logger = structlog.get_logger(__name__)


@dataclass
class SlackUser:
    """Slack user data.

    Attributes:
        user_id: The Slack user ID.
        email: The user's email address.
        display_name: The user's display name.
    """

    user_id: str
    email: str | None = None
    display_name: str | None = None


class SlackService:
    """Slack Socket Mode service.

    Provides methods for sending DMs, looking up users, and handling
    Socket Mode events for interactive message responses.

    Attributes:
        settings: Slack API configuration.
    """

    def __init__(self, settings: SlackSettings) -> None:
        """Initialize the Slack service.

        Args:
            settings: Slack API configuration.
        """
        self.settings = settings
        self._web_client: AsyncWebClient | None = None
        self._socket_client: SocketModeClient | None = None

    def _get_web_client(self) -> AsyncWebClient:
        """Get or create web client.

        Returns:
            The Slack async web client.
        """
        if self._web_client is None:
            self._web_client = AsyncWebClient(token=self.settings.bot_token)
        return self._web_client

    async def send_dm(
        self,
        user_id: str,
        text: str,
        blocks: list | None = None,
    ) -> str | None:
        """Send a direct message to a user.

        Args:
            user_id: The Slack user ID to message.
            text: The message text (fallback for blocks).
            blocks: Optional Block Kit blocks for rich formatting.

        Returns:
            The message timestamp if successful, None otherwise.
        """
        client = self._get_web_client()

        logger.info("sending_slack_dm", user_id=user_id)

        response = await client.chat_postMessage(
            channel=user_id,
            text=text,
            blocks=blocks,
        )

        if response["ok"]:
            ts = response["ts"]
            logger.info("slack_dm_sent", user_id=user_id, ts=ts)
            return ts

        logger.error("slack_dm_failed", user_id=user_id, error=response.get("error"))
        return None

    async def lookup_user_by_email(self, email: str) -> SlackUser | None:
        """Look up a Slack user by email.

        Args:
            email: The email address to search for.

        Returns:
            SlackUser if found, None otherwise.
        """
        client = self._get_web_client()

        try:
            response = await client.users_lookupByEmail(email=email)
            if response["ok"]:
                user = response["user"]
                return SlackUser(
                    user_id=user["id"],
                    email=user.get("profile", {}).get("email"),
                    display_name=user.get("profile", {}).get("display_name"),
                )
        except Exception as e:
            logger.warning("slack_user_lookup_failed", email=email, error=str(e))

        return None

    async def start_socket_mode(self) -> None:
        """Start Socket Mode client.

        Initializes the Socket Mode WebSocket connection, registers event
        listeners for interactive messages, slash commands, and Events API
        payloads, then keeps the connection alive.
        """
        logger.info("socket_mode_start_requested")

        self._socket_client = SocketModeClient(
            app_token=self.settings.app_token,
            web_client=self._get_web_client(),
        )

        async def _listener(
            client: SocketModeClient,
            req: SocketModeRequest,
        ) -> None:
            """Route incoming Socket Mode requests by type."""
            if req.type == "interactive":
                payload = req.payload
                interaction_type = payload.get("type", "")

                if interaction_type == "block_actions":
                    await self._handle_block_action(payload, client, req)
                elif interaction_type == "view_submission":
                    await self._handle_view_submission(payload, client, req)
                else:
                    logger.warning(
                        "unhandled_interactive_type",
                        interaction_type=interaction_type,
                    )
                    await client.send_socket_mode_response(
                        SocketModeResponse(envelope_id=req.envelope_id),
                    )

            elif req.type == "slash_commands":
                await self._handle_slash_command(req.payload, client, req)

            elif req.type == "events_api":
                event = req.payload.get("event", {})
                await self._handle_event(event, client, req)

            else:
                logger.warning("unhandled_request_type", request_type=req.type)
                await client.send_socket_mode_response(
                    SocketModeResponse(envelope_id=req.envelope_id),
                )

        self._socket_client.socket_mode_request_listeners.append(_listener)

        await self._socket_client.connect()
        logger.info("socket_mode_connected")

        while True:
            await asyncio.sleep(1)

    async def _handle_block_action(
        self,
        payload: dict,
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle interactive block action events (button clicks).

        Args:
            payload: The interaction payload from Slack.
            client: The Socket Mode client for acknowledgement.
            req: The original Socket Mode request.
        """
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id", "unknown")
            logger.info("block_action_received", action_id=action_id)

        await client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id),
        )

    async def _handle_view_submission(
        self,
        payload: dict,
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle modal view submission events.

        Args:
            payload: The view submission payload from Slack.
            client: The Socket Mode client for acknowledgement.
            req: The original Socket Mode request.
        """
        callback_id = payload.get("view", {}).get("callback_id", "unknown")
        logger.info("view_submission_received", callback_id=callback_id)

        await client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id),
        )

    async def _handle_slash_command(
        self,
        payload: dict,
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle slash command events.

        Args:
            payload: The slash command payload from Slack.
            client: The Socket Mode client for acknowledgement.
            req: The original Socket Mode request.
        """
        command = payload.get("command", "unknown")
        logger.info("slash_command_received", command=command)

        await client.send_socket_mode_response(
            SocketModeResponse(
                envelope_id=req.envelope_id,
                payload={"text": "Bravo received your command"},
            ),
        )

    async def _handle_event(
        self,
        event: dict,
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle Events API events.

        Args:
            event: The inner event payload (e.g. message.im, app_mention).
            client: The Socket Mode client for acknowledgement.
            req: The original Socket Mode request.
        """
        event_type = event.get("type", "unknown")
        logger.info("event_received", event_type=event_type)

        await client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id),
        )

    async def close(self) -> None:
        """Close Slack clients.

        Closes any open Socket Mode connections.
        """
        if self._socket_client:
            await self._socket_client.close()
            self._socket_client = None
        logger.info("slack_service_closed")
