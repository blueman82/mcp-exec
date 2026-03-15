"""
access_command.py

This module contains the AccessCommand class for handling access requests.
"""

from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.slack.authorisation.user_verification import UserVerifier
from packages.slack.blockkits.handlers.access_request_blocks import AccessRequestBlocks
from packages.slack.channel_events.models import ProcessingResult
from packages.slack.command_processing.base_command_handler import BaseCommandHandler
from packages.slack.command_processing.command_parameters.models import (
    AccessCommandParams,
    CommandParams,
)
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class AccessCommand(BaseCommandHandler):
    """
    Handler for the /ketchup access command.

    This command allows users to check their access status and request access
    if they don't have it.
    """

    def __init__(
        self,
        slack_posting_handler: SlackPostingHandler,
        user_verifier: UserVerifier,
    ):
        """
        Initialize the AccessCommand with dependencies.

        Args:
            slack_posting_handler: Handler for posting Slack messages
            user_verifier: Service for verifying user authorization
        """
        super().__init__()
        self.slack_posting_handler = slack_posting_handler
        self.user_verifier = user_verifier
        logger.info("AccessCommand initialized")

    async def process_access_params(
        self,
        params: CommandParams,
        user_id: str,
        incoming_channel: str,
        response_url: str,
    ) -> ProcessingResult:
        """
        Process the access command.

        Args:
            params: The command parameters
            user_id: ID of the user who issued the command
            incoming_channel: Channel where the command was issued
            response_url: Response URL for interactive components

        Returns:
            Dict with status code and body
        """
        # Validate params is the correct type
        if not isinstance(params, AccessCommandParams):
            logger.error("Invalid params type: %s", type(params))
            return self.create_validation_error_response("Invalid command parameters")

        try:
            logger.info(f"Processing access command for user {user_id}")

            # Check if user is already authorized
            is_authorized = await self.user_verifier.validate_user_id(user_id)

            if is_authorized:
                # User already has access
                message = "✅ You already have access to Ketchup! You can use any Ketchup command."
                await self.slack_posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=message,
                    response_url=response_url,
                )
                logger.info(f"User {user_id} checked access - already authorized")
            else:
                # Show access request UI
                blocks = AccessRequestBlocks.build_unauthorized_message(
                    user_id=user_id, show_request_button=True
                )
                await self.slack_posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    blocks=blocks,
                    message="Access Request",  # Fallback text
                    response_url=response_url,
                )
                logger.info(f"User {user_id} shown access request UI")

            return ProcessingResult(status_code=200, body="")

        except Exception as e:
            logger.error(f"Error processing access command: {e}", exc_info=True)
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message="Sorry, there was an error processing your request. Please try again later.",
                response_url=response_url,
            )
            return ProcessingResult(status_code=500, body="Error")
