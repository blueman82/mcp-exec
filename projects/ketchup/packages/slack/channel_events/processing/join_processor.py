"""
join_processor.py

Handles processing for eligible member_joined events, specifically when the bot joins.
"""

import asyncio
import os
import time
from typing import Optional

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore

# Need to import ChannelMetadata
from packages.db.models.channel_metadata import ChannelMetadata

# Added dependencies needed by the moved logic
from packages.secrets.manager import SecretsManager
from packages.slack.channel_events.eligibility.ineligible_handler import (
    handle_ineligible_bot_join,
)

# Extracted user join processing
from packages.slack.channel_events.processing.user_join_processor import (
    process_regular_user_join,
)
from packages.slack.channel_operations.channel_eligibility import (
    ChannelEligibilityService,
)
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.maintenance import get_jira_prompt_handler
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


async def process_eligible_bot_join(
    event: dict,
    channel_id: str,
    user_id: str,
    response_url: Optional[str],
    # Dependencies
    dynamodb_store: DynamoDBStore,
    # Accept ChannelInfoOps instead of ChannelLookupOps
    # channel_lookup_ops: SlackChannelLookupOps,
    channel_info_ops: ChannelInfoOps,
    posting_handler: SlackPostingHandler,
):
    """
    Processes the event when the bot joins an eligible channel.
    Stores metadata if missing.

    Args:
        event: The Slack event data.
        channel_id: The ID of the channel the bot joined.
        user_id: The ID of the user who joined the channel.
        response_url: Optional response URL.
        dynamodb_store: DynamoDB store instance.
        channel_info_ops: Instance of ChannelInfoOps.
        posting_handler: Posting handler instance.
    """
    logger.info("Processing eligible bot join for channel %s", channel_id)
    try:
        # Ensure the channel exists in the database or add it
        channel_details = await dynamodb_store.get_channel_details(channel_id)
        if not channel_details:
            logger.warning(
                "Channel %s not found in DB during bot join, attempting lookup and add.",
                channel_id,
            )
            try:
                # Correct the method name here
                channel_info_result = await channel_info_ops.get_channel_info_from_api(channel_id)
                if channel_info_result:
                    # Convert event_ts to integer for date_created_epoch
                    try:
                        creation_epoch = int(
                            float(
                                channel_info_result.get(
                                    "created",
                                    event.get("event_ts", str(int(time.time()))),
                                )
                            )
                        )
                    except (ValueError, TypeError):
                        logger.warning(
                            "Could not parse channel created timestamp '%s' to int, using event_ts '%s'",
                            channel_info_result.get("created"),
                            event.get("event_ts", str(int(time.time()))),
                        )
                        try:
                            creation_epoch = int(
                                float(event.get("event_ts", str(int(time.time()))))
                            )
                        except (ValueError, TypeError):
                            logger.warning("Could not parse event_ts either, using current time.")
                            creation_epoch = int(time.time())

                    # Determine product type
                    channel_name = channel_info_result.get("name", "unknown")
                    product_type = dynamodb_store.channel_ops.determine_product_type(channel_name)
                    logger.info(
                        "Determined product type for %s as: %s",
                        channel_id,
                        product_type,
                    )

                    # Create a ChannelMetadata object
                    metadata = ChannelMetadata(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        date_created_epoch=creation_epoch,
                        archived=channel_info_result.get("is_archived", False),
                        custom_fields={
                            "customer_name": "NOT YET AVAILABLE",
                            "jira_ticket": "NOT YET AVAILABLE",
                            "product": product_type,
                        },
                    )
                    # Use the correct method via channel_ops
                    await dynamodb_store.channel_ops.store_metadata(metadata)
                    logger.info("Added missing channel %s metadata to DB.", channel_id)
                else:
                    logger.error("Failed to lookup details for channel %s.", channel_id)
            except Exception as lookup_error:
                logger.error("Error looking up channel details: %s", str(lookup_error))
        else:
            # Optional: Update last_activity or bot_joined_at timestamp if needed
            logger.info("Channel %s already exists in DB.", channel_id)

        # Potentially trigger other actions upon bot joining an eligible channel
        # E.g., post a welcome message, update channel topic, etc.

        # NEW: Trigger maintenance detection workflow
        maintenance_feature_enabled = (
            os.getenv("KETCHUP_MAINTENANCE_DETECTION", "false").lower() == "true"
        )

        # Optional: Whitelist specific channels for testing
        test_channels = os.getenv("KETCHUP_MAINTENANCE_TEST_CHANNELS", "").split(",")
        is_test_channel = any(channel_id == ch.strip() for ch in test_channels if ch.strip())

        if maintenance_feature_enabled or is_test_channel:
            logger.info("Maintenance detection enabled, starting JIRA prompt workflow")

            try:
                # Get JIRA prompt handler via TypedDI (all dependencies auto-resolved)
                jira_handler = await get_jira_prompt_handler()

                # Start workflow in background (don't block bot join)
                asyncio.create_task(jira_handler.start_jira_prompt_workflow(channel_id))

                logger.info("Maintenance detection workflow started for channel %s", channel_id)

            except Exception as maintenance_error:
                logger.error(
                    "Failed to start maintenance detection: %s",
                    str(maintenance_error),
                    exc_info=True,
                )
                # Don't fail bot join if maintenance detection fails

    except Exception as e:
        logger.error(
            "Error processing eligible bot join for channel %s: %s",
            channel_id,
            str(e),
            exc_info=True,
        )
        # Consider notifying admin or inviter if possible


