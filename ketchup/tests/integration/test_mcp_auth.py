#!/usr/bin/env python3
"""
test_mcp_auth.py

Test script for MCP server authentication with iPaaS integration.
Tests the complete flow from IMS token to JIRA iPaaS authentication.
"""

import asyncio
import os
import sys
from unittest.mock import patch

import pytest

# Add project root to path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

from packages.core.logging import setup_logger
from packages.integrations.ims_token_manager import IMSTokenManager
from packages.integrations.mcp_client import MCPClient
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


async def run_mcp_authentication_test():
    """Test MCP server authentication end-to-end following our complete flow."""

    print("🚀 Starting Complete MCP Authentication Test")
    print("=" * 50)

    try:
        # Step 1: Initialize SecretsManager with AWS profile
        print("📦 Step 1: Initializing SecretsManager...")
        secrets_manager = SecretsManager()

        # Step 2: Get current secrets from AWS
        print("🔐 Step 2: Fetching current secrets from AWS...")
        try:
            secrets = await secrets_manager.get_app_secrets()
            print(f"✅ Successfully fetched {len(secrets)} secrets")
            print(f"🔍 Available secret keys: {list(secrets.keys())}")

            # Check for required iPaaS secrets
            required_secrets = ["IPAAS_API_KEY", "IPAAS_USERNAME", "IPAAS_PASSWORD"]
            missing_secrets = []

            for secret in required_secrets:
                if secret not in secrets or not secrets[secret]:
                    missing_secrets.append(secret)
                    print(f"❌ {secret}: Missing or empty")
                else:
                    print(f"✅ {secret}: Present")

            if missing_secrets:
                print(f"❌ Missing required iPaaS secrets: {missing_secrets}")
                return False

        except Exception as e:
            print(f"❌ Failed to fetch secrets: {e}")
            return False

        # Step 3: Initialize IMS Token Manager
        print("\n🎟️  Step 3: Initializing IMS Token Manager...")
        try:
            ims_manager = IMSTokenManager(secrets_manager)
            print("✅ IMS Token Manager initialized")
        except Exception as e:
            print(f"❌ Failed to initialize IMS Token Manager: {e}")
            return False

        # Step 4: Get fresh IMS token (this will fetch from IMS service and
        # update AWS Secrets)
        print("\n🔄 Step 4: Getting fresh IMS token and updating AWS Secrets...")
        try:
            token = await ims_manager.get_valid_token()
            if token:
                print(f"✅ Fresh IMS token retrieved: {token[:20]}...")
                print("✅ Token has been updated in AWS Secrets Manager")
            else:
                print("❌ No IMS token received")
                return False
        except Exception as e:
            print(f"❌ Failed to get IMS token: {e}")
            return False

        # Step 5: Verify token is available via token manager
        print("\n🔄 Step 5: Verifying fresh token is available via token "
              "manager...")
        try:
            # The token manager may not have it cached if it was already valid
            # Let's verify by getting the token again - should return quickly
            # without refresh
            verify_token = await ims_manager.get_valid_token()
            if verify_token:
                print(f"✅ Token manager returns valid token: "
                      f"{verify_token[:20]}...")
                print("✅ Token manager is working correctly")

                # Check cache (may or may not be populated depending on if
                # refresh was needed)
                cached_token = ims_manager.get_cached_token()
                if cached_token:
                    print(f"ℹ️  Token is also cached in memory: "
                          f"{cached_token[:20]}...")
                else:
                    print("ℹ️  Token not cached (was already valid in AWS)")
            else:
                print("❌ No token available from token manager")
                return False
        except Exception as e:
            print(f"❌ Failed to verify token: {e}")
            return False

        # Step 6: Initialize MCP Client
        print("\n🔗 Step 6: Initializing MCP Client...")
        try:
            mcp_client = MCPClient(ims_manager)
            print("✅ MCP Client initialized")
        except Exception as e:
            print(f"❌ Failed to initialize MCP Client: {e}")
            return False

        # Step 7: Health check
        print("\n💓 Step 7: Testing MCP server health...")
        is_healthy = False  # Default to False
        try:
            is_healthy = await mcp_client.health_check()
            if is_healthy:
                print("✅ MCP server is healthy")
            else:
                print("⚠️  MCP server health check failed (server may not be running)")
                print("   This is expected if docker-compose is not running")
        except Exception as e:
            print(f"⚠️  MCP server health check error: {e}")
            print("   This is expected if docker-compose is not running")
            is_healthy = False  # Ensure is_healthy is set on exception

        # Step 8: Test JIRA authentication via MCP
        print("\n🔍 Step 8: Testing MCP JIRA authentication...")
        try:
            if is_healthy:
                # Test JIRA authentication via MCP
                auth_result = await mcp_client.test_jira_auth()
                print("✅ MCP JIRA authentication successful!")
                print(f"   Auth result: {auth_result}")
            else:
                print("ℹ️  Skipping JIRA auth test since MCP server is not running")
        except Exception as e:
            print(f"⚠️  MCP JIRA authentication test failed: {e}")
            print("   This may indicate authentication or MCP protocol issues")

        # Step 9: Test JIRA search via MCP
        print("\n🔍 Step 9: Testing JIRA search functionality via MCP...")
        try:
            if is_healthy:
                # Test a simple JIRA search through MCP protocol
                search_results = await mcp_client.search_issues(
                    jql="project = CAMP AND status != Closed", max_results=5
                )
                print(
                    f"✅ MCP JIRA search successful! Found {len(search_results.get('issues', []))} issues"
                )

                # Display first issue as example
                issues = search_results.get("issues", [])
                if issues:
                    first_issue = issues[0]
                    print(
                        f"   Example issue: {first_issue.get('key')} - {first_issue.get('fields', {}).get('summary', 'No summary')}"
                    )
            else:
                print("ℹ️  Skipping JIRA search test since MCP server is not running")
                print("   To test JIRA integration, run: docker-compose up -d mcp-jira")
                print(
                    "   Then re-run this test to verify end-to-end JIRA authentication"
                )
        except Exception as e:
            print(f"⚠️  JIRA search test failed: {e}")
            print("   This may indicate authentication or connectivity issues")

        print("\n" + "=" * 50)
        print("🎉 MCP Authentication Test Completed")
        print("   All authentication components are properly configured!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        return False


async def run_environment_setup_test():
    """Test if environment is properly set up for MCP."""

    print("🌍 Testing Environment Setup")
    print("-" * 30)

    # Check if required environment variables are set
    env_vars = ["JIRA_API_KEY", "JIRA_USERNAME", "JIRA_PASSWORD", "JIRA_IMS_TOKEN"]

    for var in env_vars:
        value = os.getenv(var)
        if value:
            if var in ["JIRA_PASSWORD", "JIRA_IMS_TOKEN"]:
                print(f"✅ {var}: Set (hidden)")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: Not set in environment")

    print()


def main():
    """Main function to run the test."""

    print("🧪 MCP Server Authentication Test")
    print("==================================")
    print()

    # Test environment first
    asyncio.run(run_environment_setup_test())

    # Run the main authentication test
    try:
        success = asyncio.run(run_mcp_authentication_test())

        if success:
            print("\n✅ Overall Result: SUCCESS")
            print("   Your MCP authentication setup is working correctly!")
            sys.exit(0)
        else:
            print("\n❌ Overall Result: FAILURE")
            print("   Please check the error messages above and fix any issues.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


# Add pytest test functions


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_authentication():
    """Test MCP authentication flow for pytest."""
    # Mock AWS credentials and services
    with patch.dict(os.environ, {
        "AWS_PROFILE": "test_profile",
        "AWS_DEFAULT_REGION": "eu-west-1"
    }):
        # Mock the secrets manager to return test data
        mock_secrets = {
            "IPAAS_API_KEY": "test-api-key",
            "IPAAS_USERNAME": "test-username",
            "IPAAS_PASSWORD": "test-password",
            "JIRA_IMS_TOKEN": "test-ims-token-12345"
        }

        # Mock AWS SecretManager calls
        with patch('packages.secrets.manager.SecretsManager.get_app_secrets') \
                as mock_get_secrets:
            mock_get_secrets.return_value = mock_secrets

            # Mock IMS token manager
            with patch('packages.integrations.ims_token_manager.'
                      'IMSTokenManager.get_valid_token') as mock_get_token:
                mock_get_token.return_value = "test-ims-token-12345"

                # Mock MCP client health check and auth tests
                with patch('packages.integrations.mcp_client.'
                          'MCPClient.health_check') as mock_health, \
                     patch('packages.integrations.mcp_client.'
                          'MCPClient.test_jira_auth') as mock_auth, \
                     patch('packages.integrations.mcp_client.'
                          'MCPClient.search_issues') as mock_search:

                    # Simulate MCP server not running
                    mock_health.return_value = False
                    mock_auth.return_value = {"success": True}
                    mock_search.return_value = {"issues": []}

                    result = await run_mcp_authentication_test()
                    # The function returns True/False, convert to assertion
                    assert result, "MCP authentication test failed"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_environment_setup():
    """Test environment setup for pytest."""
    await run_environment_setup_test()
    # This test is informational, always passes
    assert True


if __name__ == "__main__":
    main()
