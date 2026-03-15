"""
incoming_events.py

This module handles incoming Slack events and commands, providing a unified interface
for processing different types of requests.
"""

import json
from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.slack.authorisation.auth import SlackAuth
from packages.slack.channel_events.events import SlackEventHandler
from packages.slack.channel_events.models import ProcessingResult, SlackRequest
from packages.slack.channel_events.request_processing.dependency_setup import (
    setup_dependencies,
)
from packages.slack.channel_events.request_processing.routing import (
    handle_events_api,
    handle_interactive_component,
    handle_slack_command,
)
from packages.slack.command_processing.command_router import CommandRouter

logger = setup_logger(__name__)


# --- Main Request Handler --- #
async def process_request(request: SlackRequest, container: TypedServiceRegistry) -> ProcessingResult:
    """
    Process a request from Slack at the module level.

    Uses the TypedServiceRegistry to manage dependencies and forwards the request
    to an EventProcessor instance created per-request.

    Args:
        request: The parsed SlackRequest.
        container: The TypedServiceRegistry instance

    Returns:
        ProcessingResult with status code and body
    """
    if not container.is_initialized():
        logger.error("process_request called with uninitialized DI container.")
        return ProcessingResult(
            status_code=500,
            body=json.dumps(
                {"error": "Internal configuration error: DI container not initialized."}
            ),
        )

    try:
        # Setup dependencies for this specific request using the container
        dependencies = await setup_dependencies(container)

        # Instantiate EventProcessor LOCALLY for this request
        logger.info("Creating EventProcessor instance for the request.")
        processor = EventProcessor(
            # Pass only the dependencies EventProcessor needs to *hold*
            # The routing functions will pull what they need from the `dependencies` dict
            clients=dependencies,  # Keep passing the full dict for now
            slack_auth=dependencies["slack_auth"],
            command_router=dependencies["command_router"],
            event_handler=dependencies["event_handler"],
        )

        # Process the request using the local processor instance
        return await processor.process_request(request)

    except ValueError as ve:  # Catch specific config errors
        logger.error("Configuration error during process_request setup: %s", ve)
        return ProcessingResult(
            status_code=500,
            body=json.dumps({"error": f"Internal configuration error: {ve}"}),
        )
    except Exception as e:
        logger.error(
            "Unhandled error during process_request setup or processing: %s",
            e,
            exc_info=True,
        )
        # Return a generic error response
        return ProcessingResult(
            status_code=500,
            body=json.dumps({"error": "An unexpected error occurred."}),
        )


# --- EventProcessor Class --- #
# This class is now much simpler, mainly holding dependencies
# and orchestrating the routing after verification.
class EventProcessor:
    """Handles processing of different Slack event types."""

    def __init__(
        self,
        clients: Dict[str, Any],  # Contains all dependencies
        slack_auth: SlackAuth,
        command_router: CommandRouter,  # Needed for routing commands
        event_handler: SlackEventHandler,  # Needed for routing events
    ):
        """
        Initialize the EventProcessor with dependencies needed for routing.

        Args:
            clients: Dictionary containing all shared dependencies for the request.
            slack_auth: Handler for Slack authentication/verification.
            command_router: Router for Slack commands.
            event_handler: Handler for specific Slack events.
        """
        # Store dependencies passed from the setup helper that are needed for routing
        self.clients = clients
        self.slack_auth = slack_auth
        self.command_router = command_router
        self.event_handler = event_handler
        # Retrieve core clients/handlers needed by routing functions
        self.slack_posting_handler = clients.get("slack_posting")
        self.feedback_reactions_handler = clients.get("feedback_reactions_handler")
        self.shortcut_handler = clients.get("shortcut_handler")
        # Retrieve feedback_report_handler again
        self.feedback_report_handler = clients.get("feedback_report_handler")
        self.channel_metadata_edit_handler = clients.get("channel_metadata_edit_handler")
        # Get HomeTabHandler for app_home_opened events
        self.home_tab_handler = clients.get("home_tab_handler")
        # Get TrustEndorsementHandler for trust button interactions
        self.trust_endorsement_handler = clients.get("trust_endorsement_handler")
        # Get AccessRequestHandler for access request automation
        self.access_request_handler = clients.get("access_request_handler")
        # Get FlagReviewHandler for flag button interactions
        self.flag_review_handler = clients.get("flag_review_handler")
        # Get CSOPMHandler for CSOPM interactive button actions
        self.csopm_handler = clients.get("csopm_handler")

    async def process_request(self, request: SlackRequest) -> ProcessingResult:
        """
        Process an incoming Slack request.

        Args:
            request: The parsed SlackRequest.

        Returns:
            ProcessingResult with status code and body.
        """
        logger.info("Processing incoming request within EventProcessor")

        # Check for retry attempts (headers already lowercase)
        retry_num = request.headers.get("x-slack-retry-num")
        if retry_num:
            logger.warning("Slack retry attempt number %s detected. Ignoring.", retry_num)
            return ProcessingResult(status_code=200, body="Retry ignored")

        # Use pre-parsed body data directly
        parsed_body_dict = request.parsed_body
        parsed_body_multivalue = request.parsed_body_multivalue

        # --- Determine Request Type and Delegate --- #
        if "command" in parsed_body_multivalue:
            return await handle_slack_command(
                parsed_body_multivalue=parsed_body_multivalue,
                command_router=self.command_router,
            )

        elif "payload" in parsed_body_multivalue:
            if self.slack_posting_handler is None:
                msg = "Slack posting handler is None"
                logger.error(msg)
                raise RuntimeError(msg)
            if self.feedback_reactions_handler is None:
                msg = "Feedback reactions handler is None"
                logger.error(msg)
                raise RuntimeError(msg)
            if self.shortcut_handler is None:
                msg = "Shortcut handler is None"
                logger.error(msg)
                raise RuntimeError(msg)
            if self.feedback_report_handler is None:
                msg = "Feedback report handler is None"
                logger.error(msg)
                raise RuntimeError(msg)
            if self.trust_endorsement_handler is None:
                msg = "Trust endorsement handler is None"
                logger.error(msg)
                raise RuntimeError(msg)
            if self.flag_review_handler is None:
                msg = "Flag review handler is None"
                logger.error(msg)
                raise RuntimeError(msg)
            return await handle_interactive_component(
                parsed_body_multivalue=parsed_body_multivalue,
                posting_handler=self.slack_posting_handler,
                feedback_handler=self.feedback_reactions_handler,
                shortcut_handler=self.shortcut_handler,
                feedback_report_handler=self.feedback_report_handler,
                channel_metadata_edit_handler=self.channel_metadata_edit_handler,
                home_tab_handler=self.home_tab_handler,
                trust_endorsement_handler=self.trust_endorsement_handler,
                access_request_handler=self.access_request_handler,
                flag_review_handler=self.flag_review_handler,
                csopm_handler=self.csopm_handler,
            )

        elif "event" in parsed_body_dict or "event" in parsed_body_multivalue:
            return await handle_events_api(
                parsed_body_multivalue=parsed_body_multivalue,
                parsed_body_dict=parsed_body_dict,
                event_handler=self.event_handler,
                home_tab_handler=self.home_tab_handler,
            )

        else:
            logger.warning("Unknown request type received")
            logger.info("Unknown request body dict: %s", parsed_body_dict)
            logger.info("Unknown request body multivalue: %s", parsed_body_multivalue)
            return ProcessingResult(status_code=400, body="Unknown request type")
