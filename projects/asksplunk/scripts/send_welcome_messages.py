#!/usr/bin/env python3
"""One-time script to send welcome messages to authorized users.

Usage:
    export SLACK_BOT_TOKEN="xoxb-..."
    python scripts/send_welcome_messages.py

Or fetch token from AWS Secrets Manager:
    python scripts/send_welcome_messages.py --from-aws
"""

import argparse
import asyncio
import os
import sys

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

# Support channel for questions/feedback
ASKSPLUNK_CHANNEL_ID = "C0AD4DRHHS8"

# 24 authorized users
AUTHORIZED_USERS = [
    "W7MGASQ2K",   # harrison
    "W5H6R82Q6",   # mhudson
    "WDHGPEL2K",   # omahony
    "W6K9PKSL8",   # omeara
    "WK66QJZ7D",   # orbell
    "WDGLSLQRK",   # pieczyra
    "W6TCPR5JA",   # szysz
    "W6YLR99EJ",   # abdelhak
    "W4R4SENSU",   # bronshte
    "W74KBA6SG",   # fofana
    "W4R4RGY4Q",   # joyon
    "W4RT2F744",   # ramage
    "WRJMCB2KV",   # adcain
    "WAF4AT10R",   # anagniho
    "W4X4VEJVD",   # anearora
    "U01SXJTMJ10", # bommakan
    "W662445MX",   # cbell
    "WBTDFEEK0",   # fontaine
    "W5BHGMYLU",   # ghader
    "WJMK76AUB",   # jamsa
    "W4R540SFJ",   # mijin
    "WCSAM821W",   # miner
    "W4WJJ3C1M",   # nrosenbe
    "W4SGKQ32T",   # sdupre
    "U0A8LAS7A6S", # pcheenepalli
]

WELCOME_MESSAGE = """:wave: Welcome to *AskSplunk*!

I translate natural language questions about Adobe Campaign logs into Splunk SPL queries.

*What I can help with:*
• Bounce analysis (hard/soft bounces, error codes, bounce rates)
• Delivery statistics (success rates, volume over time)
• Instance/customer filtering (e.g., "bounces for virginatlantic")
• HTTP/Apache error analysis

*Example questions:*
• "Show me hard bounces"
• "What's the delivery success rate?"
• "Which domains have the most bounces?"
• "Show me 550 error codes"

*How to ask:*
• Send me a direct message with your question
• Follow up in the same thread for related questions

*What happens:*
1. I'll analyze your question
2. If I need clarification, I'll ask (reply with just the number)
3. I'll return a ready-to-run Splunk query with plain language + technical explanation

:lock: *Privacy:* Your message content is never logged. Only metadata (user ID, timestamp) is recorded.

Questions? Drop a message in <#C0AD4DRHHS8>."""


async def get_bot_token_from_aws(profile: str | None = None) -> str:
    """Fetch bot token from AWS Secrets Manager.

    Args:
        profile: AWS profile name (uses AWS_PROFILE env var if not specified)
    """
    import aioboto3
    import json

    session = aioboto3.Session(profile_name=profile)
    async with session.client("secretsmanager", region_name="eu-west-1") as client:
        response = await client.get_secret_value(SecretId="splunk-bot/slack-tokens")
        secret = json.loads(response["SecretString"])
        return secret["bot_token"]


