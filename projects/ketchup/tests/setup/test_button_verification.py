"""Simple test to verify button creation logic."""

import os
import sys

# Add the project root to the path
sys.path.insert(0, "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup")

# Set up environment variables
os.environ["KETCHUP_TRUST_ENDORSEMENT_FEATURE"] = "true"
os.environ["KETCHUP_TRUST_ENDORSEMENT_GLOBAL"] = "true"

from packages.core.config.feature_flags import FeatureFlags

print("\n=== FEATURE FLAGS CHECK ===")
print(f"Trust endorsement enabled: {FeatureFlags.is_trust_endorsement_enabled()}")
print(f"Trust endorsement global: {FeatureFlags.is_trust_endorsement_global()}")

# Check the logic used in status_generator.py
trust_global_enabled = FeatureFlags.is_trust_endorsement_enabled()
trust_global_all = FeatureFlags.is_trust_endorsement_global()
trust_channel_enabled = False  # Simulating channel-specific disabled

print("\n=== BUTTON LOGIC CHECK ===")
print(f"Global feature enabled: {trust_global_enabled}")
print(f"Global for all channels: {trust_global_all}")
print(f"Channel specific enabled: {trust_channel_enabled}")

add_buttons = trust_global_enabled and (trust_global_all or trust_channel_enabled)
print(f"Will add buttons: {add_buttons}")

# Now simulate with channel-specific enabled
trust_channel_enabled = True
add_buttons_channel = trust_global_enabled and (
    trust_global_all or trust_channel_enabled
)
print(f"\nWith channel-specific enabled: {add_buttons_channel}")

# Now simulate with global disabled but feature enabled
os.environ["KETCHUP_TRUST_ENDORSEMENT_GLOBAL"] = "false"
trust_global_all = FeatureFlags.is_trust_endorsement_global()
add_buttons_partial = trust_global_enabled and (
    trust_global_all or trust_channel_enabled
)
print(f"\nWith global disabled but channel enabled: {add_buttons_partial}")

print("\n=== BLOCK CREATION ===")
if add_buttons:
    status_update_id = "12345_abcd"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test content"}}]

    # Add button block
    blocks.append(
        {
            "type": "actions",
            "block_id": "status_actions",
            "elements": [
                {
                    "style": "primary",
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✓ Trust this summary",
                    },
                    "action_id": "trust_status_update",
                    "value": status_update_id,
                }
            ],
        }
    )

    print("Initial blocks with trust button:")
    import json

    print(json.dumps(blocks, indent=2))

    # Simulate the update with flag button
    message_ts = "1234567890.123456"
    channel_id = "C123"

    updated_blocks = blocks.copy()
    for i, block in enumerate(updated_blocks):
        if block.get("block_id") == "status_actions":
            updated_blocks[i] = {
                "type": "actions",
                "block_id": "status_actions",
                "elements": [
                    {
                        "style": "primary",
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✓ Trust this summary",
                        },
                        "action_id": "trust_status_update",
                        "value": status_update_id,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🚩 Flag for review",
                        },
                        "action_id": "flag_status_review",
                        "value": f"{channel_id}|{message_ts}|{status_update_id}",
                    },
                ],
            }
            break

    print("\nUpdated blocks with both buttons:")
    print(json.dumps(updated_blocks, indent=2))
