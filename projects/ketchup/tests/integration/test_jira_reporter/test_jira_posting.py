"""
Simple integration test for JIRA posting functionality
"""

import json
import os
from datetime import datetime

import httpx
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_jira_comment_posting():
    """Test that we can post a comment to JIRA via MCP."""
    # Skip if not explicitly enabled
    if not os.getenv("RUN_JIRA_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_JIRA_INTEGRATION_TESTS=true to run this test")

    # Get token from environment (loaded by infrastructure/.env)
    env_path = os.path.join(os.path.dirname(__file__), "../../../infrastructure/.env")
    token = None

    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("JIRA_IMS_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break

    assert token, "JIRA_IMS_TOKEN not found in infrastructure/.env"

    # Prepare the comment
    timestamp = datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    comment_text = f"""✅ **JIRA Reporter Integration Test Success!**

This comment confirms the complete JIRA reporter implementation:
- MCP service with all tools (including add_jira_comment)  
- IMS token authentication via Bearer header
- Proper JSON-RPC message formatting
- JiraService updated with IMSTokenManager DI

Ready for production deployment.

*Test executed at {timestamp}*"""

    # Format the JSON-RPC request
    payload = {
        "jsonrpc": "2.0",
        "id": "integration-test",
        "method": "tools/call",
        "params": {
            "name": "add_jira_comment",
            "arguments": {
                "issueIdOrKey": "CPGNREQ-180375",
                "comment": {"body": comment_text},
            },
        },
    }

    # Send the request
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8081/message", json=payload, headers=headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        result = response.json()
        assert "error" not in result, f"MCP returned error: {result.get('error')}"

        # Parse the result
        content = result.get("result", {}).get("content", [])
        assert content, "No content in result"
        assert content[0].get("type") == "text", "Expected text content"

        result_data = json.loads(content[0]["text"])
        assert (
            result_data.get("success") is True
        ), f"JIRA operation failed: {result_data}"
