"""
view_submissions.py

This module processes Slack view submissions, such as modal form submissions.
"""

from typing import Any, Dict, cast

from packages.core.logging import setup_logger
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler

logger = setup_logger(__name__)


async def process_view_submission(
    payload: Dict[str, Any],
    feedback_report_handler: FeedbackReportHandler,
    flag_review_handler: Any = None,
) -> bool:
    """
    Process modal view submissions.

    Args:
        payload: The parsed Slack payload dictionary for view_submission.
        feedback_report_handler: Instance of FeedbackReportHandler.
        flag_review_handler: Instance of FlagReviewHandler.

    Returns:
        Boolean indicating whether the submission was processed successfully.
    """

    view = payload.get("view", {})
    callback_id = view.get("callback_id")

    logger.info("Processing view submission with callback_id: %s", callback_id)

    # Handle flag review modal submission
    if callback_id == "reply_feedback_modal":
        if flag_review_handler is None:
            logger.error("Flag review handler not available for reply_feedback_modal submission")
            return False
        logger.info("Routing reply_feedback_modal to flag_review_handler")
        return await flag_review_handler.process_flag_action(payload)

    # Handle command reply modal submission
    if callback_id == "reply_command_feedback_modal":
        if flag_review_handler is None:
            logger.error(
                "Flag review handler not available for reply_command_feedback_modal submission"
            )
            return False
        logger.info("Routing reply_command_feedback_modal to flag_review_handler")
        return await flag_review_handler.process_command_flag_action(payload)

    # Handle command flag review modal submission
    if callback_id == "command_flag_review_modal":
        if flag_review_handler is None:
            logger.error(
                "Flag review handler not available for command_flag_review_modal submission"
            )
            return False
        logger.info(
            "Routing command_flag_review_modal to flag_review_handler.process_command_flag_action"
        )
        return await flag_review_handler.process_command_flag_action(payload)

    # Handle feedback report submission
    if callback_id == "submit_feedback_report":
        # Extract feedback details
        state_values = payload.get("view", {}).get("state", {}).get("values", {})
        user_id = payload.get("user", {}).get("id")
        trigger_id = payload.get("trigger_id")

        # Get values from the input blocks
        feedback_name = state_values.get("feedback_name", {}).get("name_input", {}).get("value")
        feedback_description = (
            state_values.get("feedback_description", {}).get("description_input", {}).get("value")
        )

        if not all([user_id, feedback_name, feedback_description, trigger_id]):
            logger.error(
                "Missing required data (user, name, description, trigger) for feedback report submission."
            )
            return False

        # Send the feedback report using the injected handler
        response_url = payload.get("response_url")
        success = await feedback_report_handler.send_feedback_report_to_channel(
            user_id=user_id,
            feedback_name=feedback_name,
            feedback_description=feedback_description,
            trigger_id=cast(str, trigger_id),
            response_url=response_url,
        )
        return success

    # Add handlers for other view submissions here

    # If we reach here, no specific handler was triggered
    logger.warning("Unhandled view_submission callback_id: %s", callback_id)
    # Optionally send an acknowledgment or error message
    return True
