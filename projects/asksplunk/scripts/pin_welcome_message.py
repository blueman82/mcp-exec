#!/usr/bin/env python3
"""Pin the welcome message to #asksplunk channel.

Usage:
    python scripts/pin_welcome_message.py --from-aws
"""

import argparse
import asyncio
import os
import sys

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

ASKSPLUNK_CHANNEL_ID = "C0AD4DRHHS8"

WELCOME_MESSAGE = """:wave: Welcome to *#asksplunk*!

This channel is for questions, feedback, and support for the AskSplunk bot.

*What is AskSplunk?*
A bot that translates natural language questions about Adobe Campaign logs into Splunk SPL queries.

*How to use AskSplunk:*
• Send a direct message to <@U09T3R0QHSM> with your question
• Follow up in the same thread for related questions

*Example questions:*
• "Show me hard bounces"
• "What's the delivery success rate?"
• "Which domains have the most bounces?"
• "Show me 550 error codes"

*What happens:*
1. The bot analyzes your question
2. If clarification is needed, it'll ask (reply with just the number)
3. You get a ready-to-run Splunk query with explanations

:lock: *Privacy:* Message content is never logged. Only metadata (user ID, timestamp) is recorded.

Questions or issues? Post here!"""


async def get_bot_token_from_aws(profile: str | None = None) -> str:
    """Fetch bot token from AWS Secrets Manager."""
    import aioboto3
    import json

    session = aioboto3.Session(profile_name=profile)
    async with session.client("secretsmanager", region_name="eu-west-1") as client:
        response = await client.get_secret_value(SecretId="splunk-bot/slack-tokens")
        secret = json.loads(response["SecretString"])
        return secret["bot_token"]


async def pin_welcome_message(bot_token: str, dry_run: bool = False) -> None:
    """Post welcome message to #asksplunk and pin it."""
    client = AsyncWebClient(token=bot_token)

    if dry_run:
        print("[DRY RUN] Would post and pin message to #asksplunk")
        print(f"\nMessage preview:\n{WELCOME_MESSAGE[:200]}...")
        return

    try:
        # Post the message
        response = await client.chat_postMessage(
            channel=ASKSPLUNK_CHANNEL_ID,
            text=WELCOME_MESSAGE,
            mrkdwn=True,
        )
        ts = response["ts"]
        print(f"[OK] Posted message (ts: {ts})")

        # Pin the message
        await client.pins_add(
            channel=ASKSPLUNK_CHANNEL_ID,
            timestamp=ts,
        )
        print("[OK] Pinned message to #asksplunk")

    except SlackApiError as e:
        print(f"[ERROR] {e.response['error']}")
        sys.exit(1)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Pin welcome message to #asksplunk")
    parser.add_argument("--from-aws", action="store_true", help="Fetch bot token from AWS Secrets Manager")
    parser.add_argument("--aws-profile", default="campaign_prod_v7", help="AWS profile name")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without doing it")
    args = parser.parse_args()

    if args.from_aws:
        print(f"Fetching bot token from AWS (profile: {args.aws_profile})...")
        bot_token = await get_bot_token_from_aws(profile=args.aws_profile)
    else:
        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        if not bot_token:
            print("Error: Set SLACK_BOT_TOKEN or use --from-aws")
            sys.exit(1)

    await pin_welcome_message(bot_token, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
