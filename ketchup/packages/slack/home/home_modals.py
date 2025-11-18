"""
home_modals.py

Handles construction and publishing of Slack modals for the Home tab, such as the preferences saved confirmation modal.
"""

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def open_success_modal(slack_client, trigger_id: str, real_name: str) -> bool:
    """Open a success modal to confirm preferences update, personalized with the user's first name.

    Args:
        slack_client: SlackAsyncClient for Slack API interactions
        trigger_id: The trigger ID provided by Slack to open the modal
        real_name: The user's real name (full name)

    Returns:
        bool: True if the modal was opened successfully, False otherwise
    """
    try:
        first_name = real_name.split()[0] if real_name else "there"
        payload = {
            "trigger_id": trigger_id,
            "view": {
                "type": "modal",
                "callback_id": "preferences_saved",
                "title": {
                    "type": "plain_text",
                    "text": "Preferences Saved",
                    "emoji": True,
                },
                "close": {"type": "plain_text", "text": "Close", "emoji": True},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *Thank you {first_name}, your preferences are now saved!*",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "Your preferences will be used to personalize your summaries. You can update them any time from the Home tab.",
                            }
                        ],
                    },
                ],
            },
        }
        data = await slack_client.api_call("views.open", payload)
        if not data.get("ok"):
            logger.error("Failed to open success modal: %s", data.get("error"))
            return False
        logger.info("Successfully opened success modal")
        return True
    except Exception as e:
        logger.error("Error opening success modal: %s", str(e))
        return False
