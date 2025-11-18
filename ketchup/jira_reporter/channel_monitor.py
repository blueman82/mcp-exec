"""
channel_monitor.py

Service for monitoring channels that need JIRA reporting.
Supports both active and archived channels.
"""

import time
from typing import List, Dict, Any, Optional

from packages.core.constants import USE_PIPELINE_PROCESSING
from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from .jira_ticket_discovery import JiraTicketDiscovery

logger = setup_logger(__name__)


class ChannelMonitor:
    """Monitors DynamoDB for channels that need JIRA reporting."""
    
    def __init__(
        self, 
        dynamodb_store: DynamoDBStore, 
        jira_discovery: Optional[JiraTicketDiscovery] = None,
        lookback_hours: int = 24,
        msg_ops: Optional[Any] = None
    ):
        """
        Initialize the archive monitor.
        
        Args:
            dynamodb_store: Pre-initialized DynamoDBStore
            jira_discovery: Optional JIRA discovery service for finding missing tickets
            lookback_hours: How many hours back to check for archived channels
            msg_ops: Channel message operations for checking activity
        """
        self.dynamodb_store = dynamodb_store
        self.jira_discovery = jira_discovery
        self.lookback_hours = lookback_hours
        self.msg_ops = msg_ops
        
    async def get_channels_needing_reports(self) -> List[Dict[str, Any]]:
        """
        Get channels that need JIRA reports.
        Uses reverse lookup to find channels with JIRA tickets.
        Only returns channels that have been quiet for 24+ hours.
        
        Returns:
            List of channel metadata dictionaries
        """
        try:
            # Get ALL channels (including active ones)
            # main.py will handle the feature flag filtering
            logger.info("Fetching all channels with JIRA tickets...")
            all_channels = await self.dynamodb_store.get_all_channel_details()
            
            # Filter for channels that have valid JIRA tickets and are CSO channels
            eligible_channels = []
            
            for channel_id, channel_data in all_channels.items():
                # Check for valid JIRA ticket
                jira_ticket = channel_data.get("jira_ticket", "")
                if not jira_ticket or jira_ticket == "NOT YET AVAILABLE":
                    continue
                
                # Check if it's a CSO channel
                channel_name = channel_data.get("channel_name", "")
                if "cso" not in channel_name.lower():
                    continue
                
                # Check JIRA report status - skip if already processed
                jira_report_status = channel_data.get("jira_report_status", "")

                # Skip ALL processed channels permanently
                if jira_report_status == "PROCESSED":
                    logger.info(
                        f"Channel {channel_id} already processed, skipping permanently"
                    )
                    continue

                # Check for FAILED status with retry limit
                if jira_report_status == "FAILED":
                    # Get the last attempt timestamp and retry count
                    last_attempt_ts = channel_data.get("jira_report_timestamp", 0)
                    retry_count = channel_data.get("jira_report_retry_count", 0)
                    max_retries = 3  # Maximum number of retry attempts
                    retry_cooldown_hours = 24  # Wait 24 hours between retries

                    # Skip if max retries exceeded
                    if retry_count >= max_retries:
                        logger.info(
                            f"Channel {channel_id} has exceeded max retries ({max_retries}), skipping permanently"
                        )
                        continue

                    # Skip if in cooldown period
                    current_time = time.time()
                    hours_since_last_attempt = (current_time - last_attempt_ts) / 3600
                    if hours_since_last_attempt < retry_cooldown_hours:
                        logger.info(
                            f"Channel {channel_id} is in cooldown period "
                            f"({hours_since_last_attempt:.1f}h < {retry_cooldown_hours}h), skipping"
                        )
                        continue

                    logger.info(
                        f"Channel {channel_id} FAILED status - retry {retry_count + 1}/{max_retries} "
                        f"after {hours_since_last_attempt:.1f}h cooldown"
                    )
                
                # Skip archived channels - they'll be handled by SQS events
                is_archived = channel_data.get("archived", False)
                if is_archived:
                    logger.info(f"Channel {channel_id} is archived, skipping (handled by SQS)")
                    continue
                
                # NEW: Check channel activity - only report if quiet for 24+ hours
                if self.msg_ops:
                    last_activity_hours = await self._get_hours_since_last_activity(channel_id)
                    if last_activity_hours is not None and last_activity_hours < self.lookback_hours:
                        logger.info(
                            f"Channel {channel_id} ({channel_name}) still active - "
                            f"last message {last_activity_hours:.1f}h ago (need {self.lookback_hours}h quiet)"
                        )
                        continue
                    elif last_activity_hours is not None:
                        logger.info(
                            f"Channel {channel_id} ({channel_name}) has been quiet for "
                            f"{last_activity_hours:.1f}h - ready for reporting"
                        )
                
                # Log channel details
                logger.info(
                    f"Channel {channel_id} ({channel_name}) - "
                    f"archived: {is_archived}, ticket: {jira_ticket}, "
                    f"status: {jira_report_status}"
                )
                
                # Add channel_id to the data
                channel_data["channel_id"] = channel_id
                eligible_channels.append(channel_data)
            
            # Sort by priority: newest channels first
            eligible_channels.sort(
                key=lambda ch: -ch.get("archived_at", 0)  # Newest first
            )
            
            logger.info(f"Found {len(eligible_channels)} eligible channels for JIRA reporting")
            return eligible_channels
            
        except Exception as e:
            logger.error(f"Error getting channels needing reports: {str(e)}")
            return []
    
    async def _get_hours_since_last_activity(self, channel_id: str) -> Optional[float]:
        """
        Get hours since last message in channel.
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            Hours since last message, or None if error
        """
        try:
            # Fetch messages to trigger the latest_message_ts update
            if USE_PIPELINE_PROCESSING:
                messages = await self.msg_ops.fetch_channel_messages_collected(
                    channel_id=channel_id,
                    limit=1
                )
            else:
                messages = await self.msg_ops.fetch_channel_messages(
                    channel_id=channel_id,
                    limit=1
                )
            
            if not messages:
                logger.info(f"Channel {channel_id} has no messages")
                # No messages means it's been quiet forever - return large number
                return 999999.0
            
            # Get the latest message timestamp from the msg_ops property
            latest_ts = self.msg_ops.latest_message_ts
            if latest_ts:
                last_message_ts = float(latest_ts)
                hours_since = (time.time() - last_message_ts) / 3600
                logger.info(
                    f"Channel {channel_id} last activity: {hours_since:.1f} hours ago"
                )
                return hours_since
            else:
                # If no timestamp available, assume it's been quiet for a long time
                logger.warning(
                    f"No timestamp available for channel {channel_id}, assuming quiet"
                )
                return 999999.0
                
        except Exception as e:
            logger.error(f"Error getting last activity for channel {channel_id}: {str(e)}")
            return None