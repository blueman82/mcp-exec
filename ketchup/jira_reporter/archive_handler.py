"""
archive_handler.py

Handles archive/unarchive operations for the JIRA reporter.
Simplified version without user context dependencies.
"""

import time
from typing import Optional

from packages.core.constants import RESTORE_STATE_TTL_SECONDS
from packages.core.logging import setup_logger
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_bot_membership_ops import SlackChannelBotMembershipOps
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


class JiraReporterArchiveHandler:
    """Handles archive operations for the JIRA reporter service."""
    
    def __init__(
        self,
        archive_ops: SlackChannelArchiveOps,
        dynamodb_store: DynamoDBStore,
        bot_membership_ops: SlackChannelBotMembershipOps,
        secrets_manager: SecretsManager,
    ):
        """
        Initialize the archive handler.
        
        Args:
            archive_ops: Slack archive operations for channel archiving
            dynamodb_store: DynamoDB store for updating channel state
            bot_membership_ops: Bot membership operations for checking/joining channels
            secrets_manager: Secrets manager for getting bot user ID
        """
        self.archive_ops = archive_ops
        self.dynamodb_store = dynamodb_store
        self.bot_membership_ops = bot_membership_ops
        self.secrets_manager = secrets_manager
        
    async def temporarily_unarchive_channel(self, channel_id: str) -> bool:
        """
        Temporarily unarchive a channel for JIRA report processing.
        Mirrors SlackChannelRestoreOps pattern with real-time checks.
        
        Args:
            channel_id: The Slack channel ID to unarchive
            
        Returns:
            True if successful or already unarchived, False otherwise
        """
        try:
            logger.info(f"Checking archive status for channel {channel_id}")
            
            # First check real-time channel status (like SlackChannelRestoreOps does)
            channel_info = await self.archive_ops.get_channel_info(channel_id)
            if not channel_info.get("ok", False):
                error_msg = channel_info.get("error", "unknown error")
                logger.error(f"Failed to get channel info for {channel_id}: {error_msg}")
                return False
                
            channel_data = channel_info.get("channel", {})
            is_archived = channel_data.get("is_archived", False)
            
            # If already unarchived, no need to do anything
            if not is_archived:
                logger.info(f"Channel {channel_id} is already unarchived, no action needed")
                return True
            
            # Channel is archived, proceed with unarchiving
            logger.info(f"Channel {channel_id} is archived, proceeding with unarchive")
            success = await self.archive_ops.unarchive_channel(channel_id)
            
            if success:
                logger.info(f"Successfully unarchived channel {channel_id}")
                
                # Check bot membership and join if needed
                bot_user_id = await self.secrets_manager.get_bot_slack_user_id_async()
                is_member = await self.bot_membership_ops.check_bot_channel_membership(channel_id)
                
                if not is_member:
                    logger.info(f"Bot is not a member of channel {channel_id}, attempting to join")
                    
                    # Get channel name for logging
                    channel_name = channel_data.get("name", "unknown")
                    
                    # Attempt to join the channel
                    join_result = await self._join_channel(channel_id, channel_name, bot_user_id)
                    
                    if not join_result:
                        logger.error(f"Failed to join channel {channel_id}, re-archiving")
                        # Re-archive since we can't proceed without being in the channel
                        await self.archive_ops.archive_channel(
                            user_id=None,
                            channel_id=channel_id,
                            incoming_channel=None,
                            skip_status_check=True
                        )
                        return False
                    
                    logger.info(f"Successfully joined channel {channel_id}")
                else:
                    logger.info(f"Bot is already a member of channel {channel_id}")
                
                # Update DynamoDB to track temporary unarchive
                ttl_timestamp = int(time.time()) + RESTORE_STATE_TTL_SECONDS  # 180 seconds (3 minutes)
                await self.dynamodb_store.update_channel_fields(
                    channel_id=channel_id,
                    updates={
                        "archived": False,
                        "temporary_unarchive": True,
                        "unarchive_reason": "jira_reporter_processing",
                        "unarchive_timestamp": int(time.time()),
                        "temp_unarchive_expiry": ttl_timestamp
                    }
                )
                
                return True
            else:
                logger.error(f"Failed to unarchive channel {channel_id}")
                return False
                
        except Exception as e:
            logger.error(f"Exception unarchiving channel {channel_id}: {str(e)}", exc_info=True)
            return False
    
    async def _join_channel(self, channel_id: str, channel_name: str, bot_user_id: str) -> bool:
        """
        Join a channel using the bot membership operations with correct bot token.
        
        Args:
            channel_id: The Slack channel ID to join
            channel_name: The channel name for logging
            bot_user_id: The bot user ID to invite
            
        Returns:
            True if successfully joined, False otherwise
        """
        try:
            # Use bot_membership_ops which has the correct bot token
            response = await self.bot_membership_ops.invite_ketchup_to_channel(
                channel_id=channel_id,
                bot_user_id=bot_user_id,
                channel_name=channel_name
            )
            
            if response.get("ok"):
                logger.info(f"Successfully joined channel {channel_id} ({channel_name})")
                return True
            else:
                error = response.get("error", "unknown")
                logger.error(f"Failed to join channel {channel_id}: {error}")
                
                # Handle specific errors
                if error == "already_in_channel":
                    logger.info(f"Bot already in channel {channel_id}, treating as success")
                    return True
                elif error == "is_archived":
                    logger.error(f"Cannot join archived channel {channel_id}")
                elif error == "channel_not_found":
                    logger.error(f"Channel {channel_id} not found")
                    
                return False
                
        except Exception as e:
            logger.error(f"Exception joining channel {channel_id}: {str(e)}", exc_info=True)
            return False
    
    async def rearchive_channel(self, channel_id: str) -> bool:
        """
        Re-archive a channel after JIRA report processing.
        Mirrors SlackChannelRestoreOps pattern with real-time checks.
        
        Args:
            channel_id: The Slack channel ID to re-archive
            
        Returns:
            True if successful or already archived, False otherwise
        """
        try:
            logger.info(f"Checking archive status for channel {channel_id}")
            
            # First check real-time channel status (like SlackChannelRestoreOps does)
            channel_info = await self.archive_ops.get_channel_info(channel_id)
            if not channel_info.get("ok", False):
                error_msg = channel_info.get("error", "unknown error")
                logger.error(f"Failed to get channel info for {channel_id}: {error_msg}")
                return False
                
            channel_data = channel_info.get("channel", {})
            is_archived = channel_data.get("is_archived", False)
            
            # If already archived, just update DB state
            if is_archived:
                logger.info(f"Channel {channel_id} is already archived, updating DB state only")
                
                # Still need to clear temporary unarchive state and restore original archived_at
                original_archived_at = None
                try:
                    db_data = await self.dynamodb_store.get_channel_details(channel_id)
                    if db_data:
                        original_archived_at = db_data.get("archived_at")
                except Exception as db_e:
                    logger.warning(f"Could not retrieve original archived_at for {channel_id}: {str(db_e)}")
                
                updates = {
                    "archived": True,
                    "temporary_unarchive": False
                }
                
                if original_archived_at:
                    updates["archived_at"] = original_archived_at
                    logger.info(f"Restoring original archived_at for {channel_id}: {original_archived_at}")
                    
                await self.dynamodb_store.update_channel_fields(
                    channel_id=channel_id,
                    updates=updates
                )
                return True
            
            # Channel is unarchived, proceed with archiving
            logger.info(f"Channel {channel_id} is unarchived, proceeding with re-archive")
            
            # Retrieve original archived_at timestamp before re-archiving
            original_archived_at = None
            try:
                channel_data = await self.dynamodb_store.get_channel_details(channel_id)
                if channel_data:
                    original_archived_at = channel_data.get("archived_at")
            except Exception as db_e:
                logger.warning(f"Could not retrieve original archived_at for {channel_id}: {str(db_e)}")
            
            # Call Slack API to archive using archive ops
            # Skip status check since we just verified it's unarchived
            success = await self.archive_ops.archive_channel(
                user_id=None,
                channel_id=channel_id,
                incoming_channel=None,
                skip_status_check=True
            )
            
            if success:
                logger.info(f"Successfully re-archived channel {channel_id}")
                
                # Update DynamoDB to clear temporary unarchive state and restore original archived_at
                updates = {
                    "archived": True,
                    "temporary_unarchive": False,
                    "rearchive_timestamp": int(time.time())
                }
                
                # Restore original archived_at if available
                if original_archived_at:
                    updates["archived_at"] = original_archived_at
                    logger.info(f"Restoring original archived_at for {channel_id}: {original_archived_at}")
                
                await self.dynamodb_store.update_channel_fields(
                    channel_id=channel_id,
                    updates=updates
                )
                
                return True
            else:
                logger.error(f"Failed to re-archive channel {channel_id}")
                return False
                
        except Exception as e:
            logger.error(f"Exception re-archiving channel {channel_id}: {str(e)}", exc_info=True)
            return False
    
    async def cleanup_stale_unarchives(self) -> int:
        """
        Clean up any channels that were temporarily unarchived but not re-archived.
        This handles cases where the reporter crashed or was stopped mid-process.
        
        Returns:
            Number of channels cleaned up
        """
        try:
            logger.info("Starting cleanup of stale temporary unarchives")
            current_time = int(time.time())
            cleaned_count = 0
            
            # Get all channels from DynamoDB
            all_channels = await self.dynamodb_store.get_all_channel_details()
            
            for channel_id, channel_data in all_channels.items():
                # Check for stale temporary unarchives
                if (channel_data.get("temporary_unarchive") and 
                    channel_data.get("temp_unarchive_expiry")):
                    
                    ttl = channel_data["temp_unarchive_expiry"]
                    if current_time > ttl:
                        logger.warning(
                            f"Found stale temporary unarchive for channel {channel_id} "
                            f"(TTL expired {current_time - ttl} seconds ago)"
                        )
                        
                        # Re-archive the channel
                        success = await self.rearchive_channel(channel_id)
                        if success:
                            cleaned_count += 1
                        else:
                            logger.error(f"Failed to clean up stale unarchive for {channel_id}")
            
            logger.info(f"Cleanup complete. Re-archived {cleaned_count} stale channels")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}", exc_info=True)
            return 0
    
    async def is_channel_archived(self, channel_id: str) -> Optional[bool]:
        """
        Check if a channel is archived using the Slack API.
        
        Args:
            channel_id: The Slack channel ID to check
            
        Returns:
            True if archived, False if not, None if error
        """
        try:
            channel_info = await self.archive_ops.get_channel_info(channel_id)
            
            if channel_info.get("ok"):
                is_archived = channel_info.get("channel", {}).get("is_archived", False)
                return is_archived
            else:
                logger.error(f"Failed to get channel info: {channel_info.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Exception checking channel archive status: {str(e)}")
            return None