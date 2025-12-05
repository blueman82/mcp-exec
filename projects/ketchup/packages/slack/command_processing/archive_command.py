"""
archive_command.py

This module contains the SlackArchiveCommand class,
which is used to process the `/ketchup archive` command.
"""

from typing import Optional, cast

from packages.core.logging import setup_logger
from packages.core.time_utils import convert_days_to_epoch
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore
from packages.slack.blockkits.base import BlockKitBuilder
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_restore_ops import SlackChannelRestoreOps
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_parameters.models import (
    ArchiveCommandParams,
    CommandParams,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SlackArchiveCommand(BaseCommandHandler):
    """
    This class is responsible for processing the `/ketchup archive` command,
    which archives Slack channels.
    """

    def __init__(
        self,
        channel_info_ops: ChannelInfoOps,
        slack_posting_handler: SlackPostingHandler,
        archive_ops: SlackChannelArchiveOps,
        dynamodb_store: DynamoDBStore,
        block_kit_builder: BlockKitBuilder,
        channel_restore_ops: SlackChannelRestoreOps,
        user_store: UserStore,
    ):
        """
        Initialize the SlackArchiveCommand class.

        Args:
            channel_info_ops: Service for channel info lookups.
            slack_posting_handler: Handler for posting messages to Slack
            archive_ops: Service for archiving/unarchiving channels
            dynamodb_store: DynamoDB store for persistence
            block_kit_builder: Service for creating Slack block kit messages
            channel_restore_ops: Handler for restoring archived channels
            user_store: Store for user preference data.
        """
        super().__init__()
        self.channel_info_ops = channel_info_ops
        self.slack_posting_handler = slack_posting_handler
        self.archive_ops = archive_ops
        self.dynamodb_store = dynamodb_store
        self.block_kit_builder = block_kit_builder
        self.channel_restore_ops = channel_restore_ops
        self.user_store = user_store
        logger.info("SlackArchiveCommand initialized.")

    async def process_archive_params(
        self,
        params: CommandParams,
        user_id: str,
        incoming_channel: str,
        response_url: Optional[str] = None,
    ) -> None:
        """
        Process the archive command parameters and execute the archive operation.

        Args:
            params: The parsed command parameters
            user_id: The ID of the user who initiated the command
            incoming_channel: The ID of the channel where the command was issued
            response_url: Optional URL for sending delayed responses
        """
        try:
            # Cast to ArchiveCommandParams for type safety
            archive_params = cast(ArchiveCommandParams, params)
            logger.info("Processing archive request for %s days", archive_params.archive_days)

            # Convert days to epoch threshold
            epoch_threshold = convert_days_to_epoch(archive_params.archive_days)
            logger.info(
                "Converted %s days into epoch threshold: %s.",
                archive_params.archive_days,
                epoch_threshold,
            )

            # Send initial response
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=f"Retrieving archived channels from the last {archive_params.archive_days} {'day' if archive_params.archive_days == 1 else 'days'}... :mag:",
                response_url=response_url,
            )

            # --- Fetch User Preferences ---
            product_preference = "all_products"  # Default
            try:
                user_data = await self.user_store.get_user(user_id)
                logger.info("User data fetched for archive command %s: %s", user_id, user_data)
                if user_data and "preferences" in user_data:
                    user_prefs = user_data["preferences"]
                    logger.info(
                        "User preferences extracted for archive command %s: %s",
                        user_id,
                        user_prefs,
                    )
                    product_preference = user_prefs.get("product_focus", ["all_products"])[0]
                else:
                    logger.info(
                        "No preferences found for user %s in archive command, using default 'all_products'.",
                        user_id,
                    )
            except Exception as e:
                logger.error(
                    "Error fetching preferences for user %s in archive command: %s. Using default 'all_products'.",
                    user_id,
                    e,
                )
            logger.info(
                "Final product preference for archive command user %s: %s",
                user_id,
                product_preference,
            )
            # --- End Fetch User Preferences ---

            # Get all archived channels from DynamoDB
            archived_channels = await self.dynamodb_store.get_all_channel_details(
                archive_lookup=True,
                days_threshold=archive_params.archive_days,
                product_preference=product_preference,
            )

            if not archived_channels:
                await self.slack_posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message="No archived channels found.",
                    response_url=response_url,
                )
                return

            # Convert archived_channels to list format expected by ArchiveMessageHandler
            channel_summaries = []
            for channel_id, details in archived_channels.items():
                summary = {
                    "channel_id": channel_id,
                    "channel_name": details.get("channel_name", "NOT YET AVAILABLE"),
                    "customer_name": details.get("customer_name", "NOT YET AVAILABLE"),
                    "jira_ticket": details.get("jira_ticket", "NOT YET AVAILABLE"),
                    "archived_at": details.get("archived_at", 0),
                }
                channel_summaries.append(summary)

            # Log the summaries for debugging
            logger.info("Sending channel summaries to BlockKit: %s", channel_summaries)

            # Send the response using the ArchiveMessageHandler
            await self.block_kit_builder.send_ketchup_archive_block_kit(
                response_url=response_url or incoming_channel,
                summaries=channel_summaries,
                incoming_channel=incoming_channel,
            )

        except Exception as e:
            logger.error("Error processing archive request: %s", str(e))
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=f"Error processing archive request: {str(e)}",
                response_url=response_url,
            )
