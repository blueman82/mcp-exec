"""
payload_processor.py

Processes Slack interactive payload types including:
- block_actions: button clicks and other interactive elements
- shortcut: global and message shortcuts
- view_submission: modal form submissions
"""

import json
import re
from typing import Any, Dict, Union

from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger
from packages.slack.home.home import HomeTabHandler
from packages.slack.interactive_elements.access_request_handler import (
    AccessRequestHandler,
)
from packages.slack.interactive_elements.channel_metadata_edit import (
    ChannelMetadataEditHandler,
)
from packages.slack.interactive_elements.feedback_reactions import (
    FeedbackReactionsHandler,
)

# Import the FeedbackReportHandler
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler
from packages.slack.interactive_elements.shortcuts import ShortcutHandler
from packages.slack.interactive_elements.trust_endorsement_handler import (
    TrustEndorsementHandler,
)
from packages.slack.interactive_elements.view_submissions import process_view_submission
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


async def process_interactive_payload(
    payload_input: Union[Dict[str, Any], str],
    posting_handler: SlackPostingHandler,
    feedback_handler: FeedbackReactionsHandler,
    shortcut_handler: ShortcutHandler,
    feedback_report_handler: FeedbackReportHandler,
    channel_metadata_edit_handler: ChannelMetadataEditHandler,
    home_tab_handler: HomeTabHandler,
    trust_endorsement_handler: TrustEndorsementHandler,
    access_request_handler: AccessRequestHandler = None,  # AccessRequestHandler - optional until fully integrated
    flag_review_handler: Any = None,  # FlagReviewHandler - optional until fully implemented
) -> bool:
    """
    Process an interactive payload from Slack.

    Args:
        payload_input: Either a parsed payload dictionary or a body_dict containing a payload key
        posting_handler: The SlackPostingHandler instance managed by the ClientFactory.
        dynamodb_store: The DynamoDBStore instance for database operations.
        feedback_handler: The FeedbackReactionsHandler instance.
        feedback_report_handler: The FeedbackReportHandler instance.
        shortcut_handler: The ShortcutHandler instance.
        slack_auth: SlackAuth instance for verification (not used in this function)

    Returns:
        Boolean indicating success
    """
    logger.info("Processing interactive payload")

    try:
        # Determine the payload format and extract it
        # Case 1: Already a parsed dictionary (from incoming_events.py)
        if isinstance(payload_input, dict) and "type" in payload_input:
            logger.info("Received direct payload dictionary")
            payload = payload_input
        # Case 2: Body dict with payload key
        elif isinstance(payload_input, dict) and "payload" in payload_input:
            logger.info("Extracting payload from body_dict")
            payload_str = payload_input.get("payload")

            # Handle payload as string or list
            if isinstance(payload_str, list):
                payload_str = payload_str[0]

            # Parse the payload JSON
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse payload JSON: %s", str(e))
                return False
        # Case 3: Unknown format
        else:
            logger.error("Invalid payload format: %s", type(payload_input))
            return False

        # Log the type of interaction
        payload_type = payload.get("type")
        logger.info("Received interactive payload of type: %s", payload_type)

        # Extract user and channel IDs for posting messages
        user_id = payload.get("user", {}).get("id")
        channel_id = payload.get("channel", {}).get("id")

        if payload_type == "block_actions":
            # Handle button clicks and other interactive elements
            actions = payload.get("actions", [])
            if not actions:
                logger.warning("No actions found in block_actions payload")
                await posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message="No actions found in payload",
                )
                return True

            # Get the first action
            action = actions[0]
            action_id = action.get("action_id", "")

            # Handle feedback actions
            if action_id.startswith("feedback_"):
                logger.info("Processing feedback action: %s", action_id)
                success = await feedback_handler.process_feedback_reaction(payload=payload)
                if not success:
                    logger.error("Failed to process feedback reaction")
                    await posting_handler.post_message(
                        user_id=user_id,
                        channel_id=channel_id,
                        message="Error processing feedback. Please try again.",
                    )
                return True

            # Route Home tab Save Preferences button to HomeTabHandler
            if (
                action_id == "save_preferences_button"
                or action_id == "home_open_feedback_modal"
                or action_id == "export_usage_csv"
            ):
                logger.info(f"Routing {action_id} to HomeTabHandler")
                return await home_tab_handler.handle_block_actions(payload)

            # Handle edit channel metadata action via injected handler
            if action_id == "edit_channel_metadata":
                try:
                    initial_values: Dict[str, str] = json.loads(action.get("value", "{}"))
                except json.JSONDecodeError:
                    initial_values = {}
                trigger_id = payload.get("trigger_id")
                # Get both origin and target channel IDs
                origin_channel_id = payload.get("channel", {}).get("id")
                target_channel_id = initial_values.get("channel_id") or origin_channel_id
                if not origin_channel_id:
                    logger.error("No origin_channel_id found for edit modal open")
                    await posting_handler.post_message(
                        user_id=user_id,
                        channel_id=None,
                        message="Internal error: missing channel context. Please try again.",
                    )
                    return False
                await channel_metadata_edit_handler.open_edit_modal(
                    trigger_id, initial_values, origin_channel_id, target_channel_id
                )
                return True

            # Process trust actions using trust endorsement handler
            if action_id == "trust_status_update":
                logger.info("Processing trust action: %s", action_id)

                # Both command and status IDs have identical timestamp_uuid format
                # Try status handler first (for automated status updates), fallback to command handler
                actions = payload.get("actions", [])
                if not actions:
                    logger.error("No actions found in trust action payload")
                    return True
                action = actions[0]
                button_value = action.get("value", "")
                if not button_value:
                    logger.error("No value found in trust action button")
                    return True

                # Try status update handler first (more common for automated updates)
                success = await trust_endorsement_handler.process_trust_action(payload=payload)

                # If status handler failed to find record, try command handler
                if not success and "_" in button_value and len(button_value.split("_")) == 2:
                    logger.info(f"Status handler failed for {button_value}, trying command handler")
                    success = await trust_endorsement_handler.process_command_trust_action(
                        payload=payload
                    )

                if not success:
                    logger.error("Failed to process trust action")
                    # Don't show error to user for trust actions
                return True

            # Process flag actions using flag review handler
            if action_id == "flag_status_review":
                if flag_review_handler is None:
                    logger.error("Flag review handler not available")
                    return True
                logger.info("Processing flag action: %s", action_id)

                # Check if this is a command (ephemeral) or status (persistent) message
                container = payload.get("container", {})
                is_ephemeral = container.get("is_ephemeral", False)

                if is_ephemeral:
                    # Command outputs are ephemeral
                    success = await flag_review_handler.process_command_flag_action(payload=payload)
                else:
                    # Status updates are persistent messages
                    success = await flag_review_handler.process_flag_action(payload=payload)

                if not success:
                    logger.error("Failed to process flag action")
                return True

            # Process access request actions (only if feature is enabled)
            if FeatureFlags.is_access_request_automation_enabled():
                if action_id == "request_access":
                    if access_request_handler is None:
                        logger.error("Access request handler not available")
                        return True
                    logger.info("Processing access request action")
                    response = await access_request_handler.handle_request_access(payload)
                    # Send response to user
                    if response:
                        response_url = payload.get("response_url")
                        await posting_handler.post_message(
                            user_id=user_id,
                            channel_id=channel_id,
                            message=response.get("text", ""),
                            response_url=response_url,
                        )
                    return True

                # Process access approval actions
                if action_id.startswith("approve_access_"):
                    if access_request_handler is None:
                        logger.error("Access request handler not available")
                        return True
                    logger.info("Processing access approval action")
                    response = await access_request_handler.handle_approve_access(payload)
                    # Send response to approver
                    if response:
                        await posting_handler.post_message(
                            user_id=user_id,
                            channel_id=channel_id,
                            message=response.get("text", ""),
                        )
                    return True

                # Process access rejection actions
                if action_id.startswith("reject_access_"):
                    if access_request_handler is None:
                        logger.error("Access request handler not available")
                        return True
                    logger.info("Processing access rejection action - opening modal")
                    await access_request_handler.handle_reject_access(payload)
                    return True

            # Process flag review actions (admin actions only)
            if action_id in ["acknowledge_feedback", "reply_to_feedback", "mark_review_completed"]:
                if flag_review_handler is None:
                    logger.error("Flag review handler not available")
                    return True
                logger.info("Processing flag review action: %s", action_id)
                success = await flag_review_handler.process_flag_action(payload=payload)
                if not success:
                    logger.error("Failed to process flag review action")
                return True

            # Process command flag review actions (admin actions only)
            if action_id in [
                "acknowledge_command_feedback",
                "reply_to_command_feedback",
            ]:
                if flag_review_handler is None:
                    logger.error("Flag review handler not available")
                    return True
                logger.info("Processing command flag review action: %s", action_id)
                success = await flag_review_handler.process_command_flag_action(payload=payload)
                if not success:
                    logger.error("Failed to process command flag review action")
                return True

            # Unknown action
            logger.warning("Unknown action_id: %s", action_id)
            await posting_handler.post_message(
                user_id=user_id,
                channel_id=channel_id,
                message="Unknown action: %s" % action_id,
            )
            return True

        elif payload_type == "shortcut":
            # Handle global and message shortcuts using the injected handler
            success = await shortcut_handler.handle_shortcut(slack_payload=payload)
            return success

        elif payload_type == "view_submission":
            callback_id = payload.get("view", {}).get("callback_id")

            # Handle access request rejection modal submission (only if feature is enabled)
            if (
                callback_id == "reject_reason_modal"
                and FeatureFlags.is_access_request_automation_enabled()
            ):
                if access_request_handler is None:
                    logger.error("Access request handler not available for modal submission")
                    return True
                logger.info("Processing access request rejection modal submission")
                response = await access_request_handler.handle_rejection_submission(payload)
                # The handler returns a response_type: "clear" for successful handling
                return True

            # Handle flag review modal submission
            if callback_id == "flag_review_modal":
                if flag_review_handler is None:
                    logger.error("Flag review handler not available for modal submission")
                    return True
                logger.info("Processing flag review modal submission")
                success = await flag_review_handler.process_flag_action(payload=payload)
                return success

            if callback_id == "edit_channel_metadata":
                # Extract modal values
                values = payload["view"]["state"]["values"]
                customer_name = values["customer_name_block"]["customer_name_input"]["value"]
                jira_ticket_input = values["jira_ticket_block"]["jira_ticket_input"]["value"]
                user_id = payload.get("user", {}).get("id")

                # Validate customer_name
                errors = {}
                if not customer_name or not customer_name.strip():
                    errors["customer_name_block"] = "Customer name is required."
                elif len(customer_name) > 100:
                    errors["customer_name_block"] = "Customer name must be 100 characters or less."
                if errors:
                    return {"response_action": "errors", "errors": errors}

                # Normalize JIRA ticket
                ticket_match = re.search(
                    r"([A-Z][A-Z0-9]+-\d+)", jira_ticket_input or "", re.IGNORECASE
                )
                jira_ticket = ticket_match.group(1).upper() if ticket_match else jira_ticket_input

                # Extract target_channel_id from private_metadata (REQUIRED)
                # This prevents data corruption by ensuring the correct channel is updated
                private_metadata = payload.get("view", {}).get("private_metadata")
                channel_id = None

                # Validate private_metadata is present and valid
                if private_metadata:
                    try:
                        meta = json.loads(private_metadata)
                        channel_id = meta.get("target_channel_id")
                        if not channel_id:
                            logger.error(
                                "target_channel_id missing from private_metadata: %s",
                                meta,
                            )
                            return False
                    except json.JSONDecodeError as e:
                        logger.error("Failed to parse private_metadata JSON: %s", str(e))
                        return False
                else:
                    logger.error("private_metadata is missing or empty for edit_channel_metadata")
                    return False

                # Update DB (snake_case args)
                try:
                    customer_name = customer_name.upper() if customer_name else customer_name
                    db_success = (
                        await channel_metadata_edit_handler.dynamodb_store.update_channel_metadata(
                            channel_id=channel_id,
                            customer_name=customer_name,
                            jira_ticket=jira_ticket,
                            user_id=user_id,
                        )
                    )
                except Exception as e:
                    logger.error("Exception during DB update: %s", str(e))
                    db_success = False

                if not db_success:
                    logger.error("Failed to update channel metadata in DB for %s", channel_id)
                    return False

                # Only show success modal confirmation
                trigger_id = payload.get("trigger_id")
                if trigger_id:
                    await channel_metadata_edit_handler.open_success_modal(trigger_id)
                else:
                    logger.error("No trigger_id found in payload for success modal.")
                return True
            # Handle other view_submissions as before
            success = await process_view_submission(
                payload=payload,
                feedback_report_handler=feedback_report_handler,
                flag_review_handler=flag_review_handler,
            )
            return success

        else:
            # Unknown payload type
            logger.warning("Unknown payload type: %s", payload_type)
            if user_id and channel_id:
                await posting_handler.post_message(
                    user_id=user_id,
                    channel_id=channel_id,
                    message="Unknown payload type: %s" % payload_type,
                )
            return False

    except Exception as e:
        logger.error("Exception in payload processing: %s", str(e))
        return False
