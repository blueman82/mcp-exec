"""
summary.py

Specialized handler for formatting and sending summary messages.

This module contains the SummaryMessageHandler class for handling
summary-type messages for multiple channels.
"""

import json
from typing import Any, Callable, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.slack.blockkits.handlers.blockkit_message_utils import (
    create_context_tooltip_block,
    create_message_blocks,
    enhance_message_for_fallback,
    format_message_body_with_response,
    format_message_header_with_channel_details,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SummaryMessageHandler:
    """
    Handles formatting and sending of summary messages.

    Responsibilities:
    - Process multiple channel summaries
    - Format messages with consistent structure
    - Send messages to Slack
    """

    def __init__(self):
        """Initialize the SummaryMessageHandler."""
        self._posting_handler = None
        self._channel_details_getter = None
        self._fallback_getter = None
        self._build_feedback_blocks = None
        self._block_kit_builder = None

    def configure(
        self,
        posting_handler: SlackPostingHandler,
        channel_details_getter: Callable,
        fallback_getter: Callable,
        build_feedback_blocks: Optional[Callable] = None,
        block_kit_builder: Optional[object] = None,
    ):
        """
        Configure the handler with dependencies.

        Args:
            posting_handler: Handler for posting messages to Slack
            channel_details_getter: Function to get channel details
            fallback_getter: Function to get channel details with fallback
            build_feedback_blocks: Optional function to build feedback blocks
            block_kit_builder: Optional block kit builder
        """
        self._posting_handler = posting_handler
        self._channel_details_getter = channel_details_getter
        self._fallback_getter = fallback_getter
        self._build_feedback_blocks = build_feedback_blocks
        self._block_kit_builder = block_kit_builder

    async def send_message(
        self,
        combined_command: str,
        response_url: str,
        summaries: List[Dict[str, Any]],
        target_channel: str,
    ) -> None:
        """
        Send summary messages for multiple channels.

        Args:
            combined_command: The original Slack command
            response_url: URL to send the response to
            summaries: List of summaries to process
            target_channel: The target channel ID
        """
        # If block_kit_builder is available, use it for rich Block Kit output
        if self._block_kit_builder is not None:
            await self._block_kit_builder.send_ketchup_summary_block_kit(
                combined_command=combined_command,
                response_url=response_url,
                summaries=summaries,
                target_channel=target_channel,
            )
            return
        logger.info("Processing %d summaries", len(summaries))
        # First, try to get channel details for the target channel
        try:
            channel_info = await self._fallback_getter(target_channel)
        except Exception as e:
            logger.error("Failed to get channel details: %s", str(e))
            channel_info = {
                "channel_id": target_channel,
                "channel_name": "unknown",
                "customer_name": "NOT YET AVAILABLE",
                "jira_ticket": "NOT YET AVAILABLE",
            }

        # Process each summary
        for summary in summaries:
            # Get the explicit type if provided, otherwise default
            summary_type_to_use = summary.get("type", "general")

            # Prepare the summary content dictionary for _process_summary
            # Handle both old and new dictionary structures
            summary_content_dict = {
                "content": summary.get("summary", summary.get("content", "No content provided"))
            }

            await self._process_summary(
                response_url=response_url,
                summary=summary_content_dict,  # Pass the standardized content dict
                channel_info=channel_info,
                summary_type=summary_type_to_use,  # Pass the explicit type
            )

    async def _process_summary(
        self,
        response_url: str,
        summary: Dict[str, Any],
        channel_info: Dict[str, Any],
        summary_type: str,
    ) -> None:
        """
        Process and send a single summary.

        Args:
            response_url: URL to send the response to
            summary: The summary data (should contain 'content' key)
            channel_info: Channel information
            summary_type: Type of summary ('short', 'long', etc.)
        """
        summary_content = summary.get("content", "No content provided")
        # Restore title to include the summary type
        summary_title = f"Ketchup App Summary - {summary_type.capitalize()}"

        # Format the message with all components
        header_str = format_message_header_with_channel_details(
            title=summary_title,
            channel_detail=channel_info,
        )
        body_str = format_message_body_with_response(
            content=summary_content,
        )
        header_blocks = create_message_blocks(header_str)
        body_blocks = create_message_blocks(body_str)

        # Add Edit button if channel_info is available
        edit_button_block = None
        if channel_info:
            edit_button_block = {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Edit Customer/Ticket"},
                        "action_id": "edit_channel_metadata",
                        "value": json.dumps(
                            {
                                "channel_id": channel_info.get("channel_id", ""),
                                "customer_name": channel_info.get("customer_name", ""),
                                "jira_ticket": channel_info.get("jira_ticket", ""),
                                # 'ts' will be added after posting
                            }
                        ),
                    }
                ],
            }

        # Add feedback blocks if available
        feedback_blocks = []
        if self._build_feedback_blocks:
            try:
                feedback_blocks = await self._build_feedback_blocks(
                    channel_id=channel_info.get("channel_id", "unknown"),
                    summary_type=summary_type,
                    command_output=summary_content,
                )
            except Exception as e:
                logger.error("Failed to build feedback blocks: %s", str(e))

        # Combine message blocks with edit button, tooltip, and feedback blocks
        combined_blocks = header_blocks
        if edit_button_block:
            combined_blocks.append(edit_button_block)
            combined_blocks.append(create_context_tooltip_block())
        combined_blocks += body_blocks
        combined_blocks += feedback_blocks

        # Send the message and capture the ts
        slack_response = None
        try:
            if response_url.startswith("http"):
                logger.info("Posting summary message to response URL")
                slack_response = await self._posting_handler.post_message(
                    response_url=response_url,
                    message=body_str,  # fallback string
                    blocks=combined_blocks,
                )
            else:
                # Use as channel ID
                logger.info("Posting summary message to channel ID")
                slack_response = await self._posting_handler.post_message(
                    channel_id=response_url,
                    message=body_str,  # fallback string
                    blocks=combined_blocks,
                )
        except Exception as e:
            logger.error("Failed to send summary message: %s", str(e))
            # Try text-only fallback
            try:
                if response_url.startswith("http"):
                    slack_response = await self._posting_handler.post_message(
                        response_url=response_url,
                        message=enhance_message_for_fallback(body_str),
                    )
                else:
                    slack_response = await self._posting_handler.post_message(
                        channel_id=response_url,
                        message=enhance_message_for_fallback(body_str),
                    )
                logger.info("Sent summary message as text-only fallback")
            except Exception as fallback_error:
                logger.error("Text-only fallback also failed: %s", str(fallback_error))
        # Extract ts and update Edit button if possible
        ts = None
        if isinstance(slack_response, dict):
            ts = slack_response.get("ts")
        # If ts is available, update the Edit button value
        if edit_button_block and ts:
            edit_button_block["elements"][0]["value"] = json.dumps(
                {
                    "channel_id": channel_info.get("channel_id", ""),
                    "customer_name": channel_info.get("customer_name", ""),
                    "jira_ticket": channel_info.get("jira_ticket", ""),
                    "ts": ts,
                }
            )
