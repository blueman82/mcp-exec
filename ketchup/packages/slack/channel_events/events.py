"""
events.py
This module contains the SlackEventHandler class, which is responsible for handling
the different types of Slack events.

The events are:
- channel_created
- member_joined
- channel_archived
- channel_unarchived
"""

from typing import Optional

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.blockkits.base import BlockKitBuilder

# Import archive processor
from packages.slack.channel_events.processing.archive_processor import (
    process_channel_archive,
)

# Import NEW channel creation event handler function
from packages.slack.channel_events.processing.creation_processor import (
    handle_channel_creation_event,
)

# Import join processor
from packages.slack.channel_events.processing.join_processor import (
    handle_member_joined_event,
)

# Import unarchive processor
from packages.slack.channel_events.processing.unarchive_processor import (
    invite_and_verify_bot_after_unarchive,
)
from packages.slack.channel_operations.channel_eligibility import (
    ChannelEligibilityService,
)
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_membership_ops import (
    ChannelMembershipOps,
)
from packages.slack.channel_operations.channel_restore_ops import SlackChannelRestoreOps
from packages.slack.channel_operations.restore_state_manager import RestoreStateManager
from packages.slack.command_processing.list_command import SlackListCommand
from packages.slack.maintenance.jira_prompt_handler import JiraPromptHandler
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SlackEventHandler:
    """
    This class is responsible for handling the different types of Slack events.
    Relies on injected dependencies.
    """

    def __init__(
        self,
        secrets_manager: SecretsManager,
        dynamodb_store: DynamoDBStore,
        posting_handler: SlackPostingHandler,
        channel_info_ops: ChannelInfoOps,
        channel_membership_ops: ChannelMembershipOps,
        channel_restore_ops: SlackChannelRestoreOps,
        block_kit_builder: BlockKitBuilder,
        channel_eligibility_service: ChannelEligibilityService,
        restore_state_manager: Optional[RestoreStateManager] = None,
        list_command: Optional[SlackListCommand] = None,
        feature_service=None,
        user_join_notification_service=None,
        user_store=None,
    ):
        """
        Initialize the SlackEventHandler with injected dependencies.

        Args:
            secrets_manager: Manager for Slack secrets
            dynamodb_store: Store for DynamoDB operations
            posting_handler: Handler for posting messages to Slack
            channel_info_ops: Operations for single channel lookups.
            channel_membership_ops: Operations for channel membership lookups.
            channel_restore_ops: Operations for channel restore/join
            block_kit_builder: Builder for Block Kit messages
            channel_eligibility_service: Service for checking channel eligibility
            list_command: Optional command for listing channels
            feature_service: Optional service for managing feature flags
            user_join_notification_service: Optional service for user join notifications
        """
        self.secrets_manager = secrets_manager
        self.dynamodb_store = dynamodb_store
        self.posting_handler = posting_handler
        self.channel_info_ops = channel_info_ops
        self.channel_membership_ops = channel_membership_ops
        self.channel_restore_ops = channel_restore_ops
        self.block_kit_builder = block_kit_builder
        self.channel_eligibility_service = channel_eligibility_service
        self.restore_state_manager = restore_state_manager
        self.list_command = list_command
        self.feature_service = feature_service
        self.user_join_notification_service = user_join_notification_service
        self.user_store = user_store
        logger.info("SlackEventHandler initialized with injected dependencies.")

    async def handle_channel_created(
        self, event: dict, response_url: Optional[str] = None
    ):
        """
        Handle channel_created event by dispatching to the standalone handler.

        Args:
            event: The Slack event data for channel creation
            response_url: Optional response URL for feedback
        """
        logger.info(
            "Dispatching channel_created event for channel %s",
            event.get("channel", {}).get("id", "UNKNOWN"),
        )
        # Call the new standalone handler function, passing dependencies from self
        await handle_channel_creation_event(
            event=event,
            response_url=response_url,
            secrets_manager=self.secrets_manager,
            channel_restore_ops=self.channel_restore_ops,
            dynamodb_store=self.dynamodb_store,
            posting_handler=self.posting_handler,
        )

    async def handle_member_joined_channel(
        self, event: dict, response_url: Optional[str] = None
    ):
        """
        Handle member_joined_channel event by dispatching to the standalone handler.

        Args:
            event: The event data
            response_url: Optional response URL
        """
        logger.info(
            "Dispatching member_joined_channel event for user %s in channel %s",
            event.get("user", "UNKNOWN"),
            event.get("channel", "UNKNOWN"),
        )
        # Call the new standalone handler function
        await handle_member_joined_event(
            event=event,
            response_url=response_url,
            # Pass necessary dependencies
            secrets_manager=self.secrets_manager,
            channel_eligibility_service=self.channel_eligibility_service,
            dynamodb_store=self.dynamodb_store,
            channel_info_ops=self.channel_info_ops,
            posting_handler=self.posting_handler,
            # Add user notification services for regular user joins
            feature_service=self.feature_service,
            user_join_notification_service=self.user_join_notification_service,
            user_store=self.user_store,
            # Add restore state manager to prevent auto-join during unarchive
            restore_state_manager=self.restore_state_manager,
        )

    async def handle_channel_archive(self, event: dict):
        """
        Handle a Slack channel_archive event.

        This function updates the channel status in DynamoDB to reflect that it has
        been archived, including the timestamp when the archival occurred.

        If the channel was previously archived and has a non-zero archived_at timestamp,
        it preserves the original timestamp rather than updating it.

        Args:
            event: Dictionary containing the Slack event data
        """
        start_message = "Starting handle_channel_archive function."
        logger.info(start_message)

        # Extract channel ID from event
        channel_id = event["channel"]

        try:
            # Delegate core processing to the imported function
            await process_channel_archive(
                channel_id=channel_id, dynamodb_store=self.dynamodb_store
            )

        except Exception as e:
            error_message = f"Error handling channel archive event for channel {channel_id}: {str(e)}"
            logger.error(error_message, exc_info=True)

    async def handle_channel_unarchive(self, event: dict):
        """
        Handle a Slack channel_unarchive event.

        Updates the channel status in DynamoDB and invites the bot back.

        Args:
            event: Dictionary containing the Slack event data
        """
        start_message = "Starting handle_channel_unarchive function."
        logger.info(start_message)

        if not event or not isinstance(event, dict) or "channel" not in event:
            logger.error("Invalid event data for channel_unarchive event: %s", event)
            return

        channel_id = event["channel"]
        logger.info("Checking channel %s in DynamoDB.", channel_id)

        try:
            if not self.dynamodb_store:
                logger.error("DynamoDB store is not initialized")
                return

            channel_data = await self.dynamodb_store.get_channel_details_consistent(
                channel_id
            )

            if not channel_data:
                logger.warning(
                    "Channel %s not found in DynamoDB. Skipping.",
                    channel_id,
                )
                return

            # Update DB only if it was marked as archived
            if channel_data.get("archived", False):
                logger.info(
                    "Updating archived status for channel %s in DynamoDB.",
                    channel_id,
                )
                try:
                    await self.dynamodb_store.update_channel_archived_status(
                        channel_id=channel_id, archived=False, archived_at=None
                    )
                    logger.info(
                        "Channel %s marked as unarchived in DynamoDB.",
                        channel_id,
                    )
                except Exception as update_error:
                    logger.error(
                        "Error updating channel archived status: %s", str(update_error)
                    )
                    # Continue anyway to attempt bot invite
            else:
                logger.info(
                    "Channel %s already marked as unarchived. Skipping DB update.",
                    channel_id,
                )

            # Invite bot back using the imported function
            channel_name = channel_data.get("channel_name", "Unknown")
            invite_success = await invite_and_verify_bot_after_unarchive(
                channel_id=channel_id,
                channel_name=channel_name,
                # Pass dependencies
                secrets_manager=self.secrets_manager,
                channel_restore_ops=self.channel_restore_ops,
                channel_info_ops=self.channel_info_ops,
            )

            if not invite_success:
                logger.error(
                    "Failed to invite and verify bot for unarchived channel %s.",
                    channel_id,
                )
                # Consider notifying admin

        except Exception as e:
            error_message = f"Error handling channel unarchive event for channel {channel_id}: {str(e)}"
            logger.error(error_message, exc_info=True)

    async def handle_app_mention(self, event: dict):
        """
        Handle @Ketchup mentions in channels.

        Args:
            event: The Slack event data for app_mention
        """
        logger.info("Handling app_mention event")

        channel_id = event.get("channel")
        text = event.get("text", "")
        user_id = event.get("user")

        # Get bot_user_id from secrets using existing method
        bot_user_id = await self.secrets_manager.get_bot_slack_user_id_async()

        # Filter out bot's own mentions
        if user_id == bot_user_id:
            logger.info("Ignoring bot's own mention")
            return

        # CHECK FOR MAINTENANCE PROMPT FIRST
        maintenance_prompt = await self.dynamodb_store.get_maintenance_prompt(
            channel_id
        )

        if maintenance_prompt:
            # Active prompt exists - this is a reply to maintenance prompt
            jira_ticket = JiraPromptHandler.extract_jira_ticket(text)

            if jira_ticket:
                logger.info(
                    f"Maintenance reply detected: {jira_ticket} in {channel_id}"
                )
                # Send acknowledgment to the user (ephemeral - only visible to them)
                await self.posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message=f"<@{user_id}> Thank you! Processing {jira_ticket}..."
                )
                # Store the reply in DynamoDB (don't delete - let waiting container find it)
                await self.dynamodb_store.store_maintenance_reply(
                    channel_id, jira_ticket
                )
                return  # Done - waiting container will pick up the reply
        else:
            # No active prompt, but check if user is providing a late JIRA ticket
            jira_ticket = JiraPromptHandler.extract_jira_ticket(text)
            
            if jira_ticket:
                # User provided JIRA ticket but prompt workflow already completed
                logger.info(
                    f"Late JIRA ticket reply detected: {jira_ticket} in {channel_id} "
                    "(no active prompt)"
                )
                await self.posting_handler.post_message(
                    channel_id=channel_id,
                    message=(
                        f"<@{user_id}> I see you provided {jira_ticket}, but the "
                        "maintenance check workflow has already completed."
                    )
                )
                return

        # Check if this is a Ketchup-generated message
        ketchup_markers = [
            "Generated by Ketchup",
            "Please rate the summary",
            "bar_chart",
            "ketchup:",
            "Response:",
            "Query:",
        ]

        if any(marker in text for marker in ketchup_markers):
            logger.info("Ignoring app mention in Ketchup-generated message")
            return

        # Log the event
        logger.info(
            f"App mentioned by user {user_id} in channel {channel_id}: {event.get('text')}"
        )

    async def handle_message(self, event: dict):
        """
        Handle general message events that might contain bot mentions.

        Args:
            event: The Slack event data for message
        """
        logger.info("Handling message event")

        # Get bot user ID
        bot_user_id = await self.secrets_manager.get_bot_slack_user_id_async()

        # Filter out bot's own messages early to prevent unnecessary processing
        if event.get("user") == bot_user_id:
            logger.info("Ignoring bot's own message in handle_message")
            return

        # Also filter out messages with bot_id (messages from any bot/app)
        if event.get("bot_id"):
            logger.info(
                f"Ignoring message from bot/app with bot_id: {event.get('bot_id')}"
            )
            return

        # Check if the message contains a mention of the bot
        text = event.get("text", "")
        if f"<@{bot_user_id}>" in text:
            logger.info(
                f"Bot mentioned in message by user {event.get('user')} in channel {event.get('channel')}: {text}"
            )

        else:
            logger.info(f"Message does not mention bot: {text}")

    async def handle_message_im(self, event: dict):
        """
        Handle direct messages to Ketchup.

        Args:
            event: The Slack event data for message.im
        """
        logger.info("Handling message.im event")

        # Get bot_user_id from secrets
        bot_user_id = await self.secrets_manager.get_bot_slack_user_id_async()

        # Filter out bot's own messages early
        if event.get("user") == bot_user_id:
            logger.info("Ignoring bot's own message in handle_message_im")
            return

        # Also filter out messages with bot_id
        if event.get("bot_id"):
            logger.info(f"Ignoring DM from bot/app with bot_id: {event.get('bot_id')}")
            return

        # Additional check: Ignore messages that look like Ketchup responses
        text = event.get("text", "")
        # Check both plain text and with potential HTML encoding/formatting
        ketchup_markers = [
            "Ketchup App Analysis Results",
            "Generated by Ketchup",
            "Analyzing your request",
            "Please rate the summary",
            "bar_chart",  # Emoji marker
            "ketchup:",  # Emoji marker
            "Response:",  # Common in Ketchup responses
            "Query:",  # Common in Ketchup responses
        ]

        if any(marker in text for marker in ketchup_markers):
            logger.info("Ignoring Ketchup-generated response message to prevent loops")
            return

        # Log the event
        logger.info(
            f"Direct message from user {event.get('user')}: {event.get('text')}"
        )

        # Direct users to slash commands
        await self.posting_handler.post_message(
            channel_id=event.get("channel"),
            message="Thanks for your message! Please use `/ketchup` to see available commands.",
        )
