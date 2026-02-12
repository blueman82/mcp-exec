#!/usr/bin/env python3
"""Onboard users to AskSplunk: resolve emails, authorize, welcome DM, channel invite.

Reads AWS_PROFILE from environment (set via .env.test).

Usage:
    # Dry run (no changes)
    python scripts/send_welcome_messages.py --dry-run

    # Onboard new users (resolve + authorize + welcome + invite)
    python scripts/send_welcome_messages.py --new-users

    # Re-run for existing users only (invite + DM, no lookup)
    python scripts/send_welcome_messages.py
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

# #asksplunk_feedback channel
ASKSPLUNK_CHANNEL_ID = "C0AD4DRHHS8"

# Previously onboarded users (already authorized + messaged)
EXISTING_USERS = [
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

# New users to onboard (email, name) — resolved to IDs at runtime
NEW_USERS_BY_EMAIL = [
    ("vkaushik@adobe.com", "Varun Kaushik"),
    ("glo00004@adobe.com", "Rishabh Mittal"),
    ("glo11132@adobe.com", "Priya Saraswath"),
    ("glo14710@adobe.com", "Maninder Bhui"),
    ("glo30275@adobe.com", "Pradeep Kumar"),
    ("glo33465@adobe.com", "Akshit Mittal"),
    ("glo34567@adobe.com", "Rizwan Ali"),
    ("glo35713@adobe.com", "Priya Kumari"),
    ("glo67526@adobe.com", "Yadagiri Rao KP"),
    ("glo76617@adobe.com", "Sharavan Kushwaha"),
    ("glo80320@adobe.com", "Pranai Sure"),
    ("haseeb@adobe.com", "Md Haseeb"),
    ("kumarsachin@adobe.com", "Sachin Kumar"),
    ("mausams@adobe.com", "Mausam Singh"),
    ("mukesh@adobe.com", "Mukesh"),
    ("rohity@adobe.com", "Rohit Yadav"),
    ("shakuls@adobe.com", "Shakul Sharma"),
    ("shipsriv@adobe.com", "Shipra Srivastava"),
    ("vsajwan@adobe.com", "Vineet Sajwan"),
    ("yosharma@adobe.com", "Yogesh Sharma"),
    ("ajayt@adobe.com", "Ajay Tiwari"),
    ("alokuma@adobe.com", "Alok Kumar"),
    ("aniskuma@adobe.com", "Anish Kumar"),
    ("rahugup@adobe.com", "Rahul Gupta"),
    ("sanjeeku@adobe.com", "Sanjeev Kumar"),
    ("suhalder@adobe.com", "Suhasish Halder"),
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


def load_env():
    """Load .env.test from project root (same pattern as conftest.py)."""
    env_test = Path(__file__).parent.parent / ".env.test"
    if env_test.exists():
        with open(env_test) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


async def get_aws_session():
    """Create aioboto3 session using AWS_PROFILE from environment."""
    import aioboto3
    return aioboto3.Session()


async def get_bot_token_from_aws() -> str:
    """Fetch bot token from AWS Secrets Manager."""
    session = await get_aws_session()
    async with session.client("secretsmanager", region_name="eu-west-1") as client:
        response = await client.get_secret_value(SecretId="splunk-bot/slack-tokens")
        secret = json.loads(response["SecretString"])
        return secret["bot_token"]


async def resolve_emails_to_ids(
    client: AsyncWebClient,
    users: list[tuple[str, str]],
    dry_run: bool = False,
) -> list[tuple[str, str, str]]:
    """Resolve email addresses to Slack user IDs via users.lookupByEmail.

    Returns list of (email, name, slack_id) tuples for resolved users.
    """
    resolved = []
    not_found = []

    for email, name in users:
        try:
            if dry_run:
                print(f"  [DRY RUN] Would look up {email} ({name})")
                resolved.append((email, name, "DRY_RUN_ID"))
                continue

            response = await client.users_lookupByEmail(email=email)
            slack_id = response["user"]["id"]
            display = response["user"].get("real_name", name)
            print(f"  [OK] {email} -> {slack_id} ({display})")
            resolved.append((email, name, slack_id))
            await asyncio.sleep(0.3)

        except SlackApiError as e:
            if e.response["error"] == "users_not_found":
                print(f"  [NOT FOUND] {email} ({name})")
            else:
                print(f"  [ERROR] {email}: {e.response['error']}")
            not_found.append((email, name))

    print(f"\n  Resolved: {len(resolved)}/{len(users)} ({len(not_found)} not found)\n")
    return resolved


async def authorize_users(
    new_ids: list[str],
    dry_run: bool = False,
) -> None:
    """Add new user IDs to authorised_slack_user_ids in AWS Secrets Manager."""
    session = await get_aws_session()
    async with session.client("secretsmanager", region_name="eu-west-1") as client:
        # Fetch current secret
        response = await client.get_secret_value(SecretId="splunk-bot/slack-tokens")
        secret = json.loads(response["SecretString"])

        # Parse existing authorized list
        ids_json = secret.get("authorised_slack_user_ids", "[]")
        if isinstance(ids_json, str):
            existing_ids = json.loads(ids_json)
        else:
            existing_ids = ids_json

        # Merge — deduplicate, preserve order
        existing_set = set(existing_ids)
        added = [uid for uid in new_ids if uid not in existing_set]

        if not added:
            print("  [SKIP] All new IDs already authorized")
            return

        updated_ids = existing_ids + added

        if dry_run:
            print(f"  [DRY RUN] Would add {len(added)} IDs to authorised_slack_user_ids")
            print(f"  [DRY RUN] Current: {len(existing_ids)} -> Would be: {len(updated_ids)}")
            for uid in added:
                print(f"    + {uid}")
            return

        # Update secret
        secret["authorised_slack_user_ids"] = json.dumps(updated_ids)
        await client.put_secret_value(
            SecretId="splunk-bot/slack-tokens",
            SecretString=json.dumps(secret),
        )
        print(f"  [OK] Added {len(added)} IDs ({len(existing_ids)} -> {len(updated_ids)} total)")


async def invite_users_to_channel(
    client: AsyncWebClient,
    users: list[str],
    dry_run: bool = False,
) -> None:
    """Invite users to the #asksplunk_feedback channel."""
    # Ensure bot is in the channel first
    if not dry_run:
        try:
            await client.conversations_join(channel=ASKSPLUNK_CHANNEL_ID)
            print("  [OK] Bot joined channel")
        except SlackApiError as e:
            if e.response["error"] == "already_in_channel":
                print("  [OK] Bot already in channel")
            else:
                print(f"  [ERROR] Bot couldn't join channel: {e.response['error']}")
                return

    success_count = 0
    already_member = 0
    error_count = 0

    for user_id in users:
        try:
            if dry_run:
                print(f"  [DRY RUN] Would invite {user_id}")
                success_count += 1
                continue

            await client.conversations_invite(
                channel=ASKSPLUNK_CHANNEL_ID,
                users=[user_id],
            )
            print(f"  [OK] Invited {user_id}")
            success_count += 1
            await asyncio.sleep(0.5)

        except SlackApiError as e:
            if e.response["error"] == "already_in_channel":
                print(f"  [SKIP] {user_id} already in channel")
                already_member += 1
            else:
                print(f"  [ERROR] {user_id}: {e.response['error']}")
                error_count += 1

    print(f"\n  Invites: {success_count} new, {already_member} existing, {error_count} errors\n")


