"""
archive.py

Specialized handler for formatting and sending archive messages.

This module contains the ArchiveMessageHandler class for handling
archive-type messages with channel lists.
"""

import re
from typing import Any, Callable, Dict, List, Optional

from packages.core.constants import (
    MAX_CHANNELS_PER_TEXT_BATCH,
    MAX_TEXT_BATCHES,
    TEXT_BATCH_CHAR_LIMIT,
)
from packages.core.exceptions import InvalidBlocksForResponseUrlError
from packages.core.logging import setup_logger
from packages.core.time_utils import convert_timestamp_to_utc
from packages.slack.blockkits.formatters import format_channel_list
from packages.slack.blockkits.handlers.blockkit_message_utils import (
    create_context_tooltip_block,
    format_channel_list_block,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class ArchiveMessageHandler:
    """
    Handles formatting and sending of archive messages.

    Responsibilities:
    - Format channel lists for display
    - Send messages to Slack
    """

    def __init__(self) -> None:
        """Initialize the ArchiveMessageHandler."""
        self._posting_handler: Optional[SlackPostingHandler] = None
        self._channel_details_getter: Optional[Callable[..., Any]] = None

    def configure(
        self,
        posting_handler: SlackPostingHandler,
        channel_details_getter: Callable[..., Any],
    ) -> None:
        """
        Configure the handler with dependencies.

        Args:
            posting_handler: Handler for posting messages to Slack
            channel_details_getter: Function to get channel details
        """
        self._posting_handler = posting_handler
        self._channel_details_getter = channel_details_getter

    async def send_message(
        self,
        response_url: str,
        summaries: List[Dict[str, Any]],
        incoming_channel: Optional[str] = None,
    ) -> None:
        """
        Send archived channel summaries to Slack, using Block Kit if possible, otherwise falling back to text batching.

        Args:
            response_url (str): URL or Channel ID to send the response to.
            summaries (List[Dict[str, Any]]): List of channel summaries.
            incoming_channel (Optional[str]): Original channel ID for fallback posting.

        Returns:
            None
        """
        channels_list = self._get_sorted_channels(summaries)
        # Use Block Kit blocks with Edit button for each channel
        message_blocks = []
        for idx, channel in enumerate(channels_list, 1):
            section_block, actions_block = format_channel_list_block(idx, channel)
            message_blocks.append(section_block)
            message_blocks.append(actions_block)
        if message_blocks:
            message_blocks.append(create_context_tooltip_block())
        formatted_list = format_channel_list(
            title="Archived Channels", channels=channels_list, include_archive_time=True
        )
        try:
            await self._send_block_kit(
                response_url, incoming_channel, formatted_list, message_blocks
            )
            logger.info("Successfully sent archive message with blocks.")
        except InvalidBlocksForResponseUrlError as ibe:
            logger.warning(
                "Posting archive message with blocks failed due to invalid blocks: %s. Attempting text-only fallback via response_url.",
                str(ibe),
            )
            if response_url.startswith("http"):
                await self._send_fallback_batches(response_url, channels_list)
            else:
                logger.error(
                    "Cannot send text-only fallback for invalid blocks as no response_url was available."
                )
        except Exception as e:
            logger.error("Failed to send archive message (initial attempt): %s", str(e))
            await self._send_general_text_fallback(response_url, incoming_channel, formatted_list)

    def _get_sorted_channels(self, summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Return channels sorted by archived_at descending.

        Args:
            summaries (List[Dict[str, Any]]): List of channel summary dicts.

        Returns:
            List[Dict[str, Any]]: Sorted list of channel dicts (most recent archived first).
        """
        return sorted(
            [summary for summary in summaries if "channel_id" in summary],
            key=lambda x: float(x.get("archived_at", 0)),
            reverse=True,
        )

    async def _send_block_kit(
        self,
        response_url: str,
        incoming_channel: Optional[str],
        formatted_list: str,
        message_blocks: List[Dict[str, Any]],
    ) -> None:
        """
        Send the block kit message, handling response_url and channel fallback.

        Args:
            response_url (str): Slack response URL or channel ID.
            incoming_channel (Optional[str]): Fallback channel ID.
            formatted_list (str): Formatted channel list as text.
            message_blocks (List[Dict[str, Any]]): Block Kit blocks for the message.

        Returns:
            None
        """
        target_channel_id = None
        actual_response_url = None
        if response_url.startswith("http"):
            actual_response_url = response_url
            target_channel_id = incoming_channel
            logger.info(
                "Posting archive message to response URL, fallback channel: %s",
                target_channel_id,
            )
        else:
            target_channel_id = response_url
            actual_response_url = None
            logger.info(
                "Posting archive message directly to channel ID: %s",
                target_channel_id,
            )
        await self._posting_handler.post_message(
            channel_id=target_channel_id,
            response_url=actual_response_url,
            message=formatted_list,
            blocks=message_blocks,
        )

    async def _send_fallback_batches(
        self, response_url: str, channels_list: List[Dict[str, Any]]
    ) -> None:
        """
        Send fallback batches as ephemeral messages via response_url.

        Args:
            response_url (str): Slack response URL.
            channels_list (List[Dict[str, Any]]): Sorted list of channel dicts.

        Returns:
            None
        """
        actual_response_url = response_url
        try:
            logger.info("Starting text fallback batching for archive message.")
            total_channels = len(channels_list)
            logger.info("Total channels for fallback: %s", total_channels)
            header_text = f"*Archived CSOs (Fallback)*\nFound *{total_channels}* archived channels."
            try:
                await self._posting_handler.post_message(
                    response_url=actual_response_url,
                    message=header_text,
                )
            except Exception as e:
                logger.warning("Failed to send fallback header message: %s", str(e))
            batches = []
            remaining_channels = channels_list.copy()
            batch_num = 1
            total_processed_fallback = 0
            while remaining_channels and batch_num <= MAX_TEXT_BATCHES:
                current_batch_text = f"*Archived CSOs (Fallback Batch {batch_num})*\n\n"
                current_batch_channel_count = 0
                channels_in_this_batch = []
                channel_idx_in_remaining = 0
                while channel_idx_in_remaining < len(remaining_channels):
                    channel_to_add = remaining_channels[channel_idx_in_remaining]
                    global_idx = total_processed_fallback + current_batch_channel_count
                    channel_text_segment = self._format_channel_for_fallback(
                        global_idx,
                        channel_to_add,
                    )
                    temp_footer = (
                        f"\n_Generated by Ketchup. :ketchup: (Fallback Batch {batch_num})_"
                    )
                    potential_batch_text = current_batch_text + channel_text_segment + temp_footer
                    if (
                        len(potential_batch_text) > TEXT_BATCH_CHAR_LIMIT
                        or current_batch_channel_count >= MAX_CHANNELS_PER_TEXT_BATCH
                    ):
                        break
                    current_batch_text += channel_text_segment
                    channels_in_this_batch.append(channel_to_add)
                    current_batch_channel_count += 1
                    channel_idx_in_remaining += 1
                if not channels_in_this_batch:
                    logger.warning(
                        "Could not add any channels to fallback batch %s due to limits.",
                        batch_num,
                    )
                    break
                batches.append(
                    {
                        "text": current_batch_text,
                        "count": current_batch_channel_count,
                    }
                )
                total_processed_fallback += current_batch_channel_count
                logger.info(
                    "Created fallback batch %s with %s channels, %s chars (approx)",
                    batch_num,
                    current_batch_channel_count,
                    len(current_batch_text),
                )
                remaining_channels = remaining_channels[current_batch_channel_count:]
                batch_num += 1
            total_batches_created = len(batches)
            logger.info("Created %s fallback batches.", total_batches_created)
            for i, batch_data in enumerate(batches):
                final_header = f"*Archived CSOs (Fallback Batch {i+1}/{total_batches_created})*\n\n"
                body_text = batch_data["text"].replace(
                    f"*Archived CSOs (Fallback Batch {i+1})*\n\n", ""
                )
                final_footer = f"\n_Generated by Ketchup. :ketchup: (Fallback Batch {i+1}/{total_batches_created})_"
                final_batch_text = final_header + body_text + final_footer
                try:
                    await self._posting_handler.post_message(
                        response_url=actual_response_url,
                        message=final_batch_text,
                    )
                except Exception as batch_error:
                    logger.error(
                        "Failed to send fallback batch %s: %s",
                        i + 1,
                        str(batch_error),
                    )
                    break
            if remaining_channels:
                remaining_count = len(remaining_channels)
                notification_text = f"*Note:* Displayed {total_processed_fallback} of {total_channels} archived channels in {total_batches_created} fallback batches. {remaining_count} channels not shown due to message limit ({MAX_TEXT_BATCHES} batches max)."
                try:
                    await self._posting_handler.post_message(
                        response_url=actual_response_url,
                        message=notification_text,
                    )
                except Exception as note_error:
                    logger.warning(
                        "Failed to send fallback truncation notification: %s",
                        str(note_error),
                    )
        except Exception as fallback_error:
            logger.error(
                "Text-only response_url fallback also failed after invalid blocks: %s",
                str(fallback_error),
            )

    async def _send_general_text_fallback(
        self, response_url: str, incoming_channel: Optional[str], formatted_list: str
    ) -> None:
        """
        Send a general text-only fallback if all else fails.

        Args:
            response_url (str): Slack response URL or channel ID.
            incoming_channel (Optional[str]): Fallback channel ID.
            formatted_list (str): Formatted channel list as text.

        Returns:
            None
        """
        try:
            target_channel_id_fallback = None
            actual_response_url_fallback = None
            if response_url.startswith("http"):
                actual_response_url_fallback = response_url
                target_channel_id_fallback = incoming_channel
            else:
                target_channel_id_fallback = response_url
            logger.info("Attempting broader text-only fallback for archive message.")
            await self._posting_handler.post_message(
                channel_id=target_channel_id_fallback,
                response_url=actual_response_url_fallback,
                message=formatted_list,
            )
            logger.info("Sent archive message as general text-only fallback.")
        except Exception as fallback_error:
            logger.error("General text-only fallback also failed: %s", str(fallback_error))

    def _format_channel_for_fallback(self, idx: int, channel: Dict[str, Any]) -> str:
        """
        Format a single channel for fallback text batching, using continuous numbering (1., 2., etc) across batches.

        Args:
            idx (int): Global index of the channel (for numbering).
            channel (Dict[str, Any]): Channel summary dict.

        Returns:
            str: Formatted channel text for fallback batching.
        """
        number = idx + 1
        archived_at = channel.get("archived_at")
        formatted_archived_at = (
            convert_timestamp_to_utc(archived_at) if archived_at else "NOT YET AVAILABLE"
        )
        jira_ticket = channel.get("jira_ticket", "NOT YET AVAILABLE")

        # Format JIRA ticket as clickable link if valid
        formatted_jira_ticket = jira_ticket
        jira_pattern = r"^[A-Z]{2,10}-[0-9]{1,7}(?![0-9])$"
        if (
            jira_ticket
            and jira_ticket != "NOT YET AVAILABLE"
            and re.match(jira_pattern, jira_ticket, re.IGNORECASE)
        ):
            formatted_jira_ticket = (
                f"<https://jira.corp.adobe.com/browse/{jira_ticket}|{jira_ticket}>"
            )

        channel_text = (
            f"{number}. *Customer Name:* {channel.get('customer_name', 'NOT AVAILABLE')}\n"
        )
        channel_text += f"   • *Support Ticket:* {formatted_jira_ticket}\n"
        channel_text += f"   • *Channel:* <#{channel.get('channel_id', 'NOT AVAILABLE')}|{channel.get('channel_name', 'NOT YET AVAILABLE')}>\n"
        channel_text += f"   • *ID:* `{channel.get('channel_id', 'NOT AVAILABLE')}`\n"
        channel_text += f"   • *Archived:* `{formatted_archived_at}`\n"
        channel_text += "\n"
        return channel_text
