"""
base.py

Core BlockKitBuilder class using composition to delegate to specialized message handlers.

This module contains the main BlockKitBuilder class that composes all handlers
and provides a consistent interface for sending formatted messages to Slack.
"""

from typing import Any, Awaitable, Callable, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.slack.blockkits.handlers.archive import ArchiveMessageHandler
from packages.slack.blockkits.handlers.lookup import LookupMessageHandler

# Import handlers directly from their modules
from packages.slack.blockkits.handlers.query import QueryMessageHandler
from packages.slack.blockkits.handlers.report import ReportMessageHandler
from packages.slack.blockkits.handlers.status import StatusMessageHandler
logger = setup_logger(__name__)


class BlockKitBuilder:
    """
    Builds and sends formatted messages to Slack using specialized handlers.

    This class uses composition to delegate to specialized handlers for
    different message types while maintaining a consistent interface.
    """

    def __init__(self, posting_handler):
        """Initialize the BlockKitBuilder with a pre-initialized SlackPostingHandler."""
        self._posting_handler = posting_handler

        # Create specialized handlers
        self._query_handler = QueryMessageHandler()
        self._status_handler = StatusMessageHandler()
        self._report_handler = ReportMessageHandler()
        self._summary_handler = SummaryMessageHandler()
        self._lookup_handler = LookupMessageHandler()
        self._archive_handler = ArchiveMessageHandler()

        # Initialize dependencies
        self._channel_details_getter = None
        self._build_feedback_blocks = None

    def configure(
        self,
        channel_details_getter: Callable[..., Awaitable[Dict[str, Any]]],
        build_feedback_blocks_func: Optional[Callable] = None,
    ) -> None:
        """
        Configure the BlockKitBuilder and all handlers.

        Args:
            channel_details_getter: Function to get channel details
            build_feedback_blocks_func: Optional function to build feedback blocks
        """
        self._channel_details_getter = channel_details_getter
        self._build_feedback_blocks = build_feedback_blocks_func

        # Configure all handlers
        self._query_handler.configure(
            self._posting_handler,
            self._channel_details_getter,
            self._get_channel_details_with_fallback,
            self._build_feedback_blocks,
        )

        self._status_handler.configure(
            self._posting_handler,
            self._channel_details_getter,
            self._get_channel_details_with_fallback,
            self._build_feedback_blocks,
        )

        self._report_handler.configure(
            self._posting_handler,
            self._channel_details_getter,
            self._get_channel_details_with_fallback,
            self._build_feedback_blocks,
        )

        self._summary_handler.configure(
            self._posting_handler,
            self._channel_details_getter,
            self._get_channel_details_with_fallback,
            self._build_feedback_blocks,
        )

        self._lookup_handler.configure(self._posting_handler, self._channel_details_getter)

        self._archive_handler.configure(self._posting_handler, self._channel_details_getter)

    async def _get_channel_details_with_fallback(self, channel_id: str) -> Dict[str, Any]:
        """
        Get channel details with fallback mechanisms.

        Args:
            channel_id: Channel ID to look up

        Returns:
            Dict with channel details
        """
        if not self._channel_details_getter:
            logger.warning("No channel_details_getter configured")
            return {
                "channel_id": channel_id,
                "channel_name": "unknown",
                "customer_name": "NOT YET AVAILABLE",
                "jira_ticket": "NOT YET AVAILABLE",
            }

        try:
            channel_details = await self._channel_details_getter(channel_id)
            if channel_details:
                return channel_details
        except Exception as e:
            logger.warning("Failed to get channel details: %s", str(e))

        # Fallback with minimal information
        return {
            "channel_id": channel_id,
            "channel_name": "unknown",
            "customer_name": "NOT YET AVAILABLE",
            "jira_ticket": "NOT YET AVAILABLE",
        }

    # Public API methods that delegate to handlers

    async def send_ketchup_query_block_kit(
        self,
        combined_command: str,
        response_url: str,
        response_text: str,
        query: Optional[str] = None,
        target_channel: Optional[str] = None,
    ) -> None:
        """
        Send a query message with a response to a query.

        Args:
            combined_command: The original Slack command
            response_url: URL to send the response to
            response_text: The text response from the AI
            query: The query string from the user
            target_channel: The target channel ID
        """
        await self._query_handler.send_message(
            combined_command, response_url, response_text, query, target_channel
        )

    async def send_ketchup_status_block_kit(
        self,
        combined_command: str,
        response_url: str,
        response_text: str,
        query: Optional[str] = None,
        target_channel: Optional[str] = None,
        execution_channel: Optional[str] = None,
    ) -> None:
        """
        Send a status message.

        Args:
            combined_command: The original Slack command
            response_url: URL to send the response to
            response_text: The text response from the AI
            query: The query string from the user
            target_channel: The target channel ID
            execution_channel: The channel where the command was executed (for feedback blocks)
        """
        await self._status_handler.send_message(
            combined_command,
            response_url,
            response_text,
            query,
            target_channel,
            execution_channel,
        )

    async def send_ketchup_report_block_kit(
        self,
        combined_command: str,
        response_url: str,
        response_text: str,
        query: Optional[str] = None,
        target_channel: Optional[str] = None,
        execution_channel: Optional[str] = None,
    ) -> None:
        """
        Send a report message.

        Args:
            combined_command: The original Slack command
            response_url: URL to send the response to
            response_text: The text response from the AI
            query: The query string from the user
            target_channel: The target channel ID
            execution_channel: The channel where the command was executed (for feedback blocks)
        """
        await self._report_handler.send_message(
            combined_command,
            response_url,
            response_text,
            query,
            target_channel,
            execution_channel,
        )

    async def send_ketchup_summary_block_kit(
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
        await self._summary_handler.send_message(
            combined_command=combined_command,
            response_url=response_url,
            summaries=summaries,
            target_channel=target_channel,
        )

    async def send_ketchup_archive_block_kit(
        self,
        response_url: str,
        summaries: List[Dict[str, Any]],
        incoming_channel: Optional[str] = None,
    ) -> None:
        """
        Send archived channel summaries.

        Args:
            response_url: URL or Channel ID to send the response to
            summaries: List of channel summaries
            incoming_channel: Original channel ID for fallback posting
        """
        await self._archive_handler.send_message(
            response_url, summaries, incoming_channel=incoming_channel
        )

    async def send_ketchup_analyze_block_kit(
        self,
        channel_id: str,
        command_user_id: str,
        response_text: str,
        original_query: Optional[str] = None,
        is_public: bool = True,
        response_url: Optional[str] = None,
    ) -> dict:
        """
        Send an analyze message with BlockKit formatting.

        Args:
            channel_id: The channel ID to send to
            command_user_id: The user ID who invoked the command
            response_text: The analysis response text
            original_query: The original query that was analyzed
            is_public: Whether to send as public message
            response_url: Optional response URL for ephemeral messages

        Returns:
            Response from Slack API
        """
        # Analyze functionality deprecated - use status handler with friendly message
        deprecation_message = "The analyze command has been deprecated. Please use `/ketchup` to see available commands."
        return await self._status_handler.send_message(
            channel_id=channel_id,
            command_user_id=command_user_id,
            response_text=deprecation_message,
            original_query=original_query,
            is_public=is_public,
            response_url=response_url,
        )

    async def send_ketchup_analyze_error_block_kit(
        self,
        channel_id: str,
        command_user_id: str,
        error_message: str,
        original_query: Optional[str] = None,
        response_url: Optional[str] = None,
    ) -> dict:
        """
        Send an analyze error message with BlockKit formatting.

        Args:
            channel_id: The channel ID to send to
            command_user_id: The user ID who invoked the command
            error_message: The error message to display
            original_query: The original query that caused the error
            response_url: Optional response URL for ephemeral messages

        Returns:
            Response from Slack API
        """
        # Analyze functionality deprecated - use status handler with friendly error message
        deprecation_message = "The analyze command has been deprecated. Please use `/ketchup` to see available commands."
        return await self._status_handler.send_error_message(
            channel_id=channel_id,
            command_user_id=command_user_id,
            error_message=deprecation_message,
            original_query=original_query,
            response_url=response_url,
        )
