"""
user_join_notification_service.py

Service for generating and sending user join notifications using AI-powered content generation.
This service reuses the exact same data collection workflow as the /ketchup status command.
"""

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import orjson

from packages.ai.prompts.auto_status import (
    get_auto_status_prompt,
    get_auto_status_system_prompt,
)
from packages.core.config.feature_flags import FeatureFlags
from packages.core.constants import USE_PIPELINE_PROCESSING
from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger
from packages.db.models.notification_tracking import FailureReason
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class UserJoinNotificationService:
    """
    Service for generating and sending user join notifications.

    Uses the same data collection workflow as /ketchup status command:
    1. Fetch ALL channel messages via channel_msg_ops
    2. Get channel metadata via channel_info_ops
    3. Enrich with JIRA context via jira_extractor
    4. Generate AI content using auto_status prompts
    5. Format and send ephemeral notification
    """

    def __init__(
        self,
        openai_handler,
        posting_handler: SlackPostingHandler,
        channel_info_ops: ChannelInfoOps,
        channel_msg_ops: SlackChannelMessageOps,
        jira_extractor: Optional[Any] = None,
        user_store: Optional[Any] = None,
        join_notification_ops: Optional[Any] = None,
    ):
        """
        Initialize the UserJoinNotificationService.

        Args:
            openai_handler: OpenAI handler for AI content generation
            posting_handler: Slack posting handler for ephemeral messages
            channel_info_ops: Service for channel info lookups
            channel_msg_ops: Service for channel message operations
            jira_extractor: Optional JIRA data extractor for enrichment
            user_store: Optional user store for checking user preferences
            join_notification_ops: Optional join notification tracking operations
        """
        self.openai_handler = openai_handler
        self.posting_handler = posting_handler
        self.channel_info_ops = channel_info_ops
        self.channel_msg_ops = channel_msg_ops
        self.jira_extractor = jira_extractor
        self.user_store = user_store
        self.join_notification_ops = join_notification_ops

        logger.info("UserJoinNotificationService initialized")

    def _map_error_to_failure_reason(self, error_type: str) -> str:
        """
        Map internal error types to FailureReason enum values.

        Args:
            error_type: Internal error type string

        Returns:
            FailureReason enum value string
        """
        error_mappings = {
            "CHANNEL_DATA_COLLECTION_FAILED": FailureReason.DATA_COLLECTION_FAILED.value,
            "AI_CONTENT_GENERATION_FAILED": FailureReason.AI_GENERATION_FAILED.value,
            "NOTIFICATION_DELIVERY_FAILED": FailureReason.SLACK_API_ERROR.value,
            "EXCEPTION_DURING_PROCESSING": FailureReason.INTERNAL_ERROR.value,
        }
        return error_mappings.get(error_type, FailureReason.INTERNAL_ERROR.value)

    async def send_join_notification(
        self,
        user_id: str,
        channel_id: str,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send a join notification to a user who joined a channel.

        Args:
            user_id: Slack user ID of the person who joined
            channel_id: Slack channel ID where the user joined
            user_profile: Optional user profile data from Slack

        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        try:
            # Fetch user data once for both preferences check and profile
            user_data = None
            if self.user_store:
                user_data = await self.user_store.get_user(user_id)

                # Check if user has join notifications enabled
                if user_data and "preferences" in user_data:
                    join_notifications_enabled = user_data["preferences"].get(
                        "join_notifications_enabled", "enabled"
                    )
                    if join_notifications_enabled == "disabled":
                        logger.info(
                            "User %s has join notifications disabled, skipping notification for channel %s",
                            user_id,
                            channel_id,
                        )
                        # Track disabled notification
                        if self.join_notification_ops:
                            tracking_data = {
                                "user_id": user_id,
                                "channel_id": channel_id,
                                "delivery_status": "disabled",
                                "notification_attempted": False,
                                "timestamp": int(time.time()),
                            }
                            await self.join_notification_ops.track_notification(tracking_data)
                        return True  # Return True since this is expected behavior

            logger.info(
                "Generating join notification for user %s in channel %s",
                user_id,
                channel_id,
            )

            # Step 1: Use fetched user data as profile if not provided
            if user_profile is None and user_data:
                user_profile = user_data
                logger.info(
                    "Using fetched user data as profile for %s: real_name=%s",
                    user_id,
                    user_data.get("real_name", "Not found"),
                )

            # Step 2: Collect channel data using same workflow as status command
            channel_data = await self._collect_channel_data(channel_id)
            if not channel_data:
                logger.error("Failed to collect channel data for %s", channel_id)
                # Track failed notification due to channel data collection failure
                if self.join_notification_ops:
                    tracking_data = {
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "delivery_status": "failed",
                        "notification_attempted": True,
                        "failure_reason_code": self._map_error_to_failure_reason(
                            "CHANNEL_DATA_COLLECTION_FAILED"
                        ),
                        "error_message": "Failed to collect channel data",
                        "timestamp": int(time.time()),
                    }
                    await self.join_notification_ops.track_notification(tracking_data)
                return False

            # Step 3: Generate AI content using auto_status prompts
            ai_content = await self._generate_notification_content(channel_data)
            if not ai_content:
                logger.error("Failed to generate AI content for channel %s", channel_id)
                # Track failed notification due to AI content generation failure
                if self.join_notification_ops:
                    tracking_data = {
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "delivery_status": "failed",
                        "notification_attempted": True,
                        "failure_reason_code": self._map_error_to_failure_reason(
                            "AI_CONTENT_GENERATION_FAILED"
                        ),
                        "error_message": "Failed to generate AI content",
                        "timestamp": int(time.time()),
                    }
                    await self.join_notification_ops.track_notification(tracking_data)
                return False

            # Step 4: Format final notification message
            final_message = self._format_final_notification(
                ai_content=ai_content,
                channel_data=channel_data,
                user_profile=user_profile,
            )

            # Step 5: Send ephemeral notification
            success = await self._send_ephemeral_notification(
                user_id=user_id, channel_id=channel_id, message=final_message
            )

            if success:
                logger.info(
                    "Successfully sent join notification to user %s in channel %s",
                    user_id,
                    channel_id,
                )
                # Track successful notification delivery
                if self.join_notification_ops:
                    tracking_data = {
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "delivery_status": "success",
                        "notification_attempted": True,
                        "timestamp": int(time.time()),
                    }
                    await self.join_notification_ops.track_notification(tracking_data)
            else:
                logger.error(
                    "Failed to send join notification to user %s in channel %s",
                    user_id,
                    channel_id,
                )
                # Track failed notification delivery
                if self.join_notification_ops:
                    tracking_data = {
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "delivery_status": "failed",
                        "notification_attempted": True,
                        "failure_reason_code": self._map_error_to_failure_reason(
                            "NOTIFICATION_DELIVERY_FAILED"
                        ),
                        "error_message": "Failed to send ephemeral notification",
                        "timestamp": int(time.time()),
                    }
                    await self.join_notification_ops.track_notification(tracking_data)

            return success

        except Exception as e:
            logger.error(
                "Error sending join notification to user %s in channel %s: %s",
                user_id,
                channel_id,
                str(e),
                exc_info=True,
            )
            # Track exception during notification processing
            if self.join_notification_ops:
                tracking_data = {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "delivery_status": "failed",
                    "notification_attempted": True,
                    "failure_reason_code": self._map_error_to_failure_reason(
                        "EXCEPTION_DURING_PROCESSING"
                    ),
                    "error_message": str(e)[:512],  # Truncate to avoid oversized messages
                    "timestamp": int(time.time()),
                }
                try:
                    await self.join_notification_ops.track_notification(tracking_data)
                except Exception as tracking_error:
                    logger.warning("Failed to track notification exception: %s", tracking_error)
            return False

    async def _collect_channel_data(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Collect channel data using the same workflow as status command.

        This follows the exact pattern:
        1. channel_msg_ops.fetch_channel_messages(limit=999999999) - ALL messages
        2. channel_info_ops.get_channel_info_from_api() - channel metadata from Slack API
        3. Get JIRA ticket from DynamoDB (missing step!)
        4. jira_extractor.get_jira_context() - JIRA enrichment via MCP

        Args:
            channel_id: Channel to collect data for

        Returns:
            Dict containing channel data or None if collection fails
        """
        try:
            logger.info(
                "Collecting channel data for %s using status command workflow",
                channel_id,
            )

            # Concurrent data collection (same as MessagePreparer.prepare_messages)
            # Choose fetch method based on feature flag
            if USE_PIPELINE_PROCESSING:
                fetch_task = self.channel_msg_ops.fetch_channel_messages_collected(
                    channel_id=channel_id,
                    limit=999999999,  # Fetch ALL messages as per plan
                    use_parallel_pagination=True,  # Enable optimization
                )
            else:
                fetch_task = self.channel_msg_ops.fetch_channel_messages(
                    channel_id=channel_id,
                    limit=999999999,  # Fetch ALL messages as per plan
                    use_parallel_pagination=True,  # Enable optimization
                )

            results = await asyncio.gather(
                self.channel_info_ops.get_channel_info_from_api(channel_id),
                fetch_task,
                return_exceptions=True,
            )

            channel_details, messages_list = results

            # Handle exceptions from gather
            if isinstance(channel_details, Exception):
                logger.error(
                    "Failed to get channel details for %s: %s",
                    channel_id,
                    str(channel_details),
                )
                return None

            if isinstance(messages_list, Exception):
                logger.error(
                    "Failed to fetch messages for %s: %s",
                    channel_id,
                    str(messages_list),
                )
                return None

            if not channel_details:
                logger.error("No channel details returned for %s", channel_id)
                return None

            # Check if bot is member (required for data access)
            if not channel_details.get("is_member"):
                logger.warning(
                    "Bot is not a member of channel %s, cannot generate notification",
                    channel_id,
                )
                return None

            # Prepare message texts for JIRA enrichment
            if not messages_list:
                logger.warning("No messages found in channel %s", channel_id)
                message_texts = ["(No messages found in channel)"]
            else:
                message_texts = messages_list

            # Step 3: JIRA enrichment (if extractor available)
            jira_context = ""
            if self.jira_extractor:
                try:
                    jira_context = await self.jira_extractor.get_jira_context(
                        channel_id, message_texts
                    )
                    logger.info("JIRA context enrichment completed for channel %s", channel_id)
                except Exception as e:
                    logger.warning("JIRA enrichment failed for channel %s: %s", channel_id, str(e))
                    # Continue without JIRA context

            # Extract JIRA ticket from context if available
            jira_ticket = None
            if jira_context and isinstance(jira_context, dict):
                jira_ticket = jira_context.get("ticket_id")

            collected_data = {
                "channel_details": channel_details,
                "messages": message_texts,
                "jira_context": jira_context,
                "jira_ticket": jira_ticket,  # Add extracted ticket ID
                "channel_id": channel_id,
                "channel_name": channel_details.get("name", "unknown_channel"),
            }

            return collected_data

        except Exception as e:
            logger.error(
                "Unexpected error collecting channel data for %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return None

    async def _generate_notification_content(self, channel_data: Dict[str, Any]) -> Optional[str]:
        """
        Generate AI notification content using auto_status prompts.

        This reuses the exact auto_status prompt system:
        - Provides JIRA as context (line 30 in auto_status.py)
        - AI excludes JIRA from output (line 62 instruction)
        - Returns Overview + 4 bullets only

        Args:
            channel_data: Dictionary containing channel details and messages

        Returns:
            Generated AI content or None if generation fails
        """
        try:
            channel_details = channel_data["channel_details"]

            # Build channel_info structure for auto_status prompt (same format as status command)
            channel_info = {
                "channel_id": channel_data["channel_id"],
                "channel_name": channel_data["channel_name"],
                "customer_name": channel_details.get("customer_name", "Unknown"),
                "jira_ticket": channel_details.get("jira_ticket", "None"),
                "product": channel_details.get("product", "Unknown"),
            }

            # Use auto_status prompts (same as status command)
            user_prompt = get_auto_status_prompt(channel_info)
            system_prompt = get_auto_status_system_prompt()

            # Combine messages and JIRA context for AI processing
            combined_text = "\n".join(channel_data["messages"])
            if channel_data["jira_context"]:
                combined_text += f"\n\nJIRA Context:\n{channel_data['jira_context']}"

            # Prepare messages for OpenAI (same structure as other commands)
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"{user_prompt}\n\nChannel Data:\n{combined_text}",
                },
            ]

            logger.info("Calling OpenAI for notification content generation")

            # Build payload using ApiExecutor's method (correct API pattern)
            payload = self.openai_handler._api_executor.build_openai_payload(
                messages=messages,
                combined_command="status",  # Use status command for token allocation
                normalized_prefs={"temperature": 0.1},  # Consistent with status command
            )

            # Execute request using correct API signature
            response_data = await self.openai_handler._api_executor.execute_request(
                payload=payload,
                channel_info=None,  # No re-archiving needed for notifications
                user_id=None,  # No specific user context needed
                incoming_channel=None,  # No incoming channel context needed
            )

            if not response_data or "choices" not in response_data or not response_data["choices"]:
                logger.error("Invalid OpenAI response format")
                return None

            # Extract content using correct format (learned from rollback)
            raw_content = response_data["choices"][0]["message"]["content"]

            # Extract from JSON if structured output is enabled
            if FeatureFlags.is_structured_json_output_enabled():
                try:
                    data = orjson.loads(raw_content)
                    ai_content = data.get("response_text", raw_content)
                    logger.info(
                        "Extracted text from JSON response (%d chars)",
                        len(ai_content),
                    )
                except orjson.JSONDecodeError as e:
                    logger.error(
                        "Failed to parse JSON response, falling back to raw content: %s",
                        e,
                    )
                    ai_content = raw_content
            else:
                # Prose mode - return as-is
                ai_content = raw_content

            logger.info("AI content generation successful")
            return ai_content

        except Exception as e:
            logger.error("Error generating AI notification content: %s", str(e), exc_info=True)
            return None

    def _format_final_notification(
        self,
        ai_content: str,
        channel_data: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Format the final notification message following exact specification.

        Format (from plan):
        👋 Hi [FirstName]! Welcome to <#[channel_id]|[channel_name]>!
        Here's what's happening in this channel (Generated: [DD-MMM-YYYY, HH:MM UTC])

        [AI-generated Overview and 4 bullets]

        JIRA Ticket: <https://jira.corp.adobe.com/browse/[TICKET]|[TICKET]>

        Want more details? Try `/ketchup status` or `/ketchup report`
        Don't want these notifications? New to Ketchup? Request access via `/ketchup access` to control preferences in Home Tab

        Args:
            ai_content: AI-generated overview and bullets
            channel_data: Channel data including JIRA ticket
            user_profile: Optional user profile for first name extraction

        Returns:
            Formatted final notification message
        """
        # Extract first name from user profile
        first_name = "there"  # Default fallback
        if user_profile and "real_name" in user_profile:
            real_name = user_profile["real_name"]
            # Extract first name (split on space, take first part)
            if real_name and real_name.strip():
                first_name = real_name.split()[0]

        # Get channel info for clickable format
        channel_id = channel_data["channel_id"]
        channel_name = channel_data["channel_name"]

        # Generate UTC timestamp in required format: DD-MMM-YYYY, HH:MM UTC
        now_utc = datetime.now(timezone.utc)
        timestamp = now_utc.strftime("%d-%b-%Y, %H:%M UTC")

        # Start with greeting and header (single wave emoji as specified)
        message_parts = [
            f"👋 Hi *{first_name}!* Welcome to <#{channel_id}|{channel_name}>!",
            f"Here's what's happening in this channel (Generated: {timestamp})",
            "",
            ai_content.strip(),
        ]

        # Apply JIRA ticket corrections using exact status-updater pattern
        ai_content_with_jira = self._apply_jira_corrections(
            content=ai_content.strip(), channel_data=channel_data
        )

        # Replace the ai_content in message_parts with corrected version
        message_parts[3] = ai_content_with_jira

        # Add footer with command suggestions
        message_parts.extend(
            [
                "",
                """
Want more details? Try `/ketchup status` or `/ketchup report`
Don't want these notifications? New to Ketchup? Request access via `/ketchup access` to control preferences in Home Tab
            """,
            ]
        )

        return "\n".join(message_parts)

    async def _send_ephemeral_notification(
        self, user_id: str, channel_id: str, message: str
    ) -> bool:
        """
        Send ephemeral notification using SlackPostingHandler._post_ephemeral.

        Args:
            user_id: User to send notification to
            channel_id: Channel where user joined
            message: Formatted notification message

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            logger.info(
                "Sending ephemeral join notification to user %s in channel %s",
                user_id,
                channel_id,
            )

            # Use direct ephemeral posting (no response_url needed)
            response = await self.posting_handler._post_ephemeral(
                user_id=user_id, channel_id=channel_id, message=message
            )

            # Check response success
            if isinstance(response, dict) and response.get("ok") is not False:
                logger.info("Join notification sent successfully")
                return True
            else:
                logger.error(
                    "Ephemeral notification failed: %s",
                    (
                        response.get("error", "Unknown error")
                        if isinstance(response, dict)
                        else "Invalid response"
                    ),
                )
                return False

        except Exception as e:
            logger.error(
                "Error sending ephemeral notification to user %s in channel %s: %s",
                user_id,
                channel_id,
                str(e),
                exc_info=True,
            )
            return False

    def _apply_jira_corrections(self, content: str, channel_data: Dict[str, Any]) -> str:
        """
        Apply JIRA ticket corrections using exact status-updater pattern.

        Args:
            content: AI-generated content
            channel_data: Channel data including jira_ticket extracted from jira_context

        Returns:
            Content with proper JIRA ticket formatting
        """
        # Get JIRA ticket from channel_data (extracted from jira_context)
        jira_ticket = channel_data.get("jira_ticket", "NOT YET AVAILABLE")

        # Step 1: Remove any existing JIRA line from AI output (to replace with correct format)
        content = self._remove_jira_line(content)

        # Step 2: Determine which JIRA ticket to use (exact status-updater pattern)
        if jira_ticket and jira_ticket != "NOT YET AVAILABLE":
            # Use ticket from database
            final_ticket = jira_ticket
        else:
            # Try to extract valid JIRA ticket from the content
            final_ticket = self._extract_valid_jira_ticket(content)

        # Step 3: Add JIRA line only if we have a valid ticket
        if final_ticket:
            jira_line = (
                f"\nJIRA Ticket: <https://jira.corp.adobe.com/browse/{final_ticket}|{final_ticket}>"
            )
            content = content.rstrip() + jira_line
        else:
            logger.warning("No valid JIRA ticket found for notification")

        return content

    def _remove_jira_line(self, content: str) -> str:
        """Remove any existing JIRA ticket line from the content."""
        # Match various JIRA line formats the AI might generate
        patterns = [
            r"\n*JIRA Ticket:.*(?:\n|$)",  # Any line starting with "JIRA Ticket:"
            r"\n*JIRA:.*(?:\n|$)",  # Any line starting with "JIRA:"
            r"\n*Ticket:.*(?:\n|$)",  # Any line starting with "Ticket:"
        ]

        for pattern in patterns:
            content = re.sub(pattern, "", content, flags=re.MULTILINE | re.IGNORECASE)

        return content

    def _extract_valid_jira_ticket(self, text: str) -> Optional[str]:
        """
        Extract the first valid JIRA ticket from text using approved projects only.

        Args:
            text: Text to search for JIRA tickets

        Returns:
            First valid JIRA ticket found or None
        """
        # Build pattern from valid ticket prefixes
        pattern = rf'\b({"|".join(VALID_JIRA_PROJECTS)})-[0-9]{{1,7}}(?![0-9])\b'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0).upper() if match else None
