"""
user_join_processor.py

Handles regular user join events (non-bot users joining channels).
Extracted from join_processor.py for CLAUDE.md file size compliance.
"""

import time

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def process_regular_user_join(
    event: dict,
    channel_id: str,
    user_id: str,
    channel_eligibility_service,
    feature_service=None,
    user_join_notification_service=None,
    join_notification_ops=None,
    restore_state_manager=None,
    dynamodb_store=None,
):
    """
    Process regular user joining a channel and send notification if enabled.

    Args:
        event: The Slack event data
        channel_id: ID of the channel user joined
        user_id: ID of the user who joined
        channel_eligibility_service: Service for checking channel eligibility
        feature_service: Optional service for checking feature flags
        user_join_notification_service: Optional service for sending notifications
        join_notification_ops: Optional service for tracking notification attempts
        restore_state_manager: Optional manager for checking channel restore state
        dynamodb_store: Optional DynamoDB store for incrementing monthly counters
    """
    logger.info(f"Processing regular user join: user {user_id} in channel {channel_id}")

    try:
        # Check if channel is being temporarily unarchived for a command
        # Skip auto-join processing to avoid duplicate message fetching
        if restore_state_manager:
            is_being_restored = await restore_state_manager.is_rearchive_needed(channel_id)
            if is_being_restored:
                logger.info(
                    "Skipping auto-join notification for user %s in channel %s - "
                    "channel is temporarily unarchived for command execution",
                    user_id, channel_id
                )
                return

        # Check if user join notifications feature is enabled for this user
        if not feature_service:
            logger.info(
                "Feature service not available, skipping user join notification"
            )
            return

        if not user_join_notification_service:
            logger.info(
                "User join notification service not available, skipping notification"
            )
            return

        # Check if feature is enabled for this channel
        is_enabled = (
            await feature_service.is_user_join_notifications_enabled_for_channel(
                channel_id
            )
        )
        if not is_enabled:
            logger.info(f"User join notifications not enabled for channel {channel_id}")
            # Track disabled notification for channel
            if join_notification_ops:
                tracking_data = {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "delivery_status": "disabled",
                    "notification_attempted": False,
                    "timestamp": int(time.time())
                }
                await join_notification_ops.track_notification(tracking_data)
            return

        # Check if channel is eligible (same eligibility as bot joins)
        is_eligible, reason = await channel_eligibility_service.is_channel_eligible(
            channel_id=channel_id,
            user_id=user_id,
            response_url=None,  # No response URL for regular events
        )

        if not is_eligible:
            logger.info(
                f"Channel {channel_id} not eligible for user join notifications: {reason}"
            )
            # Track ineligible notification attempt
            if join_notification_ops:
                tracking_data = {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "delivery_status": "failed",
                    "notification_attempted": False,
                    "failure_reason_code": "CHANNEL_INELIGIBLE",
                    "error_message": f"Channel not eligible: {reason}",
                    "timestamp": int(time.time())
                }
                await join_notification_ops.track_notification(tracking_data)
            return

        # Get channel name for notification
        try:
            # Try to get channel name from event first
            channel_name = event.get("channel_name")
            if not channel_name:
                # Fallback: extract from channel ID or use ID as name
                channel_name = channel_id
                logger.info(f"Using channel ID as name: {channel_name}")
        except Exception as e:
            logger.warning(f"Could not determine channel name: {e}")
            channel_name = channel_id

        # Send notification to user
        notification_success = (
            await user_join_notification_service.send_join_notification(
                user_id=user_id, channel_id=channel_id
            )
        )

        # Increment monthly metrics counters for war room notifications
        if dynamodb_store:
            try:
                from datetime import datetime, timezone
                month_key = datetime.now(timezone.utc).strftime("%Y_%m")

                # Always increment sent counter
                await dynamodb_store.increment_monthly_counter(
                    "war_room_sent", month_key, 1
                )

                # Increment success or failed counter based on result
                if notification_success:
                    await dynamodb_store.increment_monthly_counter(
                        "war_room_success", month_key, 1
                    )
                    logger.info(
                        f"Successfully sent join notification to user {user_id} in channel {channel_id}"
                    )
                else:
                    await dynamodb_store.increment_monthly_counter(
                        "war_room_failed", month_key, 1
                    )
                    logger.warning(
                        f"Failed to send join notification to user {user_id} in channel {channel_id}"
                    )
            except Exception as e:
                logger.warning(f"Failed to increment war_room counter: {e}")
                # Still log original result even if counter fails
                if notification_success:
                    logger.info(
                        f"Successfully sent join notification to user {user_id} in channel {channel_id}"
                    )
                else:
                    logger.warning(
                        f"Failed to send join notification to user {user_id} in channel {channel_id}"
                    )

    except Exception as e:
        logger.error(
            f"Error processing regular user join for {user_id} in {channel_id}: {e}"
        )
        # Don't raise - this should not block the user's join process
