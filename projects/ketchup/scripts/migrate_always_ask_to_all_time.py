#!/usr/bin/env python3
"""One-time migration: update users with time_window='always_ask' to 'all_time'.

The 'always_ask' option was never functional — it behaved identically to 'all_time'.
This script updates any DynamoDB records that still have it set.

Usage:
    # Dry run (default) — shows affected users without modifying anything
    AWS_PROFILE=campaign_prod_v7 python scripts/migrate_always_ask_to_all_time.py

    # Execute the migration
    AWS_PROFILE=campaign_prod_v7 python scripts/migrate_always_ask_to_all_time.py --execute
"""

import argparse
import sys

import boto3

TABLE_NAME = "ketchup_channel_information"
REGION = "eu-west-1"


def scan_always_ask_users(table):
    """Scan for USER# items where preferences.time_window = 'always_ask'."""
    users = []
    scan_kwargs = {
        "FilterExpression": "begins_with(PK, :pk_prefix) AND preferences.time_window = :tw",
        "ExpressionAttributeValues": {
            ":pk_prefix": "USER#",
            ":tw": "always_ask",
        },
        "ProjectionExpression": "PK, SK, preferences.time_window",
    }

    while True:
        response = table.scan(**scan_kwargs)
        users.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return users


def update_user(table, pk, sk):
    """Update a single user's time_window from 'always_ask' to 'all_time'."""
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET preferences.time_window = :tw",
        ConditionExpression="preferences.time_window = :old",
        ExpressionAttributeValues={
            ":tw": "all_time",
            ":old": "always_ask",
        },
    )


def main():
    parser = argparse.ArgumentParser(description="Migrate always_ask → all_time in DynamoDB")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the updates (default is dry-run)",
    )
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    print(f"Scanning {TABLE_NAME} for users with time_window='always_ask'...")
    users = scan_always_ask_users(table)

    if not users:
        print("No users found with time_window='always_ask'. Nothing to do.")
        return

    print(f"Found {len(users)} user(s):")
    for user in users:
        print(f"  {user['PK']}")

    if not args.execute:
        print("\nDry run — no changes made. Use --execute to apply updates.")
        return

    print(f"\nUpdating {len(users)} user(s)...")
    updated = 0
    for user in users:
        try:
            update_user(table, user["PK"], user["SK"])
            updated += 1
            print(f"  Updated {user['PK']}")
        except Exception as e:
            print(f"  FAILED {user['PK']}: {e}", file=sys.stderr)

    print(f"\nDone. Updated {updated}/{len(users)} users.")


if __name__ == "__main__":
    main()
