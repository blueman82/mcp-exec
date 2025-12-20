"""
jira_prompt_handler.py

Handler for prompting users for JIRA tickets and processing maintenance checks.
"""

import asyncio
import re
from typing import Dict, Optional

from packages.ai.maintenance_checker import MaintenanceChecker
from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class JiraPromptHandler:
    """
    Handles JIRA ticket prompting for maintenance detection.

    Manages:
    - Posting prompt messages with retry attempts
    - Listening for @Ketchup mentions with JIRA tickets
    - Deleting old prompts when posting new ones
    - Processing maintenance checks after receiving JIRA ticket
    """

    MAX_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 120  # 2 minutes per attempt

    # WORKFLOW TIMEOUT BEHAVIOR:
    # - Each attempt allows 120 seconds (2 minutes) for user to respond
    # - Total workflow timeout: 3 attempts × 120 seconds = 6 minutes max
    # - If user responds AFTER the 120-second window:
    #   1. DynamoDB record has expired and been deleted
    #   2. Event handler detects "late response" (no active prompt found)
    #   3. User receives message: "I didn't catch it within the expected timeframe"
    #   4. Late JIRA ticket is still stored for audit/recovery purposes
    # - Why 120s? Slack message delivery is reliable, but users need time to notice
    #   and respond. 2 minutes balances prompt visibility with retrying efficiently.

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        maintenance_checker: MaintenanceChecker,
        db_store: DynamoDBStore,
        mcp_client,
        channel_msg_ops,
        secrets_manager: SecretsManager,
    ):
        """
        Initialize the JIRA prompt handler.

        Args:
            posting_handler: Slack posting handler
            maintenance_checker: Maintenance checker service
            db_store: DynamoDB store for channel metadata updates
            mcp_client: MCP JIRA client for fetching JIRA tickets
            channel_msg_ops: Channel message operations service
            secrets_manager: Secrets manager for getting bot user ID
        """
        self.posting_handler = posting_handler
        self.maintenance_checker = maintenance_checker
        self.db_store = db_store
        self.mcp_client = mcp_client
        self.channel_msg_ops = channel_msg_ops
        self.secrets_manager = secrets_manager
        self.active_prompts: Dict[str, str] = {}  # channel_id -> message_ts

    async def start_jira_prompt_workflow(self, channel_id: str) -> None:
        """
        Start the JIRA ticket prompt workflow for a channel.

        Posts initial prompt and starts retry loop.

        Args:
            channel_id: Slack channel ID
        """
        logger.info(f"Starting JIRA prompt workflow for channel: {channel_id}")

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            logger.info(f"JIRA prompt attempt {attempt}/{self.MAX_ATTEMPTS} for {channel_id}")

            # Post prompt message
            message_ts = await self._post_jira_prompt(channel_id, attempt)

            if not message_ts:
                logger.error(f"Failed to post JIRA prompt for {channel_id}")
                return

            # Store message timestamp for deletion later
            self.active_prompts[channel_id] = message_ts

            # Wait for reply (checking for 2 minutes)
            jira_ticket = await self._wait_for_jira_reply(
                channel_id, self.RETRY_DELAY_SECONDS, message_ts
            )

            if jira_ticket:
                logger.info(f"Received JIRA ticket {jira_ticket} for {channel_id}")

                # Update prompt message instead of deleting (avoids tombstone)
                await self._update_prompt_to_received(channel_id, jira_ticket)

                # Process maintenance check
                await self._process_maintenance_check(channel_id, jira_ticket)
                return

            # Delete old prompt before posting new one (except on last attempt)
            if attempt < self.MAX_ATTEMPTS:
                await self._delete_prompt_message(channel_id)

        # All attempts failed - post timeout message
        logger.warning(
            f"No JIRA ticket received after {self.MAX_ATTEMPTS} attempts " f"for {channel_id}"
        )
        await self._delete_prompt_message(channel_id)
        await self._post_timeout_message(channel_id)

    async def _post_jira_prompt(self, channel_id: str, attempt: int) -> Optional[str]:
        """
        Post JIRA ticket prompt message using mrkdwn formatting.

        Args:
            channel_id: Slack channel ID
            attempt: Current attempt number (1-3)

        Returns:
            Message timestamp if successful, None otherwise
        """
        if attempt == 1:
            text = "🤖 *Ketchup needs information:* What is the JIRA ticket for this incident? Please `@mention` me with the ticket number."
        else:
            text = (
                f"🤖 *Ketchup needs information:* What is the JIRA ticket for this incident? "
                f"Please `@mention` me with the ticket number. _(Attempt {attempt}/{self.MAX_ATTEMPTS})_"
            )

        # Retry loop with exponential backoff for transient errors
        max_retries = 3
        retry_delay = 2  # seconds

        for retry in range(max_retries):
            try:
                response = await self.posting_handler.post_message(
                    channel_id=channel_id, message=text
                )

                if response and response.get("ok"):
                    return response.get("ts")

                # Check for transient errors that should trigger retry
                error = response.get("error", "") if response else ""
                if error in ["channel_not_found", "is_archived"] and retry < max_retries - 1:
                    logger.warning(
                        f"Transient error '{error}' posting to {channel_id}, "
                        f"retrying in {retry_delay}s (attempt {retry+1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                logger.error(f"Failed to post JIRA prompt: {response}")
                return None

            except Exception as e:
                # For exceptions, check if error message contains transient error indicators
                error_str = str(e).lower()
                if (
                    "channel_not_found" in error_str or "is_archived" in error_str
                ) and retry < max_retries - 1:
                    logger.warning(
                        f"Transient error '{e}' posting to {channel_id}, "
                        f"retrying in {retry_delay}s (attempt {retry+1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                logger.error(f"Error posting JIRA prompt: {e}", exc_info=True)
                return None

        # All retries exhausted
        return None

    async def _wait_for_jira_reply(
        self, channel_id: str, timeout_seconds: int, prompt_ts: str
    ) -> Optional[str]:
        """
        Wait for JIRA ticket reply via app_mention event (event-driven).

        Instead of polling message history, we store state in DynamoDB and the
        app_mention event handler will detect replies and store them.

        FLOW:
        1. Store "MAINTENANCE_PROMPT#{channel_id}" in DynamoDB with attempt #
        2. Event handler (app_mention) detects user @mention with JIRA ticket
        3. Event handler stores reply in DynamoDB under same key
        4. This method polls DynamoDB every 5 seconds to check for reply
        5. If reply found before timeout, return the JIRA ticket
        6. If timeout expires, delete DynamoDB record and return None

        TIMEOUT BEHAVIOR:
        - Timeout = 120 seconds (RETRY_DELAY_SECONDS)
        - After 120s expires, DynamoDB record is deleted
        - Any @mention AFTER 120s is treated as "late response" by event handler
        - Late responses are logged but not processed (see events.py:325-351)

        Args:
            channel_id: Slack channel ID
            timeout_seconds: How long to wait (seconds) - always 120 for maintenance
            prompt_ts: Timestamp of prompt message

        Returns:
            JIRA ticket key if found, None otherwise
        """
        # Store prompt state in DynamoDB (so app_mention can see it)
        await self.db_store.put_maintenance_prompt(
            channel_id=channel_id,
            prompt_ts=prompt_ts,
            attempt=(
                self.active_prompts.get(channel_id, {}).get("attempt", 1)
                if isinstance(self.active_prompts.get(channel_id), dict)
                else 1
            ),
        )

        # Poll DynamoDB for reply (every 5 seconds is efficient + responsive)
        # The app_mention event handler will update the same DynamoDB record
        # when it detects a user response with a JIRA ticket
        for i in range(timeout_seconds // 5):
            await asyncio.sleep(5)

            # Check if reply was received
            prompt_state = await self.db_store.get_maintenance_prompt(channel_id)

            if not prompt_state:
                # State not found - might be race condition, continue waiting
                # (DynamoDB might be slightly lagged or record might be in transition)
                continue

            if prompt_state.get("jira_ticket"):
                # Reply received! User provided JIRA ticket in time
                jira_ticket = prompt_state["jira_ticket"]
                await self.db_store.delete_maintenance_prompt(channel_id)
                logger.info(f"JIRA reply received within timeout window: {jira_ticket}")
                return jira_ticket

        # Timeout - no reply received within 120 seconds
        # Delete the DynamoDB record so app_mention knows to treat future responses as "late"
        await self.db_store.delete_maintenance_prompt(channel_id)
        logger.info(
            f"No JIRA reply within {timeout_seconds}s for {channel_id}, "
            "moving to next attempt or final timeout"
        )
        return None

    async def _check_recent_messages_for_jira(
        self, channel_id: str, prompt_ts: str
    ) -> Optional[str]:
        """
        Check recent channel messages for replies to our prompt with JIRA tickets.

        Validates:
        - Message is from a user (not bot)
        - Message timestamp is after prompt
        - Message mentions @Ketchup
        - Message contains valid JIRA ticket pattern
        - JIRA ticket project is in approved list

        Args:
            channel_id: Slack channel ID
            prompt_ts: Timestamp of prompt message (validate replies are after this)

        Returns:
            JIRA ticket key if found, None otherwise
        """
        try:
            # Fetch last 10 messages - need raw API response, not formatted messages
            # Use _make_api_request directly to get message dictionaries
            url = f"{await self.channel_msg_ops.get_api_base_url()}/conversations.history"
            params = {
                "channel": channel_id,
                "limit": 10,
                "oldest": "0",
                "include_all_metadata": False,
            }

            response = await self.channel_msg_ops._make_api_request(
                url, "GET", self.channel_msg_ops.headers, params
            )

            messages = response.get("messages", [])
            if not messages:
                return None

            # Get bot user ID for filtering
            bot_user_id = await self.secrets_manager.get_bot_slack_user_id_async()

            # Look for valid replies with JIRA tickets
            for msg in messages:
                text = msg.get("text", "")
                msg_ts = msg.get("ts", "")
                user_id = msg.get("user", "")

                # VALIDATION 1: Ignore bot's own messages
                if user_id == bot_user_id:
                    continue

                # VALIDATION 2: Message must be AFTER our prompt
                if not msg_ts or float(msg_ts) <= float(prompt_ts):
                    continue

                # VALIDATION 3: Message must mention @Ketchup (indicates it's directed at bot)
                # Check for bot mention in Slack format: <@BOT_USER_ID>
                bot_mention = f"<@{bot_user_id}>"
                if bot_mention not in text and "@ketchup" not in text.lower():
                    continue

                # VALIDATION 4: Must contain a valid JIRA ticket pattern
                jira_ticket = self.extract_jira_ticket(text)
                if not jira_ticket:
                    continue

                # VALIDATION 5: Validate ticket project against known valid projects
                ticket_project = jira_ticket.split("-")[0]  # Extract "CPGNREQ" from "CPGNREQ-12345"
                if ticket_project not in VALID_JIRA_PROJECTS:
                    logger.warning(
                        f"Ignoring ticket {jira_ticket} - project {ticket_project} "
                        f"not in valid projects list"
                    )
                    continue

                # All validations passed!
                logger.info(f"Valid JIRA ticket reply from user {user_id}: {jira_ticket}")
                return jira_ticket

            return None

        except Exception as e:
            logger.error(f"Error checking recent messages: {e}", exc_info=True)
            return None

    @staticmethod
    def extract_jira_ticket(text: str) -> Optional[str]:
        """
        Extract JIRA ticket from text.

        Handles:
        - URL format: https://jira.corp.adobe.com/browse/CPGNREQ-182819
        - Uppercase: CPGNREQ-182819
        - Lowercase: cpgnreq-182819

        Args:
            text: Message text

        Returns:
            JIRA ticket key (uppercase), or None

        Examples:
            >>> JiraPromptHandler.extract_jira_ticket("@Ketchup CPGNREQ-182819")
            'CPGNREQ-182819'
            >>> JiraPromptHandler.extract_jira_ticket(
            ...     "@Ketchup https://jira.corp.adobe.com/browse/CPGNREQ-182819"
            ... )
            'CPGNREQ-182819'
        """
        # Pattern 1: URL format
        url_match = re.search(r"jira\.corp\.adobe\.com/browse/([A-Z]+-\d+)", text, re.IGNORECASE)
        if url_match:
            return url_match.group(1).upper()

        # Pattern 2: Ticket key (case insensitive)
        ticket_match = re.search(r"\b([A-Z]+-\d+)\b", text, re.IGNORECASE)
        if ticket_match:
            return ticket_match.group(1).upper()

        return None

    async def _update_prompt_to_received(self, channel_id: str, jira_ticket: str) -> bool:
        """
        Update the JIRA prompt message to show ticket was received.
        Avoids leaving "This message was deleted" tombstone.

        Args:
            channel_id: Slack channel ID
            jira_ticket: The JIRA ticket received

        Returns:
            True if successful, False otherwise
        """
        message_ts = self.active_prompts.get(channel_id)
        if not message_ts:
            return False

        # Retry loop with exponential backoff for transient errors
        max_retries = 3
        retry_delay = 2  # seconds

        for retry in range(max_retries):
            try:
                await self.posting_handler.update_message(
                    channel_id=channel_id,
                    ts=message_ts,
                    message=f"✅ Received {jira_ticket} - checking maintenance status...",
                )
                # Keep message_ts in active_prompts for deletion after final result
                logger.info(f"Updated JIRA prompt for {channel_id} with ticket {jira_ticket}")
                return True

            except Exception as e:
                # Check if error message contains transient error indicators
                error_str = str(e).lower()
                if (
                    "channel_not_found" in error_str or "is_archived" in error_str
                ) and retry < max_retries - 1:
                    logger.warning(
                        f"Transient error '{e}' updating message in {channel_id}, "
                        f"retrying in {retry_delay}s (attempt {retry+1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                logger.warning(f"Failed to update JIRA prompt: {e}")
                return False

        # All retries exhausted
        return False

    async def _delete_prompt_message(self, channel_id: str) -> bool:
        """
        Delete the JIRA prompt message.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if successful, False otherwise
        """
        message_ts = self.active_prompts.get(channel_id)
        if not message_ts:
            return False

        # Deletion failure is non-fatal - channel operations (rename, archive) can cause transient errors
        try:
            await self.posting_handler.delete_message(channel_id=channel_id, message_ts=message_ts)
            del self.active_prompts[channel_id]
            logger.info(f"Deleted JIRA prompt for {channel_id}")
            return True

        except Exception as e:
            logger.warning(
                f"Failed to delete JIRA prompt (non-fatal): {e}. "
                f"Workflow will continue. Channel: {channel_id}"
            )
            return False

    async def _process_maintenance_check(self, channel_id: str, jira_ticket: str) -> None:
        """
        Process maintenance check after receiving JIRA ticket.

        Args:
            channel_id: Slack channel ID
            jira_ticket: JIRA ticket key (e.g., "CPGNREQ-182819")
        """
        # DEFENSIVE: Store JIRA ticket FIRST before any operations that might fail.
        # This ensures we never lose the user-provided ticket info, even if
        # MCP fails, instance URL is missing, or an exception occurs.
        try:
            await self.db_store.channel_ops.update_channel_fields(
                channel_id=channel_id, updates={"jira_ticket": jira_ticket}
            )
            logger.info(f"Stored JIRA ticket {jira_ticket} for channel {channel_id}")
        except Exception as e:
            # Log but continue - we still want to try the maintenance check
            logger.warning(f"Failed to store JIRA ticket defensively: {e}")

        try:
            # Fetch JIRA ticket via MCP
            jira_data = await self._fetch_jira_ticket(jira_ticket)

            if not jira_data:
                logger.error(f"Failed to fetch JIRA ticket {jira_ticket}")
                await self._post_error_message(
                    channel_id,
                    f"⚠️ Received {jira_ticket} but unable to fetch ticket details. "
                    "The ticket has been recorded for this channel.",
                )
                return

            # Extract instance URL from customfield_22302
            instance_url = jira_data.get("fields", {}).get("customfield_22302")

            if not instance_url:
                logger.error(f"No instance URL in JIRA ticket {jira_ticket}")
                await self._post_error_message(
                    channel_id,
                    f"⚠️ {jira_ticket} does not contain an instance URL (customfield_22302). "
                    "Cannot determine maintenance status. The ticket has been recorded.",
                )
                return

            logger.info(f"Instance URL from JIRA: {instance_url}")

            # Check for maintenance
            maintenance_info = await self.maintenance_checker.check_maintenance(instance_url)

            if maintenance_info:
                # Maintenance found - post pinned message
                await self._post_maintenance_found_message(
                    channel_id, maintenance_info, jira_ticket
                )
            else:
                # No maintenance - post regular message
                normalized_instance = self.maintenance_checker.normalize_instance_name(instance_url)
                await self._post_no_maintenance_message(
                    channel_id, normalized_instance, jira_ticket
                )

        except Exception as e:
            logger.error(f"Error processing maintenance check: {e}", exc_info=True)
            await self._post_error_message(
                channel_id,
                f"⚠️ Error checking maintenance for {jira_ticket}: {str(e)[:100]}. "
                "The ticket has been recorded for this channel.",
            )

    async def _fetch_jira_ticket(self, jira_ticket: str) -> Optional[Dict]:
        """
        Fetch JIRA ticket data via MCP.

        Args:
            jira_ticket: JIRA ticket key

        Returns:
            JIRA ticket data dict, or None if fetch fails
        """
        try:
            # Use MCP client to fetch JIRA ticket
            # Must explicitly request customfield_22302 (instance URL)
            response = await self.mcp_client.search_issues(
                jql=f'key = "{jira_ticket}"', fields=["summary", "status", "customfield_22302"]
            )

            if response and response.get("issues"):
                return response["issues"][0]

            return None

        except Exception as e:
            logger.error(f"Error fetching JIRA ticket {jira_ticket}: {e}", exc_info=True)
            return None

    async def _post_maintenance_found_message(
        self, channel_id: str, maintenance_info: Dict, jira_ticket: str
    ) -> None:
        """
        Post pinned message when maintenance is found.

        Args:
            channel_id: Slack channel ID
            maintenance_info: Maintenance info dict from checker
            jira_ticket: JIRA ticket key
        """
        customer_name = maintenance_info.get("customer_name", "Unknown")
        instance_name = maintenance_info.get("instance_name", "")
        starts_at_iso = maintenance_info.get("starts_at", "")

        # Format instance URL
        instance_url = self.maintenance_checker.denormalize_instance_url(instance_name)

        # Format start time
        starts_at_formatted = self.maintenance_checker.format_maintenance_start_time(starts_at_iso)

        text = f"""🔧 **SCHEDULED MAINTENANCE DETECTED**

**Customer**: {customer_name}
**Instance**: {instance_url}
**Maintenance Start**: {starts_at_formatted}

This channel may be related to scheduled maintenance rather than an incident."""

        try:
            # Delete intermediate "Received..." message before posting final result
            await self._delete_prompt_message(channel_id)

            # Post message
            response = await self.posting_handler.post_message(channel_id=channel_id, message=text)

            if response and response.get("ok"):
                message_ts = response.get("ts")

                # Pin the message
                await self.posting_handler.pin_message(channel_id=channel_id, message_ts=message_ts)

                # Update DynamoDB with customer_name
                # NOTE: jira_ticket is already stored defensively at start of _process_maintenance_check
                # Using update_channel_fields instead of update_channel_metadata (which requires user_id)
                await self.db_store.channel_ops.update_channel_fields(
                    channel_id=channel_id,
                    updates={"customer_name": customer_name, "jira_ticket": jira_ticket},
                )

                logger.info(f"Posted and pinned maintenance message for {channel_id}")

        except Exception as e:
            logger.error(f"Error posting maintenance message: {e}", exc_info=True)

    async def _post_no_maintenance_message(
        self, channel_id: str, instance_name: str, jira_ticket: str
    ) -> None:
        """
        Post message when no maintenance is found.

        Args:
            channel_id: Slack channel ID
            instance_name: Normalized instance name
            jira_ticket: JIRA ticket key
        """
        instance_url = self.maintenance_checker.denormalize_instance_url(instance_name)
        text = f"ℹ️ No scheduled maintenance found for {instance_url}"

        try:
            # Delete intermediate "Received..." message before posting final result
            await self._delete_prompt_message(channel_id)

            # Post final result
            await self.posting_handler.post_message(channel_id=channel_id, message=text)

            # Update DynamoDB with jira_ticket (use generic update method)
            await self.db_store.channel_ops.update_channel_fields(
                channel_id=channel_id, updates={"jira_ticket": jira_ticket}
            )

            logger.info(f"Posted no-maintenance message for {channel_id}")

        except Exception as e:
            logger.error(f"Error posting no-maintenance message: {e}", exc_info=True)

    async def _post_timeout_message(self, channel_id: str) -> None:
        """
        Post message when all retry attempts fail (no JIRA ticket provided).

        Args:
            channel_id: Slack channel ID
        """
        text = "⚠️ Unable to determine maintenance status - missing JIRA ticket information"

        try:
            await self.posting_handler.post_message(channel_id=channel_id, message=text)
            logger.info(f"Posted timeout message for {channel_id}")

        except Exception as e:
            logger.error(f"Error posting timeout message: {e}", exc_info=True)

    async def _post_error_message(self, channel_id: str, message: str) -> None:
        """
        Post a specific error message to the channel.

        Unlike _post_timeout_message, this is used when we received a JIRA ticket
        but encountered an error during processing. The message should be
        informative about what went wrong.

        Args:
            channel_id: Slack channel ID
            message: The error message to post
        """
        try:
            await self.posting_handler.post_message(channel_id=channel_id, message=message)
            logger.info(f"Posted error message for {channel_id}")

        except Exception as e:
            logger.error(f"Error posting error message: {e}", exc_info=True)
