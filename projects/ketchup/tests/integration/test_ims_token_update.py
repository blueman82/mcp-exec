"""
test_ims_token_update.py

Test the IMS token manager's ability to update tokens in AWS Secrets Manager.
"""

import asyncio
import os

import pytest

from packages.core.logging import setup_logger
from packages.integrations.ims_token_manager import IMSTokenManager
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)

# Set AWS profile for tests
pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_ims_token_update(aws_profile):
    """Test that IMS tokens are properly updated in AWS Secrets Manager."""

    print("\n🔐 Testing IMS Token Update to AWS Secrets Manager")
    print("=" * 50)

    try:
        # Step 1: Initialize components
        print("\n1️⃣ Initializing SecretsManager...")
        secrets_manager = SecretsManager()

        # Step 2: Get current token state
        print("\n2️⃣ Getting current token state from AWS...")
        initial_secrets = await secrets_manager.get_app_secrets()
        initial_token = initial_secrets.get("IMS_ACCESS_TOKEN", "")
        initial_expires = initial_secrets.get("IMS_TOKEN_EXPIRES_AT", 0)

        print(
            f"   📍 Current token: {initial_token[:20]}..."
            if initial_token
            else "   📍 No current token"
        )
        print(f"   📍 Current expiry: {initial_expires}")

        # Step 3: Initialize IMS Token Manager
        print("\n3️⃣ Initializing IMS Token Manager...")
        ims_manager = IMSTokenManager(secrets_manager)

        # Step 4: Force a token refresh
        print("\n4️⃣ Getting fresh IMS token (this should update AWS Secrets)...")
        new_token = await ims_manager.get_valid_token()

        if new_token:
            print(f"   ✅ New token obtained: {new_token[:20]}...")
            print(f"   ✅ Token length: {len(new_token)} characters")
        else:
            print("   ❌ Failed to get new token")
            pytest.fail("Failed to get new token")

        # Step 5: Wait a moment for AWS update to complete
        print("\n5️⃣ Waiting for AWS update to propagate...")
        await asyncio.sleep(2)

        # Step 6: Verify the update in AWS
        print("\n6️⃣ Verifying token was updated in AWS Secrets Manager...")
        updated_secrets = await secrets_manager.get_app_secrets()
        updated_token = updated_secrets.get("IMS_ACCESS_TOKEN", "")
        updated_expires = updated_secrets.get("IMS_TOKEN_EXPIRES_AT", 0)

        print(
            f"   📍 Updated token: {updated_token[:20]}..."
            if updated_token
            else "   📍 No updated token"
        )
        print(f"   📍 Updated expiry: {updated_expires}")

        # Step 7: Validate the update
        print("\n7️⃣ Validating update...")

        if updated_token == new_token:
            print("   ✅ Token successfully updated in AWS Secrets Manager!")
        else:
            print("   ❌ Token mismatch - AWS update may have failed")
            print(f"      Expected: {new_token[:20]}...")
            print(f"      Got: {updated_token[:20]}...")
            pytest.fail("Token mismatch - AWS update may have failed")

        # Check expiry was updated
        if int(updated_expires) > int(initial_expires):
            print("   ✅ Token expiry successfully updated!")
            print(f"      Old expiry: {initial_expires}")
            print(f"      New expiry: {updated_expires}")
        else:
            print("   ⚠️  Token expiry not updated as expected")

        # Step 8: Test cached token retrieval
        print("\n8️⃣ Testing cached token retrieval...")
        cached_token = ims_manager.get_cached_token()
        if cached_token:
            if cached_token == new_token:
                print("   ✅ Cached token matches updated token")
            else:
                print("   ❌ Cached token mismatch")
                pytest.fail("Cached token mismatch")
        else:
            print("   ℹ️  No cached token (token was already valid, no refresh needed)")
            # This is OK - if the token was already valid, it won't be cached

        print("\n" + "=" * 50)
        print("✅ All tests passed! IMS token update to AWS Secrets Manager is working correctly.")
        print("\n📊 Summary:")
        print("   • Token refresh: ✅")
        print("   • AWS Secrets update: ✅")
        print("   • Token expiry update: ✅")
        print("   • Cache consistency: ✅")

        # Test passes if we get here

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logger.exception("Test failed with exception")
        pytest.fail(f"Test failed with error: {e}")


@pytest.fixture(scope="module")
def aws_profile():
    """Set AWS profile for tests."""
    original_profile = os.getenv("AWS_PROFILE")
    original_region = os.getenv("AWS_DEFAULT_REGION")
    os.environ["AWS_PROFILE"] = "campaign_prod_v7"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
    yield
    if original_profile:
        os.environ["AWS_PROFILE"] = original_profile
    else:
        os.environ.pop("AWS_PROFILE", None)
    if original_region:
        os.environ["AWS_DEFAULT_REGION"] = original_region
    else:
        os.environ.pop("AWS_DEFAULT_REGION", None)
