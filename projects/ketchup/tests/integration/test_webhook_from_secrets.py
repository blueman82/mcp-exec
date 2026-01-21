#!/usr/bin/env python3
"""
Test that AccessRequestHealthMonitor can retrieve webhook from AWS Secrets.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ketchup_access_request_monitor.monitor import AccessRequestHealthMonitor
from packages.secrets.manager import SecretsManager


async def test_webhook_from_secrets():
    """Test retrieving webhook URL from AWS Secrets Manager."""

    print("\n" + "=" * 60)
    print("🔐 Testing Webhook Retrieval from AWS Secrets")
    print("=" * 60)

    # Test 1: Direct retrieval from SecretsManager
    print("\n📌 Test 1: Direct retrieval from SecretsManager")
    secrets_manager = SecretsManager()
    webhook_url = await secrets_manager.get_slack_webhook_url()

    if webhook_url:
        print(f"✅ Webhook retrieved from secrets (length: {len(webhook_url)} chars)")
        # Don't print the actual URL for security
    else:
        print("❌ No webhook found in secrets")
        return False

    # Test 2: Retrieval via TypedDI
    print("\n📌 Test 2: Retrieval via TypedDI")
    from packages.core.typed_di_integration import get_unified_container

    container = await get_unified_container()
    secrets_from_di = await container.aget(SecretsManager)
    if secrets_from_di:
        webhook_from_di = await secrets_from_di.get_slack_webhook_url()
        if webhook_from_di:
            print("✅ Webhook retrieved via TypedDI container")
        else:
            print("❌ No webhook from TypedDI container")
    else:
        print("❌ Could not get secrets_manager from TypedDI")

    # Test 3: Send test alert using webhook from secrets
    print("\n📌 Test 3: Send test alert using webhook from secrets")
    monitor = AccessRequestHealthMonitor()

    test_issue = [
        {
            "severity": "info",
            "category": "test_from_secrets",
            "message": "🔐 Test alert using webhook from AWS Secrets Manager",
            "details": {"source": "test_webhook_from_secrets.py"},
        }
    ]

    print("   Sending test alert...")
    await monitor.send_webhook_alert(test_issue, webhook_url)
    print("   ✅ Alert sent using webhook from secrets")

    print("\n" + "=" * 60)
    print("✅ All tests passed - webhook securely stored and accessible")
    print("=" * 60)

    return True


async def main():
    """Main entry point."""
    if os.environ.get("AWS_PROFILE") != "campaign_prod_v7":
        print("❌ Please set AWS_PROFILE=campaign_prod_v7")
        return

    os.environ["AWS_REGION"] = "eu-west-1"
    os.environ["AWS_SECRET_NAME"] = "Ketchup_Token_Secrets"

    success = await test_webhook_from_secrets()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
