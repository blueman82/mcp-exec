"""
query_command.py

This module contains the SlackQueryHandler class,
which is used to process the `/ketchup query` command.
"""

import re
from typing import Any, Dict, Optional

import orjson

from packages.ai.core.openai_handler import OpenAIHandler
from packages.core.config.feature_flags import FeatureFlags
from packages.core.exceptions import MessagePreparationError
from packages.core.logging import setup_logger
from packages.core.utils import normalize_prompt_for_agent
from packages.db.user_store import UserStore
from packages.secrets.manager import SecretsManager
from packages.slack.blockkits.base import BlockKitBuilder
from packages.slack.blockkits.handlers.query import QueryMessageHandler
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps
from packages.slack.channel_operations.channel_restore_ops import SlackChannelRestoreOps
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_decorators import handle_archived_channel
from packages.slack.command_processing.command_parameters.models import (
    CommandParams,
    QueryCommandParams,
)
from packages.slack.config.slack_config import SlackConfig
from packages.slack.home.home_utils import normalize_user_preferences
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


class SlackQueryHandler(BaseCommandHandler):
    """
    This class is responsible for processing the `/ketchup query` command, which
    answers specific questions about Slack channel content using AI.

    NOTE: All dependencies are assigned explicitly in __init__, consistent with the rest of the codebase.
    """

    def __init__(
        self: "SlackQueryHandler",
        channel_info_ops: ChannelInfoOps,
        archive_ops: SlackChannelArchiveOps,
        openai_handler: OpenAIHandler,
        block_kit_builder: BlockKitBuilder,
        channel_message_ops: SlackChannelMessageOps,
        slack_posting_handler: SlackPostingHandler,
        user_store: UserStore,
        slack_config: SlackConfig,
        secrets_manager: SecretsManager,
        user_ops: Optional[SlackUserOps] = None,
        channel_restore_ops: Optional[SlackChannelRestoreOps] = None,
        dynamodb_store=None,
        feedback_reactions_handler=None,
    ) -> None:
        """
        Initialize the SlackQueryHandler class.

        Args:
            channel_info_ops: Service for channel info lookups.
            archive_ops: Service for archiving/unarchiving channels
            openai_handler: Service for interacting with OpenAI
            block_kit_builder: Service for creating Slack block kit messages
            channel_message_ops: Service for fetching channel messages
            slack_posting_handler: Handler for posting messages to Slack (must be DI, no fallback)
            user_store: UserStore instance for database operations.
            slack_config: Pre-initialized SlackConfig instance (required).
            secrets_manager: Pre-initialized SecretsManager instance (required).
            user_ops: Optional handler for user operations (for testing/DI)
            channel_restore_ops: Handler for restoring archived channels
        """
        super().__init__()
        self.channel_info_ops = channel_info_ops
        self.archive_ops = archive_ops
        self.openai_handler = openai_handler
        self.block_kit_builder = block_kit_builder
        self.channel_message_ops = channel_message_ops
        self.slack_posting_handler = slack_posting_handler
        self.user_store = user_store
        self.slack_config = slack_config
        self.secrets_manager = secrets_manager
        self.user_ops = user_ops
        self.channel_restore_ops = channel_restore_ops
        self.dynamodb_store = dynamodb_store
        if slack_posting_handler is None:
            raise ValueError(
                "slack_posting_handler must be provided via DI (with slack_config, secrets_manager)"
            )
        if user_ops is None:
            raise ValueError(
                "user_ops must be provided via dependency injection (with slack_config)"
            )

        # Extract build_feedback_blocks if available
        feedback_builder_func = None
        if (
            feedback_reactions_handler
            and hasattr(feedback_reactions_handler, "build_feedback_blocks")
            and callable(feedback_reactions_handler.build_feedback_blocks)
        ):
            feedback_builder_func = feedback_reactions_handler.build_feedback_blocks

        self.query_message_handler = QueryMessageHandler()
        self.query_message_handler.configure(
            posting_handler=slack_posting_handler,
            channel_details_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            fallback_getter=dynamodb_store.get_channel_details if dynamodb_store else None,
            build_feedback_blocks=feedback_builder_func,
            block_kit_builder=block_kit_builder,
        )
        logger.info("SlackQueryHandler initialized.")

    @classmethod
    async def create(
        cls: type["SlackQueryHandler"],
        channel_info_ops: Any,
        archive_ops: Any,
        openai_handler: Any,
        block_kit_builder: Any,
        channel_message_ops: Any,
        slack_posting_handler: Any,
        user_store: Any,
        slack_config: Any,
        secrets_manager: Any,
        user_ops: Any,
        channel_restore_ops: Optional[Any] = None,
    ) -> "SlackQueryHandler":
        """
        Create an instance of SlackQueryHandler with initialized dependencies.

        This factory method ensures that all dependencies are properly initialized
        before the SlackQueryHandler instance is created.

        Args:
            channel_info_ops: Service for channel info lookups.
            archive_ops: Service for archiving/unarchiving channels
            openai_handler: Service for interacting with OpenAI
            block_kit_builder: Service for creating Slack block kit messages
            channel_message_ops: Service for fetching channel messages
            slack_posting_handler: Handler for posting messages to Slack
            user_store: UserStore instance for database operations.
            slack_config: Pre-initialized SlackConfig instance (required).
            secrets_manager: Pre-initialized SecretsManager instance (required).
            user_ops: Handler for user operations (required)
            channel_restore_ops: Handler for restoring archived channels

        Returns:
            An initialized SlackQueryHandler instance
        """
        await openai_handler.initialize()
        return cls(
            channel_info_ops=channel_info_ops,
            archive_ops=archive_ops,
            openai_handler=openai_handler,
            block_kit_builder=block_kit_builder,
            channel_message_ops=channel_message_ops,
            slack_posting_handler=slack_posting_handler,
            user_store=user_store,
            slack_config=slack_config,
            secrets_manager=secrets_manager,
            user_ops=user_ops,
            channel_restore_ops=channel_restore_ops,
        )

    async def _resolve_channel_parameter(self, channel_param: str) -> Optional[str]:
        """Resolve channel parameter to actual channel ID."""
        from packages.slack.command_processing.channel_resolver import resolve_channel_parameter

        return await resolve_channel_parameter(channel_param)  # Return as-is on error

    @handle_archived_channel
    async def process_query_request(
        self,
        params: CommandParams,
        user_id: str,
        channel_id: Optional[str] = None,
        dm_channel_id: Optional[str] = None,
        incoming_channel: Optional[str] = None,
        response_url: Optional[str] = None,
        user_name: Optional[str] = None,  # Add user_name parameter
    ) -> Optional[Dict[str, Any]]:
        """
        Process the 'query' command.

        Args:
            params: The command parameters
            user_id: Slack user ID
            channel_id: The target channel ID where the command should be executed
            dm_channel_id: The channel ID where the command was issued (for messaging user)
            incoming_channel: The channel ID where the command was issued (for backward compatibility)
            response_url: The response URL for interactive components/slash commands

        Returns:
            The generated response or None if there was an error
        """
        start_message = "Starting process_query_request function."
        logger.info(start_message)

        if not isinstance(params, QueryCommandParams):
            logger.error("Invalid params type: %s", type(params))
            return self.create_validation_error_response("Invalid command parameters")

        target_channel_id = params.target_channel_id
        query_text = params.query_text
        _ = params.original_command

        # Resolve channel parameter if needed
        resolved_channel_id = await self._resolve_channel_parameter(target_channel_id)
        if resolved_channel_id:
            target_channel_id = resolved_channel_id
        else:
            logger.error("Failed to resolve channel parameter: %s", target_channel_id)
            return self.create_validation_error_response(
                "Could not resolve the specified channel. Please check the channel name or ID and try again."
            )

        if channel_id is None or channel_id != target_channel_id:
            logger.info("Using target_channel_id %s as channel_id", target_channel_id)
            channel_id = target_channel_id

        # Use incoming_channel as dm_channel_id if provided for backward compatibility
        messaging_channel = dm_channel_id or incoming_channel or ""
        if not messaging_channel:
            logger.error("No messaging channel provided for process_query_request.")
            return self.create_error_response("No messaging channel provided.")

        # Efficiently resolve Slack mentions only if present
        if "<@" in query_text:
            # Only resolve mentions if the text contains Slack user mentions
            query_text = await self._resolve_slack_mentions(query_text)

        try:
            # Process the query
            generated_text = await self._process_query(
                channel_id=channel_id,
                query_text=query_text,
                user_id=user_id,
                messaging_channel=messaging_channel,
                response_url=response_url,
                user_name=user_name,
            )
            # Use QueryMessageHandler to send the formatted query response
            await self.query_message_handler.send_message(
                combined_command=f"/ketchup query {channel_id} {query_text}",
                response_url=response_url or messaging_channel,
                response_text=generated_text,
                query=query_text,
                target_channel=channel_id,
            )
            return self.create_success_response({"message": "Query processed successfully."})
        except Exception as e:
            logger.error("Error processing query: %s", str(e))
            return self.create_error_response(f"Error processing query: {str(e)}")

    async def _process_query(
        self,
        channel_id: str,
        query_text: str,
        user_id: str,
        messaging_channel: str,
        response_url: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> str:
        """
        Process the query and return the generated text.
        """
        command_verified = f"/ketchup query {channel_id} {query_text}"
        logger.info(
            "Processing query command with channel_id: %s, query: %s, user_id: %s",
            channel_id,
            query_text,
            user_id,
        )
        await self.slack_posting_handler.post_message(
            user_id=user_id,
            channel_id=messaging_channel,
            message="Processing query command... :bulb:",
            response_url=response_url or messaging_channel,
        )
        channel_details = await self.channel_info_ops.get_channel_details(
            user_id=user_id,
            channel_id=channel_id,
            dm_channel_id=messaging_channel,
            response_url=response_url,
        )
        if channel_details is None:
            error_message = f"Could not get channel details for {channel_id} - channel may not exist or bot has no access"
            logger.error(error_message)
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=messaging_channel,
                message=f"Missing or invalid channel ID. Channel IDs start with C or G followed by 8-11 characters. Please verify the channel ID: `{channel_id}` and try again. Format: `/ketchup query #channel-id your question`",
                response_url=messaging_channel,
            )
            error_message = f"Bot is not a member of channel {channel_id}. Please invite the bot to the channel first."
            logger.error(error_message)
            raise Exception(error_message)
        channel_name, is_member, _, _ = channel_details
        if not is_member:
            logger.warning("Bot is not a member of %s. Query might fail.", channel_id)

        # Fetch, define default, extract, and normalize user preferences
        user_data = await self.user_store.get_user(user_id)
        default_raw_prefs = {
            "product_focus": ["all_products"],
            "detail_level": "balanced",
            "time_window": "past_24_hours",
        }
        raw_preferences = (
            user_data.get("preferences", default_raw_prefs) if user_data else default_raw_prefs
        )
        normalized_prefs_for_ai = normalize_user_preferences(raw_preferences)
        logger.info(
            "Query command: user_id=%s, raw_prefs=%s, normalized_prefs_for_ai=%s",
            user_id,
            raw_preferences,
            normalized_prefs_for_ai,
        )

        # Normalize the query to prevent multi-line interpretation issues
        normalized_query = normalize_prompt_for_agent(query_text)
        logger.info(f"Normalized query for processing: {normalized_query[:100]}...")

        try:
            response_data = await self.openai_handler.call_openai_endpoint(
                combined_command=command_verified,
                user_id=user_id,
                incoming_channel=messaging_channel,
                passed_channel_id=channel_id,
                channel_name=channel_name,
                query_text=normalized_query,  # Use normalized query
                normalized_prefs_for_ai=normalized_prefs_for_ai,
            )
        except MessagePreparationError as e:
            logger.error("Message preparation failed for channel %s: %s", channel_id, e)
            # This error is already handled at the channel validation level,
            # but we should raise a more descriptive error for the query command
            raise Exception(
                f"Unable to process query for channel {channel_id}: bot may not be a member of the channel"
            ) from e
        if not response_data or "choices" not in response_data or not response_data["choices"]:
            logger.error("Invalid or empty response from OpenAI endpoint.")
            generated_text = "Sorry, I received an invalid response from the AI. Please try again."
        else:
            raw_content = response_data["choices"][0]["message"]["content"]

            if FeatureFlags.is_structured_json_output_enabled():
                try:
                    # Parse JSON response
                    data = orjson.loads(raw_content)
                    # Extract the response_text field
                    generated_text = data.get("response_text", raw_content)
                    logger.info("Extracted text from JSON response (%d chars)", len(generated_text))
                except orjson.JSONDecodeError as e:
                    logger.error(
                        "Failed to parse JSON response, falling back to raw content: %s", e
                    )
                    generated_text = raw_content  # Fallback to raw if JSON invalid
            else:
                # Prose mode - return as-is
                generated_text = raw_content

        return generated_text

    async def _resolve_slack_mentions(self, text: str) -> str:
        """
        Replace Slack user mentions in the text with full names from the user store.

        Note:
            This function only resolves user names from the DB (via user_store). If a user is not found,
            the mention is left as <@USERID>. Elsewhere in the system (e.g., SlackUserOps), missing users
            will be fetched from Slack's API and cached in the DB for future lookups. This keeps mention
            resolution fast and side-effect free.

        Args:
            text: The input text possibly containing <@USERID> or <@USERID|username> mentions
        Returns:
            The text with mentions replaced by full names
        """
        mention_pattern = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]+)?>")
        user_ids = set(mention_pattern.findall(text))
        if not user_ids:
            return text

        user_id_to_name: dict[str, str] = {}
        for user_id in user_ids:
            try:
                user_info = await self.user_store.get_user(user_id)
                real_name = user_info.get("real_name") if user_info else None
                resolved_name = real_name or user_id
                user_id_to_name[user_id] = resolved_name
                logger.info("Resolved Slack user %s to %s", user_id, resolved_name)
            except Exception as e:
                logger.warning("Could not resolve Slack user %s: %s", user_id, e)
                user_id_to_name[user_id] = f"<@{user_id}>"

        def replace_mention(match: re.Match[str]) -> str:
            """
            Replace a Slack user mention with the user's full name.
            """
            uid = match.group(1)
            return user_id_to_name.get(uid, match.group(0))

        return mention_pattern.sub(replace_mention, text)

    def create_success_response(self, message: dict) -> dict:
        """
        Create a standardized success response.

        Args:
            message: The success message to include (now a dict)

        Returns:
            A dictionary containing the success response
        """
        response = {"status": "success"}
        if isinstance(message, dict):
            response.update(message)
        else:
            response["message"] = str(message)
        response["feedback_sent"] = True
        return response
