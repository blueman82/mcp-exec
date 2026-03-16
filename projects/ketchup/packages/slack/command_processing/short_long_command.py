"""
short_long_command.py

This module contains the SlackSummaryHandler class,
which is used to process the `/ketchup short` and `/ketchup long` commands.
"""

from typing import Any, Dict, Optional

from packages.core.exceptions import MessagePreparationError
from packages.core.logging import setup_logger
from packages.slack.blockkits.handlers.summary import SummaryMessageHandler
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_decorators import handle_archived_channel
from packages.slack.command_processing.command_parameters.models import (
    CommandParams,
    SummaryCommandParams,
)
from packages.slack.home.home_utils import normalize_user_preferences

logger = setup_logger(__name__)


class SlackSummaryHandler(BaseCommandHandler):
    """
    This class is responsible for processing the `/ketchup short` and `/ketchup long` commands,
    which generate summaries of Slack channel content.
    """

    def __init__(
        self,
        channel_info_ops: ChannelInfoOps,
        archive_ops,
        openai_handler,
        block_kit_builder,
        channel_message_ops,
        slack_posting_handler,
        user_store,
        channel_restore_ops=None,
        dynamodb_store=None,
        feedback_reactions_handler=None,
    ):
        """
        Initialize the SlackSummaryHandler class.

        Args:
            channel_info_ops: Service for channel info lookups.
            archive_ops: Service for archiving/unarchiving channels
            openai_handler: Service for interacting with OpenAI
            block_kit_builder: Service for creating Slack block kit messages
            channel_message_ops: Service for fetching channel messages
            slack_posting_handler: Handler for posting messages to Slack (must be DI, no fallback)
            user_store: UserStore instance for user preferences.
            channel_restore_ops: Handler for restoring archived channels
            dynamodb_store: DynamoDB store for persistence
        """
        super().__init__()
        self.channel_info_ops = channel_info_ops
        self.archive_ops = archive_ops
        self.openai_handler = openai_handler
        self.block_kit_builder = block_kit_builder
        self.channel_message_ops = channel_message_ops
        if slack_posting_handler is None:
            raise ValueError(
                "slack_posting_handler must be provided via DI (with slack_config, secrets_manager)"
            )
        self.slack_posting_handler = slack_posting_handler
        self.user_store = user_store
        self.channel_restore_ops = channel_restore_ops
        self.dynamodb_store = dynamodb_store

        # Extract build_feedback_blocks if available
        feedback_builder_func = None
        if (
            feedback_reactions_handler
            and hasattr(feedback_reactions_handler, "build_feedback_blocks")
            and callable(feedback_reactions_handler.build_feedback_blocks)
        ):
            feedback_builder_func = feedback_reactions_handler.build_feedback_blocks

        self.summary_message_handler = SummaryMessageHandler()
        self.summary_message_handler.configure(
            posting_handler=slack_posting_handler,
            channel_details_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            fallback_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            build_feedback_blocks=feedback_builder_func,
            block_kit_builder=block_kit_builder,
        )
        logger.info("SlackSummaryHandler initialized.")

    async def _resolve_channel_parameter(self, channel_param: str) -> Optional[str]:
        """Resolve channel parameter to actual channel ID."""
        from packages.slack.command_processing.channel_resolver import resolve_channel_parameter

        return await resolve_channel_parameter(channel_param)  # Return as-is on error

    @handle_archived_channel
    async def process_summary_params(
        self,
        params: CommandParams,
        user_id: str,
        channel_id: Optional[str] = None,
        dm_channel_id: Optional[str] = None,
        response_url: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Process the 'short' or 'long' summary command.

        Args:
            params: The command parameters
            user_id: Slack user ID
            channel_id: The target channel ID where the command should be executed
            dm_channel_id: The channel ID where the command was issued (for messaging user)
            response_url: The response URL for interactive components/slash commands

        Returns:
            The generated response or None if there was an error
        """
        # Validate params is the correct type
        if not isinstance(params, SummaryCommandParams):
            logger.error("Invalid params type: %s", type(params))
            return self.create_validation_error_response("Invalid command parameters")

        # Extract parameters from the params object
        target_channel_id = params.target_channel_id
        summary_type = params.summary_type
        command_verified = params.original_command

        # Resolve channel parameter if needed
        resolved_channel_id = await self._resolve_channel_parameter(target_channel_id)
        if resolved_channel_id:
            target_channel_id = resolved_channel_id
        else:
            logger.error("Failed to resolve channel parameter: %s", target_channel_id)
            return self.create_validation_error_response(
                "Could not resolve the specified channel. Please check the channel name or ID and try again."
            )

        # Reroute 'short' command to 'status' with user notification
        if summary_type == "short":
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message=":warning: 'Short' command has been replaced by Status. Running a Status report for you now :clipboard:",
                response_url=response_url,
            )
            summary_type = "status"
            command_verified = command_verified.replace("short", "status", 1)
        # Reroute 'long' command to 'report' with user notification
        elif summary_type == "long":
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message=":warning: 'Long' command has been replaced by Full Report. Running a Full Report for you now :memo:",
                response_url=response_url,
            )
            summary_type = "report"
            command_verified = command_verified.replace("long", "report", 1)

        # Ensure channel_id is the target channel (may be passed differently depending on caller)
        if channel_id is None or channel_id != target_channel_id:
            logger.info("Using target_channel_id %s as channel_id", target_channel_id)
            channel_id = target_channel_id

        # Use incoming_channel as dm_channel_id if provided for backward compatibility
        messaging_channel = dm_channel_id
        if messaging_channel is None and hasattr(params, "incoming_channel"):
            messaging_channel = getattr(params, "incoming_channel", None)
        if messaging_channel is None:
            logger.error("No messaging channel provided for process_summary_params.")
            return self.create_error_response("No messaging channel provided.")

        # Prefer explicit response_url, then params.response_url, then messaging_channel
        effective_response_url = (
            response_url or getattr(params, "response_url", None) or messaging_channel
        )

        # Post initial acknowledgement
        if summary_type == "status":
            ack_message = "Generating status update... :clipboard:"
        elif summary_type == "report":
            ack_message = "Generating full report... :memo:"
        else:
            ack_message = "Generating summary... :memo:"
        await self.slack_posting_handler.post_message(
            user_id=user_id,
            channel_id=messaging_channel,
            message=ack_message,
            response_url=effective_response_url,
        )

        try:
            # Process the summary and get the generated text
            generated_text = await self._process_summary(
                channel_id=channel_id,
                summary_type=summary_type,
                user_id=user_id,
                dm_channel_id=messaging_channel,  # Use messaging_channel here
                response_url=effective_response_url or "",  # Always pass a str
                command_verified=command_verified,
            )
            # Determine title for summary
            title = channel_id  # Default to ID if name isn't easily available here
            try:  # Attempt to get name again, but don't fail if it doesn't work
                channel_details_final = await self.channel_info_ops.get_channel_details(
                    user_id,
                    channel_id,
                    dm_channel_id=messaging_channel,
                    response_url=effective_response_url,
                )
                if channel_details_final:
                    title = channel_details_final[0] or title  # Use name if found
            except Exception:
                logger.warning("Could not re-fetch channel name for Block Kit title.")
            # Prepare summary dict for handler
            summaries = [
                {
                    "name": title,
                    "id": channel_id,
                    "summary": generated_text,
                    "type": summary_type,
                }
            ]
            # Use SummaryMessageHandler to send the formatted summary response
            await self.summary_message_handler.send_message(
                combined_command=command_verified,
                response_url=effective_response_url,
                summaries=summaries,
                target_channel=channel_id,
            )
            return self.create_success_response("Summary generated successfully.")
        except Exception as e:
            logger.error("Error processing summary: %s", str(e), exc_info=True)
            # Try to send an error message back to the user
            try:
                await self.slack_posting_handler.post_message(
                    user_id=user_id,
                    channel_id=messaging_channel,
                    message=f"Sorry, I encountered an error generating the summary: {str(e)}",
                    response_url=effective_response_url,
                )
            except Exception as post_err:
                logger.error("Failed to send error message back to user: %s", post_err)
            # Return an error response for the Lambda
            return self.create_error_response(f"Error processing summary: {str(e)}")

    async def _process_summary(
        self,
        channel_id: str,
        summary_type: str,
        user_id: str,
        dm_channel_id: str,
        response_url: str,
        command_verified: str,
    ) -> str:
        """
        Process the summary and generate a response.

        Args:
            channel_id: The target channel ID
            summary_type: The type of summary ('short' or 'long')
            user_id: The user ID
            dm_channel_id: The channel to send messages to (for error reporting)
            response_url: The response URL for interactive components
            command_verified: The verified command string

        Returns:
            The generated and corrected summary text.

        Raises:
            Exception: If channel details cannot be fetched, membership is invalid,
                       or AI generation fails.
        """
        command_log = f"Processing {summary_type} command for channel_id: {channel_id}"
        logger.info(command_log)

        # Initial processing message is sent by the caller (process_summary_params)

        # Retrieve channel details (Reusing logic from old code)
        channel_details = await self.channel_info_ops.get_channel_details(
            user_id=user_id,
            channel_id=channel_id,
            dm_channel_id=dm_channel_id,
            response_url=response_url,
        )

        if channel_details is None:
            # Error message already sent by get_channel_details
            error_message = f"Could not get channel details for {channel_id}"
            logger.error(error_message)
            raise Exception(error_message)

        channel_name, is_member, _, _ = channel_details

        if not is_member:
            # Error message already sent by get_channel_details
            error_message = f"Bot is not a member of channel {channel_id}"
            logger.info("%s. User notified. Stopping command processing.", error_message)
            raise Exception(error_message)

        # Fetch, define default, extract, and normalize user preferences
        user_data = await self.user_store.get_user(user_id)
        default_raw_prefs = {
            "product_focus": ["all_products"],
            "detail_level": "balanced",
            "time_window": "past_24_hours",  # Default for summaries, can be overridden by prefs
        }
        raw_preferences = (
            user_data.get("preferences", default_raw_prefs) if user_data else default_raw_prefs
        )
        normalized_prefs_for_ai = normalize_user_preferences(raw_preferences)
        logger.info(
            "Summary command (type: %s): user_id=%s, raw_prefs=%s, normalized_prefs_for_ai=%s",
            summary_type,
            user_id,
            raw_preferences,
            normalized_prefs_for_ai,
        )

        # Process command through OpenAI endpoint (Reusing logic from old code)
        # Assumes openai_handler.call_openai_endpoint handles message fetching internally
        try:
            response_data = await self.openai_handler.call_openai_endpoint(
                combined_command=command_verified,
                user_id=user_id,
                incoming_channel=dm_channel_id,  # Pass DM channel for context
                passed_channel_id=channel_id,
                channel_name=channel_name,
                normalized_prefs_for_ai=normalized_prefs_for_ai,  # Pass normalized preferences
                # Note: old code didn't pass query_text for summary, check if needed
            )
        except MessagePreparationError as e:
            logger.error(
                "Message preparation failed for channel %s during summary generation: %s",
                channel_id,
                e,
            )
            # This error is already handled at the channel validation level,
            # but we should raise a more descriptive error for the summary command
            raise Exception(
                f"Unable to generate {summary_type} summary for channel {channel_id}: bot may not be a member of the channel"
            ) from e

        if not response_data or "choices" not in response_data or not response_data["choices"]:
            error_message = "Failed to get valid response from OpenAI for summary"
            logger.error(error_message)
            raise Exception(error_message)

        generated_text = response_data["choices"][0]["message"]["content"]

        # --- Correction Logic (Adapted from old code) --- #
        if self.dynamodb_store and channel_details:
            logger.info(
                "Checking AI summary for missing Customer/JIRA info against DB/Slack details."
            )
            # Use the channel_name from get_channel_details for customer correction
            customer_name_from_slack = channel_name
            placeholder_customer = "Customer Name: NOT YET AVAILABLE"
            if (
                placeholder_customer in generated_text
                and customer_name_from_slack
                and customer_name_from_slack not in ["unknown", "NOT YET AVAILABLE"]
            ):
                generated_text = generated_text.replace(
                    placeholder_customer, f"Customer Name: {customer_name_from_slack}"
                )
                logger.info("Corrected Customer Name in AI summary using Slack API data.")

            # Correct JIRA Ticket using DB data
            placeholder_jira_variations = [
                "Support Ticket: NOT YET AVAILABLE",
                "Support Ticket: NOT YET AVAILABLE",
            ]
            needs_jira_check = any(p in generated_text for p in placeholder_jira_variations)
            if needs_jira_check:
                try:
                    full_channel_details_dict = await self.dynamodb_store.get_channel_details(
                        channel_id
                    )
                    if full_channel_details_dict:
                        jira_ticket_from_db = full_channel_details_dict.get("jira_ticket")
                        if jira_ticket_from_db and jira_ticket_from_db != "NOT YET AVAILABLE":
                            for placeholder in placeholder_jira_variations:
                                if placeholder in generated_text:
                                    generated_text = generated_text.replace(
                                        placeholder,
                                        f"Support Ticket: {jira_ticket_from_db}",
                                    )
                                    logger.info(
                                        "Corrected JIRA Ticket in AI summary using DB data."
                                    )
                                    break
                    else:
                        logger.warning(
                            "Could not fetch full channel details from DB for %s during JIRA correction.",
                            channel_id,
                        )
                except Exception as db_error:
                    logger.error(
                        "Error fetching full details from DB for JIRA correction: %s",
                        db_error,
                    )
        # --- End Correction Logic --- #

        logger.info("Successfully generated %s summary for %s.", summary_type, channel_id)
        return generated_text
        # Note: Block Kit sending is moved to the caller (process_summary_params)

    @classmethod
    async def create(
        cls,
        channel_info_ops: ChannelInfoOps,
        archive_ops,
        openai_handler,
        block_kit_builder,
        channel_message_ops,
        slack_posting_handler,
        user_store,
        channel_restore_ops=None,
        dynamodb_store=None,
    ):
        """
        Create an instance of SlackSummaryHandler with initialized dependencies.

        Args:
            channel_info_ops: Service for channel info lookups
            archive_ops: Service for archiving/unarchiving channels
            openai_handler: Service for interacting with OpenAI
            block_kit_builder: Service for creating Slack block kit messages
            channel_message_ops: Service for fetching channel messages
            slack_posting_handler: Handler for posting messages to Slack
            user_store: UserStore instance for user preferences.
            channel_restore_ops: Handler for restoring archived channels
            dynamodb_store: DynamoDB store for persistence

        Returns:
            An initialized SlackSummaryHandler instance
        """
        # Initialize the OpenAI handler
        await openai_handler.initialize()

        # Create and return the SlackSummaryHandler instance
        return cls(
            channel_info_ops=channel_info_ops,
            archive_ops=archive_ops,
            openai_handler=openai_handler,
            block_kit_builder=block_kit_builder,
            channel_message_ops=channel_message_ops,
            slack_posting_handler=slack_posting_handler,
            user_store=user_store,
            channel_restore_ops=channel_restore_ops,
            dynamodb_store=dynamodb_store,
        )
