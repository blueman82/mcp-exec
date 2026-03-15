"""
routing.py

Handles routing of verified and parsed Slack requests to the appropriate handlers.
"""

import json
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.slack.channel_events.events import SlackEventHandler
from packages.slack.channel_events.models import ProcessingResult
from packages.slack.command_processing.command_router import CommandRouter
from packages.slack.home.home import HomeTabHandler
from packages.slack.interactive_elements.channel_metadata_edit import (
    ChannelMetadataEditHandler,
)
from packages.slack.interactive_elements.feedback_reactions import (
    FeedbackReactionsHandler,
)
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler
from packages.slack.interactive_elements.payload_processor import (
    process_interactive_payload,
)
from packages.slack.interactive_elements.shortcuts import ShortcutHandler
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


async def handle_slack_command(
    parsed_body_multivalue: Dict[str, List[str]], command_router: CommandRouter
) -> ProcessingResult:
    """
    Handles incoming slash commands by routing them.

    Args:
        parsed_body_multivalue: The multi-value parsed request body.
        command_router: The CommandRouter instance.

    Returns:
        ProcessingResult with status code and response body.
    """
    logger.info("Request identified as a Slash Command, routing...")
    response_url = parsed_body_multivalue.get("response_url", [None])[0]
    if not response_url:
        logger.error("No response_url found in command payload for routing")
        # Cannot acknowledge without response_url, return error
        return ProcessingResult(
            status_code=400,
            body=json.dumps({"error": "Missing response_url for command"}),
        )

    try:
        # Route the command using the injected command_router
        await command_router.route_command(parsed_body_multivalue, response_url)
        logger.info("Command routed successfully")
        return ProcessingResult(status_code=200, body="")  # Ack command
    except Exception as e:
        logger.error("Error routing command: %s", e, exc_info=True)
        # Attempt to post error via response_url if possible
        # Note: Error posting might already be handled inside router/handlers
        try:
            # Access posting handler via router if possible, or need to pass it
            # Assuming router has access or we pass posting_handler explicitly
            posting_handler = getattr(command_router, "slack_posting_handler", None)
            if posting_handler:
                await posting_handler.post_message(
                    response_url=response_url,
                    message=f"Error processing command: {e}",
                )
            else:
                logger.warning("Cannot post command routing error: posting_handler unavailable.")
        except Exception as post_err:
            logger.error("Failed to post command routing error: %s", post_err)
        # Return 200 to ack receipt, even if internal processing failed
        return ProcessingResult(status_code=200, body="Error processing command")


