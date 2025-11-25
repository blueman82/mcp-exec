#!/usr/bin/env python3
"""Fix the leaked prompt content in channel C093030809M"""

import asyncio
import os

import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Simple logger
class Logger:
    def info(self, msg):
        print(f"[INFO] {msg}")

    def error(self, msg, exc_info=None):
        print(f"[ERROR] {msg}")


logger = Logger()

CHANNEL_ID = "C093030809M"
MESSAGE_TS = "1752174225.370169"


async def fix_message():
    """Fix the leaked prompt message"""
    try:
        # Get Slack token from environment
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        if not slack_token:
            logger.error("SLACK_BOT_TOKEN not found in environment")
            return

        # Get the current message content
        url = "https://slack.com/api/conversations.history"
        headers = {
            "Authorization": f"Bearer {slack_token}",
            "Content-Type": "application/json",
        }
        params = {
            "channel": CHANNEL_ID,
            "latest": MESSAGE_TS,
            "inclusive": True,
            "limit": 1,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response_data = await response.json()

        if not response_data.get("ok"):
            logger.error(f"Failed to fetch message: {response_data.get('error')}")
            return

        messages = response_data.get("messages", [])
        if not messages:
            logger.error("No message found with that timestamp")
            return

        message = messages[0]
        text = message.get("text", "")

        logger.info(f"Found message with {len(text)} characters")

        # Check if it contains the leaked prompt content
        if "#################################################" in text:
            # Get content before the first delimiter
            good_content = text.split(
                "#################################################"
            )[0].strip()

            logger.info(f"Cleaning message - keeping {len(good_content)} characters")

            # Update the message with cleaned content
            update_url = "https://slack.com/api/chat.update"
            update_data = {
                "channel": CHANNEL_ID,
                "ts": MESSAGE_TS,
                "text": good_content,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    update_url, headers=headers, json=update_data
                ) as response:
                    update_result = await response.json()

                    if update_result.get("ok"):
                        logger.info(
                            "Successfully updated message to remove leaked prompt content"
                        )
                    else:
                        logger.error(
                            f"Failed to update message: {update_result.get('error')}"
                        )
        else:
            logger.info(
                "Message doesn't contain leaked prompt content - no action needed"
            )
            logger.info(f"Current message text: {text[:200]}...")

    except Exception as e:
        logger.error(f"Error fixing message: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(fix_message())
