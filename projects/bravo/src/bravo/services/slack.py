"""Slack Socket Mode client service.

This module provides async Slack integration using Socket Mode for
receiving events and the Web API for sending messages.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web.async_client import AsyncWebClient

from bravo.config import SlackSettings
from bravo.db import queries
from bravo.services.blocks import (
    build_acknowledged_blocks,
    build_snoozed_blocks,
    build_unsnoozed_blocks,
    build_yes_updates_blocks,
)

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
        blocks: list[dict[str, Any]] | None = None,
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
            ts: str = response["ts"]
            logger.info("slack_dm_sent", user_id=user_id, ts=ts)
            return ts

        logger.error("slack_dm_failed", user_id=user_id, error=response.get("error"))
        return None

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Update an existing Slack message in-place.

        Args:
            channel: The channel containing the message.
            ts: The message timestamp to update.
            text: Updated fallback text.
            blocks: Optional updated Block Kit blocks.

        Returns:
            True if the update succeeded, False otherwise.
        """
        client = self._get_web_client()
        try:
            response = await client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks,
            )
            ok = bool(response["ok"])
            if not ok:
                logger.error(
                    "slack_message_update_not_ok",
                    channel=channel,
                    ts=ts,
                    error=response.get("error"),
                )
            return ok
        except Exception:
            logger.exception("slack_message_update_failed", channel=channel, ts=ts)
            return False

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

        self._socket_client.socket_mode_request_listeners.append(_listener)  # type: ignore[arg-type]

        await self._socket_client.connect()  # type: ignore[no-untyped-call]
        logger.info("socket_mode_connected")

        while True:
            await asyncio.sleep(1)

    async def _handle_block_action(
        self,
        payload: dict[str, Any],
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle interactive block action events (button clicks).

        Args:
            payload: The interaction payload from Slack.
            client: The Socket Mode client for acknowledgement.
            req: The original Socket Mode request.
        """
        # ACK immediately to satisfy Slack's 3-second deadline
        await client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id),
        )

        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id", "")
            logger.info("block_action_received", action_id=action_id)

            try:
                if action_id == "nudge_yes_updates":
                    await self._handle_nudge_yes_updates(payload, action)
                elif action_id == "nudge_no_updates":
                    await self._handle_nudge_no_updates(payload, action)
                elif action_id in ("nudge_snooze_1h", "nudge_snooze_4h"):
                    await self._handle_nudge_snooze(payload, action)
                elif action_id == "nudge_unsnooze":
                    await self._handle_nudge_unsnooze(payload, action)
                else:
                    logger.warning("unhandled_action_id", action_id=action_id)
            except Exception:
                logger.exception("block_action_handler_error", action_id=action_id)

    @staticmethod
    def _msg_context(payload: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
        """Extract channel, ts, and blocks from an interaction payload."""
        return (
            payload["channel"]["id"],
            payload["message"]["ts"],
            payload["message"].get("blocks", []),
        )

    async def _handle_nudge_yes_updates(
        self, payload: dict[str, Any], action: dict[str, Any]
    ) -> None:
        """Handle 'Yes, updates coming' button click.

        Args:
            payload: The interaction payload from Slack.
            action: The specific action that was triggered.
        """
        channel_id, message_ts, original_blocks = self._msg_context(payload)

        nudge = await queries.get_nudge_by_slack_ts(message_ts)
        if not nudge:
            logger.warning("nudge_not_found_for_ts", ts=message_ts)
            return

        await queries.update_nudge_status(nudge["id"], "RESPONDED")
        await self.update_message(
            channel=channel_id,
            ts=message_ts,
            text="Updates incoming",
            blocks=build_yes_updates_blocks(original_blocks=original_blocks),
        )

    async def _handle_nudge_no_updates(
        self, payload: dict[str, Any], action: dict[str, Any]
    ) -> None:
        """Handle 'No updates needed' button click.

        Args:
            payload: The interaction payload from Slack.
            action: The specific action that was triggered.
        """
        channel_id, message_ts, original_blocks = self._msg_context(payload)

        nudge = await queries.get_nudge_by_slack_ts(message_ts)
        if not nudge:
            logger.warning("nudge_not_found_for_ts", ts=message_ts)
            return

        await queries.update_nudge_status(nudge["id"], "ACKNOWLEDGED")
        await self.update_message(
            channel=channel_id,
            ts=message_ts,
            text="Acknowledged",
            blocks=build_acknowledged_blocks(original_blocks=original_blocks),
        )

    async def _handle_nudge_snooze(
        self, payload: dict[str, Any], action: dict[str, Any]
    ) -> None:
        """Handle snooze button click (1h or 4h).

        Args:
            payload: The interaction payload from Slack.
            action: The specific action that was triggered.
        """
        channel_id, message_ts, original_blocks = self._msg_context(payload)

        # Parse ticket_key and duration from value (e.g. "BRAVO-123|1h")
        value = action.get("value", "")
        parts = value.split("|", 1)
        ticket_key = parts[0]
        duration = parts[1] if len(parts) > 1 else "1h"

        nudge = await queries.get_nudge_by_slack_ts(message_ts)
        if not nudge:
            logger.warning("nudge_not_found_for_ts", ts=message_ts)
            return

        snoozed_until = datetime.now(UTC) + timedelta(
            hours=4 if duration == "4h" else 1
        )
        snoozed_until_text = snoozed_until.strftime("%H:%M UTC")

        await queries.update_nudge_snooze(nudge["id"], snoozed_until)
        await self.update_message(
            channel=channel_id,
            ts=message_ts,
            text=f"Snoozed until {snoozed_until_text}",
            blocks=build_snoozed_blocks(
                original_blocks=original_blocks,
                snoozed_until_text=snoozed_until_text,
                ticket_key=ticket_key,
            ),
        )

    async def _handle_nudge_unsnooze(
        self, payload: dict[str, Any], action: dict[str, Any]
    ) -> None:
        """Handle unsnooze button click.

        Args:
            payload: The interaction payload from Slack.
            action: The specific action that was triggered.
        """
        channel_id, message_ts, original_blocks = self._msg_context(payload)
        ticket_key = action.get("value", "")

        # Snoozed nudges have status='SNOOZED', not 'SENT'
        nudge = await queries.get_snoozed_nudge_by_slack_ts(message_ts)
        if not nudge:
            logger.warning("nudge_not_found_for_unsnooze", ts=message_ts)
            return

        await queries.clear_nudge_snooze(nudge["id"])
        await self.update_message(
            channel=channel_id,
            ts=message_ts,
            text="Nudge restored",
            blocks=build_unsnoozed_blocks(
                original_blocks=original_blocks,
                ticket_key=ticket_key,
            ),
        )

    async def _handle_view_submission(
        self,
        payload: dict[str, Any],
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
        payload: dict[str, Any],
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
        event: dict[str, Any],
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
            await self._socket_client.close()  # type: ignore[no-untyped-call]
            self._socket_client = None
        logger.info("slack_service_closed")