async def handle_interactive_component(
    parsed_body_multivalue: Dict[str, List[str]],
    posting_handler: SlackPostingHandler,
    feedback_handler: FeedbackReactionsHandler,
    shortcut_handler: ShortcutHandler,
    feedback_report_handler: FeedbackReportHandler,
    channel_metadata_edit_handler: ChannelMetadataEditHandler,
    home_tab_handler: HomeTabHandler,
    trust_endorsement_handler: Any,  # TrustEndorsementHandler
    access_request_handler: Any = None,  # AccessRequestHandler - optional for access request automation
    flag_review_handler: Any = None,  # FlagReviewHandler - optional until implemented
    csopm_handler: Any = None,  # CSOPMHandler - optional for CSOPM notifications
) -> ProcessingResult:
    """
    Handles incoming interactive component payloads.

    Args:
        parsed_body_multivalue: The multi-value parsed request body.
        posting_handler: The SlackPostingHandler instance.
        feedback_handler: The FeedbackReactionsHandler instance.
        shortcut_handler: The ShortcutHandler instance.
        feedback_report_handler: The FeedbackReportHandler instance.

    Returns:
        ProcessingResult with status code and response body.
    """
    logger.info("Request identified as an Interactive Component")
    payload_list = parsed_body_multivalue.get("payload")
    if not payload_list or not isinstance(payload_list, list) or not payload_list[0]:
        logger.error("Invalid or missing payload in interactive component request")
        return ProcessingResult(
            status_code=400,
            body=json.dumps({"error": "Invalid payload format"}),
        )

    payload_str = payload_list[0]
    try:
        payload = json.loads(payload_str)
        logger.info("Parsed Interactive Payload: %s", payload)
        result = await process_interactive_payload(
            payload_input=payload,
            posting_handler=posting_handler,
            feedback_handler=feedback_handler,
            shortcut_handler=shortcut_handler,
            feedback_report_handler=feedback_report_handler,
            channel_metadata_edit_handler=channel_metadata_edit_handler,
            home_tab_handler=home_tab_handler,
            trust_endorsement_handler=trust_endorsement_handler,
            access_request_handler=access_request_handler,
            flag_review_handler=flag_review_handler,
            csopm_handler=csopm_handler,
        )
        logger.info("Processed interactive payload successfully.")
        # Return modal response (errors/update) if handler returned a dict
        if isinstance(result, dict) and result.get("response_action"):
            return ProcessingResult(status_code=200, body=json.dumps(result))
        return ProcessingResult(status_code=200, body="")  # Ack interaction
    except json.JSONDecodeError:
        logger.error("Failed to parse interactive payload JSON: %s", payload_str[:100])
        return ProcessingResult(
            status_code=400,
            body=json.dumps({"error": "Invalid payload format"}),
        )
    except Exception as e:
        logger.error("Error processing interactive payload: %s", e, exc_info=True)
        # Attempt to notify if possible (e.g., via response_url if available in payload)
        response_url = payload.get("response_url") if isinstance(payload, dict) else None
        if response_url:
            try:
                await posting_handler.post_message(
                    response_url=response_url,
                    message=f"Error processing interaction: {e}",
                )
            except Exception as post_error:
                logger.error("Failed to send interaction error via response_url: %s", post_error)

        # Ack receipt even on error to prevent Slack retries
        return ProcessingResult(status_code=200, body="Error processing interaction")


