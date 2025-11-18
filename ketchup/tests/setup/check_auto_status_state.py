#!/usr/bin/env python3
"""Check the current state of all auto-status enabled channels after timestamp reset."""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Set AWS environment variables
os.environ["AWS_PROFILE"] = "campaign_prod_v7"
os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"

# Add parent directories to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import aioboto3

from packages.core.config import get_config
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore


async def check_auto_status_channels():
    """Check all auto-status enabled channels."""
    config = get_config()

    # Create aioboto3 session and DynamoDB client
    session = aioboto3.Session()
    async with session.resource("dynamodb", region_name=config.AWS_REGION) as dynamodb:
        table = await dynamodb.Table(config.DYNAMODB_TABLE)

        # Create DynamoDB async client wrapper
        dynamodb_client = DynamoDBAsyncClient(table)

        # Create stores
        db_store = DynamoDBStore(
            dynamodb_client=dynamodb_client, table_name=config.DYNAMODB_TABLE
        )

        user_store = UserStore(db_store)

        # List of channels to check (from the user's request)
        channels_to_check = [
            "C093NECRX98",
            "C094LKK783V",
            "C093030809M",
            "C091GU7LT6J",
            "C09552K6KND",
            "C094TF1L76C",
            "C094JHLSQ9K",
            "C094KP1UYSX",
            "C094PDCAK46",
            "C0940PJQKH9",
            "C094DQY7HLH",
            "C092W1ZPWUB",
            "C0945Q2AS8Z",
            "C094BNAUTDJ",
            "C094DHHT3H8",
            "C0940M1FBUJ",
            "C094715NTDL",
            "C093NN1MEVC",
        ]

        workspace_id = "T0910LX2G72"
        reset_timestamp = 1751725977
        current_time = datetime.now()
        current_timestamp = int(current_time.timestamp())

        print(
            f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (timestamp: {current_timestamp})"
        )
        print(
            f"Reset timestamp: {reset_timestamp} ({datetime.fromtimestamp(reset_timestamp).strftime('%Y-%m-%d %H:%M:%S')})"
        )
        print("=" * 120)

        # Get all auto-status enabled channels
        print("FETCHING ALL AUTO-STATUS ENABLED CHANNELS...")
        all_channels = await user_store.get_auto_status_enabled_channels(workspace_id)
        print(f"Found {len(all_channels)} auto-status enabled channels")
        print()

        # Check provided channels
        print("CHECKING PROVIDED CHANNELS:")
        print("-" * 120)

        results = []
        matched_count = 0
        overdue_count = 0

        for channel_id in channels_to_check:
            try:
                features = await user_store.get_channel_features(
                    workspace_id, channel_id
                )

                if features and features.get("auto_status", {}).get("enabled"):
                    auto_status = features["auto_status"]
                    last_run = auto_status.get("last_run", 0)
                    last_message_ts = auto_status.get("last_message_ts", 0)

                    # Calculate next expected update
                    if last_run:
                        next_update_dt = datetime.fromtimestamp(last_run) + timedelta(
                            minutes=55
                        )
                        time_until_next = next_update_dt - current_time
                        is_overdue = time_until_next.total_seconds() < 0
                    else:
                        next_update_dt = None
                        time_until_next = None
                        is_overdue = False

                    matches_reset = last_run == reset_timestamp
                    if matches_reset:
                        matched_count += 1
                    if is_overdue:
                        overdue_count += 1

                    result = {
                        "channel_id": channel_id,
                        "last_run": last_run,
                        "last_message_ts": last_message_ts,
                        "matches_reset": matches_reset,
                        "is_overdue": is_overdue,
                    }

                    results.append(result)

                    print(f"Channel: {channel_id}")
                    print(
                        f"  Last run:     {last_run} ({datetime.fromtimestamp(last_run).strftime('%Y-%m-%d %H:%M:%S') if last_run else 'None'})"
                    )
                    print(
                        f"  Last message: {last_message_ts} ({datetime.fromtimestamp(last_message_ts).strftime('%Y-%m-%d %H:%M:%S') if last_message_ts else 'None'})"
                    )
                    print(f"  Matches reset: {'✓' if matches_reset else '✗'}")
                    if next_update_dt:
                        print(
                            f"  Next update:  {next_update_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        if is_overdue:
                            print(
                                f"  Status:       OVERDUE by {str(-time_until_next).split('.')[0]}"
                            )
                        else:
                            print(
                                f"  Status:       Due in {str(time_until_next).split('.')[0]}"
                            )
                    print("-" * 50)
                else:
                    print(f"Channel: {channel_id} - NOT ENABLED or NO FEATURES FOUND")
                    print("-" * 50)

            except Exception as e:
                print(f"Channel: {channel_id} - ERROR: {str(e)}")
                print("-" * 50)

        # Check all enabled channels
        print("\n\nALL AUTO-STATUS ENABLED CHANNELS:")
        print("=" * 120)

        all_channel_ids = [item["channel_id"] for item in all_channels]

        # Count additional channels
        additional_channels = [
            cid for cid in all_channel_ids if cid not in channels_to_check
        ]
        missing_channels = [
            cid for cid in channels_to_check if cid not in all_channel_ids
        ]

        print(f"Total enabled channels: {len(all_channels)}")
        print(f"Channels in provided list: {len(channels_to_check)}")
        print(
            f"Channels found in DB: {len([r for r in results if r['channel_id'] in all_channel_ids])}"
        )
        print(f"Additional channels in DB: {len(additional_channels)}")
        print(f"Missing from DB: {len(missing_channels)}")

        if additional_channels:
            print(f"\nAdditional channels not in provided list: {additional_channels}")
            # Check their status
            print("\nChecking additional channels:")
            for channel_id in additional_channels[:5]:  # Just check first 5
                try:
                    features = await user_store.get_channel_features(
                        workspace_id, channel_id
                    )
                    if features and features.get("auto_status", {}):
                        auto_status = features["auto_status"]
                        last_run = auto_status.get("last_run", 0)
                        print(
                            f"  - {channel_id}: last_run={last_run} ({datetime.fromtimestamp(last_run).strftime('%Y-%m-%d %H:%M:%S') if last_run else 'None'})"
                        )
                except Exception as e:
                    print(f"  - {channel_id}: ERROR - {str(e)}")

        if missing_channels:
            print(f"\nChannels missing from DB: {missing_channels}")

        # Summary
        print("\n\nSUMMARY:")
        print("=" * 120)
        print(
            f"Reset timestamp: {reset_timestamp} ({datetime.fromtimestamp(reset_timestamp).strftime('%Y-%m-%d %H:%M:%S')})"
        )
        print(
            f"Current time:    {current_timestamp} ({current_time.strftime('%Y-%m-%d %H:%M:%S')})"
        )
        print(
            f"Time since reset: {str(current_time - datetime.fromtimestamp(reset_timestamp)).split('.')[0]}"
        )
        print()
        print(f"Channels checked: {len(results)}")
        print(f"Channels matching reset timestamp: {matched_count}/{len(results)}")
        print(f"Channels overdue for update: {overdue_count}")

        not_matching = [r for r in results if not r["matches_reset"]]
        if not_matching:
            print(f"\nChannels NOT matching reset timestamp ({len(not_matching)}):")
            for r in not_matching:
                print(
                    f"  - {r['channel_id']}: last_run={r['last_run']} ({datetime.fromtimestamp(r['last_run']).strftime('%Y-%m-%d %H:%M:%S') if r['last_run'] else 'None'})"
                )

        overdue = [r for r in results if r.get("is_overdue")]
        if overdue:
            print(f"\nChannels OVERDUE for update ({len(overdue)}):")
            for r in overdue:
                print(f"  - {r['channel_id']}")

        # Calculate expected next run window
        print("\n\nNEXT UPDATE WINDOW:")
        print("=" * 120)
        reset_dt = datetime.fromtimestamp(reset_timestamp)
        next_window_start = reset_dt + timedelta(minutes=55)
        next_window_end = reset_dt + timedelta(minutes=60)  # 5 minute window
        print(
            f"Expected update window: {next_window_start.strftime('%Y-%m-%d %H:%M:%S')} to {next_window_end.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if current_time > next_window_end:
            print(
                f"WARNING: Update window has passed! Overdue by {str(current_time - next_window_end).split('.')[0]}"
            )
        elif current_time >= next_window_start:
            print("INFO: Currently in update window")
        else:
            print(
                f"INFO: Next update in {str(next_window_start - current_time).split('.')[0]}"
            )


if __name__ == "__main__":
    asyncio.run(check_auto_status_channels())
