"""
Direct test of JIRA posting with token refresh, avoiding DI container complexity
"""

import os
from datetime import datetime

import httpx
import pytest

from jira_reporter.jira_service import JiraService
from packages.integrations.ims_token_manager import IMSTokenManager

# Direct imports to avoid DI container issues
from packages.secrets.manager import SecretsManager


@pytest.mark.asyncio
@pytest.mark.integration
async def test_jira_with_direct_token_refresh():
    """Test JIRA posting by directly using IMSTokenManager for fresh tokens."""
    if not os.getenv("RUN_JIRA_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_JIRA_INTEGRATION_TESTS=true to run this test")

    # Create SecretsManager directly
    secrets_manager = SecretsManager()

    # Create IMSTokenManager directly
    ims_token_manager = IMSTokenManager(secrets_manager=secrets_manager)

    # Get fresh token
    print("Getting fresh IMS token...")
    try:
        fresh_token = await ims_token_manager.get_valid_token()
        print(f"✅ Got fresh token starting with: {fresh_token[:30]}...")
    except Exception as e:
        print(f"❌ Failed to get fresh token: {e}")
        pytest.fail(f"Could not get fresh IMS token: {e}")

    # Create JIRA service with dependencies
    jira_service = JiraService(
        secrets_manager=secrets_manager, ims_token_manager=ims_token_manager
    )

    # Override MCP base URL for testing
    jira_service.mcp_base_url = "http://localhost:8081"

    # Prepare comment
    timestamp = datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    comment_text = f"""✅ **JIRA Reporter Integration Success!**

This comment confirms the complete integration:
- Fresh IMS token obtained via IMSTokenManager
- Token refresh mechanism working correctly
- JiraService using dependency injection
- MCP service integration complete

The jira_reporter is ready for production deployment.

*Posted at {timestamp}*"""

    # Post comment
    print("Posting comment to CPGNREQ-180375...")
    success = await jira_service.post_comment_to_ticket(
        jira_ticket_id="CPGNREQ-180375", comment_text=comment_text
    )

    if success:
        print("✅ SUCCESS! Comment posted to JIRA ticket CPGNREQ-180375")
    else:
        pytest.fail("Failed to post comment to JIRA")

    assert success is True


@pytest.mark.asyncio
async def test_mcp_health_with_fresh_token():
    """Test MCP health check with fresh token."""
    if not os.getenv("RUN_JIRA_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_JIRA_INTEGRATION_TESTS=true to run this test")

    # Get fresh token
    secrets_manager = SecretsManager()
    ims_token_manager = IMSTokenManager(secrets_manager=secrets_manager)

    try:
        fresh_token = await ims_token_manager.get_valid_token()

        # Test MCP health
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8081/health",
                headers={"Authorization": f"Bearer {fresh_token}"},
            )

            assert response.status_code == 200
            print("✅ MCP health check passed with fresh token")

    except Exception as e:
        pytest.fail(f"Health check failed: {e}")
