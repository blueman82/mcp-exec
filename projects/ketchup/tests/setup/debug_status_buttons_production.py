"""Test status update button creation in production-like conditions."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add project to path
sys.path.insert(0, "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup")

# Set environment variables as they would be in production
os.environ["KETCHUP_TRUST_ENDORSEMENT_FEATURE"] = "true"
os.environ["KETCHUP_TRUST_ENDORSEMENT_GLOBAL"] = "true"


@pytest.mark.asyncio
async def test_status_generator_buttons():
    """Test that the status generator creates buttons correctly."""

    from ketchup_status_updater.status_generator import AutoStatusGenerator
    from packages.core.config.feature_flags import FeatureFlags

    print("\n=== PRODUCTION ENVIRONMENT SIMULATION ===")
    print(
        f"KETCHUP_TRUST_ENDORSEMENT_FEATURE: {os.environ.get('KETCHUP_TRUST_ENDORSEMENT_FEATURE')}"
    )
    print(f"KETCHUP_TRUST_ENDORSEMENT_GLOBAL: {os.environ.get('KETCHUP_TRUST_ENDORSEMENT_GLOBAL')}")
    print(f"Trust enabled: {FeatureFlags.is_trust_endorsement_enabled()}")
    print(f"Trust global: {FeatureFlags.is_trust_endorsement_global()}")

    # Create mocks
    db_store = MagicMock()
    db_store.trust_ops = MagicMock()
    db_store.trust_ops.store_status_update_metadata = AsyncMock()

    mcp_client = MagicMock()
    secrets_manager = MagicMock()
    slack_config = MagicMock()
    openai_handler = MagicMock()
    channel_msg_ops = MagicMock()
    channel_info_ops = MagicMock()

    posting_handler = MagicMock()
    posting_handler._slack_token = "xoxb-test"
    posting_handler._init_slack_token = AsyncMock()

    # Capture the blocks passed to _post_channel_message
    posted_blocks = []

    async def capture_post(channel_id, message, blocks=None):
        posted_blocks.extend(blocks or [])
        return {"ok": True, "ts": "1234567890.123456"}

    posting_handler._post_channel_message = capture_post

    # Capture blocks passed to update_message
    updated_blocks = []

    async def capture_update(channel_id, ts, message, blocks=None):
        updated_blocks.extend(blocks or [])
        return {"ok": True}

    posting_handler.update_message = capture_update
    posting_handler._delete_message = AsyncMock(return_value={"ok": True})

    channel_operations = MagicMock()
    channel_operations.get_channel_details = AsyncMock(
        return_value={
            "channel_id": "C123",
            "channel_name": "test-channel",
            "jira_ticket": "TEST-123",
            "features": {"trust_endorsement_enabled": True},  # Channel has trust enabled
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

    # Test _post_to_slack_public
    result = await generator._post_to_slack_public(
        channel_id="C123", content="Test status message", status_update_id="12345_abcd"
    )

    print("\n=== RESULTS ===")
    print(f"Post successful: {result.get('success')}")

    print(f"\nInitial post blocks ({len(posted_blocks)} blocks):")
    for i, block in enumerate(posted_blocks):
        print(f"  Block {i}: type={block.get('type')}")
        if block.get("type") == "actions":
            elements = block.get("elements", [])
            print(f"    - {len(elements)} element(s)")
            for elem in elements:
                print(
                    f"      - {elem.get('action_id')}: {elem.get('text', {}).get('text', 'No text')}"
                )

    print(f"\nUpdated blocks ({len(updated_blocks)} blocks):")
    for i, block in enumerate(updated_blocks):
        print(f"  Block {i}: type={block.get('type')}")
        if block.get("type") == "actions":
            elements = block.get("elements", [])
            print(f"    - {len(elements)} element(s)")
            for elem in elements:
                print(
                    f"      - {elem.get('action_id')}: {elem.get('text', {}).get('text', 'No text')}"
                )

    # Check if buttons were added
    initial_has_buttons = any(b.get("type") == "actions" for b in posted_blocks)
    updated_has_buttons = any(b.get("type") == "actions" for b in updated_blocks)

    print("\n=== SUMMARY ===")
    print(f"✅ Initial post has buttons: {initial_has_buttons}")
    print(f"✅ Updated message has buttons: {updated_has_buttons}")

    if initial_has_buttons:
        action_blocks = [b for b in posted_blocks if b.get("type") == "actions"]
        trust_found = any("trust_status_update" in str(b) for b in action_blocks)
        print(f"✅ Trust button found in initial post: {trust_found}")

    if updated_has_buttons:
        action_blocks = [b for b in updated_blocks if b.get("type") == "actions"]
        trust_found = any("trust_status_update" in str(b) for b in action_blocks)
        flag_found = any("flag_status_review" in str(b) for b in action_blocks)
        print(f"✅ Trust button found in update: {trust_found}")
        print(f"✅ Flag button found in update: {flag_found}")


if __name__ == "__main__":
    asyncio.run(test_status_generator_buttons())
