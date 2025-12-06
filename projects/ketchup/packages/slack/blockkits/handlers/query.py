"""
query.py

Specialized handler for formatting and sending query messages.

This module contains the QueryMessageHandler class for handling
query-type messages with responses.
"""

import json
from typing import Callable, Optional

from packages.core.logging import setup_logger
from packages.slack.blockkits.formatters import clean_response_text
from packages.slack.blockkits.handlers.blockkit_message_utils import (
    create_context_tooltip_block,
    create_message_blocks,
    enhance_message_for_fallback,
    format_message_body_with_response,
    format_message_header_with_channel_details,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class QueryMessageHandler:
    """
    Handles formatting and sending of query messages.

    Responsibilities:
    - Clean up response text to remove duplicated elements
    - Retrieve channel details
    - Format messages with consistent structure
    - Send messages to Slack
    """

    def __init__(self):
        """Initialize the QueryMessageHandler."""
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
        response_text: str,
        query: Optional[str] = None,
        target_channel: Optional[str] = None,
    ) -> None:
        """
        Send a formatted query message to Slack.

        Args:
            combined_command: The original Slack command
            response_url: URL to send the response to
            response_text: The text response from the AI
            query: The query string from the user
            target_channel: The target channel ID
        """
        # If block_kit_builder is available, use it for rich Block Kit output
        if self._block_kit_builder is not None:
            await self._block_kit_builder.send_ketchup_query_block_kit(
                combined_command=combined_command,
                response_url=response_url,
                response_text=response_text,
                query=query,
                target_channel=target_channel,
            )
            return

        # Clean response text to remove repetitions
        cleaned_response = clean_response_text(response_text, query)
        command_type = combined_command.split(" ")[1]

        # Get channel details if target channel is provided
        channel_details = None
        if target_channel:
            try:
                channel_details = await self._fallback_getter(target_channel)
            except Exception as e:
                logger.error("Failed to get channel details: %s", str(e))
                # Continue with None channel_details

        # Format the message with the cleaned response
        # Use a consistent title rather than showing the raw command
        title = "Ketchup App Query Response"
        header_str = format_message_header_with_channel_details(
            title=title,
            channel_detail=channel_details,
            query=query,
        )
        body_str = format_message_body_with_response(
            content=cleaned_response,
            query=query,
        )
        header_blocks = create_message_blocks(header_str)
        body_blocks = create_message_blocks(body_str)

        # Add Edit button if channel details are available
        edit_button_block = None
        if channel_details:
            edit_button_block = {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Edit Customer/Ticket"},
                        "action_id": "edit_channel_metadata",
                        "value": json.dumps(
                            {
                                "channel_id": channel_details.get("channel_id", ""),
                                "customer_name": channel_details.get("customer_name", ""),
                                "jira_ticket": channel_details.get("jira_ticket", ""),
                            }
                        ),
                    }
                ],
            }

        # Add feedback blocks if available
        feedback_blocks = []
        if self._build_feedback_blocks and target_channel:
            try:
                feedback_blocks = await self._build_feedback_blocks(
                    channel_id=target_channel,
                    summary_type=command_type,
                    command_output=cleaned_response,
                )
            except Exception as e:
                logger.error("Failed to build feedback blocks: %s", str(e))

        # Combine blocks: header, edit button, tooltip, body, feedback
        combined_blocks = header_blocks
        if edit_button_block:
            combined_blocks.append(edit_button_block)
            combined_blocks.append(create_context_tooltip_block())
        combined_blocks += body_blocks
        combined_blocks += feedback_blocks

        # Send the message
        try:
            if response_url.startswith("http"):
                logger.info("Posting query message to response URL")
                await self._posting_handler.post_message(
                    response_url=response_url,
                    message=body_str,  # fallback string
                    blocks=combined_blocks,
                )
            else:
                # Use as channel ID
                logger.info("Posting query message to channel ID")
                await self._posting_handler.post_message(
                    channel_id=response_url,
                    message=body_str,  # fallback string
                    blocks=combined_blocks,
                )
        except Exception as e:
            logger.error("Failed to send query message: %s", str(e))
            # Try text-only fallback with enhanced formatting
            try:
                if response_url.startswith("http"):
                    await self._posting_handler.post_message(
                        response_url=response_url,
                        message=enhance_message_for_fallback(body_str),
                    )
                else:
                    await self._posting_handler.post_message(
                        channel_id=response_url,
                        message=enhance_message_for_fallback(body_str),
                    )
                logger.info("Sent query message as text-only fallback")
            except Exception as fallback_error:
                logger.error("Text-only fallback also failed: %s", str(fallback_error))