async def invite_users_to_channel(bot_token: str, dry_run: bool = False, users: list[str] | None = None) -> None:
    """Invite users to the #asksplunk channel.

    Args:
        bot_token: Slack bot token
        dry_run: If True, only print what would happen without actually inviting
        users: List of user IDs to invite (defaults to AUTHORIZED_USERS)
    """
    users = users or AUTHORIZED_USERS
    client = AsyncWebClient(token=bot_token)

    # Ensure bot is in the channel first
    if not dry_run:
        try:
            await client.conversations_join(channel=ASKSPLUNK_CHANNEL_ID)
            print("[OK] Bot joined #asksplunk")
        except SlackApiError as e:
            if e.response["error"] == "already_in_channel":
                print("[OK] Bot already in #asksplunk")
            else:
                print(f"[ERROR] Bot couldn't join #asksplunk: {e.response['error']}")
                print("Please manually /invite the bot to the channel first.")
                return

    success_count = 0
    already_member = 0
    error_count = 0

    for user_id in users:
        try:
            if dry_run:
                print(f"[DRY RUN] Would invite {user_id} to #asksplunk")
                success_count += 1
                continue

            await client.conversations_invite(
                channel=ASKSPLUNK_CHANNEL_ID,
                users=[user_id],
            )
            print(f"[OK] Invited {user_id} to #asksplunk")
            success_count += 1
            await asyncio.sleep(0.5)  # Rate limit

        except SlackApiError as e:
            if e.response["error"] == "already_in_channel":
                print(f"[SKIP] {user_id} already in #asksplunk")
                already_member += 1
            else:
                print(f"[ERROR] Failed to invite {user_id}: {e.response['error']}")
                error_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to invite {user_id}: {e}")
            error_count += 1

    print(f"\nChannel invites: {success_count} invited, {already_member} already members, {error_count} errors\n")


async def send_welcome_messages(bot_token: str, dry_run: bool = False, users: list[str] | None = None) -> None:
    """Send welcome DMs to users.

    Args:
        bot_token: Slack bot token
        dry_run: If True, only print what would be sent without actually sending
        users: List of user IDs to message (defaults to AUTHORIZED_USERS)
    """
    users = users or AUTHORIZED_USERS
    client = AsyncWebClient(token=bot_token)

    success_count = 0
    error_count = 0

    for user_id in users:
        try:
            if dry_run:
                print(f"[DRY RUN] Would send to {user_id}")
                success_count += 1
                continue

            # Open DM channel with user
            response = await client.conversations_open(users=[user_id])
            channel_id = response["channel"]["id"]

            # Send welcome message
            await client.chat_postMessage(
                channel=channel_id,
                text=WELCOME_MESSAGE,
                mrkdwn=True,
            )

            print(f"[OK] Sent to {user_id}")
            success_count += 1

            # Rate limit: 1 message per second to be safe
            await asyncio.sleep(1)

        except SlackApiError as e:
            print(f"[ERROR] Failed for {user_id}: {e.response['error']}")
            error_count += 1
        except Exception as e:
            print(f"[ERROR] Failed for {user_id}: {e}")
            error_count += 1

    print(f"\nComplete: {success_count} sent, {error_count} errors")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send welcome messages to authorized AskSplunk users")
    parser.add_argument("--from-aws", action="store_true", help="Fetch bot token from AWS Secrets Manager")
    parser.add_argument("--aws-profile", default="campaign_prod_v7", help="AWS profile name (default: campaign_prod_v7)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without actually doing it")
    parser.add_argument("--skip-invite", action="store_true", help="Skip channel invitation, only send DMs")
    parser.add_argument("--invite-only", action="store_true", help="Only invite to channel, skip welcome DMs")
    parser.add_argument("--user", help="Target a specific user ID instead of all users")
    args = parser.parse_args()

    if args.from_aws:
        print(f"Fetching bot token from AWS Secrets Manager (profile: {args.aws_profile})...")
        bot_token = await get_bot_token_from_aws(profile=args.aws_profile)
    else:
        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        if not bot_token:
            print("Error: Set SLACK_BOT_TOKEN environment variable or use --from-aws")
            sys.exit(1)

    if args.dry_run:
        print("[DRY RUN MODE - no actions will be taken]\n")

    # Determine target users
    target_users = [args.user] if args.user else AUTHORIZED_USERS

    # Step 1: Invite users to #asksplunk channel
    if not args.skip_invite:
        print(f"Inviting {len(target_users)} user(s) to #asksplunk...")
        await invite_users_to_channel(bot_token, dry_run=args.dry_run, users=target_users)

    # Step 2: Send welcome DMs
    if not args.invite_only:
        print(f"Sending welcome messages to {len(target_users)} user(s)...")
        await send_welcome_messages(bot_token, dry_run=args.dry_run, users=target_users)


if __name__ == "__main__":
    asyncio.run(main())
