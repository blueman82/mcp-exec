"""Slack Socket Mode client service.

This module provides async Slack integration using Socket Mode for
receiving events and the Web API for sending messages.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web.async_client import AsyncWebClient

from bravo.config import SlackSettings
from bravo.db import queries
from bravo.protocols import JiraClientProto, PATServiceProto
from bravo.services.blocks import (
    _replace_actions,
    build_acknowledged_blocks,
    build_collect_pat_modal,
    build_comment_modal,
    build_fix_error_blocks,
    build_fix_now_modal,
    build_fix_submitted_blocks,
    build_pat_error_modal,
    build_snoozed_blocks,
    build_unsnoozed_blocks,
    build_yes_updates_blocks,
)
from bravo.services.jira import JiraMCPError

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

    def __init__(
        self,
        settings: SlackSettings,
        jira: JiraClientProto,
        pat_service: PATServiceProto | None = None,
    ) -> None:
        """Initialize the Slack service.

        Args:
            settings: Slack API configuration.
            jira: Jira client for on-demand ticket field lookups.
            pat_service: Optional PAT storage for per-user Jira auth.
        """
        self.settings = settings
        self.jira = jira
        self._pat_service = pat_service
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

    async def open_modal(
        self, trigger_id: str, view: dict[str, Any]
    ) -> bool:
        """Open a Slack modal view.

        Args:
            trigger_id: The trigger ID from an interaction payload.
            view: The modal view payload.

        Returns:
            True if the modal was opened successfully, False otherwise.
        """
        client = self._get_web_client()
        try:
            await client.views_open(trigger_id=trigger_id, view=view)
            logger.info("modal_opened", callback_id=view.get("callback_id"))
            return True
        except Exception:
            logger.exception("modal_open_failed", trigger_id=trigger_id)
            return False

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
                if action_id == "nudge_fix_now":
                    await self._handle_nudge_fix_now(payload, action)
                elif action_id == "nudge_yes_updates":
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
        trigger_id = payload.get("trigger_id", "")
        user_id = payload["user"]["id"]
        ticket_key = action.get("value", "")
        channel_id, message_ts, _ = self._msg_context(payload)

        # PAT gate: collect PAT before Jira write
        if self._pat_service and not await self._pat_service.has_pat(user_id):
            modal = build_collect_pat_modal()
            modal["private_metadata"] = json.dumps({
                "original_action": "yes_updates",
                "ticket_key": ticket_key,
                "channel": channel_id,
                "ts": message_ts,
            })
            await self.open_modal(trigger_id, modal)
            return

        # User already has PAT — go straight to comment modal
        comment_view = build_comment_modal(
            ticket_key, "Ready to post your update",
        )
        comment_view["private_metadata"] = json.dumps({
            "ticket_key": ticket_key,
            "channel": channel_id,
            "ts": message_ts,
        })
        await self.open_modal(trigger_id, comment_view)

    async def _complete_yes_updates(
        self, *, user_id: str, ticket_key: str, channel_id: str, message_ts: str,
    ) -> None:
        """Add audit comment, update nudge status, and update Slack message."""
        try:
            await self.jira.add_comment(
                ticket_key,
                "[Bravo] Engineer acknowledged — updates coming",
                slack_user_id=user_id,
            )
        except Exception:
            logger.warning("yes_updates_comment_failed", ticket_key=ticket_key, exc_info=True)

        nudge = await queries.get_nudge_by_slack_ts(message_ts)
        if not nudge:
            logger.warning("nudge_not_found_for_ts", ts=message_ts)
            return

        await queries.update_nudge_status(nudge["id"], "RESPONDED")
        original_blocks = await self._fetch_message_blocks(channel_id, message_ts)
        await self.update_message(
            channel=channel_id, ts=message_ts, text="Updates incoming",
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

    async def _handle_nudge_fix_now(
        self, payload: dict[str, Any], action: dict[str, Any]
    ) -> None:
        """Handle 'Fix now' button click — open modal with missing fields.

        Args:
            payload: The interaction payload from Slack.
            action: The specific action that was triggered.
        """
        trigger_id = payload.get("trigger_id", "")
        ticket_key = action.get("value", "")
        channel_id, message_ts, _ = self._msg_context(payload)
        user_id = payload["user"]["id"]

        current_fields = await self.jira.get_ticket_fields(ticket_key)
        if not current_fields:
            logger.warning("fix_now_ticket_not_found", ticket_key=ticket_key)
            return

        # PAT gate: collect PAT before proceeding to Jira writes
        if self._pat_service and not await self._pat_service.has_pat(user_id):
            modal = build_collect_pat_modal()
            modal["private_metadata"] = json.dumps({
                "original_action": "fix_now",
                "ticket_key": ticket_key,
                "channel": channel_id,
                "ts": message_ts,
                "current_fields": current_fields,
            })
            await self.open_modal(trigger_id, modal)
            return

        modal = build_fix_now_modal(
            ticket_key=ticket_key,
            current_fields=current_fields,
        )

        if not modal["blocks"]:
            logger.info("fix_now_no_missing_fields", ticket_key=ticket_key)
            return

        # Carry message context through to the submission handler
        modal["private_metadata"] = json.dumps({
            "ticket_key": ticket_key,
            "channel": channel_id,
            "ts": message_ts,
        })

        await self.open_modal(trigger_id, modal)

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

        try:
            # PAT modal controls its own ACK (response_action)
            if callback_id == "collect_pat_modal":
                await self._handle_collect_pat_submission(payload, client, req)
                return

            # Comment modal: ACK immediately, spawn background work
            if callback_id == "comment_modal":
                await client.send_socket_mode_response(
                    SocketModeResponse(envelope_id=req.envelope_id),
                )
                asyncio.create_task(self._handle_comment_submission(payload))
                return

            # Default ACK for other submissions
            await client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id),
            )

            if callback_id == "fix_now_modal":
                await self._handle_fix_now_submission(payload)
            else:
                logger.warning("unhandled_view_submission", callback_id=callback_id)
        except Exception:
            logger.exception("view_submission_handler_error", callback_id=callback_id)

    async def _handle_collect_pat_submission(
        self,
        payload: dict[str, Any],
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Process PAT collection modal — validate, store, and continue."""
        user_id = payload["user"]["id"]
        values = payload.get("view", {}).get("state", {}).get("values", {})
        pat_value = (
            values.get("pat_input_block", {}).get("pat_value", {}).get("value", "")
        )
        metadata = json.loads(
            payload.get("view", {}).get("private_metadata", "{}")
        )

        # Strip whitespace, reject empty
        pat_value = pat_value.strip() if pat_value else ""
        if not pat_value:
            await client.send_socket_mode_response(
                SocketModeResponse(
                    envelope_id=req.envelope_id,
                    payload={
                        "response_action": "errors",
                        "errors": {"pat_input_block": "Please enter your Jira PAT"},
                    },
                )
            )
            return

        # Validate PAT before storing — never log the PAT value
        is_valid = await self.jira.test_auth(user_pat=pat_value)
        if not is_valid:
            logger.warning("pat_validation_failed", user_id=user_id)
            error_view = build_pat_error_modal(
                metadata.get("ticket_key", ""),
            )
            # Preserve original metadata so retry continues the flow
            error_view["private_metadata"] = payload.get("view", {}).get(
                "private_metadata", "{}"
            )
            await client.send_socket_mode_response(
                SocketModeResponse(
                    envelope_id=req.envelope_id,
                    payload={"response_action": "update", "view": error_view},
                )
            )
            return

        # PAT is valid — store it
        await self._pat_service.store_pat(user_id, pat_value)
        logger.info("pat_validated_and_stored", user_id=user_id)

        # Continue with the original action
        if metadata.get("original_action") == "fix_now":
            current_fields = metadata.get("current_fields", {})
            next_view = build_fix_now_modal(
                ticket_key=metadata.get("ticket_key", ""),
                current_fields=current_fields,
            )
            next_view["private_metadata"] = json.dumps({
                "ticket_key": metadata.get("ticket_key", ""),
                "channel": metadata.get("channel", ""),
                "ts": metadata.get("ts", ""),
            })

            if next_view["blocks"]:
                await client.send_socket_mode_response(
                    SocketModeResponse(
                        envelope_id=req.envelope_id,
                        payload={"response_action": "update", "view": next_view},
                    )
                )
                return

        if metadata.get("original_action") == "yes_updates":
            # Transition to comment modal in-place
            ticket_key = metadata.get("ticket_key", "")
            comment_view = build_comment_modal(
                ticket_key, "PAT verified \u2014 connected to Jira",
            )
            comment_view["private_metadata"] = json.dumps({
                "ticket_key": ticket_key,
                "channel": metadata.get("channel", ""),
                "ts": metadata.get("ts", ""),
            })
            await client.send_socket_mode_response(
                SocketModeResponse(
                    envelope_id=req.envelope_id,
                    payload={"response_action": "update", "view": comment_view},
                )
            )
            return

        # No missing fields or unknown action — just close
        await client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id),
        )

    async def _handle_comment_submission(self, payload: dict[str, Any]) -> None:
        """Process comment modal submission — post to Jira, enqueue re-eval.

        Runs as a background task (spawned from _handle_view_submission)
        so that the Slack ACK completes within the 3-second deadline.

        Args:
            payload: The view submission payload from Slack.
        """
        metadata = json.loads(
            payload.get("view", {}).get("private_metadata", "{}")
        )
        ticket_key = metadata.get("ticket_key", "")
        channel_id = metadata.get("channel", "")
        message_ts = metadata.get("ts", "")
        user_id = payload.get("user", {}).get("id", "")
        values = payload.get("view", {}).get("state", {}).get("values", {})
        comment_text = (
            values.get("comment_input_block", {})
            .get("comment_value", {})
            .get("value", "")
        )

        if not comment_text or not comment_text.strip():
            logger.warning("comment_submission_empty", ticket_key=ticket_key)
            return

        comment_text = comment_text.strip()

        # Post comment to Jira (critical path)
        try:
            await self.jira.add_comment(
                ticket_key, comment_text, slack_user_id=user_id,
            )
        except Exception:
            logger.exception("comment_jira_post_failed", ticket_key=ticket_key)
            # Update Slack message with error
            original_blocks = await self._fetch_message_blocks(channel_id, message_ts)
            await self.update_message(
                channel=channel_id,
                ts=message_ts,
                text=f"Could not post comment to {ticket_key}",
                blocks=build_fix_error_blocks(
                    original_blocks=original_blocks,
                    ticket_key=ticket_key,
                    error_message=f"Could not post comment to {ticket_key} \u2014 try again",
                ),
            )
            return

        logger.info("comment_posted_to_jira", ticket_key=ticket_key)

        # Update nudge status
        nudge = await queries.get_nudge_by_slack_ts(message_ts)
        if nudge:
            await queries.update_nudge_status(nudge["id"], "RESPONDED")

            # Enqueue re-evaluation (best-effort)
            try:
                await queries.enqueue_re_evaluation(
                    ticket_key=ticket_key,
                    nudge_id=nudge["id"],
                    channel_id=channel_id,
                    message_ts=message_ts,
                )
            except Exception:
                logger.warning(
                    "reeval_enqueue_failed",
                    ticket_key=ticket_key,
                    exc_info=True,
                )

        # Update Slack message: "Comment posted, evaluation in progress"
        original_blocks = await self._fetch_message_blocks(channel_id, message_ts)
        reply_context: dict[str, Any] = {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "\u2705 Comment posted \u2014 re-evaluation in progress",
                },
            ],
        }
        from bravo.services.blocks import _replace_actions
        updated_blocks = _replace_actions(original_blocks, reply_context)
        await self.update_message(
            channel=channel_id,
            ts=message_ts,
            text="Comment posted, evaluation in progress",
            blocks=updated_blocks,
        )

    async def _fetch_message_blocks(
        self, channel: str, ts: str
    ) -> list[dict[str, Any]]:
        """Fetch current Block Kit blocks from an existing Slack message.

        Args:
            channel: The channel containing the message.
            ts: The message timestamp.

        Returns:
            List of block dicts, or empty list on failure.
        """
        client = self._get_web_client()
        try:
            history = await client.conversations_history(
                channel=channel, latest=ts, inclusive=True, limit=1,
            )
            messages = history.get("messages", [])
            if messages:
                return messages[0].get("blocks", [])
        except Exception:
            logger.warning("fetch_message_blocks_failed", channel=channel, ts=ts)
        return []

    async def _handle_fix_now_submission(self, payload: dict[str, Any]) -> None:
        """Process 'Fix now' modal submission — update Jira and nudge message.

        Args:
            payload: The view submission payload from Slack.
        """
        metadata = json.loads(
            payload.get("view", {}).get("private_metadata", "{}")
        )
        ticket_key = metadata.get("ticket_key", "")
        channel_id = metadata.get("channel", "")
        message_ts = metadata.get("ts", "")
        user_id = payload.get("user", {}).get("id", "")
        values = payload.get("view", {}).get("state", {}).get("values", {})

        fields: dict[str, Any] = {}
        fields_updated: list[str] = []

        desc_block = values.get("fix_description", {}).get("description_input", {})
        if desc_value := desc_block.get("value"):
            fields["description"] = desc_value
            fields_updated.append("description")

        pri_block = values.get("fix_priority", {}).get("priority_input", {})
        if selected := pri_block.get("selected_option"):
            fields["priority"] = {"name": selected["value"]}
            fields_updated.append("priority")

        comp_block = values.get("fix_components", {}).get("components_input", {})
        if comp_value := comp_block.get("value"):
            fields["components"] = [
                {"name": c.strip()} for c in comp_value.split(",") if c.strip()
            ]
            fields_updated.append("components")

        if not fields:
            logger.warning("fix_now_no_fields_submitted", ticket_key=ticket_key)
            return

        # Update Jira — on failure, show error with retry buttons
        try:
            await self.jira.update_issue(ticket_key, fields, slack_user_id=user_id)
        except (JiraMCPError, httpx.TimeoutException, httpx.TransportError) as exc:
            logger.error(
                "fix_now_jira_update_failed",
                ticket_key=ticket_key,
                error=str(exc),
            )
            if isinstance(exc, httpx.TimeoutException):
                error_msg = f"Jira update timed out for {ticket_key} \u2014 try again"
            else:
                error_msg = (
                    f"Could not update {ticket_key} \u2014 check field values or try again"
                )
            original_blocks = await self._fetch_message_blocks(channel_id, message_ts)
            await self.update_message(
                channel=channel_id,
                ts=message_ts,
                text=error_msg,
                blocks=build_fix_error_blocks(
                    original_blocks=original_blocks,
                    ticket_key=ticket_key,
                    error_message=error_msg,
                ),
            )
            return

        field_list = ", ".join(fields_updated)

        # Audit comment — partial failure is non-fatal
        comment_failed = False
        try:
            await self.jira.add_comment(
                ticket_key,
                f"[Bravo] Fields updated via Fix now: {field_list}",
                slack_user_id=user_id,
            )
        except Exception:
            logger.warning("fix_now_comment_failed", ticket_key=ticket_key, exc_info=True)
            comment_failed = True

        logger.info(
            "fix_now_jira_updated",
            ticket_key=ticket_key,
            fields=fields_updated,
        )

        # Update nudge status
        nudge = await queries.get_nudge_by_slack_ts(message_ts)
        if nudge:
            await queries.update_nudge_status(nudge["id"], "RESPONDED")

        # Fetch current message blocks for in-place update
        original_blocks = await self._fetch_message_blocks(channel_id, message_ts)

        success_text = f"Fixed: {field_list}"
        if comment_failed:
            success_text += " (audit comment failed)"

        await self.update_message(
            channel=channel_id,
            ts=message_ts,
            text=success_text,
            blocks=build_fix_submitted_blocks(
                original_blocks=original_blocks,
                fields_updated=fields_updated,
            ),
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
