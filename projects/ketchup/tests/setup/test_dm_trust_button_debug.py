#!/usr/bin/env python
"""
Debug test for DM trust button issue.

This test simulates:
1. User runs /ketchup status in a DM (D0840EX80R5)
2. Command execution record is stored
3. Trust button is clicked
4. System tries to find the command execution record
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.interactive_elements.trust_endorsement_handler import (
    TrustEndorsementHandler,
)

logger = setup_logger(__name__)


async def debug_dm_trust_button():
    """Debug the DM trust button issue."""

    # Setup
    dm_channel_id = "D0840EX80R5"  # The DM channel where command was executed

    # Initialize stores
    from packages.db.config.dynamodb_config import DynamoDBConfig
    from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

    config = DynamoDBConfig()
    client = DynamoDBAsyncClient(config)
    db_store = DynamoDBStore(client, config.get_table_name())

    # Generate command execution ID like the real system does
    timestamp = int(datetime.now(timezone.utc).timestamp())
    unique_suffix = str(uuid.uuid4())[:8]
    command_execution_id = f"{timestamp}_{unique_suffix}"

    logger.info("\n" + "=" * 80)
    logger.info("Testing DM Trust Button Issue")
    logger.info(f"DM Channel: {dm_channel_id}")
    logger.info(f"Command Execution ID: {command_execution_id}")
    logger.info("=" * 80 + "\n")

    # Step 1: Store command execution (simulating what happens when /ketchup status is run)
    logger.info("Step 1: Storing command execution record...")

    # Extract timestamp and uuid from command_execution_id
    ts, uuid_part = command_execution_id.split("_")

    # Store in format: CHANNEL#{channel_id} / COMMAND#{timestamp}#{uuid}
    sk_value = f"COMMAND#{ts}#{uuid_part}"
    command_item = {
        "PK": {"S": f"CHANNEL#{dm_channel_id}"},
        "SK": {"S": sk_value},
        "command_execution_id": {"S": command_execution_id},
        "command_type": {"S": "status"},
        "command_output": {"S": "Test status output"},
        "channel_id": {"S": dm_channel_id},
        "timestamp": {"N": str(ts)},
        "created_at": {"S": datetime.now(timezone.utc).isoformat()},
        "trusted_by": {"L": []},
        "trust_count": {"N": "0"},
    }

    logger.info(f"Storing with PK: CHANNEL#{dm_channel_id}")
    logger.info(f"Storing with SK: {sk_value}")

    try:
        await db_store.client.put_item(
            table_name=db_store.table_name, item=command_item
        )
        logger.info("✅ Command execution record stored successfully")
    except Exception as e:
        logger.error(f"❌ Failed to store command execution: {e}")
        return

    # Step 2: Try to retrieve it like the trust handler does
    logger.info(
        "\nStep 2: Attempting to retrieve command execution (simulating trust button click)..."
    )

    # Method 1: Direct lookup (what the trust handler tries first)
    logger.info("\nMethod 1: Direct lookup...")
    try:
        response = await db_store.client.get_item(
            table_name=db_store.table_name,
            key={"PK": {"S": f"CHANNEL#{dm_channel_id}"}, "SK": {"S": sk_value}},
        )

        if "Item" in response:
            logger.info(
                f"✅ Direct lookup successful! Found item: {response['Item'].get('command_execution_id')}"
            )
        else:
            logger.error("❌ Direct lookup failed - no item found")
    except Exception as e:
        logger.error(f"❌ Direct lookup error: {e}")

    # Method 2: Scan (what the trust handler falls back to)
    logger.info("\nMethod 2: Scan for command execution...")
    try:
        # Try the scan method the trust handler uses
        response = await db_store.client.scan(
            table_name=db_store.table_name,
            filter_expression="SK = :sk",
            expression_attribute_values={":sk": sk_value},
        )

        count = len(response.get("Items", []))
        logger.info(f"Scan found {count} items")

        if count > 0:
            item = response["Items"][0]
            logger.info(
                f"✅ Scan successful! Found item with channel_id: {item.get('channel_id')}"
            )
        else:
            logger.error("❌ Scan failed - no items found")

    except Exception as e:
        logger.error(f"❌ Scan error: {e}")

    # Step 3: Check what's actually in the database
    logger.info("\nStep 3: Checking what's actually stored in DynamoDB...")
    try:
        # Query by PK to see all items for this channel
        response = await db_store.client.query(
            table_name=db_store.table_name,
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": f"CHANNEL#{dm_channel_id}"},
        )

        items = response.get("Items", [])
        logger.info(f"Found {len(items)} items for channel {dm_channel_id}")

        for item in items:
            if "COMMAND#" in item.get("SK", ""):
                logger.info(
                    f"  - Command: SK={item.get('SK')}, ID={item.get('command_execution_id')}"
                )

    except Exception as e:
        logger.error(f"❌ Query error: {e}")

    # Step 4: Test with the actual trust handler
    logger.info("\nStep 4: Testing with actual TrustEndorsementHandler...")

    # Mock the necessary dependencies
    class MockPostingHandler:
        async def update_message(self, *args, **kwargs):
            pass

    class MockSecretsManager:
        async def get_slack_api_token_async(self):
            return "mock-token"

    trust_handler = TrustEndorsementHandler(
        posting_handler=MockPostingHandler(),
        db_store=db_store,
        secrets_manager=MockSecretsManager(),
    )

    # Try to find the command execution channel
    found_channel = await trust_handler._find_command_execution_channel(
        command_execution_id
    )

    if found_channel:
        logger.info(f"✅ Trust handler found channel: {found_channel}")
    else:
        logger.error("❌ Trust handler could not find command execution channel")

    # Cleanup - remove test data
    logger.info("\nStep 5: Cleaning up test data...")
    try:
        await db_store.client.delete_item(
            table_name=db_store.table_name,
            key={"PK": {"S": f"CHANNEL#{dm_channel_id}"}, "SK": {"S": sk_value}},
        )
        logger.info("✅ Test data cleaned up")
    except Exception as e:
        logger.warning(f"Could not clean up test data: {e}")

    logger.info("\n" + "=" * 80)
    logger.info("Debug test completed")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(debug_dm_trust_button())
