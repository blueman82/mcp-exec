#!/usr/bin/env python3
"""Send AskSplunk feedback survey to all authorized users via Slack DM.

Reads AWS_PROFILE from environment (set via .env.test).

Usage:
    # Dry run (no changes)
    python scripts/send_survey.py --survey-id survey_2026_q1 --dry-run

    # Send survey to all authorized users
    python scripts/send_survey.py --survey-id survey_2026_q1

    # Print aggregated results
    python scripts/send_survey.py --survey-id survey_2026_q1 --results
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from asksplunk.survey.formatter import format_survey_message, format_survey_results
from asksplunk.survey.manager import SurveyManager


def load_env() -> None:
    """Load .env.test from project root."""
    env_test = Path(__file__).parent.parent / ".env.test"
    if env_test.exists():
        with open(env_test) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


async def _get_slack_secret() -> dict:
    """Fetch slack-tokens secret from AWS Secrets Manager."""
    import aioboto3

    session = aioboto3.Session()
    async with session.client("secretsmanager", region_name="eu-west-1") as client:
        response = await client.get_secret_value(SecretId="splunk-bot/slack-tokens")
        return json.loads(response["SecretString"])


async def get_bot_token_from_aws() -> str:
    """Fetch bot token from AWS Secrets Manager."""
    return (await _get_slack_secret())["bot_token"]


async def get_authorized_user_ids() -> list[str]:
    """Fetch authorized user IDs from AWS Secrets Manager."""
    secret = await _get_slack_secret()
    ids_json = secret.get("authorised_slack_user_ids", "[]")
    return json.loads(ids_json) if isinstance(ids_json, str) else ids_json


async def send_surveys(
    slack_client: AsyncWebClient,
    survey_manager: SurveyManager,
    survey_id: str,
    user_ids: list[str],
    dry_run: bool = False,
) -> None:
    """Send survey DMs and create status records."""
    blocks = format_survey_message(survey_id)
    success_count = 0
    error_count = 0

    for user_id in user_ids:
        try:
            if dry_run:
                print(f"  [DRY RUN] Would DM {user_id} with survey {survey_id}")
                success_count += 1
                continue

            response = await slack_client.conversations_open(users=[user_id])
            channel_id = response["channel"]["id"]
            await slack_client.chat_postMessage(
                channel=channel_id,
                blocks=blocks,
                text="AskSplunk Feedback Survey",
            )
            await survey_manager.create_status(survey_id, user_id, channel_id)
            print(f"  [OK] Sent to {user_id}")
            success_count += 1
            await asyncio.sleep(1)

        except SlackApiError as e:
            print(f"  [ERROR] {user_id}: {e.response['error']}")
            error_count += 1

    print(f"\n  Surveys: {success_count} sent, {error_count} errors")


async def print_results(survey_manager: SurveyManager, survey_id: str) -> None:
    """Print aggregated survey results to stdout."""
    results = await survey_manager.get_results(survey_id)
    print(format_survey_results(results))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send AskSplunk feedback survey")
    parser.add_argument(
        "--survey-id", required=True, help="Survey identifier (e.g., survey_2026_q1)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would happen without doing it"
    )
    parser.add_argument(
        "--results", action="store_true", help="Print aggregated results instead of sending"
    )
    args = parser.parse_args()

    load_env()
    print(f"Using AWS_PROFILE={os.environ.get('AWS_PROFILE', '(not set)')}")

    async with SurveyManager() as survey_manager:
        if args.results:
            print(f"Fetching results for {args.survey_id}...\n")
            await print_results(survey_manager, args.survey_id)
            return

        print("Fetching bot token from AWS Secrets Manager...")
        bot_token = await get_bot_token_from_aws()

        if args.dry_run:
            print("[DRY RUN MODE]\n")

        slack_client = AsyncWebClient(token=bot_token)

        print("Fetching authorized user IDs...")
        user_ids = await get_authorized_user_ids()
        print(f"Found {len(user_ids)} authorized users\n")

        print(f"Sending survey {args.survey_id} to {len(user_ids)} user(s)...")
        await send_surveys(
            slack_client, survey_manager, args.survey_id, user_ids, dry_run=args.dry_run
        )


if __name__ == "__main__":
    asyncio.run(main())
