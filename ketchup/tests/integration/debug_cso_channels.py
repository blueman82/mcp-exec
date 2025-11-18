"""
Debug script to investigate CSO channel count discrepancy.

This script queries DynamoDB directly and shows exactly which channels
are being counted as "Currently Active CSO Channels".
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from packages.core.typed_di_integration import get_unified_container
from packages.db.operations.channel_operations import ChannelOperations
from packages.core.config.system_channels import get_excluded_channels


async def debug_cso_channels():
    """Query DynamoDB and show all CSO channels with details."""
    print("=" * 80)
    print("CSO Channel Count Debug Report")
    print("=" * 80)
    print()

    # Initialize container
    container = await get_unified_container()
    channel_ops = container.get(ChannelOperations)

    # Get all channels
    all_channels = await channel_ops.get_all_channel_details()
    print(f"📊 Total channels in DynamoDB: {len(all_channels)}")
    print()

    # Get exclusion list
    excluded_channels = get_excluded_channels()
    print(f"🚫 Excluded system channels: {excluded_channels}")
    print()

    # Filter for CSO channels (has product field)
    cso_channels = []
    for channel_id, details in all_channels.items():
        if details.get("product"):
            cso_channels.append(
                {
                    "channel_id": channel_id,
                    "name": details.get("name", "Unknown"),
                    "product": details.get("product"),
                    "archived": details.get("archived", False),
                    "excluded": channel_id in excluded_channels,
                }
            )

    print(f"📦 Total CSO channels (has product field): {len(cso_channels)}")
    print()

    # Split by exclusion status
    excluded_cso = [ch for ch in cso_channels if ch["excluded"]]
    non_excluded_cso = [ch for ch in cso_channels if not ch["excluded"]]

    if excluded_cso:
        print(f"🚫 EXCLUDED CSO channels ({len(excluded_cso)}):")
        for ch in excluded_cso:
            print(
                f"  - {ch['channel_id']} ({ch['name']}): {ch['product']}, archived={ch['archived']}"
            )
        print()

    # Split non-excluded by archived status
    currently_active = [ch for ch in non_excluded_cso if not ch["archived"]]
    archived = [ch for ch in non_excluded_cso if ch["archived"]]

    print(
        f"✅ CURRENTLY ACTIVE CSO channels (after exclusions): {len(currently_active)}"
    )
    for ch in currently_active:
        print(f"  - {ch['channel_id']} ({ch['name']}): {ch['product']}")
    print()

    # Count by product
    active_campaign = len(
        [ch for ch in currently_active if ch["product"] == "campaign"]
    )
    active_ajo = len([ch for ch in currently_active if ch["product"] == "ajo"])

    print("📈 Product Breakdown:")
    print(f"  - Campaign: {active_campaign}")
    print(f"  - AJO: {active_ajo}")
    print(f"  - TOTAL: {len(currently_active)}")
    print()

    if archived:
        print(f"📦 ARCHIVED CSO channels: {len(archived)}")
        for ch in archived:
            print(f"  - {ch['channel_id']} ({ch['name']}): {ch['product']}")
        print()

    # Verify expected counts
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    print("Expected from user: 4 Campaign, 2 AJO (total 6)")
    print(
        f"Current dashboard: {len(currently_active)} ({active_campaign} Campaign, {active_ajo} AJO)"
    )
    print()

    if len(currently_active) != 6 or active_campaign != 4 or active_ajo != 2:
        print("❌ DISCREPANCY DETECTED!")
        print()
        print("Possible causes:")
        print("1. A channel's archived status changed")
        print("2. A channel's product field changed")
        print("3. A new channel was added")
        print("4. A channel is missing from the exclusion list")
    else:
        print("✅ Counts match expected values")


if __name__ == "__main__":
    asyncio.run(debug_cso_channels())
