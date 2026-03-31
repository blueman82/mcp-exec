"""
generator.py

This module contains the AutoStatusGenerator class, which is responsible for
generating and posting status reports to Slack.

Migrated from ketchup_status_updater/status_generator.py
"""

import hashlib
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import orjson

from packages.ai.core.operations.message_preparation import MessagePreparer
from packages.ai.cost_calculator import TokenTracker
from packages.ai.prompts.auto_status import get_auto_status_prompt, get_auto_status_system_prompt
from packages.core.config.feature_flags import FeatureFlags
from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class AutoStatusGenerator:
    """Generate status reports without user context dependencies."""

    def __init__(
        self,
        db_store,
        mcp_client,
        secrets_manager,
        slack_config,
        openai_handler,
        channel_info_ops,
        channel_msg_ops,
        posting_handler,
        channel_operations,
    ):
        self.db_store = db_store
        self.mcp_client = mcp_client
        self.secrets_manager = secrets_manager
        self.slack_config = slack_config
        self.openai_handler = openai_handler
        self.channel_info_ops = channel_info_ops
        self.channel_msg_ops = channel_msg_ops
        self.posting_handler = posting_handler
        self.channel_operations = channel_operations

    async def check_for_activity(
        self, channel_id: str, channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if there's new activity (Slack messages, thread replies, or JIRA comments) since last update."""
        try:
            # Get fresh timestamps from DB instead of potentially stale channel_config
            fresh_channel = await self.channel_operations.query_ops.get_channel_details(channel_id)
            if fresh_channel:
                last_message_ts = fresh_channel.get("auto_status_last_message_ts", "0")
                last_thread_ts = fresh_channel.get("auto_status_last_thread_ts", "0")
                last_jira_comment_ts = fresh_channel.get("auto_status_last_jira_comment_ts", "0")
            else:
                # Fallback to channel_config if DB fetch fails
                last_message_ts = channel_config.get("auto_status_last_message_ts", "0")
                last_thread_ts = channel_config.get("auto_status_last_thread_ts", "0")
                last_jira_comment_ts = channel_config.get("auto_status_last_jira_comment_ts", "0")

            logger.info(
                f"[{channel_id}] Checking for activity since message_ts: {last_message_ts}, thread_ts: {last_thread_ts}"
            )

            # Check for new Slack messages and thread activity
            has_new_messages = False
            has_thread_activity = False
            latest_message_ts = last_message_ts  # Default to last known timestamp
            latest_thread_ts = last_thread_ts

            # Always check for messages to get the latest timestamp
            token_tracker = TokenTracker()

            message_preparer = MessagePreparer(
                token_tracker=token_tracker,
                channel_msg_ops=self.channel_msg_ops,
                channel_info_ops=self.channel_info_ops,
            )

            try:
                prepared_messages, metadata = (
                    await message_preparer.prepare_messages_for_auto_status(
                        channel_id=channel_id,
                        since_ts=last_message_ts if last_message_ts != "0" else None,
                        # Bot filtering happens automatically in channel_msg_ops
                    )
                )
                # Use the new has_channel_messages field from metadata
                has_new_messages = metadata.get("has_channel_messages", False)
                has_thread_activity = metadata.get("has_thread_activity", False)

                # Capture the latest timestamp we've seen
                latest_message_ts = metadata.get("latest_ts", last_message_ts)

                # Also check for thread activity timestamp separately to update it
                _, latest_thread_ts, _ = await self.channel_msg_ops.check_recent_thread_activity(
                    channel_id, last_thread_ts
                )

                logger.info(
                    f"[{channel_id}] Activity check complete: has_new_messages={has_new_messages}, has_thread_activity={has_thread_activity}, latest_ts={latest_message_ts}"
                )

                # On first run (last_message_ts == "0"), we need to ensure there's activity to post
                # But we should NOT override the channel vs thread classification
                # The metadata already tells us if there are channel messages vs just threads
                if last_message_ts == "0":
                    # For first run, we'll post if there's ANY activity (channel OR thread)
                    # But keep the correct classification of what type of activity
                    logger.info(
                        f"First run detected for {channel_id}, keeping activity classification from metadata"
                    )

            except Exception as e:
                logger.error(f"Error checking for new messages in {channel_id}: {e}")
                # On container restart, don't assume activity on API errors
                has_new_messages = False  # Conservative approach: skip posting on errors

            # Check for new JIRA comments
            has_jira_updates = False
            channel_details = await self.channel_operations.get_channel_details(channel_id)
            jira_ticket = channel_details.get("jira_ticket", "")

            if jira_ticket and jira_ticket != "NOT YET AVAILABLE" and last_jira_comment_ts != "0":
                try:
                    # Get latest JIRA comment timestamp
                    latest_jira_ts = await self._get_latest_jira_comment_timestamp(jira_ticket)
                    if latest_jira_ts and latest_jira_ts > last_jira_comment_ts:
                        has_jira_updates = True
                except Exception as e:
                    logger.warning(f"Error checking JIRA updates: {e}")
                    # Don't assume activity for JIRA errors

            return {
                "has_activity": has_new_messages or has_thread_activity or has_jira_updates,
                "has_new_messages": has_new_messages,
                "has_thread_activity": has_thread_activity,
                "has_jira_updates": has_jira_updates,
                "latest_message_ts": latest_message_ts,  # Return the latest timestamp we've seen
                "latest_thread_ts": latest_thread_ts,  # Return the latest thread timestamp
            }

        except Exception as e:
            logger.error(f"Error checking activity for {channel_id}: {e}")
            # On error, assume activity to avoid missing updates
            return {
                "has_activity": True,
                "has_new_messages": True,
                "has_thread_activity": False,
                "has_jira_updates": False,
                "latest_message_ts": channel_config.get(
                    "auto_status_last_message_ts", "0"
                ),  # Return current timestamp on error
                "latest_thread_ts": channel_config.get("auto_status_last_thread_ts", "0"),
            }

    async def generate_and_post_status(
        self,
        channel_id: str,
        channel_name: str,
        channel_config: Dict[str, Any],
        activity_check: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Generate and post status report using direct AI interaction."""
        try:
            # Step 1: Get last processed timestamps for incremental fetching (store originals for verification)
            original_last_message_ts = channel_config.get("auto_status_last_message_ts", "0")
            original_last_thread_ts = channel_config.get("auto_status_last_thread_ts", "0")
            original_last_jira_ts = channel_config.get("auto_status_last_jira_comment_ts", "0")

            # Step 2: Prepare messages incrementally (only new messages since last run)
            token_tracker = TokenTracker()

            message_preparer = MessagePreparer(
                token_tracker=token_tracker,
                channel_msg_ops=self.channel_msg_ops,
                channel_info_ops=self.channel_info_ops,
            )

            # For first run, get ALL messages; otherwise incremental
            # IMPORTANT: Use original timestamp to avoid missing messages due to processor updates
            is_first_run = original_last_message_ts == "0"
            try:
                prepared_messages, channel_metadata = (
                    await message_preparer.prepare_messages_for_auto_status(
                        channel_id=channel_id,
                        since_ts=(
                            None if is_first_run else original_last_message_ts
                        ),  # Use ORIGINAL timestamp, not potentially updated one
                        # Bot filtering happens automatically in channel_msg_ops
                    )
                )
            except Exception as e:
                logger.error(f"Error preparing messages: {e}")
                # Fallback - return error state with empty metadata
                prepared_messages = "Error fetching messages"
                channel_metadata = {
                    "latest_ts": original_last_message_ts,
                    "has_thread_activity": False,
                    "has_channel_messages": False,
                }

            # Extract activity indicators from metadata - DO NOT override based on message content!
            has_new_messages = channel_metadata.get("has_channel_messages", False)
            has_thread_activity = channel_metadata.get("has_thread_activity", False)

            # If this is not the first run and there are no new messages, indicate that in the prompt
            if not is_first_run and not has_new_messages:
                logger.info(f"No new messages found for channel {channel_id} since last update")

            # Step 3: Get channel details from DB
            channel_details = await self.channel_operations.get_channel_details(channel_id)

            # Step 4: Get previous status for context (if exists)
            previous_status = channel_config.get("auto_status_last_content", "")

            # Step 5: Get JIRA comments if ticket exists (with fallback)
            jira_comments_raw = None
            has_jira_updates = False
            jira_ticket = channel_details.get("jira_ticket", "")

            if jira_ticket and jira_ticket != "NOT YET AVAILABLE":
                try:
                    jira_comments_raw = await self._fetch_jira_comments_raw(jira_ticket)

                    # Always check timestamps - never assume activity just because comments exist
                    latest_jira_ts = await self._get_latest_jira_comment_timestamp(jira_ticket)
                    if latest_jira_ts and latest_jira_ts > original_last_jira_ts:
                        has_jira_updates = True

                except Exception as e:
                    logger.warning(f"JIRA MCP not available for {jira_ticket}: {e}")
                    # Continue with just Slack messages

            # Step 4: Get prompts from prompt files
            channel_info = {
                "channel_name": channel_name,
                "channel_id": channel_id,
                "customer_name": channel_details.get("customer_name", "NOT YET AVAILABLE"),
                "jira_ticket": channel_details.get("jira_ticket", "NOT YET AVAILABLE"),
                "product": channel_details.get("product", "unknown"),
            }

            system_prompt = get_auto_status_system_prompt()
            # Use default preferences (balanced detail level)
            user_prompt = get_auto_status_prompt(channel_info)
            # Step 7: Build full prompt with all context
            full_user_prompt = user_prompt

            # Add context sections (these are for AI to analyze, not to include in output)
            full_user_prompt += "\n\n--- CONTEXT FOR ANALYSIS (DO NOT INCLUDE IN OUTPUT) ---"

            # Add previous status if exists (for incremental context)
            if previous_status and not is_first_run:
                # Get the last run timestamp to provide temporal context
                last_run_ts = channel_config.get("auto_status_last_run", 0)
                if last_run_ts:
                    last_run_date = datetime.fromtimestamp(float(last_run_ts)).strftime(
                        "%Y-%m-%d %H:%M UTC"
                    )
                    full_user_prompt += f"\n\nPrevious Status Update (Generated: {last_run_date}):\n{previous_status}"
                else:
                    full_user_prompt += f"\n\nPrevious Status Update:\n{previous_status}"

            # Add new messages
            full_user_prompt += f"\n\nChannel Messages to Analyze:\n{prepared_messages}"

            # Debug log to see what messages we're sending to AI
            logger.info(f"[DEBUG] Prepared messages length: {len(prepared_messages)}")
            logger.info(f"[DEBUG] Has thread activity: {has_thread_activity}")
            if has_thread_activity:
                # Log first 500 chars of messages to see if threads are included
                logger.info(f"[DEBUG] First 500 chars of messages: {prepared_messages[:500]}")

            # Add JIRA comments if available
            if jira_comments_raw:
                full_user_prompt += f"\n\nJIRA Comments to Analyze:\n{jira_comments_raw}"

            full_user_prompt += "\n\n--- END OF CONTEXT ---"

            # Add instructions based on run type
            if is_first_run:
                # First run - provide guidance on initial status
                if has_jira_updates and jira_comments_raw:
                    full_user_prompt += "\n\nNOTE: This is the initial status update. JIRA comments are included in the context - incorporate relevant information from both Slack messages and JIRA."
            else:
                # Incremental updates
                # Check Slack messages, thread activity, and JIRA updates
                if has_new_messages or has_thread_activity or has_jira_updates:
                    full_user_prompt += "\n\nIMPORTANT INSTRUCTIONS:"
                    full_user_prompt += "\n- The Previous Status Update shows what was last communicated (check its timestamp)"
                    full_user_prompt += "\n- Generate a FRESH status reflecting the CURRENT state based on all available information"
                    full_user_prompt += "\n- If the previous status is old (>12 hours) and new messages are minimal, be cautious about maintaining outdated narratives"
                    full_user_prompt += "\n- Focus on what's actually known from the messages rather than assumptions"

                    # Add specific guidance based on activity type
                    if not has_new_messages and not has_thread_activity and has_jira_updates:
                        full_user_prompt += "\n- Note: While there are no new Slack messages, there ARE new JIRA comments. Your Overview MUST mention that this update is based on JIRA activity. Include these JIRA updates in your analysis."
                    elif has_thread_activity and not has_new_messages and not has_jira_updates:
                        full_user_prompt += "\n- Note: There is new THREAD activity (replies to existing messages). Focus on the thread discussions and include the latest updates from thread replies."
                    elif (has_new_messages or has_thread_activity) and not has_jira_updates:
                        full_user_prompt += "\n- Note: There are new Slack messages/threads but no JIRA updates since the last status."
                    elif (has_new_messages or has_thread_activity) and has_jira_updates:
                        full_user_prompt += "\n- Note: There are both new Slack messages/threads AND new JIRA comments. Synthesize both sources in your analysis."

                else:
                    # Only say "no activity" if ALL are false
                    full_user_prompt += "\n\nIMPORTANT: There are NO NEW MESSAGES since the last update. Your Overview MUST indicate 'No new activity since the last update' while still providing the current status."

            full_user_prompt += "\n\nREMINDER: Output ONLY the Overview and 4 bullet points as specified in the format above. Do NOT include the context sections."

            # Step 8: Call AI directly
            status_content = await self._generate_ai_response(
                system_prompt=system_prompt, user_prompt=full_user_prompt
            )

            # Step 9: Apply corrections
            corrected_content = self._apply_corrections(
                content=status_content, channel_name=channel_name, channel_details=channel_details
            )

            # Step 9.5: FINAL ACTIVITY VERIFICATION - Double-check before posting
            # This prevents false positives from activity detection errors during container restart
            # Pass original timestamps to avoid race condition with timestamp updates
            final_check = await self._verify_real_activity(
                channel_id,
                channel_config,
                original_last_message_ts,
                original_last_thread_ts,
                original_last_jira_ts,
            )
            if not final_check:
                logger.warning(
                    f"Channel {channel_id}: Final verification detected no real activity despite initial detection. "
                    f"Likely container restart false positive. Aborting post."
                )
                return False

            # Step 10: Format and post with trust button
            # Use the activity detection results we already have from earlier
            logger.info("[MESSAGE FORMAT DEBUG] Calling _format_final_message with:")
            logger.info(f"  - has_new_messages: {has_new_messages}")
            logger.info(f"  - has_thread_activity: {has_thread_activity}")
            logger.info(f"  - has_jira_updates: {has_jira_updates}")

            final_message = self._format_final_message(
                corrected_content,
                channel_name,
                channel_id,
                has_slack_activity=has_new_messages,
                has_thread_activity=has_thread_activity,
                has_jira_activity=has_jira_updates,
            )
            status_update_id = self._generate_status_update_id(channel_id)

            post_result = await self._post_to_slack_public(
                channel_id, final_message, status_update_id
            )

            if post_result.get("success"):
                # Step 11: Store status content and update timestamps
                # Note: newest_message_ts is tracked in channel_metadata

                # Get latest JIRA comment timestamp if JIRA ticket exists
                latest_jira_ts = channel_config.get("auto_status_last_jira_comment_ts", "0")
                if jira_ticket and jira_ticket != "NOT YET AVAILABLE":
                    new_jira_ts = await self._get_latest_jira_comment_timestamp(jira_ticket)
                    if new_jira_ts:
                        latest_jira_ts = new_jira_ts

                # Get latest thread timestamp
                activity_result = await self.check_for_activity(channel_id, channel_config)
                latest_thread_ts = activity_result.get("latest_thread_ts", "0")

                # Increment monthly metrics counter for auto_status_posts
                try:
                    month_key = datetime.now(timezone.utc).strftime("%Y_%m")
                    await self.db_store.increment_monthly_counter("auto_status_posts", month_key, 1)
                    logger.debug(f"Incremented auto_status_posts counter for {month_key}")
                except Exception as e:
                    logger.warning(f"Failed to increment monthly counter: {e}")
                    # Don't fail the whole operation for counter increment failure

                # Note: auto_status_last_message_ts is already updated by processor after activity check
                await self.channel_operations.update_channel_fields(
                    channel_id=channel_id,
                    updates={
                        "auto_status_last_content": corrected_content,
                        "auto_status_last_jira_comment_ts": latest_jira_ts,
                        "auto_status_last_thread_ts": latest_thread_ts,
                        "auto_status_attempt_count": 0,  # Reset on success
                    },
                )

                # Step 12: Store command execution metadata for trust buttons (always store for buttons to work)
                await self._store_status_update_metadata(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    status_update_id=post_result["status_update_id"],
                    message_ts=post_result["message_ts"],
                    content_hash=self._generate_content_hash(corrected_content),
                )

            return post_result.get("success", False)

        except Exception as e:
            logger.error(f"Error generating status for {channel_id}: {e}", exc_info=True)
            return False

    async def _generate_ai_response(self, system_prompt: str, user_prompt: str) -> str:
        """Call AI API directly without user context."""
        # Prepare messages for API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Use the OpenAI handler's execute_prompt method directly
        response = await self.openai_handler.execute_prompt(
            messages=messages,
            reasoning_effort="low",
            max_tokens=2048,  # Status reports need more tokens
        )

        return response

    def _apply_corrections(
        self, content: str, channel_name: str, channel_details: Dict[str, Any]
    ) -> str:
        """Apply corrections to AI output."""
        # Replace placeholder with actual channel name
        content = content.replace("[PLACEHOLDER]", f"#{channel_name}")
        content = content.replace("NOT YET AVAILABLE", f"#{channel_name}")

        # Handle JIRA ticket formatting
        jira_ticket = channel_details.get("jira_ticket", "NOT YET AVAILABLE")

        # Step 1: Remove any existing JIRA line from AI output (to replace with correct format)
        content = self._remove_jira_line(content)

        # Step 2: Determine which JIRA ticket to use
        if jira_ticket and jira_ticket != "NOT YET AVAILABLE":
            # Use ticket from database
            final_ticket = jira_ticket
        else:
            # Try to extract valid JIRA ticket from the content
            final_ticket = self._extract_valid_jira_ticket(content)

        # Step 3: Add JIRA line only if we have a valid ticket
        if final_ticket:
            jira_line = (
                f"\nJIRA Ticket: <https://jira.corp.adobe.com/browse/{final_ticket}|{final_ticket}>"
            )
            content = content.rstrip() + "\n" + jira_line

        return content

    def _generate_status_update_id(self, channel_id: str) -> str:
        """Generate a unique ID for this status update."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        unique_suffix = secrets.token_hex(4)  # 8 chars
        return f"{timestamp}_{unique_suffix}"

    def _format_final_message(
        self,
        content: str,
        channel_name: str,
        channel_id: str,
        has_slack_activity: bool = False,
        has_thread_activity: bool = False,
        has_jira_activity: bool = False,
    ) -> str:
        """Format the final message with header including why this update was triggered."""
        # Build activity indicators
        activity_indicators = []

        if has_slack_activity:
            activity_indicators.append(":slack:")

        if has_thread_activity:
            activity_indicators.append(":thread:")

        if has_jira_activity:
            activity_indicators.append(":jira-logo:")

        # Create activity source line
        activity_source_line = ""
        if activity_indicators:
            activity_source_line = f"Activity source: {' '.join(activity_indicators)}\n"

        # Build human-readable source names for disclaimer
        source_names = [
            name
            for flag, name in (
                (has_jira_activity, "Jira"),
                (has_slack_activity, "Slack"),
                (has_thread_activity, "Slack thread"),
            )
            if flag
        ]

        if not source_names:
            disclaimer = "_This is the initial auto-generated summary for this channel. Please review and validate every detail carefully before using it for CFS, ticketing, or any formal communication._"
        else:
            source_text = (
                source_names[0]
                if len(source_names) == 1
                else (
                    f"{source_names[0]} and {source_names[1]}"
                    if len(source_names) == 2
                    else f"{', '.join(source_names[:-1])}, and {source_names[-1]}"
                )
            )
            disclaimer = (
                f"_This auto-generated summary is based on {source_text} discussions. "
                f"Please review and validate every detail carefully before using it for CFS, ticketing, or any formal communication._"
            )

        header = (
            f"*Ketchup Automated Status Update*\n"
            f"Channel: <#{channel_id}|{channel_name}>\n"
            f"{activity_source_line}"
            f"Status checked hourly: Updates posted only when activity detected\n"
            f"{disclaimer}\n"
            f"{'─' * 40}\n\n"
        )

        return header + content

    async def _post_to_slack_public(
        self, channel_id: str, content: str, status_update_id: str
    ) -> Dict[str, Any]:
        """Post a new status message to Slack channel, deleting previous post if exists."""
        try:
            # Step 1: Delete previous post if timestamp exists (backward compatible)
            await self._delete_previous_post_if_exists(channel_id)

            # Step 2: Ensure token is initialized
            if not self.posting_handler._slack_token:
                await self.posting_handler._init_slack_token()

            # Step 3: Create blocks - always include the main content
            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": content}}]

            # Only add trust button if feature is enabled globally OR for this specific channel
            trust_global_enabled = FeatureFlags.is_trust_endorsement_enabled()
            trust_global_all = FeatureFlags.is_trust_endorsement_global()
            trust_channel_enabled = await self._is_trust_enabled_for_channel(channel_id)

            logger.info(f"[TRUST BUTTON DEBUG] Channel {channel_id}:")
            logger.info(f"  - Global feature enabled: {trust_global_enabled}")
            logger.info(f"  - Global for all channels: {trust_global_all}")
            logger.info(f"  - Channel specific enabled: {trust_channel_enabled}")
            logger.info(
                f"  - Will add button: {trust_global_enabled and (trust_global_all or trust_channel_enabled)}"
            )

            # Store whether we'll add buttons (needed after posting)
            add_buttons = trust_global_enabled and (trust_global_all or trust_channel_enabled)

            # For now, add placeholder actions block that we'll update after posting
            if add_buttons:
                blocks.append(
                    {
                        "type": "actions",
                        "block_id": "status_actions",
                        "elements": [
                            {
                                "style": "primary",
                                "type": "button",
                                "text": {"type": "plain_text", "text": "✓ Trust this summary"},
                                "action_id": "trust_status_update",
                                "value": status_update_id,
                            }
                        ],
                    }
                )

            # Step 4: Post as a new message to the channel
            response = await self.posting_handler._post_channel_message(
                channel_id=channel_id, message=content, blocks=blocks
            )

            if response.get("ok"):
                message_ts = response.get("ts")
                logger.info(
                    f"Successfully posted new auto-status to {channel_id} with trust button"
                )

                # Step 5: Update message with flag button now that we have message_ts
                if add_buttons:
                    # Update the actions block to include both buttons with correct values
                    updated_blocks = blocks.copy()
                    for i, block in enumerate(updated_blocks):
                        if block.get("block_id") == "status_actions":
                            updated_blocks[i] = {
                                "type": "actions",
                                "block_id": "status_actions",
                                "elements": [
                                    {
                                        "style": "primary",
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "✓ Trust this summary",
                                        },
                                        "action_id": "trust_status_update",
                                        "value": status_update_id,
                                    },
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "🚩 Flag for review",
                                        },
                                        "action_id": "flag_status_review",
                                        "value": f"{channel_id}|{message_ts}|{status_update_id}",
                                    },
                                ],
                            }
                            break

                    # Update the message with both buttons
                    await self.posting_handler.update_message(
                        channel_id=channel_id, ts=message_ts, message=content, blocks=updated_blocks
                    )

                # Step 6: Store new post timestamp for future deletion
                await self._store_post_timestamp(channel_id, message_ts)

                return {
                    "success": True,
                    "message_ts": message_ts,
                    "status_update_id": status_update_id,
                }
            else:
                logger.error(f"Failed to post: {response.get('error', 'Unknown error')}")
                return {"success": False}

        except Exception as e:
            logger.error(f"Error posting to Slack: {e}")
            return {"success": False}

    async def _delete_previous_post_if_exists(self, channel_id: str) -> None:
        """Delete previous status post if timestamp exists (backward compatible)."""
        try:
            # Get channel config
            channel_config = await self.channel_operations.get_channel_details(channel_id)
            if not channel_config:
                logger.info(f"No channel config found for {channel_id}")
                return

            # Check for previous post timestamp (backward compatible)
            last_post_ts = channel_config.get("auto_status_last_post_ts", "0")

            if last_post_ts == "0" or not last_post_ts:
                logger.info(f"No previous post to delete for channel {channel_id}")
                return

            # Attempt deletion
            logger.info(f"Deleting previous status post {last_post_ts} from channel {channel_id}")

            # Ensure token is initialized
            if not self.posting_handler._slack_token:
                await self.posting_handler._init_slack_token()

            delete_response = await self.posting_handler.delete_message(
                channel_id=channel_id, message_ts=last_post_ts
            )

            if delete_response.get("ok"):
                logger.info(f"Successfully deleted previous post {last_post_ts}")
            else:
                logger.warning(f"Failed to delete previous post: {delete_response.get('error')}")
                # Don't fail - continue with new post

        except Exception as e:
            logger.warning(f"Error deleting previous post for channel {channel_id}: {e}")
            # Don't fail - continue with new post

    async def _store_post_timestamp(self, channel_id: str, message_ts: str) -> None:
        """Store the timestamp of the posted message for future deletion."""
        try:
            await self.channel_operations.update_channel_fields(
                channel_id=channel_id, updates={"auto_status_last_post_ts": message_ts}
            )
            logger.info(f"Stored post timestamp {message_ts} for channel {channel_id}")
        except Exception as e:
            logger.warning(f"Failed to store post timestamp: {e}")
            # Non-critical - next post won't delete this one, but that's OK

    async def _fetch_jira_comments_raw(self, jira_ticket: str) -> Optional[str]:
        """Fetch JIRA comments and return them as formatted text for AI analysis."""
        try:
            # Use MCP client passed in constructor
            mcp_client = self.mcp_client

            # Use the existing get_issue_comments method
            comments = await mcp_client.get_issue_comments(jira_ticket)

            if not comments:
                logger.info(f"No JIRA comments found for {jira_ticket}")
                return None

            # Sort by created date (most recent first) and take top 5
            sorted_comments = sorted(comments, key=lambda x: x.get("created", ""), reverse=True)[:5]

            # Extract and format comment bodies for AI consumption
            comment_texts = []

            for comment in sorted_comments:
                author = comment.get("author", {}).get("displayName", "Unknown")
                created = comment.get("created", "")[:10]  # Just date part
                body = comment.get("body", "")

                # Clean up the comment body (remove excessive formatting)
                clean_body = body.replace("\n\n", "\n").strip()
                if clean_body:
                    comment_texts.append(f"[{created}] {author}: {clean_body}")

            if not comment_texts:
                return None

            # Return raw formatted comments for AI to analyze along with Slack messages
            return "\n---\n".join(comment_texts)

        except Exception as e:
            logger.warning(f"Could not fetch JIRA comments for {jira_ticket}: {e}")
            return None

    async def _get_latest_jira_comment_timestamp(self, jira_ticket: str) -> Optional[str]:
        """Get the timestamp of the latest JIRA comment."""
        try:
            comments = await self.mcp_client.get_issue_comments(jira_ticket)

            if not comments:
                return None

            # Find the latest comment timestamp
            latest_timestamp = None
            for comment in comments:
                created = comment.get("created", "")
                if created and (not latest_timestamp or created > latest_timestamp):
                    latest_timestamp = created

            return latest_timestamp

        except Exception as e:
            logger.warning(f"Could not get JIRA comment timestamps for {jira_ticket}: {e}")
            return None

    def _generate_content_hash(self, content: str) -> str:
        """Generate a hash of the content for comparison."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _store_status_update_metadata(
        self,
        channel_id: str,
        channel_name: str,
        status_update_id: str,
        message_ts: str,
        content_hash: str,
    ) -> None:
        """Store metadata for trust tracking."""
        try:
            timestamp = int(status_update_id.split("_")[0])

            # Use trust operations to store the metadata
            await self.db_store.trust_ops.store_status_update_metadata(
                channel_id=channel_id,
                status_update_id=status_update_id,
                timestamp=timestamp,
                content_preview=content_hash,  # Using hash as preview for now
            )

            logger.info(f"Stored trust metadata for status update {status_update_id}")

        except Exception as e:
            logger.error(f"Failed to store trust metadata: {e}")
            # Don't fail the whole operation just for trust metadata

    async def _is_trust_enabled_for_channel(self, channel_id: str) -> bool:
        """Check if trust endorsement is enabled for a specific channel."""
        try:
            # Import here to avoid circular import
            from packages.core.constants import TRUST_ENABLED_CHANNELS

            # First check if channel is in the TRUST_ENABLED_CHANNELS list
            if channel_id in TRUST_ENABLED_CHANNELS:
                logger.info(f"[TRUST CHECK] Channel {channel_id} is in TRUST_ENABLED_CHANNELS")
                return True

            # Get channel details from DB
            channel_details = await self.channel_operations.get_channel_details(channel_id)
            if not channel_details:
                logger.info(f"[TRUST CHECK] No channel details found for {channel_id}")
                return False

            # Check if trust_endorsement_enabled is in the channel's enabled features
            features = channel_details.get("features", {})
            trust_enabled = features.get("trust_endorsement_enabled", False)

            logger.info(f"[TRUST CHECK] Channel {channel_id} features: {features}")
            logger.info(f"[TRUST CHECK] Trust endorsement enabled: {trust_enabled}")

            return trust_enabled
        except Exception as e:
            logger.error(f"Error checking trust endorsement for channel {channel_id}: {e}")
            return False

    def _remove_jira_line(self, content: str) -> str:
        """Remove any existing JIRA ticket line from the content."""
        # Match various JIRA line formats the AI might generate
        patterns = [
            r"\n*JIRA Ticket:.*(?:\n|$)",  # Any line starting with "JIRA Ticket:"
            r"\n*JIRA:.*(?:\n|$)",  # Any line starting with "JIRA:"
            r"\n*Ticket:.*(?:\n|$)",  # Any line starting with "Ticket:"
        ]

        for pattern in patterns:
            content = re.sub(pattern, "", content, flags=re.MULTILINE | re.IGNORECASE)

        return content.rstrip()

    def _extract_valid_jira_ticket(self, text: str) -> Optional[str]:
        """
        Extract the first valid JIRA ticket from text using approved projects only.

        Args:
            text: Text to search for JIRA tickets

        Returns:
            First valid JIRA ticket found or None
        """
        # Build pattern from valid ticket prefixes
        pattern = rf'\b({"|".join(VALID_JIRA_PROJECTS)})-[0-9]{{1,7}}(?![0-9])\b'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0).upper() if match else None

    async def _verify_real_activity(
        self,
        channel_id: str,
        channel_config: Dict[str, Any],
        original_last_message_ts: str = None,
        original_last_thread_ts: str = None,
        original_last_jira_ts: str = None,
    ) -> bool:
        """
        Strict verification of activity to prevent false positives during container restart.

        This does a fresh, strict check for activity using direct API calls rather than
        relying on potentially error-prone cached results or exception handling defaults.

        Uses original timestamps to avoid race condition where timestamps are updated
        before verification completes.

        Args:
            channel_id: Channel to verify
            channel_config: Channel configuration
            original_last_message_ts: Original message timestamp before updates
            original_last_thread_ts: Original thread timestamp before updates
            original_last_jira_ts: Original JIRA timestamp before updates

        Returns:
            True if there's verified real activity, False otherwise
        """
        try:
            # Get fresh channel details from DB for non-timestamp data
            fresh_channel = await self.channel_operations.query_ops.get_channel_details(channel_id)
            if not fresh_channel:
                logger.warning(f"Channel {channel_id} not found in DB during final verification")
                return False

            # Use original timestamps passed in to avoid race condition
            # Fall back to channel_config if originals not provided
            last_message_ts = original_last_message_ts or channel_config.get(
                "auto_status_last_message_ts", "0"
            )
            last_thread_ts = original_last_thread_ts or channel_config.get(
                "auto_status_last_thread_ts", "0"
            )
            last_jira_ts = original_last_jira_ts or channel_config.get(
                "auto_status_last_jira_comment_ts", "0"
            )
            last_run = fresh_channel.get("auto_status_last_run", 0)

            # If this appears to be first run but we have stored timestamps, be suspicious
            if last_message_ts == "0" and (last_run > 0 or last_thread_ts != "0"):
                logger.warning(
                    f"Channel {channel_id}: Suspicious first-run detection with existing timestamps"
                )
                return False

            # Check for real message activity with direct API call
            has_real_message_activity = False
            try:
                # Get bot user ID for filtering following existing pattern
                try:
                    bot_user_id = await self.secrets_manager.get_bot_slack_user_id_async()
                except Exception:
                    # For tests, use a fallback
                    bot_user_id = getattr(self.channel_msg_ops, "_bot_user_id", "U12345")

                # Simple direct check for recent messages
                url = f"{await self.channel_msg_ops.get_api_base_url()}/conversations.history"
                headers = self.channel_msg_ops.headers
                # Apply buffer to avoid precision mismatches in final verification
                oldest_ts_buffered = last_message_ts
                if last_message_ts and last_message_ts != "0":
                    try:
                        # Convert to float, subtract 5 seconds for safety, then back to string
                        # This ensures messages with slightly larger decimal timestamps aren't missed
                        oldest_ts_buffered = str(float(last_message_ts) - 5)
                        logger.debug(
                            f"Applied 5-second buffer to final verification: {last_message_ts} -> {oldest_ts_buffered}"
                        )
                    except (ValueError, TypeError):
                        # If conversion fails, use original value
                        oldest_ts_buffered = last_message_ts
                        logger.warning(
                            f"Could not apply buffer to final verification timestamp {last_message_ts}, using original"
                        )

                params = {"channel": channel_id, "limit": 10}
                # Only add oldest if we have a valid timestamp
                if oldest_ts_buffered != "0":
                    params["oldest"] = oldest_ts_buffered

                response = await self.channel_msg_ops._make_api_request(url, "GET", headers, params)
                response_data = orjson.loads(response["body"])

                if response_data.get("ok"):
                    messages = response_data.get("messages", [])
                    # Filter out bot messages and system messages
                    user_messages = []
                    for msg in messages:
                        # Skip bot messages
                        if msg.get("user") == bot_user_id or msg.get("bot_id"):
                            continue
                        # Skip system messages
                        if msg.get("subtype") in {
                            "channel_join",
                            "channel_leave",
                            "channel_topic",
                            "channel_purpose",
                            "channel_name",
                            "channel_archive",
                        }:
                            continue
                        # Skip messages that mention @Ketchup (unless they're thread replies)
                        text = msg.get("text", "")
                        if bot_user_id and f"<@{bot_user_id}>" in text:
                            # If it's a thread reply, keep it (might have valuable context)
                            if msg.get("thread_ts") and msg.get("ts") != msg.get("thread_ts"):
                                pass  # Keep thread replies
                            else:
                                continue  # Skip non-thread @Ketchup mentions

                        user_messages.append(msg)

                    # Check if any real user messages exist
                    if user_messages:
                        has_real_message_activity = True
                        logger.info(
                            f"Channel {channel_id}: Found {len(user_messages)} real user messages"
                        )
                    else:
                        logger.info(
                            f"Channel {channel_id}: No real user messages found in verification"
                        )

                else:
                    logger.error(
                        f"Channel {channel_id}: API error in final verification: {response_data.get('error')}"
                    )
                    return False  # Conservative: don't post on verification errors

            except Exception as e:
                logger.error(f"Channel {channel_id}: Exception in final message verification: {e}")
                return False  # Conservative: don't post on verification errors

            # Check for real thread activity
            has_real_thread_activity = False
            try:
                # Check thread activity using the existing method - handle both sync and async calls
                if callable(self.channel_msg_ops.check_recent_thread_activity):
                    # Check if it's async or sync
                    try:
                        thread_activity, _, _ = (
                            await self.channel_msg_ops.check_recent_thread_activity(
                                channel_id, last_thread_ts
                            )
                        )
                    except TypeError:
                        # If await fails, try sync call
                        thread_activity, _, _ = self.channel_msg_ops.check_recent_thread_activity(
                            channel_id, last_thread_ts
                        )
                else:
                    # Handle mock objects or other cases
                    result = self.channel_msg_ops.check_recent_thread_activity(
                        channel_id, last_thread_ts
                    )
                    if hasattr(result, "__await__"):
                        thread_activity, _, _ = await result
                    else:
                        thread_activity, _, _ = result

                if thread_activity:
                    has_real_thread_activity = True
                    logger.info(f"Channel {channel_id}: Found thread activity in verification")
                else:
                    logger.info(f"Channel {channel_id}: No thread activity found in verification")
            except Exception as e:
                logger.error(f"Channel {channel_id}: Exception in final thread verification: {e}")
                # Don't fail the whole check for thread errors, just mark as no thread activity
                has_real_thread_activity = False

            # Check for real JIRA activity
            has_real_jira_activity = False
            try:
                jira_ticket = fresh_channel.get("jira_ticket", "")
                if jira_ticket and jira_ticket != "NOT YET AVAILABLE":
                    latest_jira_ts = await self._get_latest_jira_comment_timestamp(jira_ticket)

                    # Check if there are newer JIRA comments
                    if latest_jira_ts and latest_jira_ts > last_jira_ts:
                        has_real_jira_activity = True
                        logger.info(f"Channel {channel_id}: Found newer JIRA comments")
                    else:
                        logger.info(f"Channel {channel_id}: No newer JIRA comments found")

            except Exception as e:
                logger.error(f"Channel {channel_id}: Exception in final JIRA verification: {e}")
                # Don't fail the whole check for JIRA errors, just mark as no JIRA activity
                has_real_jira_activity = False

            # Final decision: require at least one type of real activity
            if (
                not has_real_message_activity
                and not has_real_thread_activity
                and not has_real_jira_activity
            ):
                logger.info(f"Channel {channel_id}: No verified activity found in final check")
                return False

            logger.info(
                f"Channel {channel_id}: Final verification confirmed real activity (messages: {has_real_message_activity}, threads: {has_real_thread_activity}, JIRA: {has_real_jira_activity})"
            )
            return True

        except Exception as e:
            logger.error(f"Channel {channel_id}: Error in final activity verification: {e}")
            return False  # Conservative: don't post on verification errors