async def handle_events_api(
    parsed_body_multivalue: Dict[str, List[str]],
    parsed_body_dict: Dict[str, Any],
    event_handler: SlackEventHandler,
    home_tab_handler: Optional[HomeTabHandler] = None,
) -> Dict[str, Any]:
    """
    Handles incoming Events API events (url_verification or event_callback).

    Args:
        parsed_body_multivalue: The multi-value parsed request body.
        parsed_body_dict: The single-value parsed request body.
        event_handler: The SlackEventHandler instance.
        home_tab_handler: Optional HomeTabHandler instance for app_home_opened events.

    Returns:
        A dictionary suitable for returning from the Lambda function.
    """
    # Determine event type (preferring multivalue source)
    event_type_list = parsed_body_multivalue.get("type")
    event_type = event_type_list[0] if event_type_list else None
    source_dict = "multivalue"

    if not event_type:
        event_type = parsed_body_dict.get("type")
        source_dict = "single-value"
        if event_type:
            logger.warning("Event type found in single-value dict, processing may be incomplete")

    logger.info(
        "Request identified as an Events API Event: %s (source: %s)",
        event_type,
        source_dict,
    )

    # Handle URL Verification
    if event_type == "url_verification":
        challenge_list = parsed_body_multivalue.get("challenge")
        challenge = challenge_list[0] if challenge_list else parsed_body_dict.get("challenge")
        logger.info("Returning URL verification challenge: %s", challenge)
        return {"statusCode": 200, "body": challenge or ""}

    # Handle Event Callbacks (nested or direct)
    nested_event_data = None
    if "event" in parsed_body_multivalue:
        nested_event_list = parsed_body_multivalue.get("event")
        if nested_event_list and isinstance(nested_event_list, list) and nested_event_list[0]:
            try:
                nested_event_data = json.loads(nested_event_list[0])
            except (json.JSONDecodeError, TypeError):
                if isinstance(nested_event_list[0], dict):
                    nested_event_data = nested_event_list[0]
                else:
                    logger.error(
                        "Could not extract nested event dict from multivalue: %s",
                        (
                            nested_event_list[0][:200] + "..."
                            if isinstance(nested_event_list[0], str)
                            else type(nested_event_list[0])
                        ),
                    )
                    return {"statusCode": 400, "body": "Invalid event format"}
        else:
            logger.error("Missing or invalid 'event' field in multivalue dict for event_callback")
            return {"statusCode": 400, "body": "Invalid event_callback structure"}

    elif "event" in parsed_body_dict:
        nested_event_data = parsed_body_dict.get("event")
        if not isinstance(nested_event_data, dict):
            logger.warning(
                "Nested 'event' field in single-value dict is not a dict: %s",
                type(nested_event_data),
            )
            nested_event_data = None

    # Process the event using SlackEventHandler
    try:
        # Determine which dictionary to process
        dict_to_process = None
        if isinstance(nested_event_data, dict):
            logger.info("Using nested event data for processing.")
            dict_to_process = nested_event_data
        elif event_type != "event_callback":  # Avoid processing the wrapper itself
            logger.info("Using top-level dictionary for direct event type processing.")
            # Choose the correct source dictionary for direct event
            if source_dict == "single-value" and isinstance(parsed_body_dict, dict):
                dict_to_process = parsed_body_dict
            # Add handling if source was multivalue but event wasn't nested (less common)
            elif source_dict == "multivalue":
                logger.error("Cannot process non-nested direct event from multivalue source.")
                return {"statusCode": 400, "body": "Unexpected event structure"}

        # If we have a dictionary to process, dispatch it
        if dict_to_process:
            actual_event_type = dict_to_process.get("type")
            logger.info("Dispatching actual event type: %s", actual_event_type)

            # Ensure actual_event_type is a valid string key before using it
            if not isinstance(actual_event_type, str) or not actual_event_type:
                logger.error(
                    "Invalid or missing event type in event data: %s",
                    actual_event_type,
                )
                return {"statusCode": 400, "body": "Invalid event data: Missing type"}

            # Special handling for app_home_opened events
            if actual_event_type == "app_home_opened" and home_tab_handler:
                logger.info("Handling app_home_opened event with HomeTabHandler")
                try:
                    await home_tab_handler.handle_app_home_opened(dict_to_process)
                except Exception as home_err:
                    logger.error(
                        "Error handling app_home_opened event: %s",
                        home_err,
                        exc_info=True,
                    )
                return {"statusCode": 200, "body": "Home tab updated"}

            # Map event types to handler methods on the event_handler object
            event_handler_map = {
                "channel_created": event_handler.handle_channel_created,
                "member_joined_channel": event_handler.handle_member_joined_channel,
                "channel_archive": event_handler.handle_channel_archive,
                "channel_unarchive": event_handler.handle_channel_unarchive,
                "app_mention": event_handler.handle_app_mention,
                "message": event_handler.handle_message,  # Handle general message events
                "message.im": event_handler.handle_message_im,
                # Add other event types and their corresponding methods here
            }

            handler_func = event_handler_map.get(actual_event_type)

            if handler_func:
                # If the handler is not callable, raise an error
                if not callable(handler_func):
                    msg = f"Handler for {actual_event_type} is not callable"
                    logger.error(msg)
                    raise RuntimeError(msg)
                # Call the appropriate method on the event_handler instance
                await handler_func(dict_to_process)
            else:
                logger.warning("Unhandled Slack event type: %s", actual_event_type)

        elif event_type == "event_callback" and not nested_event_data:
            # This case happens if event_type is 'event_callback' but 'event' field was bad/missing
            logger.error(
                "Event type is 'event_callback' but nested 'event' data is invalid or missing."
            )
            return {"statusCode": 400, "body": "Invalid event_callback structure"}
        else:
            # Case where no valid dictionary was identified for processing
            logger.warning(
                "No valid event dictionary found to process for event_type: %s",
                event_type,
            )

        return {"statusCode": 200, "body": "Event received"}

    except Exception as e:
        logger.error("Error during event processing by SlackEventHandler: %s", e, exc_info=True)
        # Return 200 to ack receipt to Slack, but log the internal error
        return {"statusCode": 200, "body": "Error processing event"}
