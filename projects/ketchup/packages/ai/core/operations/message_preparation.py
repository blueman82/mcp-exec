"""
message_preparation.py

Handles preparing the list of messages to be sent to the OpenAI API,
including fetching channel history and formatting.
"""

import asyncio
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from packages.ai.cost_calculator import TokenTracker
from packages.ai.model_prompts import get_prompt_for_command
from packages.core.constants import USE_PIPELINE_PROCESSING
from packages.core.exceptions import MessagePreparationError
from packages.core.logging import setup_logger
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps

logger = setup_logger(__name__)


def time_window_to_oldest_ts(time_window: str) -> str:
    """Convert a time_window preference to a Slack oldest_ts value.

    Args:
        time_window: One of "past_2_hours", "past_24_hours", "all_time".

    Returns:
        A Slack timestamp string. "0" means fetch all messages.
    """
    now = time.time()
    mapping = {
        "past_2_hours": now - 7200,
        "past_24_hours": now - 86400,
    }
    ts = mapping.get(time_window)
    return str(ts) if ts else "0"


class MessagePreparer:
    """Prepares messages for OpenAI API calls, managing context and token limits."""

    def __init__(
        self,
        token_tracker: TokenTracker,
        channel_msg_ops: SlackChannelMessageOps,
        channel_info_ops: ChannelInfoOps,
    ):
        """
        Initialize MessagePreparer.

        Args:
            token_tracker: Token tracker instance.
            channel_msg_ops: Slack channel message operations instance.
            channel_info_ops: Instance for single channel info lookup.
        """
        self.token_tracker = token_tracker
        self.channel_msg_ops = channel_msg_ops
        self.channel_info_ops = channel_info_ops

    async def prepare_messages(
        self,
        combined_command: str,
        user_id: str,
        incoming_channel: str,
        passed_channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,  # channel_name seems less critical if we fetch details
        query_text: Optional[str] = None,
        oldest_ts: str = "0",
        normalized_user_preferences: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, str]], Optional[Dict[str, Any]]]:
        """
        Prepare messages for OpenAI based on command parameters.

        Fetches channel details and messages, formats them with instructions.

        Args:
            combined_command: The verified command string.
            user_id: The Slack user ID initiating the request.
            incoming_channel: The channel where the command was issued.
            passed_channel_id: The target channel ID (if provided explicitly).
            channel_name: The name of the channel (potentially unused if lookup succeeds).
            query_text: The query text for specific query commands.
            oldest_ts: Slack timestamp for filtering messages. "0" means fetch all messages.
            normalized_user_preferences: Optional dictionary of normalized user preferences.

        Returns:
            Tuple containing:
            - List of message objects for OpenAI API.
            - Dictionary with target channel information including original archive status.
              Returns None for channel_info if preparation fails.
        """
        # Get the appropriate prompt for this command using the imported function
        instructions = get_prompt_for_command(
            combined_command, query_text, user_prefs=normalized_user_preferences
        )
        if not instructions:
            error_message = f"No instructions generated for command: {combined_command}"
            logger.error(error_message)
            # Raise the specific exception instead of returning a structure
            raise MessagePreparationError(error_message)

        # Determine target channel ID
        target_channel_id = passed_channel_id if passed_channel_id else incoming_channel
        logger.info(
            "Determined target channel for message preparation: %s",
            target_channel_id,
        )

        # Concurrently fetch channel details and messages
        try:
            # Choose fetch method based on feature flag
            if USE_PIPELINE_PROCESSING:
                fetch_task = self.channel_msg_ops.fetch_channel_messages_collected(
                    channel_id=target_channel_id,
                    oldest_ts=oldest_ts,
                    use_parallel_pagination=True,
                )
            else:
                fetch_task = self.channel_msg_ops.fetch_channel_messages(
                    channel_id=target_channel_id,
                    oldest_ts=oldest_ts,
                    use_parallel_pagination=True,
                )

            results = await asyncio.gather(
                self.channel_info_ops.get_channel_info_from_api(target_channel_id),
                fetch_task,
                return_exceptions=True,
            )
            channel_details, messages_list = results

            # Handle exceptions from gather
            if isinstance(channel_details, Exception):
                raise MessagePreparationError(
                    f"Could not access channel details for <#{target_channel_id}>. Error: {str(channel_details)}"
                ) from channel_details

            if isinstance(messages_list, Exception):
                raise MessagePreparationError(
                    f"Could not fetch messages from <#{target_channel_id}>. Error: {str(messages_list)}"
                ) from messages_list

            if not channel_details:
                raise MessagePreparationError(
                    f"Failed to retrieve channel details for {target_channel_id}"
                )

            target_channel_name = channel_details.get("name", "unknown_channel")
            if not channel_details.get("is_member"):
                raise MessagePreparationError(
                    f"Ketchup is not a member of channel {target_channel_id} ({target_channel_name})"
                )

            if not messages_list:
                logger.warning(
                    "No messages found in channel %s (%s)",
                    target_channel_id,
                    target_channel_name,
                )
                messages_list = ["(No messages found in channel)"]

        except MessagePreparationError as e:
            logger.error(
                "Error during message preparation for channel %s: %s",
                target_channel_id,
                str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred during concurrent message preparation for channel %s: %s",
                target_channel_id,
                str(e),
                exc_info=True,
            )
            raise MessagePreparationError(
                f"An unexpected error occurred while preparing messages for <#{target_channel_id}>."
            ) from e

        # Combine messages and add channel reference
        reference_text = f"\n\n(Reference: <#{target_channel_id}|{target_channel_name}>)"
        # Avoid extra newlines if the list only contains the placeholder
        if messages_list == ["(No messages found in channel)"]:
            combined_text = (
                messages_list[0] + reference_text.lstrip()
            )  # Remove leading newline from ref
        else:
            messages_list.append(reference_text)
            combined_text = "\n".join(messages_list)

        # Prepare channel info dictionary for potential re-archiving
        channel_info = {
            "target_channel": target_channel_id,
            "channel_name": target_channel_name,
            "originally_archived": channel_details.get("is_archived", False),
        }

        # Return formatted messages and channel info
        return [
            {"role": "system", "content": instructions},
            {"role": "user", "content": combined_text},
        ], channel_info

    async def prepare_messages_for_auto_status(
        self,
        channel_id: str,
        since_ts: Optional[str] = None,
        suppress_notification: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Prepare messages for auto-status generation with incremental fetching support.

        Args:
            channel_id: The channel to get messages from
            since_ts: Timestamp to fetch messages after (for incremental updates), None for ALL messages
            suppress_notification: Suppress token limit warnings for automated runs

        Returns:
            Tuple of (formatted_messages, channel_metadata)
            channel_metadata includes 'latest_ts' for tracking and separate activity indicators

        Note: Bot message filtering happens automatically in the channel_msg_ops layer
        """
        try:
            # Check for thread activity first if we have a since_ts
            has_thread_activity = False
            active_thread_timestamps = []

            if since_ts:
                has_thread_activity, _, active_thread_timestamps = (
                    await self.channel_msg_ops.check_recent_thread_activity(channel_id, since_ts)
                )

            # Fetch messages (with threads if there's thread activity)
            if USE_PIPELINE_PROCESSING:
                messages_list = await self.channel_msg_ops.fetch_channel_messages_collected(
                    channel_id=channel_id,
                    oldest_ts=since_ts if since_ts else "0",
                    limit=200,
                    additional_thread_timestamps=(
                        active_thread_timestamps if has_thread_activity else None
                    ),
                )
            else:
                messages_list = await self.channel_msg_ops.fetch_channel_messages(
                    channel_id=channel_id,
                    oldest_ts=since_ts if since_ts else "0",
                    limit=200,
                    additional_thread_timestamps=(
                        active_thread_timestamps if has_thread_activity else None
                    ),
                )

            # To determine if we have channel messages, we need to check if there are any
            # messages that are NOT thread replies. Since we can't inspect message metadata
            # in formatted messages, we use a heuristic.
            has_channel_messages = False

            if since_ts:
                # To accurately detect channel messages, fetch without thread expansion
                if USE_PIPELINE_PROCESSING:
                    channel_check_messages = (
                        await self.channel_msg_ops.fetch_channel_messages_collected(
                            channel_id=channel_id,
                            oldest_ts=since_ts,
                            limit=200,
                            additional_thread_timestamps=None,  # No thread expansion
                        )
                    )
                else:
                    channel_check_messages = await self.channel_msg_ops.fetch_channel_messages(
                        channel_id=channel_id,
                        oldest_ts=since_ts,
                        limit=200,
                        additional_thread_timestamps=None,  # No thread expansion
                    )

                # If we get messages without thread expansion:
                # - Could be new channel posts
                # - Could be parent messages of threads with new activity
                # Conservative approach: only mark as channel messages if:
                # 1. We have no thread activity (so any messages are channel messages), OR
                # 2. We have more messages than active threads (excess must be channel messages)
                if not has_thread_activity:
                    # No thread activity, so any messages are channel messages
                    has_channel_messages = len(channel_check_messages) > 0
                else:
                    # We have thread activity. Only mark as having channel messages if
                    # we have MORE messages than active threads (the excess are channel messages)
                    has_channel_messages = len(channel_check_messages) > len(
                        active_thread_timestamps
                    )
            else:
                # No since_ts (first run), any messages count as channel activity
                has_channel_messages = len(messages_list) > 0

            # Messages already fetched above with appropriate thread expansion

            if not messages_list:
                return "No messages found", {
                    "latest_ts": since_ts or "0",
                    "has_channel_messages": False,
                    "has_thread_activity": has_thread_activity,
                }

            # Get the actual latest message timestamp from channel_msg_ops
            latest_ts = self.channel_msg_ops.latest_message_ts or since_ts or "0"

            # Join messages into a single string
            formatted_messages = "\n".join(messages_list) if messages_list else "No messages found"

            # Collapse large code blocks to reduce noise from pasted error logs
            formatted_messages = self._collapse_large_code_blocks(formatted_messages)

            # Return formatted messages and enhanced metadata
            return formatted_messages, {
                "latest_ts": latest_ts,
                "has_thread_activity": has_thread_activity,
                "has_channel_messages": has_channel_messages,
                "message_count": len(messages_list),
                "thread_count": (len(active_thread_timestamps) if active_thread_timestamps else 0),
            }

        except Exception as e:
            logger.error(f"Error preparing messages for auto-status: {e}")
            return "Error fetching messages", {
                "latest_ts": since_ts or "0",
                "has_channel_messages": False,
                "has_thread_activity": False,
            }

    @staticmethod
    def _collapse_large_code_blocks(text: str, min_lines: int = 5) -> str:
        """Collapse code blocks with 5+ lines into a one-line summary.

        Large pasted error logs dominate LLM attention and get misinterpreted
        as current state. This replaces them with a brief description.
        """

        def _summarise_block(match: re.Match) -> str:
            content = match.group(1)
            lines = [ln for ln in content.strip().splitlines() if ln.strip()]
            if len(lines) < min_lines:
                return match.group(0)  # leave small blocks alone
            # Count distinct error-like patterns for the summary
            error_keywords = {"error", "failed", "exception", "timeout", "refused"}
            has_errors = any(kw in content.lower() for kw in error_keywords)
            label = "error/log" if has_errors else "log"
            return f"[QUOTED {label.upper()}: {len(lines)} lines omitted — see original message]"

        return re.sub(r"```(.*?)```", _summarise_block, text, flags=re.DOTALL)
