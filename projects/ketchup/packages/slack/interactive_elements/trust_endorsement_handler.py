"""
trust_endorsement_handler.py

Handles trust endorsement interactions for Ketchup's automated status updates.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import aiohttp

from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class TrustEndorsementHandler:
    """Handles trust endorsement actions on status updates."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        db_store: DynamoDBStore,
        secrets_manager,
    ):
        """
        Initialize the trust endorsement handler.

        Args:
            posting_handler: Slack posting handler for message updates
            db_store: DynamoDB store for trust data persistence
            secrets_manager: Secrets manager for API tokens
        """
        self.posting_handler = posting_handler
        self.db_store = db_store
        self.secrets_manager = secrets_manager
        self._rate_limit_cache = {}  # Simple in-memory rate limiting

    async def process_trust_action(self, payload: Dict[str, Any]) -> bool:
        """
        Process a trust endorsement action from a button click.

        Args:
            payload: The Slack interactive payload

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if trust feature is enabled
            if not FeatureFlags.is_trust_endorsement_enabled():
                logger.warning("Trust endorsement button clicked but feature is disabled")
                return False

            # Extract required data from payload
            user = payload.get("user", {})
            user_id = user.get("id")
            user_name = user.get("name", user_id)

            actions = payload.get("actions", [])
            if not actions:
                logger.error("No actions found in trust action payload")
                return False
            action = actions[0]
            status_update_id = action.get("value")

            channel = payload.get("channel", {})
            channel_id = channel.get("id")

            message = payload.get("message", {})
            message_ts = message.get("ts")

            # Validate inputs
            if not all([user_id, status_update_id, channel_id, message_ts]):
                logger.error("Missing required data in trust action payload")
                return False

            # Check rate limiting
            if not self._check_rate_limit(user_id):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                # Don't show error to user, just ignore
                return True

            # Add trust endorsement
            trust_data = await self._add_trust_endorsement(
                channel_id=channel_id,
                status_update_id=status_update_id,
                user_id=user_id,
                user_name=user_name,
            )

            if not trust_data:
                logger.error(f"Failed to add trust for {status_update_id}")
                return False

            # Check if user already trusted
            user_already_trusted = trust_data.get("user_already_trusted", False)

            if user_already_trusted:
                # User already trusted - do nothing, no update needed
                logger.info(f"User {user_id} already trusted this update, skipping message update")
                return True

            # Get updated trust display for new trust
            display_data = self._format_trust_display(trust_data.get("trusted_by", []))

            # Update the message with new trust count
            await self._update_message_with_trust(
                channel_id=channel_id,
                message_ts=message_ts,
                message_blocks=message.get("blocks", []),
                trust_display=display_data["display"],
                show_button=True,  # Keep button visible for other users
            )

            logger.info(
                f"User {user_id} trusted status update {status_update_id}. "
                f"Total trust count: {trust_data.get('trust_count', 0)}"
            )

            return True

        except Exception as e:
            logger.error(f"Error processing trust action: {e}", exc_info=True)
            return False

    async def process_command_trust_action(self, payload: Dict[str, Any]) -> bool:
        """
        Process a trust endorsement action for a command.

        Args:
            payload: The Slack interactive payload

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if trust feature is enabled
            if not FeatureFlags.is_trust_endorsement_enabled():
                logger.warning("Trust endorsement button clicked but feature is disabled")
                return False

            # Extract required data from payload
            user = payload.get("user", {})
            user_id = user.get("id")
            user_name = user.get("name", user_id)

            action = payload.get("actions", [])[0]
            command_execution_id = action.get("value")

            channel = payload.get("channel", {})
            channel_id = channel.get("id")
            channel_name = channel.get("name", "unknown")

            logger.info(
                f"Trust button clicked by {user_id} for command {command_execution_id} in channel {channel_id} ({channel_name})"
            )

            # Validate inputs
            if not all([user_id, command_execution_id, channel_id]):
                logger.error("Missing required data in command trust action payload")
                logger.error(
                    f"Missing: user_id={bool(user_id)}, command_execution_id={bool(command_execution_id)}, channel_id={bool(channel_id)}"
                )
                return False

            # Check rate limiting
            if not self._check_rate_limit(user_id):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                # Don't show error to user, just ignore
                return True

            # Try to extract channel from command execution ID context first
            # Check if we can find the original channel from the button value format
            actual_channel_id = None

            # Try direct lookup using the command execution ID format
            # Commands are stored as CHANNEL#{channel_id}/COMMAND#{timestamp}#{uuid}
            timestamp, uuid_part = command_execution_id.split("_")

            # Attempt direct lookup by trying the current channel first
            # This works for buttons clicked in the same channel where command was run
            try:
                response = await self.db_store.client.get_item(
                    table_name=self.db_store.table_name,
                    key={
                        "PK": {"S": f"CHANNEL#{channel_id}"},
                        "SK": {"S": f"COMMAND#{timestamp}#{uuid_part}"},
                    },
                )
                if "Item" in response:
                    actual_channel_id = channel_id
                    logger.info(
                        f"Found command execution in current channel: {channel_id} (DM: {channel_id.startswith('D')})"
                    )
                else:
                    logger.info(f"Direct lookup in channel {channel_id} found no item")
            except Exception as e:
                logger.info(f"Direct lookup in current channel failed: {e}")

            # If direct lookup failed, fall back to scanning across all channels
            if not actual_channel_id:
                logger.info(
                    f"Direct lookup failed for channel {channel_id}, scanning for command execution {command_execution_id}"
                )
                actual_channel_id = await self._find_command_execution_channel(command_execution_id)

            if not actual_channel_id:
                logger.error(f"Could not find channel for command execution {command_execution_id}")
                return False

            # Add command trust endorsement using the actual channel
            trust_data = await self._add_command_trust_endorsement(
                channel_id=actual_channel_id,
                command_execution_id=command_execution_id,
                user_id=user_id,
                user_name=user_name,
            )

            if not trust_data:
                logger.error(f"Failed to add trust for command {command_execution_id}")
                return False

            # Check if user already trusted
            user_already_trusted = trust_data.get("user_already_trusted", False)

            # Show acknowledgment modal
            trigger_id = payload.get("trigger_id")
            if trigger_id:
                await self._show_trust_acknowledgment_modal(
                    trigger_id=trigger_id, already_trusted=user_already_trusted
                )
            else:
                logger.warning("No trigger_id found for trust acknowledgment modal")

            if user_already_trusted:
                logger.info(f"User {user_id} already trusted this command")
            else:
                logger.info(
                    f"User {user_id} trusted command {command_execution_id}. "
                    f"Total trust count: {trust_data.get('trust_count', 0)}"
                )

            return True

        except Exception as e:
            logger.error(f"Error processing command trust action: {e}", exc_info=True)
            return False

    async def _find_command_execution_channel(self, command_execution_id: str) -> str:
        """Find the channel where a command execution was stored."""
        try:
            # Extract timestamp and uuid from command_execution_id
            timestamp, uuid_part = command_execution_id.split("_")
            sk_value = f"COMMAND#{timestamp}#{uuid_part}"

            logger.info(
                f"Searching for command execution {command_execution_id} with SK: {sk_value}"
            )

            # Use DynamoDB scan to find the command execution across all channels
            # This is not ideal for performance but necessary for this lookup
            items = []
            try:
                # Try using the wrapper's scan method first
                scan_kwargs: dict = {
                    "table_name": self.db_store.table_name,
                    "filter_expression": "SK = :sk",
                    "expression_attribute_values": {":sk": sk_value},
                }
                while True:
                    response = await self.db_store.client.scan(**scan_kwargs)
                    items.extend(response.get("Items", []))
                    if items:
                        break
                    last_key = response.get("LastEvaluatedKey")
                    if not last_key:
                        break
                    scan_kwargs["exclusive_start_key"] = last_key
                logger.info(f"Using wrapper scan method, response type: {type(response)}")
            except Exception as wrapper_error:
                logger.warning(f"Wrapper scan failed, trying direct client: {wrapper_error}")
                # Fallback to direct boto3 client
                underlying_client = await self.db_store.client._get_client()
                items = []
                boto_kwargs: dict = {
                    "TableName": self.db_store.table_name,
                    "FilterExpression": "SK = :sk",
                    "ExpressionAttributeValues": {":sk": {"S": sk_value}},
                    "ProjectionExpression": "PK, channel_id",
                }
                while True:
                    response = await underlying_client.scan(**boto_kwargs)
                    items.extend(response.get("Items", []))
                    if items:
                        break
                    last_key = response.get("LastEvaluatedKey")
                    if not last_key:
                        break
                    boto_kwargs["ExclusiveStartKey"] = last_key
                logger.info("Using direct boto3 client scan")
            count = response.get("Count", 0)
            logger.info(f"DynamoDB scan response: {count} items found")

            if items:
                # Extract channel_id from the first match
                item = items[0]
                logger.info(f"Found item: {item}")

                # Handle both wrapper format (plain values) and boto3 format (typed values)
                if isinstance(item.get("channel_id"), dict):
                    # boto3 format: {"S": "value"}
                    channel_id = item.get("channel_id", {}).get("S")
                    pk = item.get("PK", {}).get("S", "")
                else:
                    # wrapper format: plain values
                    channel_id = item.get("channel_id")
                    pk = item.get("PK", "")

                if channel_id:
                    logger.info(f"Found channel_id from item: {channel_id}")
                    return channel_id

                # Fallback: extract from PK format CHANNEL#channel_id
                if pk and pk.startswith("CHANNEL#"):
                    extracted_channel = pk[8:]  # Remove "CHANNEL#" prefix
                    logger.info(f"Extracted channel_id from PK: {extracted_channel}")
                    return extracted_channel

            logger.warning(f"No command execution record found for {command_execution_id}")
            return None

        except Exception as e:
            logger.error(f"Error finding command execution channel: {e}", exc_info=True)
            return None

    async def _add_command_trust_endorsement(
        self, channel_id: str, command_execution_id: str, user_id: str, user_name: str
    ) -> Dict[str, Any]:
        """Add a trust endorsement to a command execution."""
        try:
            # Use trust operations to add endorsement
            trust_data = await self.db_store.trust_ops.add_command_trust_endorsement(
                channel_id=channel_id,
                command_execution_id=command_execution_id,
                user_id=user_id,
                user_name=user_name,
            )

            return trust_data

        except Exception as e:
            logger.error(f"Error adding command trust endorsement: {e}")
            return None

    def _check_rate_limit(self, user_id: str, max_per_minute: int = 10) -> bool:
        """Simple rate limiting check."""
        now = datetime.now(timezone.utc).timestamp()
        minute_key = int(now // 60)

        user_key = f"{user_id}_{minute_key}"
        count = self._rate_limit_cache.get(user_key, 0)

        if count >= max_per_minute:
            return False

        self._rate_limit_cache[user_key] = count + 1

        # Clean old entries (older than 5 minutes)
        cutoff = minute_key - 5
        old_keys = [k for k in self._rate_limit_cache if int(k.split("_")[1]) < cutoff]
        for k in old_keys:
            del self._rate_limit_cache[k]

        return True

    async def _add_trust_endorsement(
        self, channel_id: str, status_update_id: str, user_id: str, user_name: str
    ) -> Dict[str, Any]:
        """Add a trust endorsement to a status update."""
        try:
            # Use trust operations to add endorsement
            trust_data = await self.db_store.trust_ops.add_trust_endorsement(
                channel_id=channel_id,
                status_update_id=status_update_id,
                user_id=user_id,
                user_name=user_name,
            )

            return trust_data

        except Exception as e:
            logger.error(f"Error adding trust endorsement: {e}")
            return None

    def _format_trust_display(self, trusted_by: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format trust data for display."""
        if not trusted_by:
            return {"display": "", "user_already_trusted": False}

        # Sort by trust time (most recent first)
        trusted_by_sorted = sorted(trusted_by, key=lambda x: x.get("trusted_at", 0), reverse=True)

        # Format for display
        if len(trusted_by_sorted) <= 3:
            names = [f"<@{t['user_id']}>" for t in trusted_by_sorted]
            display = f"✓ Trusted by: {', '.join(names)}"
        else:
            first_three = [f"<@{t['user_id']}>" for t in trusted_by_sorted[:3]]
            remaining = len(trusted_by_sorted) - 3
            display = f"✓ Trusted by: {', '.join(first_three)}, +{remaining}"

        return {
            "display": display,
            "count": len(trusted_by),
            "users": trusted_by_sorted,
            "user_already_trusted": False,
        }

    async def _update_message_with_trust(
        self,
        channel_id: str,
        message_ts: str,
        message_blocks: List[Dict[str, Any]],
        trust_display: str,
        show_button: bool = True,
    ) -> None:
        """Update the Slack message with new trust data."""
        try:
            # Update the blocks
            updated_blocks = []
            trust_block_added = False

            for block in message_blocks:
                # Check if this is an existing trust display block
                if block.get("type") == "section" and block.get("text", {}).get(
                    "text", ""
                ).startswith("✓ Trusted by:"):
                    # Replace with updated trust display if we have one
                    if trust_display and not trust_block_added:
                        updated_blocks.append(
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": trust_display},
                            }
                        )
                        trust_block_added = True
                    # Skip the old trust block (don't add it)
                    continue

                # Keep other content blocks
                elif block.get("type") == "section":
                    updated_blocks.append(block)

                # Handle actions block
                elif block.get("type") == "actions":
                    # Add trust display before actions if not already added
                    if trust_display and not trust_block_added:
                        updated_blocks.append(
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": trust_display},
                            }
                        )
                        trust_block_added = True

                    # Keep button if user hasn't trusted yet
                    if show_button:
                        updated_blocks.append(block)

                # Keep any other block types (dividers, etc.)
                else:
                    updated_blocks.append(block)

            # Update the message
            await self.posting_handler.update_message(
                channel_id=channel_id,
                ts=message_ts,
                message="",  # Empty text, blocks contain the content
                blocks=updated_blocks,
            )

        except Exception as e:
            logger.error(f"Error updating message with trust: {e}")

    async def _show_trust_acknowledgment_modal(
        self, trigger_id: str, already_trusted: bool
    ) -> bool:
        """Show a modal to acknowledge trust action for commands."""
        try:
            # Prepare modal content based on trust status
            if already_trusted:
                title = "Already Trusted"
                icon = "ℹ️"
                main_text = "You've already trusted this summary"
                context_text = "Thank you for your previous feedback."
            else:
                title = "Trust Recorded"
                icon = "✅"
                main_text = "Thank you for trusting this summary!"
                context_text = "Your trust helps improve our AI summaries."

            modal_view = {
                "type": "modal",
                "callback_id": "trust_acknowledgment_modal",
                "title": {"type": "plain_text", "text": title},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"{icon} *{main_text}*"},
                    },
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": context_text}],
                    },
                ],
            }

            # Get Slack API token
            slack_api_token = await self.secrets_manager.get_slack_api_token_async()

            # Make direct API call to open modal
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            api_payload = {"trigger_id": trigger_id, "view": modal_view}

            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=api_payload) as response:
                    logger.info(f"Trust acknowledgment modal response status: {response.status}")
                    response_data = await response.json()

                    if not response_data.get("ok"):
                        logger.error(
                            f"Failed to open trust acknowledgment modal: {response_data.get('error')}"
                        )
                        return False
                    else:
                        logger.info(
                            f"Trust acknowledgment modal opened successfully (already_trusted={already_trusted})"
                        )
                        return True

        except Exception as e:
            logger.error(f"Error opening trust acknowledgment modal: {e}")
            return False
