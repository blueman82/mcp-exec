"""
list_command.py

This module contains the SlackListCommand class,
which is used to process the `/ketchup list` command.
"""

from typing import Any, Dict, List, Optional

from packages.core.constants import FEEDBACK_CHANNEL, TEST_CHANNEL
from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore
from packages.slack.blockkits.base import BlockKitBuilder
from packages.slack.blockkits.handlers.lookup import LookupMessageHandler
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_membership_ops import (
    ChannelMembershipOps,
)
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_parameters.models import (
    CommandParams,
    ListCommandParams,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SlackListCommand(BaseCommandHandler):
    """
    This class is responsible for processing the `/ketchup list` command,
    which lists all channels where Ketchup is a member.
    """

    def __init__(
        self,
        channel_info_ops: ChannelInfoOps,
        channel_membership_ops: ChannelMembershipOps,
        slack_posting_handler: SlackPostingHandler,
        dynamodb_store: DynamoDBStore,
        block_kit_builder: BlockKitBuilder,
        user_store: UserStore,
        feedback_reactions_handler=None,
    ):
        """
        Initialize the SlackListCommand class with required dependencies.

        Args:
            channel_info_ops: Operations for channel information.
            channel_membership_ops: Operations for channel membership lookups.
            slack_posting_handler: Service for posting messages to Slack.
            dynamodb_store: Service for interacting with DynamoDB.
            block_kit_builder: Builder for creating and sending Slack block kit messages.
            user_store: Store for user preference data.
        """
        super().__init__()
        self.channel_info_ops = channel_info_ops
        self.channel_membership_ops = channel_membership_ops
        self.slack_posting_handler = slack_posting_handler
        self.dynamodb_store = dynamodb_store
        self.block_kit_builder = block_kit_builder
        self.lookup_message_handler = LookupMessageHandler()
        self.user_store = user_store
        self.lookup_message_handler.configure(
            posting_handler=slack_posting_handler,
            channel_details_getter=dynamodb_store.get_channel_details,
        )
        logger.info(
            "SlackListCommand.__init__: Info Ops ID: %s", id(self.channel_info_ops)
        )
        logger.info("SlackListCommand initialized with injected dependencies.")

    async def process_list_params(
        self,
        params: CommandParams,
        user_id: str,
        incoming_channel: str,
        response_url: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Process the 'list' command.

        Args:
            params: The command parameters
            user_id: Slack user ID
            incoming_channel: The channel where the command was issued
            response_url: The response URL for interactive components

        Returns:
            The generated response or None if there was an error
        """
        # Validate params is the correct type
        if not isinstance(params, ListCommandParams):
            logger.error("Invalid params type: %s", type(params))
            return self.create_validation_error_response("Invalid command parameters")

        # Extract parameters from the params object
        command_verified = params.original_command

        try:
            # Process the list request and get the response
            channel_list = await self._process_list(
                user_id=user_id,
                incoming_channel=incoming_channel,
                response_url=response_url,
                command_verified=command_verified,
            )
            # Use LookupMessageHandler to send the formatted channel list with helper text
            await self.lookup_message_handler.send_message(
                response_url=response_url or incoming_channel,
                channels_list=channel_list,
                include_helper_text=True,
            )
            return self.create_success_response({"message": "List command processed"})
        except Exception as e:
            logger.error("Error processing list request: %s", str(e))
            return self.create_error_response(
                f"Error processing list request: {str(e)}"
            )

    async def _process_list(
        self,
        user_id: str,
        incoming_channel: str,
        response_url: str,
        command_verified: str,
    ) -> list:
        """
        Process the list request and return the channel list for display.
        """
        logger.info("Starting list command processing.")
        await self.slack_posting_handler.post_message(
            user_id=user_id,
            channel_id=incoming_channel,
            message="Retrieving channel list... :mag:",
            response_url=response_url,
        )

        # --- Fetch User Preferences ---
        product_preference = "all_products"  # Default
        try:
            user_data = await self.user_store.get_user(user_id)
            logger.info(
                "User data fetched for %s: %s", user_id, user_data
            )  # Log raw user data
            if user_data and "preferences" in user_data:
                user_prefs = user_data["preferences"]
                logger.info(
                    "User preferences extracted for %s: %s", user_id, user_prefs
                )  # Log extracted prefs
                # Use the first product focus, default to 'all_products'
                product_preference = user_prefs.get("product_focus", ["all_products"])[
                    0
                ]
            else:
                logger.info(
                    "No preferences found for user %s, using default 'all_products'.",
                    user_id,
                )
        except Exception as e:
            logger.error(
                "Error fetching preferences for user %s: %s. Using default 'all_products'.",
                user_id,
                e,
            )
        # Log the final preference value being used
        logger.info(
            "Final product preference determined for user %s: %s",
            user_id,
            product_preference,
        )
        # --- End Fetch User Preferences ---

        # Get the list of channels that the bot is a member of using membership_ops
        slack_channels = (
            await self.channel_membership_ops.lookup_membership_of_channels()
        )

        if not slack_channels:
            no_channels_message = "No channels found that Ketchup is a member of."
            logger.warning(no_channels_message)
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=no_channels_message,
                response_url=response_url,
            )
            return []

        # Ensure all channels exist in DynamoDB before proceeding
        newly_added = await self.dynamodb_store.ensure_channels_exist(slack_channels)
        if newly_added:
            logger.info(
                "Added %d channels to DynamoDB that existed in Slack but not in DB: %s",
                len(newly_added),
                newly_added,
            )

        # Extract channel IDs from the Slack channel list
        channel_ids = [ch.get("id") for ch in slack_channels if ch.get("id")]
        if not channel_ids:
            logger.warning("No valid channel IDs found after membership lookup.")
            return []
        # Log the channel IDs being used for lookup
        logger.info(f"Fetching details for channel IDs: {channel_ids}")

        # Get details only for the specific channels the bot is in using batch operation
        stored_channels = await self.dynamodb_store.get_all_channel_details(
            list_of_channels=channel_ids, product_preference=product_preference
        )

        # Build the formatted channel list for display
        channel_list = self._build_channel_list(slack_channels, stored_channels)
        return channel_list

    def _build_channel_list(
        self, slack_channels: List[Dict[str, Any]], stored_channels: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Build a formatted list of channels with their metadata.

        Args:
            slack_channels: List of channels from Slack API
            stored_channels: Dictionary of channel metadata from DynamoDB

        Returns:
            List of channel objects with formatted data for display
        """
        logger.info("Building channel list with stored_channels: %s", stored_channels)
        channel_list = []

        # Iterate over the potentially filtered stored_channels from the DB
        for channel_id, stored_data in stored_channels.items():
            if (
                channel_id == FEEDBACK_CHANNEL
                or channel_id == TEST_CHANNEL
                or channel_id == "C094BNAUTDJ"
            ):
                continue  # Exclude the feedback and test channels
            # Find the corresponding channel_name from the slack_channels list
            # This is slightly inefficient but necessary as channel_name might not be
            # consistently up-to-date in the DB compared to Slack API fetch.
            channel_name = "unknown-channel-name"  # Default
            for slack_channel in slack_channels:

                if slack_channel.get("id") == channel_id:
                    channel_name = slack_channel.get("name", channel_name)
                    break

            # Convert customer name to uppercase for consistent display
            customer_name = stored_data.get("customer_name", "NOT YET AVAILABLE")
            if customer_name and customer_name != "NOT YET AVAILABLE":
                customer_name = customer_name.upper()

            jira_ticket = stored_data.get("jira_ticket", "NOT YET AVAILABLE")
            last_updated = stored_data.get("last_updated", "Never")

            channel_list.append(
                {
                    "channel_id": channel_id,
                    "channel_name": channel_name,  # Use name found from slack_channels
                    "customer_name": customer_name,
                    "jira_ticket": jira_ticket,
                    "last_updated": last_updated,
                }
            )

        # Sort channels by name
        channel_list.sort(key=lambda x: x["channel_name"])

        return channel_list
