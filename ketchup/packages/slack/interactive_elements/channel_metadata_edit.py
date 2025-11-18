"""
channel_metadata_edit.py

Module to handle opening and managing the "Edit Channel Metadata" modal in Slack.
"""

import json
from typing import Any, Dict

import aiohttp

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class ChannelMetadataEditHandler:
    """
    Handler for opening and managing the Edit Channel Metadata modal.

    Uses Slack API `views.open` to present a modal where users can update
    the customer name and JIRA ticket for a channel.

    Attributes:
        _posting_handler (SlackPostingHandler): Handler for Slack API messaging.
        _secrets_manager (SecretsManager): Retrieves Slack API tokens.
        dynamodb_store (DynamoDBStore): For updating channel metadata in DB.
    """

    def __init__(
        self,
        posting_handler: SlackPostingHandler,
        secrets_manager: SecretsManager,
        dynamodb_store: DynamoDBStore,
    ):
        """
        Initialize the ChannelMetadataEditHandler.

        Args:
            posting_handler (SlackPostingHandler): For sending Slack messages.
            secrets_manager (SecretsManager): For retrieving Slack API token.
            dynamodb_store (DynamoDBStore): For updating channel metadata in DB.
        """
        self._posting_handler = posting_handler
        self._secrets_manager = secrets_manager
        self.dynamodb_store = dynamodb_store
        logger.info("ChannelMetadataEditHandler initialized.")

    async def _build_edit_modal(
        self,
        initial_values: Dict[str, str],
        origin_channel_id: str,
        target_channel_id: str,
    ) -> Dict[str, Any]:
        """
        Build the Block Kit view payload for the edit modal.

        Args:
            initial_values (Dict[str, str]): Prefilled values for inputs.
            origin_channel_id (str): The Slack channel ID where the edit was initiated.
            target_channel_id (str): The Slack channel ID of the record being edited.

        Returns:
            Dict[str, Any]: JSON payload for Slack `views.open` API.
        """
        return {
            "type": "modal",
            "callback_id": "edit_channel_metadata",
            "private_metadata": json.dumps(
                {
                    "origin_channel_id": origin_channel_id,
                    "target_channel_id": target_channel_id,
                }
            ),
            "title": {"type": "plain_text", "text": "Edit Customer & Ticket"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "customer_name_block",
                    "label": {"type": "plain_text", "text": "Customer Name"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "customer_name_input",
                        "initial_value": initial_values.get("customer_name", ""),
                        "max_length": 100,
                    },
                },
                {
                    "type": "input",
                    "block_id": "jira_ticket_block",
                    "label": {"type": "plain_text", "text": "JIRA Ticket"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "jira_ticket_input",
                        "initial_value": initial_values.get("jira_ticket", ""),
                    },
                },
            ],
        }

    async def open_edit_modal(
        self,
        trigger_id: str,
        initial_values: Dict[str, str],
        origin_channel_id: str,
        target_channel_id: str,
    ) -> bool:
        """
        Open the Edit Channel Metadata modal in Slack.

        Args:
            trigger_id (str): Slack trigger_id for the modal.
            initial_values (Dict[str, str]): Prefill for 'customer_name' and 'jira_ticket'.
            origin_channel_id (str): The Slack channel ID where the edit was initiated.
            target_channel_id (str): The Slack channel ID of the record being edited.

        Returns:
            bool: True if the modal was opened successfully, False otherwise.
        """
        try:
            slack_token = await self._secrets_manager.get_slack_api_token_async()
        except Exception as e:
            logger.error("Failed to retrieve Slack API token: %s", e)
            return False

        url = "https://slack.com/api/views.open"
        headers = {
            "Authorization": f"Bearer {slack_token}",
            "Content-Type": "application/json",
        }
        view = await self._build_edit_modal(
            initial_values, origin_channel_id, target_channel_id
        )
        payload = {"trigger_id": trigger_id, "view": view}

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.error("Failed to open edit modal: %s", data.get("error"))
                    return False
        return True

    async def open_success_modal(self, trigger_id: str) -> bool:
        """
        Open a success modal to confirm channel metadata update.

        Args:
            trigger_id (str): The trigger ID provided by Slack to open the modal

        Returns:
            bool: True if the modal was opened successfully, False otherwise.
        """
        logger.info(
            "Opening success modal for channel metadata update with trigger ID %s",
            trigger_id,
        )
        try:
            slack_token = await self._secrets_manager.get_slack_api_token_async()
            url = "https://slack.com/api/views.open"
            headers = {
                "Authorization": f"Bearer {slack_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "trigger_id": trigger_id,
                "view": {
                    "type": "modal",
                    "callback_id": "success_channel_metadata_edit",
                    "title": {"type": "plain_text", "text": "Update Successful"},
                    "close": {"type": "plain_text", "text": "Close"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "✅ *Channel metadata updated successfully! Run your command again to see the updates.*",
                            },
                        },
                        {"type": "divider"},
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "Your changes have been saved. Thank you!",
                                }
                            ],
                        },
                    ],
                },
            }
            timeout = aiohttp.ClientTimeout(total=10)
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
