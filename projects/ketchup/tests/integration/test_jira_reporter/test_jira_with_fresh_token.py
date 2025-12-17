"""
Test JIRA posting with fresh IMS token from token manager
"""

import os

# Import jira_service directly to test the real implementation
import sys
from datetime import datetime

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_jira_posting_with_fresh_token():
    """Test JIRA posting using fresh token from IMS token manager."""
    if not os.getenv("RUN_JIRA_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_JIRA_INTEGRATION_TESTS=true to run this test")

    # Import after skip check to avoid unnecessary imports
    from ketchup_unified_scheduler.services.jira_reporter.service import JiraService
    from packages.core.typed_di_integration import cleanup_container, get_container
    from packages.integrations.ims_token_manager import IMSTokenManager
    from packages.secrets.manager import SecretsManager

    try:
        logger.info("Initializing DI container...")
        container = await get_container()

        # Get services from container using TypedDI
        secrets_manager = await container.aget(SecretsManager)
        ims_token_manager = await container.aget(IMSTokenManager)

        logger.info("Getting fresh IMS token...")
        fresh_token = await ims_token_manager.get_valid_token()
        logger.info(f"Got token starting with: {fresh_token[:20]}...")

        # Create JIRA service with proper dependencies
        jira_service = JiraService(
            secrets_manager=secrets_manager, ims_token_manager=ims_token_manager
        )

        # Prepare comment
        timestamp = datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        comment_text = f"""✅ **JIRA Reporter Production-Ready Test**

This comment was posted using:
- Fresh IMS token from IMSTokenManager
- Proper DI container initialization
- JiraService with all dependencies

This confirms the jira_reporter will work correctly in production with automatic token refresh.

*Test executed at {timestamp}*"""

        logger.info("Posting comment to CPGNREQ-180375...")
        success = await jira_service.post_comment_to_ticket(
            jira_ticket_id="CPGNREQ-180375", comment_text=comment_text
        )

        assert success is True, "Failed to post comment to JIRA"
        logger.info("✅ Successfully posted comment to JIRA!")

    finally:
        await cleanup_container()


@pytest.mark.asyncio
async def test_mcp_with_fresh_token():
    """Test MCP directly with fresh token to isolate the issue."""
    if not os.getenv("RUN_JIRA_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_JIRA_INTEGRATION_TESTS=true to run this test")

    from packages.core.typed_di_integration import cleanup_container, get_container
    from packages.integrations.ims_token_manager import IMSTokenManager

    try:
        container = await get_container()
        ims_token_manager = await container.aget(IMSTokenManager)

        # Get fresh token
        fresh_token = await ims_token_manager.get_valid_token()

        # Test MCP directly
        payload = {
            "jsonrpc": "2.0",
            "id": "fresh-token-test",
            "method": "tools/call",
            "params": {
                "name": "search_jira_issues",
                "arguments": {"query": "key = CPGNREQ-180375", "max_results": 1},
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {fresh_token}",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8081/message", json=payload, headers=headers
            )

            assert response.status_code == 200
            result = response.json()
            assert "error" not in result

            logger.info("✅ MCP authentication working with fresh token!")

    finally:
        await cleanup_container()
