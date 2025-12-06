"""
feedback_report.py

This module handles the Slack feedback report flow, including opening the
feedback modal and sending the report to a designated channel using a dedicated handler class.
"""

from typing import Any, Dict, Optional

import aiohttp

from packages.core.constants import FEEDBACK_CHANNEL
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class FeedbackReportHandler:
    """Handles the feedback report workflow via Slack modals and messages."""

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        secrets_manager: SecretsManager,
    ):
        """
        Initializes the FeedbackReportHandler.

        Args:
            posting_handler: Handler for posting messages to Slack.
            secrets_manager: Handler for retrieving secrets like API tokens.
        """
        self._posting_handler = posting_handler
        self._secrets_manager = secrets_manager
        logger.info("FeedbackReportHandler initialized.")

    async def _build_feedback_report_modal(self) -> Dict[str, Any]:
        """
        Build a Block Kit layout for the feedback report modal.

        Returns:
            A dictionary representing the modal view for submitting a feedback report
        """
        logger.info("Building feedback report modal")

        return {
            "type": "modal",
            "callback_id": "submit_feedback_report",
            "title": {"type": "plain_text", "text": "Report Feedback"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "feedback_name",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "name_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter feedback title...",
                        },
                    },
                    "label": {"type": "plain_text", "text": "Feedback Name"},
                },
                {
                    "type": "input",
                    "block_id": "feedback_description",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "description_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Please enter feedback...",
                        },
                    },
                    "label": {"type": "plain_text", "text": "Feedback Description"},
                },
            ],
        }

    async def open_feedback_report_modal(self, trigger_id: str) -> bool:
        """
        Open the feedback report modal for the user.

        Args:
            trigger_id: The trigger ID provided by Slack to open the modal

        Returns:
            Boolean indicating success
        """
        logger.info("Opening feedback report modal with trigger ID %s", trigger_id)

        try:
            # Use injected secrets manager
            slack_api_token = await self._secrets_manager.get_slack_api_token_async()

            # Configure Slack API endpoint
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            # Build modal view using class method
            modal_view = await self._build_feedback_report_modal()

            # Prepare request payload
            payload = {
                "trigger_id": trigger_id,
                "view": modal_view,
            }

            # Use the posting handler's session if available, or create a new one
            # Note: This assumes SlackPostingHandler exposes its session or _make_api_request method
            # If not, we might need to adjust SlackPostingHandler or use a separate AsyncClient here.
            # For now, let's assume a direct post capability or session access.
            # A more robust solution might involve SlackPostingHandler having a `views_open` method.
            # Simplified approach using a temporary session for now:
            timeout = aiohttp.ClientTimeout(total=120)  # 2-minute timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    logger.info(
                        "Received response status: %s from Slack API views.open",
                        response.status,
                    )
                    response_data = await response.json()

                    if not response_data.get("ok"):
                        logger.error(
                            "Failed to open feedback report modal: %s",
                            response_data.get("error"),
                        )
                        return False
                    else:
                        logger.info("Feedback report modal opened successfully")
                        return True
        except Exception as e:
            logger.error("Error opening feedback report modal: %s", str(e), exc_info=True)
            return False

    async def _send_success_modal(self, trigger_id: str) -> bool:
        """
        Open a success modal to confirm feedback submission.

        Args:
            trigger_id: The trigger ID provided by Slack to open the modal

        Returns:
            Boolean indicating success
        """
        logger.info("Opening success modal with trigger ID %s", trigger_id)

        try:
            # Use injected secrets manager
            slack_api_token = await self._secrets_manager.get_slack_api_token_async()

            # Configure Slack API endpoint
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_api_token}",
                "Content-Type": "application/json",
            }

            # Prepare success modal
            payload = {
                "trigger_id": trigger_id,
                "view": {
                    "type": "modal",
                    "callback_id": "success_feedback_report",
                    "title": {"type": "plain_text", "text": "Submission Successful"},
                    "close": {"type": "plain_text", "text": "Close"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "✅ *Your feedback has been posted successfully!* 🎉",
                            },
                        },
                        {"type": "divider"},
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "Thank you for your input! Your feedback helps us improve Ketchup! 😊",
                                }
                            ],
                        },
                    ],
                },
            }

            # Simplified approach using a temporary session for now:
            timeout = aiohttp.ClientTimeout(total=120)  # 2-minute timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    logger.info(
                        "Received response status: %s from Slack API views.open (success modal)",
                        response.status,
                    )
                    response_data = await response.json()

                    if not response_data.get("ok"):
                        logger.error(
                            "Failed to open success modal: %s",
                            response_data.get("error"),
                        )
                        return False
                    else:
                        logger.info("Success modal opened successfully")
                        return True
        except Exception as e:
            logger.error("Error opening success modal: %s", str(e), exc_info=True)
            return False

    async def send_feedback_report_to_channel(
        self,
        user_id: str,
        feedback_name: str,
        feedback_description: str,
        trigger_id: str,
        response_url: Optional[str] = None,
    ) -> bool:
        """
        Send a feedback report to a designated Slack channel and open a success modal.

        Args:
            user_id: The Slack user ID who submitted the feedback
            feedback_name: The title of the feedback
            feedback_description: The detailed feedback description
            trigger_id: The Slack trigger ID for opening the success modal
            response_url: Optional Slack response URL for interactive message responses

        Returns:
            Boolean indicating success
        """
        logger.info(
            "Sending feedback report from user %s to channel %s",
            user_id,
            FEEDBACK_CHANNEL,
        )

        try:
            # Construct the feedback report blocks
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚨 New Feedback Report 🚨"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Feedback Title:* {feedback_name}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Description:*\n{feedback_description}",
                    },
                },
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"📝 Reported by <@{user_id}>"}],
                },
            ]

            # Post feedback to designated channel using injected handler
            post_success = await self._posting_handler.post_message(
                channel_id=FEEDBACK_CHANNEL, blocks=blocks, response_url=response_url
            )

            if post_success:
                # Open success modal using class method
                modal_success = await self._send_success_modal(trigger_id)
                if modal_success:
                    logger.info("Feedback report successfully sent and success modal opened")
                else:
                    logger.warning("Feedback report sent, but failed to open success modal.")
                return True  # Report sent, even if modal failed
            else:
                logger.error("Failed to post feedback report to channel")
                return False

        except Exception as e:
            logger.error("Error sending feedback report: %s", str(e), exc_info=True)
            return False
