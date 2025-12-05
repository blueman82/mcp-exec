"""
channel_eligibility.py

Module for handling channel eligibility checks and related operations.
"""

import time
from typing import Optional, Tuple

from packages.core.constants import (
    CHANNEL_KEYWORD_TO_PRODUCT,
    ELIGIBILITY_MAX_CHANNEL_AGE_DAYS,
)
from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class ChannelEligibilityService:
    """Service to check if a channel meets eligibility criteria."""

    def __init__(
        self,
        channel_info_ops: ChannelInfoOps,
        posting_handler: SlackPostingHandler,
        dynamodb_store: DynamoDBStore,
    ):
        """
        Initialize the ChannelEligibilityService.

        Args:
            channel_info_ops: Instance of ChannelInfoOps.
            posting_handler: Instance of SlackPostingHandler.
            dynamodb_store: Instance of DynamoDBStore.
        """
        self.channel_info_ops = channel_info_ops
        self.posting_handler = posting_handler
        self.dynamodb_store = dynamodb_store
        logger.info("ChannelEligibilityService initialized.")

    async def is_channel_eligible(
        self, channel_id: str, user_id: str, response_url: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a given channel is eligible based on predefined criteria.

        Args:
            channel_id: The ID of the channel to check.
            user_id: The ID of the user initiating the check (for messaging).
            response_url: Optional response URL for feedback.

        Returns:
            A tuple containing:
            - bool: True if the channel is eligible, False otherwise.
            - Optional[str]: A reason for ineligibility if applicable, otherwise None.
        """
        logger.info("Checking eligibility for channel %s", channel_id)

        # 1. Check DynamoDB first
        try:
            channel_data = await self.dynamodb_store.get_channel_details(channel_id)
            if channel_data and channel_data.get("eligible") is not None:
                is_eligible = channel_data["eligible"]
                reason = channel_data.get("eligibility_reason")
                logger.info(
                    "Eligibility status found in DynamoDB for channel %s: Eligible=%s, Reason=%s",
                    channel_id,
                    is_eligible,
                    reason,
                )
                return is_eligible, reason
            logger.info(
                "No eligibility status found in DynamoDB for channel %s. Checking API.",
                channel_id,
            )
        except Exception as db_error:
            logger.warning(
                "Error checking DynamoDB for channel %s eligibility: %s. Proceeding with API check.",
                channel_id,
                db_error,
            )

        # 2. Fetch channel details from Slack API using ChannelInfoOps
        try:
            channel_info = await self.channel_info_ops.get_channel_info_from_api(channel_id)

            if not channel_info:
                logger.warning("Could not retrieve channel info for %s", channel_id)
                # Try to inform the user if response_url is available
                if response_url:
                    await self.posting_handler.post_message(
                        user_id=user_id,
                        message=f"Could not retrieve information for channel `{channel_id}`. Cannot determine eligibility.",
                        response_url=response_url,
                        # No channel_id here as we don't know where the user is
                    )
                return False, "Could not retrieve channel information"

            channel_name = channel_info.get("name", "")
            is_private = channel_info.get("is_private", False)
            is_archived = channel_info.get("is_archived", False)
            created_timestamp = channel_info.get("created")

            # 3. Apply Eligibility Rules

            # Check if this is an exempt channel first (before other checks)
            exempt_channels = ["ketchup_access_requests", "ketchup-alerts"]
            if channel_name.lower().replace("#", "") in exempt_channels:
                logger.info(
                    "Channel %s is in exempt list - automatically eligible",
                    channel_name,
                )
                return True, None

            # Now check other eligibility rules
            if is_archived:
                return False, "Channel is archived"
            if is_private:
                return False, "Channel is private"

            # Reinstate and modify name check: check if name *contains* any keyword
            # from CHANNEL_KEYWORD_TO_PRODUCT (case-insensitive)
            channel_name_lower = channel_name.lower()
            approved_keywords = [key.lower() for key in CHANNEL_KEYWORD_TO_PRODUCT.keys()]
            if not (
                "cso" in channel_name_lower
                and any(keyword in channel_name_lower for keyword in approved_keywords)
            ):
                return (
                    False,
                    "This channel's name doesn't follow the standard format for an active CSO War Room.",
                )

            # Reinstate age check
            if created_timestamp:
                try:
                    current_time = time.time()
                    channel_age_days = int(
                        (current_time - float(created_timestamp)) // (24 * 60 * 60)
                    )
                    if channel_age_days > ELIGIBILITY_MAX_CHANNEL_AGE_DAYS:
                        return (
                            False,
                            f"Channel is over {ELIGIBILITY_MAX_CHANNEL_AGE_DAYS} days old ({channel_age_days} days)",
                        )
                except (ValueError, TypeError) as time_err:
                    logger.warning(
                        "Could not calculate channel age for %s due to timestamp error: %s",
                        channel_id,
                        time_err,
                    )
                    # Decide how to handle age check failure - treat as ineligible
                    # For now, let's treat as ineligible if timestamp is invalid
                    return (
                        False,
                        "This channel's name doesn't follow the standard format for an active CSO War Room.",
                    )
            else:
                logger.warning(
                    "Could not find creation timestamp for channel %s to check age.",
                    channel_id,
                )
                # Treat as ineligible if creation timestamp is missing
                return (
                    False,
                    "This channel's name doesn't follow the standard format for an active CSO War Room.",
                )

            # If all checks pass, channel is eligible
            logger.info("Channel %s is eligible based on API check.", channel_id)
            # Optionally, update DynamoDB with the eligibility status here
            # await self.dynamodb_store.update_channel_eligibility(channel_id, True, None)
            return True, None

        except Exception as e:
            logger.error("Error checking channel eligibility for %s: %s", channel_id, str(e))
            if response_url:
                await self.posting_handler.post_message(
                    user_id=user_id,
                    message=f"An error occurred while checking eligibility for channel `{channel_id}`.",
                    response_url=response_url,
                )
            return False, f"Error checking eligibility: {str(e)}"

    async def handle_ineligible_channel(
        self,
        channel_id: str,
        inviter_id: str,
        reason: str,
    ) -> None:
        """
        Handle a channel that's ineligible for the bot.

        Args:
            channel_id: The channel ID
            inviter_id: The user who invited the bot
            reason: The reason for ineligibility
        """
        try:
            # Construct rejection message
            rejection_message = f"Sorry <@{inviter_id}>, Ketchup can only join approved CSO War Room Channels. Reason: {reason}. It will now leave this channel."

            # Send rejection message using the posting handler
            await self.posting_handler.post_message(
                user_id=inviter_id,  # Send as ephemeral message to the inviter
                channel_id=channel_id,
                message=rejection_message,
            )

            # Leave channel using the Slack API directly via the existing client method
            url = f"{await self.channel_info_ops.get_api_base_url()}/conversations.leave"
            payload = {"channel": channel_id}

            # Fetch necessary headers (including auth token) using the public headers property
            headers = self.channel_info_ops.headers  # Access the property synchronously

            # Call _make_api_request with headers and json_data
            response_data = await self.channel_info_ops._make_api_request(
                url,
                "POST",
                headers=headers,  # Pass the fetched headers
                json_data=payload,
            )

            # response_data is already a dict from _make_api_request
            if response_data.get("ok"):
                logger.info("Successfully left channel %s", channel_id)
            else:
                logger.error(
                    "Failed to leave channel %s: %s",
                    channel_id,
                    response_data.get("error", "Unknown error"),
                )

            # Delete DynamoDB record if exists
            await self.dynamodb_store.delete_channel_if_exists(channel_id)

            logger.info("Successfully handled ineligible channel %s: %s", channel_id, reason)
        except Exception as e:
            logger.error("Error handling ineligible channel %s: %s", channel_id, str(e))
