"""
ineligible_handler.py

Handles the scenario when the bot is added to an ineligible Slack channel.
"""

from typing import Optional

from packages.core.constants import ELIGIBILITY_REASON_PREFIX_AGE
from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.channel_operations.channel_eligibility import (
    ChannelEligibilityService,
)

logger = setup_logger(__name__)


async def handle_ineligible_bot_join(
    channel_id: str,
    inviter_id: Optional[str],
    reason: str,
    channel_eligibility_service: ChannelEligibilityService,
    dynamodb_store: DynamoDBStore,
):
    """
    Handles the case when the bot joins an ineligible channel.

    If the reason for ineligibility is the channel's age, it first checks
    DynamoDB to see if the channel was temporarily unarchived. If so,
    the bot remains; otherwise, it proceeds with the standard ineligible handling.

    Args:
        channel_id: The ID of the ineligible channel.
        inviter_id: The ID of the user who invited the bot (if available).
        reason: The reason the channel is ineligible.
        channel_eligibility_service: The service responsible for handling ineligible channels.
        dynamodb_store: DynamoDB store instance for checking temporary unarchive status.
    """
    logger.info(
        "Checking ineligible bot join for channel %s (Inviter: %s). Reason: %s",
        channel_id,
        inviter_id or "Unknown",
        reason,
    )

    if reason.startswith(ELIGIBILITY_REASON_PREFIX_AGE):
        logger.info(
            "Ineligibility due to age for channel %s. Checking for temporary unarchive status.",
            channel_id,
        )
        try:
            is_temporary = await dynamodb_store.check_if_temporary_unarchive(channel_id)
            if is_temporary:
                logger.warning(
                    "Bot joined old channel %s, but it's temporarily unarchived. Bot will remain.",
                    channel_id,
                )
                return
            else:
                logger.info(
                    "Channel %s is old and not temporarily unarchived. Proceeding with leave.",
                    channel_id,
                )
        except Exception as db_check_error:
            logger.error(
                "Error checking temporary unarchive status for channel %s: %s. Proceeding with default ineligible handling.",
                channel_id,
                str(db_check_error),
            )

    logger.warning(
        "Proceeding with standard ineligible handling for channel %s.", channel_id
    )
    await channel_eligibility_service.handle_ineligible_channel(
        channel_id=channel_id, inviter_id=inviter_id, reason=reason
    )
