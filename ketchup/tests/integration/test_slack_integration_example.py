#!/usr/bin/env python3
"""
Example Slack integration test using the base integration test framework.

Shows how to test Slack operations like message posting and channel info.
"""
import asyncio
import sys

from base_integration_test import run_simple_integration_test


async def test_slack_channel_operations(services, logger):
    """Test Slack channel information retrieval."""
    channel_ops = services["channel_operations"]
    info_ops = services["info_ops"]

    test_channel = "C094BNAUTDJ"  # test_acc_cso_2

    logger.info(f"Testing Slack channel operations on {test_channel}...")

    # Test 1: Get channel details from database
    logger.info("Getting channel details from database...")
    channel_config = await channel_ops.get_channel_details(test_channel)

    if channel_config:
        logger.info(
            f"✅ Found channel in database: {channel_config.get('channel_name')}"
        )
    else:
        logger.error("❌ Channel not found in database")
        return False

    # Test 2: Get channel info from Slack API
    logger.info("Getting channel info from Slack API...")
    try:
        channel_info = await info_ops.get_channel_info(test_channel)

        if channel_info:
            logger.info("✅ Retrieved channel info from Slack:")
            logger.info(f"  - Name: {channel_info.get('name')}")
            logger.info(f"  - Members: {channel_info.get('num_members', 0)}")
            logger.info(f"  - Created: {channel_info.get('created')}")
        else:
            logger.error("❌ Failed to get channel info from Slack")
            return False

    except Exception as e:
        logger.error(f"❌ Error getting channel info: {e}")
        return False

    return True


async def test_slack_message_fetching(services, logger):
    """Test fetching messages from a Slack channel."""
    msg_ops = services["msg_ops"]

    test_channel = "C094BNAUTDJ"  # test_acc_cso_2

    logger.info(f"Testing message fetching from {test_channel}...")

    try:
        # Fetch last 10 messages
        messages = await msg_ops.fetch_channel_messages(
            channel_id=test_channel, limit=10
        )

        if messages:
            logger.info(f"✅ Successfully fetched {len(messages)} messages")

            # Show first few messages (truncated)
            for i, msg in enumerate(messages[:3]):
                preview = msg[:100] + "..." if len(msg) > 100 else msg
                logger.info(f"  Message {i+1}: {preview}")
        else:
            logger.warning("⚠️ No messages found (channel might be empty)")
            # This is still a pass - channel might legitimately be empty

        return True

    except Exception as e:
        logger.error(f"❌ Error fetching messages: {e}")
        return False


async def test_slack_user_operations(services, logger):
    """Test Slack user operations."""
    user_ops = services["user_ops"]

    logger.info("Testing Slack user operations...")

    # Test getting bot user info
    try:
        bot_info = await user_ops.get_bot_info()

        if bot_info:
            logger.info("✅ Got bot info:")
            logger.info(f"  - Bot ID: {bot_info.get('bot_id')}")
            logger.info(f"  - User ID: {bot_info.get('user_id')}")
            logger.info(f"  - Name: {bot_info.get('name')}")
        else:
            logger.error("❌ Failed to get bot info")
            return False

    except Exception as e:
        logger.error(f"❌ Error getting bot info: {e}")
        return False

    return True


async def main():
    """Run all Slack integration tests."""

    # Common services needed for Slack tests
    slack_services = [
        "channel_operations",
        "info_ops",
        "msg_ops",
        "user_ops",
        "slack_posting",
        "slack_config",
    ]

    # Test 1: Channel operations
    success1 = await run_simple_integration_test(
        test_name="slack_channel_operations",
        test_func=test_slack_channel_operations,
        required_services=slack_services,
    )

    print("\n" + "=" * 60 + "\n")

    # Test 2: Message fetching
    success2 = await run_simple_integration_test(
        test_name="slack_message_fetching",
        test_func=test_slack_message_fetching,
        required_services=slack_services,
    )

    print("\n" + "=" * 60 + "\n")

    # Test 3: User operations
    success3 = await run_simple_integration_test(
        test_name="slack_user_operations",
        test_func=test_slack_user_operations,
        required_services=slack_services,
    )

    return success1 and success2 and success3


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
