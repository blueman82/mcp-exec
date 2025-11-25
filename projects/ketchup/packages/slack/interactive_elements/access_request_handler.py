"""
access_request_handler.py

Handle access request interactive elements.
"""

import json
import time
from typing import Any, Dict, List, Optional

from packages.core.constants import ACCESS_REQUEST_CHANNEL, ACCESS_REQUEST_STATUS
from packages.core.distributed_lock import DistributedLock
from packages.core.logging import setup_logger
from packages.db.models.access_request import AccessRequest
from packages.db.operations.access_request_operations import AccessRequestOperations
from packages.secrets.manager import SecretsManager
from packages.slack.blockkits.handlers.access_request_blocks import AccessRequestBlocks
from packages.slack.metrics.access_request_monitor import AccessRequestMonitor

logger = setup_logger(__name__)


class AccessRequestHandler:
    """Handle access request interactive elements."""

    def __init__(
        self,
        slack_client,
        access_request_ops: AccessRequestOperations,
        secrets_manager: SecretsManager,
        metrics_service: AccessRequestMonitor,
        distributed_lock: DistributedLock,
    ):
        """
        Initialize the access request handler.

        Args:
            slack_client: Slack client for API calls
            access_request_ops: Access request database operations
            secrets_manager: Secrets manager for updating user lists
            metrics_service: Local metrics service
            distributed_lock: Distributed lock for preventing race conditions
        """
        self.slack_client = slack_client
        self.access_request_ops = access_request_ops
        self.secrets_manager = secrets_manager
        self.metrics = metrics_service
        self.distributed_lock = distributed_lock
        self.blocks = AccessRequestBlocks()

    async def handle_request_access(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the initial access request button click.

        Args:
            payload: The Slack interactive payload

        Returns:
            Response for Slack
        """
        try:
            user = payload.get("user", {})
            user_id = user.get("id")
            user_name = user.get("name", user_id)

            # Get user email from Slack profile using GET request
            try:
                # Use direct GET request since users.info requires params, not JSON body
                url = f"{await self.slack_client.get_api_base_url()}/users.info"
                headers = self.slack_client.headers
                params = {"user": user_id}

                response = await self.slack_client._make_api_request(
                    url, "GET", headers, params=params
                )

                # Parse the response body
                response_data = json.loads(response["body"])

                if response_data.get("ok"):
                    user_email = (
                        response_data.get("user", {})
                        .get("profile", {})
                        .get("email", f"{user_name}@adobe.com")
                    )
                else:
                    logger.error(
                        f"Failed to get user profile: {response_data.get('error', 'Unknown error')}"
                    )
                    user_email = f"{user_name}@adobe.com"
            except Exception as e:
                logger.error(f"Error getting user email: {e}")
                user_email = f"{user_name}@adobe.com"

            # Create access request
            request = AccessRequest(
                user_id=user_id,
                user_name=user_name,
                user_email=user_email,
                request_timestamp=time.time(),
                status=ACCESS_REQUEST_STATUS["PENDING"],
            )

            success, message, created_request = (
                await self.access_request_ops.create_request_with_validation(request)
            )

            if not success:
                # Show error message
                await self.metrics.increment_metric(
                    (
                        "rate_limited"
                        if "too many requests" in message.lower()
                        else "duplicate"
                    ),
                    user_id=user_id,
                )

                return {"response_type": "ephemeral", "text": message}

            # Post notification to access request channel
            blocks = self.blocks.build_access_request_notification(
                user_id=user_id,
                user_name=user_name,
                user_email=user_email,
                reason=None,  # Could add a modal to collect this
                request_time=created_request.request_timestamp,
            )

            # Post to access request channel
            msg_response = await self.slack_client.api_call(
                "chat.postMessage",
                {
                    "channel": ACCESS_REQUEST_CHANNEL,
                    "blocks": blocks,
                    "text": f"New access request from {user_name}",
                },
            )

            if msg_response.get("ok"):
                # Update request with message timestamp
                created_request.channel_ts = msg_response["ts"]
                await self.access_request_ops.client.update_item(
                    key={
                        "PK": {"S": f"USER#{user_id}"},
                        "SK": {
                            "S": f"ACCESS_REQUEST#{created_request.request_timestamp}"
                        },
                    },
                    update_expression="SET channel_ts = :ts",
                    expression_attribute_values={":ts": {"S": msg_response["ts"]}},
                    table_name=self.access_request_ops.table_name,
                )

            # Emit metric
            await self.metrics.increment_metric(
                "created", user_id=user_id, user_name=user_name
            )

            return {
                "response_type": "ephemeral",
                "text": "✅ Your access request has been submitted! You'll receive a DM when it's processed.",
            }

        except Exception as e:
            logger.error(f"Error handling access request: {e}", exc_info=True)
            await self.metrics.increment_metric("error", user_id=user_id, error=str(e))

            return {
                "response_type": "ephemeral",
                "text": "❌ An error occurred while processing your request. Please try again or contact support.",
            }

    async def handle_approve_access(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the approve button click.

        Args:
            payload: The Slack interactive payload

        Returns:
            Response for Slack
        """
        try:
            approver = payload.get("user", {})
            approver_id = approver.get("id")
            approver_name = approver.get("name", approver_id)

            action = payload.get("actions", [])[0]
            value_parts = action.get("value", "").split("|")
            if len(value_parts) != 2:
                return {"response_type": "ephemeral", "text": "❌ Invalid request data"}

            user_id, request_timestamp = value_parts[0], float(value_parts[1])

            # Use distributed lock to prevent race conditions
            lock_key = f"ACCESS_REQUEST#{user_id}#{request_timestamp}"

            async with self.distributed_lock.acquire_lock(lock_key) as lock_acquired:
                if not lock_acquired:
                    return {
                        "response_type": "ephemeral",
                        "text": "⏳ Another approver is processing this request. Please wait.",
                    }

                # Update request with approval
                success, message = (
                    await self.access_request_ops.update_request_decision(
                        user_id=user_id,
                        request_timestamp=request_timestamp,
                        decision=ACCESS_REQUEST_STATUS["APPROVED"],
                        decided_by_id=approver_id,
                        decided_by_name=approver_name,
                    )
                )

                if not success:
                    return {"response_type": "ephemeral", "text": message}

                # Update user's authorization
                await self._add_user_to_authorized_list(user_id)

                # Update the original message
                channel = payload.get("channel", {})
                channel_id = channel.get("id")
                message_ts = payload.get("message", {}).get("ts")

                await self._update_request_message(
                    channel=channel_id,
                    ts=message_ts,
                    blocks=payload.get("message", {}).get("blocks", []),
                    approver_id=approver_id,
                    decision="approved",
                    decision_time=time.time(),
                )

                # Send approval DM to user
                await self._send_approval_dm(user_id)

                # Emit metric
                await self.metrics.increment_metric(
                    "approved", user_id=user_id, approver_id=approver_id
                )

                return {
                    "response_type": "ephemeral",
                    "text": f"✅ Access approved for <@{user_id}>",
                }

        except Exception as e:
            logger.error(f"Error handling approval: {e}", exc_info=True)
            return {
                "response_type": "ephemeral",
                "text": "❌ Error processing approval. Please try again.",
            }

    async def handle_reject_access(self, payload: Dict[str, Any]):
        """
        Handle the reject button click - opens a modal.

        Args:
            payload: The Slack interactive payload
        """
        try:
            action = payload.get("actions", [])[0]

            # Store data in private metadata for the modal
            private_metadata = {
                "user_id": action["value"].split("|")[0],
                "request_timestamp": action["value"].split("|")[1],
                "original_blocks": payload["message"]["blocks"],
                "channel_ts": payload["message"]["ts"],
            }

            modal = self.blocks.build_rejection_modal()
            modal["private_metadata"] = json.dumps(private_metadata)

            await self.slack_client.api_call(
                "views.open", {"trigger_id": payload["trigger_id"], "view": modal}
            )

        except Exception as e:
            logger.error(f"Error opening rejection modal: {e}")

    async def handle_rejection_submission(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle the rejection modal submission."""
        try:
            rejector = payload["user"]
            view = payload["view"]

            # Get rejection reason
            reason = view["state"]["values"]["reason_block"]["reason_input"]["value"]

            # Parse private metadata
            metadata = json.loads(view["private_metadata"])
            user_id = metadata["user_id"]
            request_timestamp = float(metadata["request_timestamp"])

            # Update request with rejection
            success, message = await self.access_request_ops.update_request_decision(
                user_id=user_id,
                request_timestamp=request_timestamp,
                decision=ACCESS_REQUEST_STATUS["REJECTED"],
                decided_by_id=rejector["id"],
                decided_by_name=rejector["name"],
                rejection_reason=reason,
            )

            if not success:
                return {"response_type": "ephemeral", "text": message}

            # Update the original message
            await self._update_request_message(
                channel=ACCESS_REQUEST_CHANNEL,
                ts=metadata["channel_ts"],
                blocks=metadata["original_blocks"],
                approver_id=rejector["id"],
                decision="rejected",
                decision_time=time.time(),
                rejection_reason=reason,
            )

            # Send rejection notification to user's DM
            await self._send_rejection_dm(user_id, reason)

            # Emit metric
            await self.metrics.increment_metric(
                "rejected", user_id=user_id, rejector_id=rejector["id"]
            )

            return {"response_type": "clear"}

        except Exception as e:
            logger.error(f"Error handling rejection: {e}")
            return {
                "response_type": "ephemeral",
                "text": "❌ Error processing rejection. Please try again.",
            }

    async def _update_request_message(
        self,
        channel: str,
        ts: str,
        blocks: List[Dict[str, Any]],
        approver_id: str,
        decision: str,
        decision_time: float,
        rejection_reason: Optional[str] = None,
    ):
        """Update the original request message after decision."""
        try:
            updated_blocks = self.blocks.build_request_processed_blocks(
                original_blocks=blocks,
                processed_by=approver_id,
                decision=decision,
                decision_time=decision_time,
                rejection_reason=rejection_reason,
            )

            await self.slack_client.api_call(
                "chat.update", {"channel": channel, "ts": ts, "blocks": updated_blocks}
            )
        except Exception as e:
            logger.error(f"Error updating request message: {e}")

    async def _send_approval_dm(self, user_id: str):
        """Send approval DM to user."""
        try:
            # Open DM channel
            dm_response = await self.slack_client.api_call(
                "conversations.open", {"users": [user_id]}
            )
            if not dm_response.get("ok"):
                logger.error(f"Failed to open DM with {user_id}")
                return

            dm_channel = dm_response["channel"]["id"]

            # Send approval message with full Ketchup introduction
            blocks = self.blocks.build_approval_dm(user_id)

            await self.slack_client.api_call(
                "chat.postMessage",
                {
                    "channel": dm_channel,
                    "blocks": blocks,
                    "text": ":wave: Welcome to Ketchup 1.0!",
                },
            )

        except Exception as e:
            logger.error(f"Error sending approval DM: {e}")

    async def _send_rejection_dm(self, user_id: str, reason: str):
        """Send rejection DM to user."""
        try:
            # Open DM channel
            dm_response = await self.slack_client.api_call(
                "conversations.open", {"users": [user_id]}
            )
            if not dm_response.get("ok"):
                logger.error(f"Failed to open DM with {user_id}")
                return

            dm_channel = dm_response["channel"]["id"]

            # Send rejection message
            await self.slack_client.api_call(
                "chat.postMessage",
                {
                    "channel": dm_channel,
                    "text": f"❌ Your Ketchup access request was rejected.\n\n*Reason:* {reason}\n\nIf you have questions, please contact the team org-omeara-all@adobe.com.",
                },
            )

        except Exception as e:
            logger.error(f"Error sending rejection DM: {e}")

    async def _add_user_to_authorized_list(self, user_id: str):
        """Add user to the authorized users list."""
        try:
            # Fetch user's email from Slack to extract LDAP username using GET request
            ldap_username = None
            try:
                # Use direct GET request since users.info requires params, not JSON body
                url = f"{await self.slack_client.get_api_base_url()}/users.info"
                headers = self.slack_client.headers
                params = {"user": user_id}

                response = await self.slack_client._make_api_request(
                    url, "GET", headers, params=params
                )

                # Parse the response body
                response_data = json.loads(response["body"])

                if response_data.get("ok"):
                    user_email = (
                        response_data.get("user", {})
                        .get("profile", {})
                        .get("email", "")
                    )
                    if user_email and "@adobe.com" in user_email:
                        # Extract LDAP username (part before @adobe.com)
                        ldap_username = user_email.split("@adobe.com")[0]
                        logger.info(
                            f"Extracted LDAP username '{ldap_username}' from email '{user_email}'"
                        )
                    else:
                        logger.warning(
                            f"Could not extract LDAP from email: {user_email}"
                        )
                else:
                    logger.error(
                        f"Failed to fetch user profile for {user_id}: {response_data.get('error')}"
                    )
            except Exception as e:
                logger.error(f"Error fetching user profile for LDAP extraction: {e}")

            # Add user to authorized list with LDAP if available
            if ldap_username:
                added = await self.secrets_manager.add_authorized_user_with_ldap(
                    user_id, ldap_username
                )
                if added:
                    logger.info(
                        f"User {user_id} (ldap: {ldap_username}) successfully added to authorized lists"
                    )
                else:
                    logger.info(
                        f"User {user_id} (ldap: {ldap_username}) was already in authorized lists"
                    )
            else:
                # Fallback to adding just Slack ID if LDAP extraction failed
                logger.warning(
                    f"LDAP extraction failed for {user_id}, adding Slack ID only"
                )
                added = await self.secrets_manager.add_authorized_user(user_id)
                if added:
                    logger.info(
                        f"User {user_id} successfully added to authorized users list (Slack ID only)"
                    )
                else:
                    logger.info(f"User {user_id} was already in authorized users list")

        except Exception as e:
            logger.error(f"Error adding user to authorized list: {e}")
            # Continue processing even if we can't update the list
            # The approval is still recorded in the database
