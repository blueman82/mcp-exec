"""
report_command.py

This module contains the SlackReports class, which is used to process the `/ketchup report` command.
"""

from typing import Any, Dict, Optional, Tuple

import orjson

from packages.core.config.feature_flags import FeatureFlags
from packages.core.typed_di_integration import get_typed_registry
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    ChannelNameResolverProtocol,
)
from packages.core.typed_di.exceptions import MissingDependencyError
from packages.core.exceptions import MessagePreparationError
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager  # Import for secrets_manager
from packages.slack.blockkits.handlers.report import ReportMessageHandler
from packages.slack.blockkits.handlers.status import StatusMessageHandler
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_decorators import handle_archived_channel
from packages.slack.config.slack_config import SlackConfig  # Import for slack_config
from packages.slack.home.home_utils import normalize_user_preferences  # Added import
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class SlackReports(BaseCommandHandler):
    """
    This class is responsible for processing the `/ketchup report` command, which
    generates a detailed incident report based on the Slack channel content.
    """

    def __init__(
        self,
        channel_info_ops: ChannelInfoOps,
        archive_ops,
        openai_handler,
        block_kit_builder,
        secrets_manager: SecretsManager,
        slack_config: SlackConfig,
        slack_posting_handler: SlackPostingHandler,
        user_store,  # Add user_store as a dependency
        dynamodb_store=None,
        channel_restore_ops=None,
        feedback_reactions_handler=None,
    ):
        """
        Initialize the SlackReports class with required dependencies.

        Args:
            channel_info_ops: Service for channel info lookups.
            archive_ops: Service for archiving/unarchiving channels
            openai_handler: Service for interacting with OpenAI
            block_kit_builder: Builder for Block Kit UI elements
            secrets_manager: Pre-initialized SecretsManager instance (required)
            slack_config: Pre-initialized SlackConfig instance (required)
            slack_posting_handler: Handler for posting messages to Slack
            user_store: UserStore instance for user preferences
            dynamodb_store: DynamoDB store for channel data
            channel_restore_ops: Handler for restoring archived channels
        """
        if slack_posting_handler is None:
            raise ValueError(
                "slack_posting_handler must be provided via dependency injection"
            )
        super().__init__()
        self.channel_info_ops = channel_info_ops
        self.archive_ops = archive_ops
        self.openai_handler = openai_handler
        self.block_kit_builder = block_kit_builder
        self.dynamodb_store = dynamodb_store
        self.channel_restore_ops = channel_restore_ops
        self.user_store = user_store  # Assign user_store
        self.secrets_manager = secrets_manager
        self.slack_config = slack_config

        self.posting_handler = slack_posting_handler
        self.slack_posting_handler = (
            self.posting_handler
        )  # Keep for backward compatibility

        # Extract build_feedback_blocks if available
        feedback_builder_func = None
        if (
            feedback_reactions_handler
            and hasattr(feedback_reactions_handler, "build_feedback_blocks")
            and callable(feedback_reactions_handler.build_feedback_blocks)
        ):
            feedback_builder_func = feedback_reactions_handler.build_feedback_blocks

        self.status_message_handler = StatusMessageHandler()
        self.status_message_handler.configure(
            posting_handler=slack_posting_handler,
            channel_details_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            fallback_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            build_feedback_blocks=feedback_builder_func,
            block_kit_builder=block_kit_builder,
        )
        self.report_message_handler = ReportMessageHandler()
        self.report_message_handler.configure(
            posting_handler=slack_posting_handler,
            channel_details_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            fallback_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            build_feedback_blocks=feedback_builder_func,
            block_kit_builder=block_kit_builder,
        )

        logger.info("SlackReports initialized.")

    @classmethod
    async def create(
        cls,
        channel_info_ops: ChannelInfoOps,
        archive_ops,
        openai_handler,
        block_kit_builder,
        secrets_manager: SecretsManager,
        slack_config: SlackConfig,
        slack_posting_handler=None,
        user_store=None,
        dynamodb_store=None,
        channel_restore_ops=None,
    ):
        """
        Create an instance of SlackReports with initialized dependencies.

        This factory method ensures that all dependencies are properly initialized
        before the SlackReports instance is created.

        Args:
            channel_info_ops: Service for channel info lookups
            archive_ops: Service for archiving/unarchiving channels
            openai_handler: Service for interacting with OpenAI
            block_kit_builder: Builder for Block Kit UI elements
            secrets_manager: Pre-initialized SecretsManager instance (required)
            slack_config: Pre-initialized SlackConfig instance (required)
            slack_posting_handler: Handler for posting messages to Slack (optional)
            user_store: UserStore instance for user preferences
            dynamodb_store: DynamoDB store for channel data
            channel_restore_ops: Handler for restoring archived channels (optional)

        Returns:
            An initialized SlackReports instance
        """
        # Initialize the OpenAI handler
        await openai_handler.initialize()

        # Create and return the SlackReports instance
        return cls(
            channel_info_ops=channel_info_ops,
            archive_ops=archive_ops,
            openai_handler=openai_handler,
            block_kit_builder=block_kit_builder,
            secrets_manager=secrets_manager,
            slack_config=slack_config,
            slack_posting_handler=slack_posting_handler,
            user_store=user_store,
            dynamodb_store=dynamodb_store,
            channel_restore_ops=channel_restore_ops,
        )

    # --- Private Helper Methods ---

    async def _resolve_channel_parameter(self, channel_param: str) -> Optional[str]:
        """Resolve channel parameter to actual channel ID."""
        try:
            # Attempt to resolve using TypedDI registry
            channel_name_resolver = None
            try:
                registry = get_typed_registry()
                channel_name_resolver = await registry.aget(ChannelNameResolverProtocol)
            except (RuntimeError, MissingDependencyError):
                # Service not available - proceed with fallback
                pass

            if not channel_name_resolver:
                logger.warning(
                    "ChannelNameResolver not available, using fallback parsing"
                )
                # Fallback: try to extract channel ID from Slack mention format
                from packages.core.constants import SLACK_CHANNEL_MENTION_REGEX
                mention_match = SLACK_CHANNEL_MENTION_REGEX.match(channel_param)
                if mention_match:
                    channel_id = mention_match.group(1)
                    logger.info(
                        "Extracted channel ID '%s' from mention format '%s'",
                        channel_id,
                        channel_param,
                    )
                    return channel_id
                # If not a mention format, return as-is (might be already a valid ID)
                return channel_param

            resolved_id, format_type = (
                await channel_name_resolver.resolve_channel_parameter(channel_param)
            )
            if resolved_id:
                logger.info(
                    "Resolved channel parameter '%s' to ID '%s' (type: %s)",
                    channel_param,
                    resolved_id,
                    format_type,
                )
                return resolved_id
            else:
                logger.error("Failed to resolve channel parameter: %s", format_type)
                return None
        except Exception as e:
            logger.error(
                "Error resolving channel parameter '%s': %s", channel_param, str(e)
            )
            return channel_param  # Return as-is on error

    def _parse_and_validate_initial_input(
        self,
        text: str,
        user_id: Optional[str],
        incoming_channel: str,
        dm_channel_id: Optional[str],
        response_url: Optional[str],
        channel_id: Optional[str],
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Parses and validates the initial command input arguments."""
        if not channel_id:
            parts = text.split()
            channel_id = parts[1] if len(parts) > 1 else None

        # If no channel specified and not in a DM, default to current channel
        if not channel_id and incoming_channel and not incoming_channel.startswith("D"):
            channel_id = incoming_channel
            logger.info(
                "No channel specified, defaulting to current channel: %s", channel_id
            )

        # Use incoming_channel as fallback for dm_channel_id
        if not dm_channel_id:
            dm_channel_id = incoming_channel

        # Check essential parameters - response_url is optional if dm_channel_id is provided
        if not all([channel_id, user_id, dm_channel_id]):
            logger.error(
                "Missing essential input parameters: channel_id=%s, user_id=%s, dm_channel_id=%s, response_url=%s",
                channel_id,
                user_id,
                dm_channel_id,
                response_url,
            )
            # Early exit or raise exception might be better, but mirroring original flow
            # In a real scenario, we'd likely post an error message here if possible
            return None, None, None, None

        return channel_id, user_id, dm_channel_id, response_url

    async def _post_initial_ack(
        self,
        user_id: str,
        dm_channel_id: Optional[str],
        message: str,
        response_url: Optional[str],
    ) -> None:
        """Posts the initial acknowledgement message to the user."""
        # Ensure dm_channel_id and response_url are provided for posting
        if not dm_channel_id and not response_url:
            logger.error(
                "Cannot post initial ack: missing dm_channel_id and response_url."
            )
            return
        await self.slack_posting_handler.post_message(
            user_id=user_id,
            channel_id=dm_channel_id,  # post_message handles None channel_id if response_url exists
            message=message,
            response_url=response_url,
        )

    async def _get_and_validate_channel_info(
        self,
        user_id: str,
        channel_id: str,
        dm_channel_id: Optional[str],
        response_url: Optional[str],
    ) -> Tuple[Optional[str], bool]:
        """Gets channel info from Slack API, validates, and checks membership."""
        # Ensure dm_channel_id and response_url are provided for channel_details call
        if not dm_channel_id and not response_url:
            logger.error(
                "Cannot get channel details: missing dm_channel_id and response_url."
            )
            return None, False
        channel_info = await self.channel_info_ops.get_channel_details(
            user_id=user_id,
            channel_id=channel_id,
            dm_channel_id=dm_channel_id,
            response_url=response_url,
        )

        if channel_info is None:
            logger.error(
                "Could not get channel details for %s from Slack API", channel_id
            )
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message=f"Missing or invalid channel ID. Channel IDs start with C or G followed by 8-11 characters. Please verify the channel ID: `{channel_id}` and try again. Format: `/ketchup status|report #channel-id`",
                response_url=response_url,
            )
            return None, False  # Indicate failure

        channel_name, is_member, _, _ = channel_info

        if not is_member:
            logger.info("Bot is not a member of channel %s", channel_id)
            # Error message already posted by get_channel_details
            return None, False  # Indicate failure

        return channel_name, True  # Indicate success

    async def _call_openai_and_extract(
        self,
        command_verified: str,
        user_id: str,
        dm_channel_id: Optional[str],
        passed_channel_id: str,
        channel_name: str,
        response_url: Optional[str],
        query_text: Optional[str] = None,
        normalized_prefs_for_ai: Optional[Dict[str, Any]] = None,
        user_name: Optional[str] = None,
    ) -> Optional[str]:
        """Calls the OpenAI endpoint and extracts the response content."""
        # Ensure incoming_channel (dm_channel_id) is not None before passing
        if dm_channel_id is None:
            logger.error("Cannot call OpenAI endpoint: dm_channel_id is None.")
            return None

        # For status and report commands, use the standard OpenAI handler with built-in JIRA enrichment
        try:
            response_data = await self.openai_handler.call_openai_endpoint(
                combined_command=command_verified,
                user_id=user_id,
                incoming_channel=dm_channel_id,
                passed_channel_id=passed_channel_id,
                channel_name=channel_name,
                query_text=query_text,
                normalized_prefs_for_ai=normalized_prefs_for_ai,
            )
        except MessagePreparationError as e:
            logger.error(
                "Message preparation failed for channel %s: %s", passed_channel_id, e
            )
            # This error is already handled at the channel validation level,
            # so we should return None to indicate failure without additional user messaging
            return None

        if (
            not response_data
            or "choices" not in response_data
            or not response_data["choices"]
        ):
            logger.error("Failed to get response from OpenAI for query: %s", query_text)
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=dm_channel_id,
                message="Failed to get response from AI.",
                response_url=response_url,
            )
            return None

        raw_content = response_data["choices"][0]["message"]["content"]

        if FeatureFlags.is_structured_json_output_enabled():
            try:
                # Parse JSON response
                data = orjson.loads(raw_content)
                # Extract the response_text field
                extracted_text = data.get("response_text", raw_content)
                logger.info("Extracted text from JSON response (%d chars)", len(extracted_text))
                return extracted_text
            except orjson.JSONDecodeError as e:
                logger.error("Failed to parse JSON response, falling back to raw content: %s", e)
                return raw_content  # Fallback to raw if JSON invalid
        else:
            # Prose mode - return as-is
            return raw_content

    async def _apply_corrections_to_response(
        self,
        models_response: str,
        channel_id: str,
        channel_name_from_slack: str,
        command_type: str,  # 'status' or 'report' for logging clarity
    ) -> str:
        """Applies corrections for Customer Name and JIRA Ticket placeholders."""
        if not self.dynamodb_store:
            logger.warning(
                "DynamoDB store not configured, skipping AI response correction for %s.",
                command_type,
            )
            return models_response

        logger.info(
            "Checking AI %s response for missing Customer/JIRA info against DB/Slack.",
            command_type,
        )

        # Correct Customer Name
        placeholder_customer = "Customer Name: NOT YET AVAILABLE"
        if (
            placeholder_customer in models_response
            and channel_name_from_slack
            and channel_name_from_slack not in ["unknown", "NOT YET AVAILABLE"]
        ):
            models_response = models_response.replace(
                placeholder_customer, f"Customer Name: {channel_name_from_slack}"
            )
            logger.info(
                "Corrected Customer Name in AI %s response using Slack data.",
                command_type,
            )

        # Correct JIRA Ticket
        placeholder_jira_variations = [
            "• **Support Ticket:** NOT YET AVAILABLE",
            "Support Ticket: NOT YET AVAILABLE",
        ]
        needs_jira_check = any(
            p in models_response for p in placeholder_jira_variations
        )
        if needs_jira_check:
            try:
                full_channel_details_dict = (
                    await self.dynamodb_store.get_channel_details(channel_id)
                )
                if full_channel_details_dict:
                    jira_ticket_from_db = full_channel_details_dict.get("jira_ticket")
                    if (
                        jira_ticket_from_db
                        and jira_ticket_from_db != "NOT YET AVAILABLE"
                    ):
                        for placeholder in placeholder_jira_variations:
                            if placeholder in models_response:
                                # Make JIRA ticket clickable with full URL
                                clickable_ticket = f"<https://jira.corp.adobe.com/browse/{jira_ticket_from_db}|{jira_ticket_from_db}>"
                                models_response = models_response.replace(
                                    placeholder,
                                    (
                                        f"• **Support Ticket:** {clickable_ticket}"
                                        if "• **" in placeholder
                                        else f"Support Ticket: {clickable_ticket}"
                                    ),
                                )
                                logger.info(
                                    "Corrected JIRA Ticket in AI %s response using DB data with clickable link.",
                                    command_type,
                                )
                                break  # Correction applied for the first match found
                else:
                    logger.warning(
                        "Could not fetch full channel details from DB for %s during JIRA correction for %s.",
                        channel_id,
                        command_type,
                    )
            except Exception as db_error:
                logger.error(
                    "Error fetching full details from DB for JIRA correction in %s: %s",
                    command_type,
                    db_error,
                )

        return models_response

    # --- End Private Helper Methods ---

    @handle_archived_channel
    async def process_status_request(
        self,
        command_verified: str,
        text: str,
        user_id: str,
        incoming_channel: str,
        dm_channel_id: Optional[str] = None,
        response_url: Optional[str] = None,
        channel_id: Optional[str] = None,  # Target channel_id
        user_name: Optional[str] = None,  # Add user_name parameter
    ) -> Optional[Dict[str, Any]]:
        """Process the 'status' command using helper methods."""
        logger.info("Starting process_status_request function.")

        target_channel_id_opt, user_id_opt, dm_channel_id_opt, response_url_opt = (
            self._parse_and_validate_initial_input(
                text, user_id, incoming_channel, dm_channel_id, response_url, channel_id
            )
        )

        # Resolve channel parameter if needed
        if target_channel_id_opt:
            resolved_channel_id = await self._resolve_channel_parameter(
                target_channel_id_opt
            )
            if resolved_channel_id:
                target_channel_id_opt = resolved_channel_id
            else:
                logger.error(
                    "Failed to resolve channel parameter: %s", target_channel_id_opt
                )
                return self.create_validation_error_response(
                    "Could not resolve the specified channel. Please check the channel name or ID and try again."
                )

        # Ensure required parameters are not None after validation
        if not target_channel_id_opt or not user_id_opt or not dm_channel_id_opt:
            logger.error("Validation failed, required parameters are None.")
            return self.create_validation_error_response(
                "Invalid initial input parameters or validation failed."
            )
        target_channel_id: str = target_channel_id_opt
        # Rename variables to avoid redefinition
        validated_user_id: str = user_id_opt
        validated_dm_channel_id: str = dm_channel_id_opt
        validated_response_url: str = response_url_opt or ""

        ack_message = "Generating status update... :clipboard:"
        command_type_log = "status"

        logger.info(
            "Processing %s command with channel_id: %s",
            command_type_log,
            target_channel_id,
        )

        # 1. Post Acknowledgement
        await self._post_initial_ack(
            validated_user_id,
            validated_dm_channel_id,
            ack_message,
            validated_response_url,
        )

        # 2. Validate Channel and Membership
        channel_name_from_slack_opt, is_valid_channel = (
            await self._get_and_validate_channel_info(
                validated_user_id,
                target_channel_id,
                validated_dm_channel_id,
                validated_response_url,
            )
        )
        if not is_valid_channel:
            return self.create_error_response(
                "Channel validation failed or bot not member."
            )
        if channel_name_from_slack_opt is None:
            logger.error(
                "Could not retrieve channel name for valid channel %s",
                target_channel_id,
            )
            await self.slack_posting_handler.post_message(
                user_id=validated_user_id,  # Use validated var
                channel_id=validated_dm_channel_id,  # Use validated var
                message="Error: Could not retrieve channel details.",
                response_url=validated_response_url,  # Use validated var
            )
            return self.create_error_response(
                "Internal error retrieving channel details."
            )
        channel_name_from_slack: str = channel_name_from_slack_opt

        # 3. Fetch user preferences and build adaptive prompt
        user_data = await self.user_store.get_user(validated_user_id)
        # Define default raw preferences
        default_raw_prefs = {
            "product_focus": ["all_products"],
            "detail_level": "balanced",
            "time_window": "past_24_hours",
        }
        raw_preferences = (
            user_data.get("preferences", default_raw_prefs)
            if user_data
            else default_raw_prefs
        )
        normalized_prefs_for_ai = normalize_user_preferences(raw_preferences)
        logger.info(
            "Status command: user_id=%s, raw_prefs=%s, normalized_prefs_for_ai=%s",
            validated_user_id,
            raw_preferences,
            normalized_prefs_for_ai,
        )
        # 4. Call OpenAI with adaptive prompt
        models_response = await self._call_openai_and_extract(
            command_verified=command_verified,
            user_id=validated_user_id,  # Use validated var
            dm_channel_id=validated_dm_channel_id,  # Use validated var
            passed_channel_id=target_channel_id,
            channel_name=channel_name_from_slack,
            response_url=validated_response_url,
            normalized_prefs_for_ai=normalized_prefs_for_ai,
            user_name=user_name,  # Pass user_name
        )
        if models_response is None:
            # Error logged in helper, maybe post error to user?
            await self.slack_posting_handler.post_message(
                user_id=validated_user_id,  # Use validated var
                channel_id=validated_dm_channel_id,  # Use validated var
                message="Failed to get response from AI.",
                response_url=validated_response_url,  # Use validated var
            )
            return self.create_error_response("Failed to get response from AI.")

        # 5. Apply Corrections
        corrected_response = await self._apply_corrections_to_response(
            models_response=models_response,
            channel_id=target_channel_id,
            channel_name_from_slack=channel_name_from_slack,
            command_type=command_type_log,
        )

        # 6. Send Final Response
        # Use DM channel if no response_url is available (e.g., app mentions)
        effective_response_target = (
            validated_response_url
            if validated_response_url
            else validated_dm_channel_id
        )

        # Use block_kit_builder if available (it has feedback blocks configured)
        if self.block_kit_builder:
            await self.block_kit_builder.send_ketchup_status_block_kit(
                combined_command=command_verified,
                response_url=effective_response_target,
                response_text=corrected_response,
                query=None,  # No query for status command
                target_channel=target_channel_id,
                execution_channel=validated_dm_channel_id,
            )
        else:
            # Fallback to status_message_handler (without feedback blocks)
            await self.status_message_handler.send_message(
                combined_command=command_verified,
                response_url=effective_response_target,
                response_text=corrected_response,
                target_channel=target_channel_id,
                execution_channel=validated_dm_channel_id,
            )
        logger.info("Successfully processed %s command.", command_type_log)
        return self.create_success_response("Status update generated successfully")

    @handle_archived_channel
    async def process_report_request(
        self,
        command_verified: str,
        text: str,
        user_id: str,
        incoming_channel: str,
        dm_channel_id: Optional[str] = None,
        response_url: Optional[str] = None,
        channel_id: Optional[str] = None,  # Target channel_id
        user_name: Optional[str] = None,  # Add user_name parameter
    ) -> Optional[Dict[str, Any]]:
        """Process the 'report' command using helper methods."""
        logger.info("Starting process_report_request function.")

        target_channel_id_opt, user_id_opt, dm_channel_id_opt, response_url_opt = (
            self._parse_and_validate_initial_input(
                text, user_id, incoming_channel, dm_channel_id, response_url, channel_id
            )
        )

        # Resolve channel parameter if needed
        if target_channel_id_opt:
            resolved_channel_id = await self._resolve_channel_parameter(
                target_channel_id_opt
            )
            if resolved_channel_id:
                target_channel_id_opt = resolved_channel_id
            else:
                logger.error(
                    "Failed to resolve channel parameter: %s", target_channel_id_opt
                )
                return self.create_validation_error_response(
                    "Could not resolve the specified channel. Please check the channel name or ID and try again."
                )

        # Ensure required parameters are not None after validation
        if not target_channel_id_opt or not user_id_opt or not dm_channel_id_opt:
            logger.error("Validation failed, required parameters are None.")
            return self.create_validation_error_response(
                "Invalid initial input parameters or validation failed."
            )
        target_channel_id: str = target_channel_id_opt
        # Rename variables to avoid redefinition
        validated_user_id: str = user_id_opt
        validated_dm_channel_id: str = dm_channel_id_opt
        validated_response_url: str = response_url_opt or ""

        report_query = "generate comprehensive incident report"
        ack_message = "Generating detailed incident report... :memo:"
        command_type_log = "report"

        logger.info(
            "Processing %s command with channel_id: %s",
            command_type_log,
            target_channel_id,
        )

        # 1. Post Acknowledgement
        await self._post_initial_ack(
            validated_user_id,
            validated_dm_channel_id,
            ack_message,
            validated_response_url,
        )

        # 2. Validate Channel and Membership
        channel_name_from_slack_opt, is_valid_channel = (
            await self._get_and_validate_channel_info(
                validated_user_id,
                target_channel_id,
                validated_dm_channel_id,
                validated_response_url,
            )
        )
        if not is_valid_channel:
            return self.create_error_response(
                "Channel validation failed or bot not member."
            )
        if channel_name_from_slack_opt is None:
            logger.error(
                f"Could not retrieve channel name for valid channel {target_channel_id}"
            )
            # Post error message to user
            await self.slack_posting_handler.post_message(
                user_id=validated_user_id,  # Use validated var
                channel_id=validated_dm_channel_id,  # Use validated var
                message="Error: Could not retrieve channel details.",
                response_url=validated_response_url,  # Use validated var
            )
            return self.create_error_response(
                "Internal error retrieving channel details."
            )
        channel_name_from_slack: str = channel_name_from_slack_opt

        # 3. Fetch user preferences and build adaptive prompt
        user_data = await self.user_store.get_user(validated_user_id)
        # Define default raw preferences
        default_raw_prefs = {
            "product_focus": ["all_products"],
            "detail_level": "balanced",
            "time_window": "past_24_hours",
        }
        raw_preferences = (
            user_data.get("preferences", default_raw_prefs)
            if user_data
            else default_raw_prefs
        )
        normalized_prefs_for_ai = normalize_user_preferences(raw_preferences)
        logger.info(
            "Report command: user_id=%s, raw_prefs=%s, normalized_prefs_for_ai=%s",
            validated_user_id,
            raw_preferences,
            normalized_prefs_for_ai,
        )
        # 4. Call OpenAI with adaptive prompt
        models_response = await self._call_openai_and_extract(
            command_verified=command_verified,
            user_id=validated_user_id,  # Use validated var
            dm_channel_id=validated_dm_channel_id,  # Use validated var
            passed_channel_id=target_channel_id,
            channel_name=channel_name_from_slack,
            query_text=report_query,
            response_url=validated_response_url,
            normalized_prefs_for_ai=normalized_prefs_for_ai,
            user_name=user_name,  # Pass user_name
        )
        if models_response is None:
            # Error logged in helper, maybe post error to user?
            await self.slack_posting_handler.post_message(
                user_id=validated_user_id,  # Use validated var
                channel_id=validated_dm_channel_id,  # Use validated var
                message="Failed to get response from AI.",
                response_url=validated_response_url,  # Use validated var
            )
            return self.create_error_response("Failed to get response from AI.")

        # 5. Apply Corrections
        corrected_response = await self._apply_corrections_to_response(
            models_response=models_response,
            channel_id=target_channel_id,
            channel_name_from_slack=channel_name_from_slack,
            command_type=command_type_log,
        )

        # 6. Send Final Response
        # Use DM channel if no response_url is available (e.g., app mentions)
        effective_response_target = (
            validated_response_url
            if validated_response_url
            else validated_dm_channel_id
        )

        # Use block_kit_builder if available (it has feedback blocks configured)
        if self.block_kit_builder:
            await self.block_kit_builder.send_ketchup_report_block_kit(
                combined_command=command_verified,
                response_url=effective_response_target,
                response_text=corrected_response,
                query=report_query,
                target_channel=target_channel_id,
                execution_channel=validated_dm_channel_id,
            )
        else:
            # Fallback to report_message_handler (without feedback blocks)
            await self.report_message_handler.send_message(
                combined_command=command_verified,
                response_url=effective_response_target,
                response_text=corrected_response,
                query=report_query,
                target_channel=target_channel_id,
                execution_channel=validated_dm_channel_id,
            )
        logger.info("Successfully processed %s command.", command_type_log)
        return self.create_success_response("Incident report generated successfully")