async def handle_member_joined_event(
    event: dict,
    response_url: Optional[str],
    # Dependencies needed for the complete flow
    secrets_manager: SecretsManager,
    channel_eligibility_service: ChannelEligibilityService,
    dynamodb_store: DynamoDBStore,
    # Accept ChannelInfoOps instead of ChannelLookupOps
    # channel_lookup_ops: SlackChannelLookupOps,
    channel_info_ops: ChannelInfoOps,
    posting_handler: SlackPostingHandler,
    # New dependencies for user join notifications
    feature_service=None,
    user_join_notification_service=None,
    user_store=None,
    join_notification_ops=None,
    restore_state_manager=None,
):
    """
    Handles the complete logic for a member_joined_channel event.

    Checks if the joined member is the bot, checks channel eligibility,
    processes eligible joins, handles ineligible joins, and manages errors.
    Also handles regular user joins by sending notification if feature is enabled.

    Args:
        event: The Slack event data.
        response_url: Optional response URL.
        secrets_manager: Secrets manager instance.
        channel_eligibility_service: Eligibility service instance.
        dynamodb_store: DynamoDB store instance.
        channel_info_ops: Instance of ChannelInfoOps.
        posting_handler: Posting handler instance.
        feature_service: Feature service for checking user join notification enablement.
        user_join_notification_service: Service for sending user join notifications.
        user_store: User store for fetching user profiles.
        join_notification_ops: Service for tracking notification attempts and results.
    """
    logger.info("Handling member_joined_channel event flow.")

    channel_id = None
    inviter_id = None

    try:
        channel_id = event.get("channel")
        user_id = event.get("user")
        inviter_id = event.get("inviter")

        if not channel_id or not user_id:
            logger.error("Missing channel ID or user ID in member_joined_channel event")
            return

        # Check if the user is the bot (using SecretsManager)
        bot_user_id = await secrets_manager.get_bot_slack_user_id_async()
        is_bot_join = user_id == bot_user_id

        if not is_bot_join:
            # This is a regular user joining, not our bot
            logger.info("Regular user %s joined channel %s", user_id, channel_id)

            # Handle user join notifications if service and feature service are available
            if user_join_notification_service and feature_service:
                await process_regular_user_join(
                    event=event,
                    user_id=user_id,
                    channel_id=channel_id,
                    channel_eligibility_service=channel_eligibility_service,
                    feature_service=feature_service,
                    user_join_notification_service=user_join_notification_service,
                    join_notification_ops=join_notification_ops,
                    restore_state_manager=restore_state_manager,
                    dynamodb_store=dynamodb_store,
                )
            else:
                logger.info(
                    "User join notification service not available or feature service missing"
                )
            return

        logger.info("Bot %s joined channel %s (Inviter: %s)", user_id, channel_id, inviter_id)

        # Use channel eligibility service to check if channel is eligible
        # Ensure inviter_id is a string before passing
        inviter_str = inviter_id if isinstance(inviter_id, str) else None
        is_eligible, reason = await channel_eligibility_service.is_channel_eligible(
            channel_id=channel_id, user_id=inviter_str or "", response_url=response_url
        )
        if not is_eligible:
            # Ensure reason is a string before passing
            reason_str = reason if isinstance(reason, str) else "Unknown reason"
            # Use the imported function to handle ineligibility, passing only expected args
            await handle_ineligible_bot_join(
                channel_id=channel_id,
                inviter_id=inviter_str,
                reason=reason_str,
                channel_eligibility_service=channel_eligibility_service,
                dynamodb_store=dynamodb_store,
            )
            return

        logger.info("Bot joined approved channel %s", channel_id)

        # Delegate the processing for an eligible bot join
        await process_eligible_bot_join(
            event,
            channel_id,
            user_id,
            response_url,
            dynamodb_store,
            channel_info_ops,
            posting_handler,
        )

    except Exception as e:
        logger.error("Error processing member_joined_channel event: %s", str(e), exc_info=True)

        # Try to notify about the error if we have channel info
        if channel_id and inviter_id:
            try:
                await posting_handler.post_message(
                    channel_id=inviter_id,  # DM to inviter
                    message=f"Failed to process bot join for channel {channel_id}: {str(e)}",
                    response_url=response_url,
                )
            except Exception as posting_error:
                logger.error("Could not notify user of error: %s", str(posting_error))