async def send_welcome_messages(
    client: AsyncWebClient,
    users: list[str],
    dry_run: bool = False,
) -> None:
    """Send welcome DMs to users."""
    success_count = 0
    error_count = 0

    for user_id in users:
        try:
            if dry_run:
                print(f"  [DRY RUN] Would DM {user_id}")
                success_count += 1
                continue

            response = await client.conversations_open(users=[user_id])
            channel_id = response["channel"]["id"]
            await client.chat_postMessage(
                channel=channel_id,
                text=WELCOME_MESSAGE,
                mrkdwn=True,
            )
            print(f"  [OK] Sent to {user_id}")
            success_count += 1
            await asyncio.sleep(1)

        except SlackApiError as e:
            print(f"  [ERROR] {user_id}: {e.response['error']}")
            error_count += 1

    print(f"\n  DMs: {success_count} sent, {error_count} errors")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Onboard users to AskSplunk: resolve, authorize, welcome, invite"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without doing it")
    parser.add_argument("--new-users", action="store_true", help="Onboard new users (resolve emails, authorize, welcome, invite)")
    parser.add_argument("--skip-invite", action="store_true", help="Skip channel invitation")
    parser.add_argument("--skip-welcome", action="store_true", help="Skip welcome DMs")
    parser.add_argument("--skip-authorize", action="store_true", help="Skip AWS Secrets Manager update")
    parser.add_argument("--resolve-only", action="store_true", help="Only resolve emails to IDs, no other actions")
    parser.add_argument("--user", help="Target a specific user ID (existing users mode)")
    args = parser.parse_args()

    load_env()
    print(f"Using AWS_PROFILE={os.environ.get('AWS_PROFILE', '(not set)')}")
    print("Fetching bot token from AWS Secrets Manager...")
    bot_token = await get_bot_token_from_aws()

    if args.dry_run:
        print("[DRY RUN MODE]\n")

    slack_client = AsyncWebClient(token=bot_token)

    if args.new_users or args.resolve_only:
        # --- New user onboarding flow ---
        print(f"Step 1: Resolving {len(NEW_USERS_BY_EMAIL)} emails to Slack IDs...")
        resolved = await resolve_emails_to_ids(slack_client, NEW_USERS_BY_EMAIL, dry_run=args.dry_run)

        if not resolved:
            print("No users resolved. Exiting.")
            sys.exit(1)

        if args.resolve_only:
            return

        new_ids = [slack_id for _, _, slack_id in resolved]

        if not args.skip_authorize:
            print("Step 2: Authorizing new users in AWS Secrets Manager...")
            await authorize_users(new_ids, dry_run=args.dry_run)
        else:
            print("Step 2: [SKIPPED] Authorization")

        if not args.skip_welcome:
            print(f"Step 3: Sending welcome DMs to {len(new_ids)} user(s)...")
            await send_welcome_messages(slack_client, new_ids, dry_run=args.dry_run)
        else:
            print("Step 3: [SKIPPED] Welcome DMs")

        if not args.skip_invite:
            print(f"Step 4: Inviting {len(new_ids)} user(s) to channel...")
            await invite_users_to_channel(slack_client, new_ids, dry_run=args.dry_run)
        else:
            print("Step 4: [SKIPPED] Channel invite")

    else:
        # --- Existing users mode (original behavior) ---
        target_users = [args.user] if args.user else EXISTING_USERS

        if not args.skip_invite:
            print(f"Inviting {len(target_users)} existing user(s) to channel...")
            await invite_users_to_channel(slack_client, target_users, dry_run=args.dry_run)

        if not args.skip_welcome:
            print(f"Sending welcome messages to {len(target_users)} existing user(s)...")
            await send_welcome_messages(slack_client, target_users, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
