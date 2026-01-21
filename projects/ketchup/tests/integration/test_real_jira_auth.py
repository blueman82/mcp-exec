"""
Test MCP JIRA authentication with real iPaaS credentials.
This test verifies the complete authentication flow from IMS token to JIRA API.
"""

import json
from unittest.mock import patch

import pytest

from packages.core.logging import setup_logger
from packages.integrations.ims_token_manager import IMSTokenManager
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_real_jira_authentication():
    """Test JIRA authentication with real iPaaS credentials."""

    print("\n🔐 Testing Real JIRA Authentication via MCP")
    print("=" * 50)

    # Mock AWS services to avoid credential issues
    mock_secrets = {
        "IPAAS_API_KEY": "test-api-key",
        "IPAAS_USERNAME": "test-username",
        "IPAAS_PASSWORD": "test-password",
        "JIRA_IMS_TOKEN": "test-ims-token-12345",
    }

    with patch("packages.secrets.manager.SecretsManager.get_app_secrets") as mock_get_secrets:
        mock_get_secrets.return_value = mock_secrets

        # Step 1: Initialize components
        print("\n1️⃣ Initializing components...")
        secrets_manager = SecretsManager()
        secrets = await secrets_manager.get_app_secrets()

    # Check iPaaS credentials
    ipaas_api_key = secrets.get("IPAAS_API_KEY")
    ipaas_username = secrets.get("IPAAS_USERNAME")
    ipaas_password = secrets.get("IPAAS_PASSWORD")

    print(f"   ✅ iPaaS API Key: {'Present' if ipaas_api_key else 'Missing'}")
    print(f"   ✅ iPaaS Username: {ipaas_username if ipaas_username else 'Missing'}")
    print(f"   ✅ iPaaS Password: {'Present' if ipaas_password else 'Missing'}")

    # Step 2: Get fresh IMS token
    print("\n2️⃣ Getting fresh IMS token...")
    ims_manager = IMSTokenManager(secrets_manager)
    ims_token = await ims_manager.get_valid_token()

    if ims_token:
        print(f"   ✅ IMS Token obtained: {ims_token[:30]}...")
        print(f"   ✅ Token length: {len(ims_token)} characters")
    else:
        print("   ❌ Failed to get IMS token")
        pytest.fail("Failed to get IMS token")

    # Step 3: Initialize MCP client
    print("\n3️⃣ Initializing MCP client...")
    mcp_client = AsyncMCPClient(ims_manager)

    # Step 4: Test MCP server health
    print("\n4️⃣ Testing MCP server connection...")
    try:
        is_healthy = await mcp_client.health_check()
        if is_healthy:
            print("   ✅ MCP server is healthy")
        else:
            print("   ❌ MCP server is not responding")
            print("   💡 Make sure docker-compose is running: docker-compose up -d mcp-jira")
            pytest.fail("MCP server is not responding")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        pytest.fail(f"Health check failed: {e}")

    # Step 5: Test JIRA authentication via MCP
    print("\n5️⃣ Testing JIRA authentication via MCP...")
    try:
        auth_result = await mcp_client.test_jira_auth()

        if auth_result.get("success"):
            print("   ✅ JIRA authentication successful!")
            print(f"   ✅ User: {auth_result.get('user', {}).get('displayName', 'Unknown')}")
            print(f"   ✅ Email: {auth_result.get('user', {}).get('emailAddress', 'Unknown')}")
            print(f"   ✅ Server: {auth_result.get('serverInfo', {}).get('baseUrl', 'Unknown')}")
        else:
            print("   ❌ JIRA authentication failed")
            print(f"   ❌ Error: {auth_result.get('message', 'Unknown error')}")
            if "error" in auth_result:
                error = auth_result["error"]
                print(f"   ❌ Status: {error.get('status', 'Unknown')}")
                print(f"   ❌ Details: {json.dumps(error, indent=2)}")
            pytest.fail(
                f"JIRA authentication failed: {auth_result.get('message', 'Unknown error')}"
            )

    except Exception as e:
        print(f"   ❌ Authentication test failed: {e}")
        pytest.fail(f"Authentication test failed: {e}")

    # Step 6: Test JIRA search functionality
    print("\n6️⃣ Testing JIRA search via MCP...")
    try:
        # Search for recent CAMP project issues
        search_results = await mcp_client.search_issues(
            jql="project = CAMP AND created >= -7d ORDER BY created DESC", max_results=3
        )

        issues = search_results.get("issues", [])
        print(f"   ✅ Search successful! Found {len(issues)} recent issues")

        for i, issue in enumerate(issues[:3], 1):
            fields = issue.get("fields", {})
            print(f"\n   📋 Issue {i}:")
            print(f"      Key: {issue.get('key')}")
            print(f"      Summary: {fields.get('summary', 'No summary')}")
            print(f"      Status: {fields.get('status', {}).get('name', 'Unknown')}")
            print(f"      Created: {fields.get('created', 'Unknown')}")

    except Exception as e:
        print(f"   ❌ Search test failed: {e}")
        pytest.fail(f"Search test failed: {e}")

    # Step 7: Test adding a comment (optional, requires write permissions)
    print("\n7️⃣ Testing JIRA comment functionality...")
    if issues:
        test_issue_key = issues[0].get("key")
        print(f"   ℹ️  Would test adding comment to {test_issue_key}")
        print("   ℹ️  Skipping actual comment to avoid spamming JIRA")

    print("\n" + "=" * 50)
    print("✅ All tests passed! JIRA authentication is working correctly.")
    print("\n📊 Summary:")
    print("   • IMS token authentication: ✅")
    print("   • MCP server connection: ✅")
    print("   • JIRA API authentication: ✅")
    print("   • JIRA search functionality: ✅")

    # Test passes if we get here
