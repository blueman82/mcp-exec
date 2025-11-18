"""
archive_processor.py

Handles processing related to Slack channel archive events, primarily database updates.
"""

import os
import time
from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.core.sqs_client import SQSClient
from packages.db.dynamodb_store import DynamoDBStore

logger = setup_logger(__name__)


async def process_channel_archive(channel_id: str, dynamodb_store: DynamoDBStore):
    """
    Handles the core logic for processing a channel_archive event.

    Checks channel existence and current archive status in DynamoDB.
    Updates the channel item with archived=True and an appropriate timestamp,
    preserving the original timestamp if one already exists.

    Args:
        channel_id: The ID of the channel that was archived.
        dynamodb_store: The DynamoDBStore instance for database operations.
    """
    channel_check_message = (
        f"Checking if channel {channel_id} exists in DynamoDB for archive processing."
    )
    logger.info(channel_check_message)

    # Check if channel exists in DynamoDB using consistent read to avoid race conditions
    channel_data = await dynamodb_store.get_channel_details_consistent(channel_id)

    # Skip if channel not found in DynamoDB
    if not channel_data:
        not_found_message = (
            f"Channel {channel_id} not found in DynamoDB. Skipping archive update."
        )
        logger.warning(not_found_message)
        return

    # Skip if channel is already archived
    if channel_data.get("archived", False):
        already_archived_message = (
            f"Channel {channel_id} is already archived. Skipping archive update."
        )
        logger.warning(already_archived_message)
        return

    # Check for existing archived_at timestamp
    existing_archived_at = channel_data.get("archived_at")

    # Only set current time if there's no previous archived_at value or it's zero
    if not existing_archived_at or existing_archived_at == 0:
        # Set new archived status and timestamp
        current_unix_time = int(time.time())
        archived_at = current_unix_time
        logger.info(
            "Setting new archived_at timestamp for channel %s: %s",
            channel_id,
            current_unix_time,
        )
    else:
        # Preserve the original archived_at timestamp
        archived_at = existing_archived_at
        logger.info(
            "Preserving original archived_at timestamp for channel %s: %s",
            channel_id,
            existing_archived_at,
        )

    update_message = f"Updating archived status for channel {channel_id} in DynamoDB."
    logger.info(update_message)

    # Update DynamoDB with archive status and timestamp
    await dynamodb_store.update_channel_archived_status(
        channel_id=channel_id, archived=True, archived_at=archived_at
    )

    success_message = (
        f"Channel {channel_id} successfully marked as archived in DynamoDB."
    )
    logger.info(success_message)

    # Clean up auto-status fields when channel is archived
    logger.info(f"Cleaning up auto-status fields for archived channel {channel_id}")
    try:
        cleanup_updates = {
            "auto_status_last_content": "",
            "auto_status_last_message_ts": "0",
            "auto_status_last_thread_ts": "0",
            "auto_status_last_post_ts": "0",
            "auto_status_last_jira_comment_ts": "0",
            "auto_status_attempt_count": 0,
            "auto_status_enabled": False,
            "auto_status_last_run": 0,
        }

        await dynamodb_store.update_channel_fields(
            channel_id=channel_id, updates=cleanup_updates
        )

        logger.info(
            f"Successfully cleaned up auto-status fields for archived channel {channel_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to clean up auto-status fields for channel {channel_id}: {e}",
            exc_info=True,
        )

    # Clean up trust endorsement data when channel is archived
    logger.info(f"Cleaning up trust endorsement data for archived channel {channel_id}")
    try:
        success = await dynamodb_store.trust_ops.cleanup_channel_trust_data(channel_id)
        if success:
            logger.info(
                f"Successfully cleaned up trust endorsement data for archived channel {channel_id}"
            )
        else:
            logger.warning(
                f"Trust endorsement cleanup returned failure for channel {channel_id}"
            )
    except Exception as e:
        logger.error(
            f"Failed to clean up trust endorsement data for channel {channel_id}: {e}",
            exc_info=True,
        )

    # Clean up feedback flag data when channel is archived
    logger.info(f"Cleaning up feedback flag data for archived channel {channel_id}")
    try:
        success = await dynamodb_store.feedback_ops.cleanup_channel_feedback_data(
            channel_id
        )
        if success:
            logger.info(
                f"Successfully cleaned up feedback flag data for archived channel {channel_id}"
            )
        else:
            logger.warning(
                f"Feedback flag cleanup returned failure for channel {channel_id}"
            )
    except Exception as e:
        logger.error(
            f"Failed to clean up feedback flag data for channel {channel_id}: {e}",
            exc_info=True,
        )

    # Trigger JIRA report if needed
    await _trigger_jira_report_if_needed(channel_id, channel_data, dynamodb_store)


async def _trigger_jira_report_if_needed(
    channel_id: str, channel_data: Dict[str, Any], dynamodb_store: DynamoDBStore
) -> None:
    """
    Check if JIRA report should be triggered for archived channel.

    Args:
        channel_id: The channel ID
        channel_data: The channel metadata
        dynamodb_store: The DynamoDB store instance
    """
    jira_ticket = channel_data.get("jira_ticket", "")
    jira_report_status = channel_data.get("jira_report_status", "")

    # Check if eligible for JIRA report
    if (
        jira_ticket
        and jira_ticket != "NOT YET AVAILABLE"
        and jira_report_status != "PROCESSED"
    ):

        # Check if JIRA reporter is enabled globally or for this channel
        # Since we don't have access to feature_service here, check the global flag
        from packages.core.config.feature_flags import FeatureFlags

        if not FeatureFlags.is_jira_reporter_enabled():
            logger.info(
                f"JIRA reporter feature not enabled, skipping trigger for channel {channel_id}"
            )
            return

        # If global flag is set, all channels are eligible
        if not FeatureFlags.is_jira_reporter_global():
            # Need to check channel-specific flag
            features = channel_data.get("features", {})
            if not features.get("jira_reporter_enabled", False):
                logger.info(
                    f"JIRA reporter not enabled for channel {channel_id}, skipping trigger"
                )
                return

        # Send event to queue
        queue_url = os.environ.get("KETCHUP_EVENTS_QUEUE_URL")
        if not queue_url:
            logger.warning(
                "KETCHUP_EVENTS_QUEUE_URL not configured, skipping JIRA report trigger"
            )
            return

        sqs_client = SQSClient(queue_url=queue_url)
        success = await sqs_client.send_message(
            {
                "event_type": "channel_archived",
                "service": "jira_reporter",
                "channel_id": channel_id,
                "jira_ticket": jira_ticket,
                "channel_name": channel_data.get("channel_name", ""),
                "timestamp": int(time.time()),
            }
        )

        if success:
            logger.info(f"Queued JIRA report for archived channel {channel_id}")
            # Mark in DB for tracking
            try:
                await dynamodb_store.channel_ops.update_channel_fields(
                    channel_id=channel_id,
                    updates={
                        "jira_report_trigger": "archive_event_queued",
                        "jira_report_queued_at": int(time.time()),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to update channel metadata for JIRA trigger: {e}")
        else:
            logger.error(f"Failed to queue JIRA report for channel {channel_id}")
