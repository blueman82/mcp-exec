"""
lookup.py

Specialized handler for formatting and sending lookup messages.

This module contains the LookupMessageHandler class for handling
lookup-type messages with channel lists.
"""

from typing import Any, Callable, Dict, List

from packages.core.logging import setup_logger
from packages.slack.blockkits.handlers.blockkit_message_utils import (
    create_context_tooltip_block,
    format_channel_list_block,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class LookupMessageHandler:
    """
    Handles formatting and sending of lookup messages.

    Responsibilities:
    - Format channel lists for display
    - Send messages to Slack
    """

    def __init__(self):
        """Initialize the LookupMessageHandler."""
        self._posting_handler = None
        self._channel_details_getter = None

    def configure(
        self, posting_handler: SlackPostingHandler, channel_details_getter: Callable
    ):
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
        channels_list: List[Dict[str, Any]],
        include_helper_text: bool = False,
    ) -> None:
        """
        Send a formatted list of channels as a lookup result, with an Edit button for each channel.

        Args:
            response_url: URL to send the response to
            channels_list: List of channel information
            include_helper_text: Whether to include helper instructions at the end
        """
        # Build Block Kit blocks for each channel
        message_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Channel Lookup Results*"},
            }
        ]
        for idx, channel in enumerate(channels_list, 1):
            section_block, actions_block = format_channel_list_block(idx, channel)
            message_blocks.append(section_block)
            message_blocks.append(actions_block)
        # Add tooltip context block
        message_blocks.append(create_context_tooltip_block())

        # Add helper instructions if requested
        if include_helper_text and channels_list:
            message_blocks.append({"type": "divider"})
            message_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "For a quick status check, use:\n"
                            "`/ketchup status <Channel ID>`\n\n"
                            "Need something specific? Ask with:\n"
                            "`/ketchup query <Channel ID> <question>`\n\n"
                            "To see a detailed incident summary:\n"
                            "`/ketchup report <Channel ID>`"
                        ),
                    },
                }
            )
        # Send the message
        try:
            if response_url.startswith("http"):
                logger.info("Posting lookup message to response URL")
                await self._posting_handler.post_message(
                    response_url=response_url,
                    message="Channel Lookup Results",
                    blocks=message_blocks,
                )
            else:
                # Use as channel ID
                logger.info("Posting lookup message to channel ID")
                await self._posting_handler.post_message(
                    channel_id=response_url,
                    message="Channel Lookup Results",
                    blocks=message_blocks,
                )
        except Exception as e:
            logger.error("Failed to send lookup message: %s", str(e))
            # Try text-only fallback
            try:
                if response_url.startswith("http"):
                    await self._posting_handler.post_message(
                        response_url=response_url, message="Channel Lookup Results"
                    )
                else:
                    await self._posting_handler.post_message(
                        channel_id=response_url, message="Channel Lookup Results"
                    )
                logger.info("Sent lookup message as text-only fallback")
            except Exception as fallback_error:
                logger.error("Text-only fallback also failed: %s", str(fallback_error))
