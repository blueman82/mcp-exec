"""Debug test to verify status update button creation."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_unified_scheduler.services.status.generator import AutoStatusGenerator


@pytest.mark.asyncio
async def test_status_button_creation():
    """Test that status generator creates trust and flag buttons."""

    # Create mock dependencies
    db_store = MagicMock()
    db_store.trust_ops = MagicMock()
    db_store.trust_ops.store_status_update_metadata = AsyncMock()

    mcp_client = MagicMock()
    mcp_client.get_issue_comments = AsyncMock(return_value=[])

    secrets_manager = MagicMock()
    secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="U123BOT")

    slack_config = MagicMock()

    openai_handler = MagicMock()
    openai_handler.execute_prompt = AsyncMock(return_value="Test status content")

    channel_msg_ops = MagicMock()
    channel_msg_ops.get_api_base_url = AsyncMock(return_value="https://slack.com/api")
    channel_msg_ops.check_recent_thread_activity = AsyncMock(return_value=(False, "0", []))
    channel_msg_ops._make_api_request = AsyncMock(
        return_value={"body": json.dumps({"ok": True, "messages": []})}
    )
    channel_msg_ops.headers = {}

    channel_info_ops = MagicMock()

    posting_handler = MagicMock()
    posting_handler._slack_token = "xoxb-test"
    posting_handler._init_slack_token = AsyncMock()
    posting_handler._post_channel_message = AsyncMock(
        return_value={"ok": True, "ts": "1234567890.123456"}
    )
    posting_handler.update_message = AsyncMock(return_value={"ok": True})
    posting_handler._delete_message = AsyncMock(return_value={"ok": True})

    channel_operations = MagicMock()
    channel_operations.get_channel_details = AsyncMock(
        return_value={
            "channel_id": "C123",
            "channel_name": "test-channel",
            "jira_ticket": "TEST-123",
            "features": {"trust_endorsement_enabled": True},
        }
    )
    channel_operations.query_ops = MagicMock()
    channel_operations.query_ops.get_channel_details = AsyncMock(
        return_value={
            "channel_id": "C123",
            "auto_status_last_message_ts": "0",
            "auto_status_last_thread_ts": "0",
            "auto_status_last_jira_comment_ts": "0",
        }
    )
    channel_operations.update_channel_fields = AsyncMock()

    # Create generator
    generator = AutoStatusGenerator(
        db_store=db_store,
        mcp_client=mcp_client,
        secrets_manager=secrets_manager,
        slack_config=slack_config,
        openai_handler=openai_handler,
        channel_info_ops=channel_info_ops,
        channel_msg_ops=channel_msg_ops,
        posting_handler=posting_handler,
        channel_operations=channel_operations,
    )

    # Mock feature flags
    with patch("ketchup_unified_scheduler.services.status.generator.FeatureFlags") as MockFeatureFlags:
        MockFeatureFlags.is_trust_endorsement_enabled.return_value = True
        MockFeatureFlags.is_trust_endorsement_global.return_value = True

        # Mock MessagePreparer
        with patch("ketchup_unified_scheduler.services.status.generator.MessagePreparer") as MockPreparer:
            mock_preparer = MagicMock()
            mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                return_value=(
                    "Test messages",
                    {
                        "has_channel_messages": True,
                        "has_thread_activity": False,
                        "latest_ts": "1234567890.123456",
                    },
                )
            )
            MockPreparer.return_value = mock_preparer

            # Test the post method
            result = await generator._post_to_slack_public(
                channel_id="C123",
                content="Test status message",
                status_update_id="12345_abcd",
            )

            print("\n=== POST TO SLACK PUBLIC RESULTS ===")
            print(f"Result: {result}")
            print(f"Post channel message called: {posting_handler._post_channel_message.called}")

            if posting_handler._post_channel_message.called:
                call_args = posting_handler._post_channel_message.call_args
                print(f"\nCall args: {call_args}")

                if call_args and call_args[1].get("blocks"):
                    blocks = call_args[1]["blocks"]
                    print("\nBlocks passed to post_channel_message:")
                    print(json.dumps(blocks, indent=2))

                    # Check for action blocks
                    action_blocks = [b for b in blocks if b.get("type") == "actions"]
                    if action_blocks:
                        print(f"\n✅ Found {len(action_blocks)} action block(s)")
                        for block in action_blocks:
                            elements = block.get("elements", [])
                            print(f"  - Block has {len(elements)} element(s)")
                            for elem in elements:
                                print(f"    - {elem.get('text', {}).get('text', 'No text')}")
                    else:
                        print("\n❌ No action blocks found")

            print(f"\nUpdate message called: {posting_handler.update_message.called}")
            if posting_handler.update_message.called:
                update_call_args = posting_handler.update_message.call_args
                print(f"Update call args: {update_call_args}")

                if update_call_args and update_call_args[1].get("blocks"):
                    blocks = update_call_args[1]["blocks"]
                    print("\nBlocks passed to update_message:")
                    print(json.dumps(blocks, indent=2))

                    # Check for action blocks
                    action_blocks = [b for b in blocks if b.get("type") == "actions"]
                    if action_blocks:
                        print(f"\n✅ Found {len(action_blocks)} action block(s) in update")
                        for block in action_blocks:
                            elements = block.get("elements", [])
                            print(f"  - Block has {len(elements)} element(s)")
                            for elem in elements:
                                print(f"    - {elem.get('text', {}).get('text', 'No text')}")
                    else:
                        print("\n❌ No action blocks found in update")


if __name__ == "__main__":
    asyncio.run(test_status_button_creation())
