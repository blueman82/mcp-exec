"""
Handles the processing steps after an eligible channel is created.
"""

import time  # Added for timestamp
from typing import Optional

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore

# Import the required model
from packages.db.models.channel_metadata import ChannelMetadata
from packages.secrets.manager import SecretsManager
from packages.slack.channel_events.eligibility.creation_checker import (
    is_new_channel_eligible,
)
from packages.slack.channel_operations.channel_restore_ops import SlackChannelRestoreOps
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


async def process_eligible_channel_creation(
    channel_id: str,
    channel_name: str,
    creator_id: str,
    event_ts: str,
    response_url: Optional[str],
    secrets_manager: SecretsManager,
    channel_restore_ops: SlackChannelRestoreOps,
    dynamodb_store: DynamoDBStore,
    posting_handler: SlackPostingHandler,
) -> None:
    """
    Processes an eligible channel creation: invites bot, stores metadata.

    Args:
        channel_id: ID of the newly created channel.
        channel_name: Name of the newly created channel.
        creator_id: ID of the user who created the channel.
        event_ts: Timestamp of the channel creation event.
        response_url: Optional response URL for feedback.
        secrets_manager: Secrets manager instance.
        channel_restore_ops: Channel restore/join operations instance.
        dynamodb_store: DynamoDB store instance.
        posting_handler: Slack posting handler instance.
    """
    logger.info(
        "Processing eligible channel creation for %s (%s)", channel_name, channel_id
    )

    try:
        # Get bot user ID
        bot_user_id = await secrets_manager.get_bot_slack_user_id_async()
        if not bot_user_id:
            logger.error("Bot user ID not found, cannot invite bot")
            await posting_handler.post_message(
                channel_id=creator_id,  # DM to creator
                message=f"Failed to get bot user ID. Cannot invite bot to {channel_name}.",
                response_url=response_url,
            )
            return

        # Invite the bot to the channel using channel_restore_ops
        invite_success = await channel_restore_ops.invite_ketchup_to_channel(
            channel_id=channel_id,
            bot_user_id=bot_user_id,
            channel_name=channel_name,
        )

        if not invite_success:
            logger.error("Failed to invite bot to newly created channel %s", channel_id)
            # Error message handled within _invite_and_verify_bot_membership
            return

        # Store channel metadata in DynamoDB
        logger.info("Storing metadata for new channel %s in DynamoDB", channel_id)
        try:
            # Convert event_ts to integer for date_created_epoch
            try:
                creation_epoch = int(float(event_ts))
            except (ValueError, TypeError):
                logger.warning(
                    "Could not parse event_ts '%s' to int, using current time.",
                    event_ts,
                )
                creation_epoch = int(time.time())

            # Determine product type
            product_type = dynamodb_store.channel_ops.determine_product_type(
                channel_name
            )
            logger.info(
                "Determined product type for %s as: %s", channel_id, product_type
            )

            # Create a ChannelMetadata object - remove 'created_by'
            metadata = ChannelMetadata(
                channel_id=channel_id,
                channel_name=channel_name,
                date_created_epoch=creation_epoch,  # Use correct param name and type
                archived=False,  # New channels are not archived
                custom_fields={  # Store other info in custom_fields if needed
                    "customer_name": "NOT YET AVAILABLE",
                    "jira_ticket": "NOT YET AVAILABLE",
                    "product": product_type,  # Set the determined product type here
                },
            )
            # Use the correct method via channel_ops
            await dynamodb_store.channel_ops.store_metadata(metadata)
            logger.info("Successfully stored metadata for channel %s", channel_id)
        except Exception as db_error:
            logger.error(
                "Failed to store metadata for channel %s: %s",
                channel_id,
                str(db_error),
            )
            # Notify creator about the DB error
            await posting_handler.post_message(
                channel_id=creator_id,
                message=f"Successfully invited bot to {channel_name}, but failed to store channel metadata: {str(db_error)}",
                response_url=response_url,
            )

    except Exception as e:
        logger.error(
            "Error during eligible channel creation processing for %s: %s",
            channel_id,
            str(e),
            exc_info=True,
        )
        await posting_handler.post_message(
            channel_id=creator_id,
            message=f"An internal error occurred while processing the creation of channel {channel_name}: {str(e)}",
            response_url=response_url,
        )


async def handle_channel_creation_event(
    event: dict,
    response_url: Optional[str],
    secrets_manager: SecretsManager,
    channel_restore_ops: SlackChannelRestoreOps,
    dynamodb_store: DynamoDBStore,
    posting_handler: SlackPostingHandler,
):
    """
    Handles the complete logic for a channel_created event.

    Extracts info, checks eligibility, processes if eligible, handles errors.

    Args:
        event: The Slack event data for channel creation.
        response_url: Optional response URL for feedback.
        secrets_manager: Secrets manager instance.
        channel_restore_ops: Channel restore/join operations instance.
        dynamodb_store: DynamoDB store instance.
        posting_handler: Slack posting handler instance.
    """
    logger.info("Handling channel_created event flow.")

    channel_id = None
    creator_id = None
    channel_name = None

    try:
        # Extract channel information from event
        channel_info = event.get("channel", {})
        channel_id = channel_info.get("id")
        channel_name = channel_info.get("name")
        creator_id = channel_info.get("creator")
        event_ts = event.get("event_ts", "")  # Get event timestamp

        if not channel_id or not channel_name or not creator_id:
            logger.error("Missing required channel info in channel_created event")
            return

        logger.info(
            "New channel created: %s (ID: %s) by user %s.",
            channel_name,
            channel_id,
            creator_id,
        )

        # Check eligibility using the imported function
        if await is_new_channel_eligible(channel_name, creator_id, secrets_manager):
            # Process the eligible channel using the other function in this module
            await process_eligible_channel_creation(
                channel_id=channel_id,
                channel_name=channel_name,
                creator_id=creator_id,
                event_ts=event_ts,
                response_url=response_url,
                # Pass dependencies down
                secrets_manager=secrets_manager,
                channel_restore_ops=channel_restore_ops,
                dynamodb_store=dynamodb_store,
                posting_handler=posting_handler,
            )
        else:
            logger.info(
                "Ignoring channel %s (ID: %s) created by user %s "
                "as it's not an approved war room based on eligibility checks.",
                channel_name,
                channel_id,
                creator_id,
            )

    except Exception as e:
        logger.error(
            "Error processing channel_created event: %s", str(e), exc_info=True
        )

        # Try to notify about the error if we have channel info
        if channel_id and creator_id:
            try:
                await posting_handler.post_message(
                    channel_id=creator_id,  # DM to creator
                    message=f"Failed to process channel creation for {channel_name or 'unknown'}: {str(e)}",
                    response_url=response_url,
                )
            except Exception as posting_error:
                logger.error("Could not notify user of error: %s", str(posting_error))
