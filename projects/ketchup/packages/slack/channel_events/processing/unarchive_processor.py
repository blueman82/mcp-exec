"""
Handles the processing steps after a channel is unarchived, specifically inviting the bot.
"""

import asyncio
from typing import Optional

from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_restore_ops import SlackChannelRestoreOps

logger = setup_logger(__name__)


async def invite_and_verify_bot_after_unarchive(
    channel_id: str,
    channel_name: Optional[str],
    secrets_manager: SecretsManager,
    channel_restore_ops: SlackChannelRestoreOps,
    channel_info_ops: ChannelInfoOps,
) -> bool:
    """
    Invites the bot to a channel after it's unarchived and verifies membership.

    Args:
        channel_id: The ID of the channel.
        channel_name: The name of the channel (optional).
        secrets_manager: Secrets manager instance.
        channel_restore_ops: Instance of SlackChannelRestoreOps.
        channel_info_ops: Instance of ChannelInfoOps.

    Returns:
        True if the bot successfully joined, False otherwise.
    """
    logger.info("Attempting to invite and verify bot for channel %s", channel_id)
    bot_user_id = await secrets_manager.get_bot_slack_user_id_async()

    if not bot_user_id:
        logger.error("Could not retrieve bot user ID from secrets manager.")
        return False

    # Check if the bot is already a member using ChannelInfoOps
    try:
        # We need user_id and dm_channel_id for get_channel_details, but they
        # are not available in this event context. We can use get_channel_info_from_api instead.
        channel_info = await channel_info_ops.get_channel_info_from_api(channel_id)
        is_member = channel_info.get("is_member", False) if channel_info else False
    except Exception as e:
        logger.error("Failed to check initial membership for %s: %s", channel_id, e)
        is_member = False  # Assume not member if check fails

    if is_member:
        logger.info("Bot is already a member of unarchived channel %s.", channel_id)
        return True

    # Use the direct invite method as user/DM context isn't available here for feedback.
    # Verification is handled locally below.
    try:
        logger.info("Inviting bot %s to channel %s", bot_user_id, channel_id)
        invite_result = await channel_restore_ops.invite_ketchup_to_channel(
            channel_id=channel_id,
            bot_user_id=bot_user_id,
            channel_name=channel_name or "unknown",
        )

        if (
            invite_result.get("ok")
            or invite_result.get("error") == "already_in_channel"
        ):
            logger.info(
                "Invite successful or bot already in channel %s. Verifying...",
                channel_id,
            )
            # Add verification loop here similar to _invite_and_verify_bot_membership
            max_checks = 5
            delay = 5
            for i in range(max_checks):
                await asyncio.sleep(delay)
                channel_info = await channel_info_ops.get_channel_info_from_api(
                    channel_id
                )
                if channel_info and channel_info.get("is_member"):
                    logger.info(
                        "Bot membership verified for %s after %d checks.",
                        channel_id,
                        i + 1,
                    )
                    return True
                logger.warning(
                    "Membership check %d/%d failed for %s.",
                    i + 1,
                    max_checks,
                    channel_id,
                )
            logger.error(
                "Failed to verify bot membership for %s after %d checks.",
                channel_id,
                max_checks,
            )
            return False
        else:
            logger.error(
                "Failed to invite bot to channel %s: %s",
                channel_id,
                invite_result.get("error", "Unknown error"),
            )
            return False

    except Exception as e:
        logger.error(
            "Exception during bot invite/verification for channel %s: %s",
            channel_id,
            e,
            exc_info=True,
        )
        return False
