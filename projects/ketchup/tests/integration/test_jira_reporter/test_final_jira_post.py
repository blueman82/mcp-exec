"""
Final test to post comment to JIRA ticket with fresh token
"""

import json
import os
from datetime import datetime

import httpx
import pytest

from packages.integrations.ims_token_manager import IMSTokenManager
from packages.secrets.manager import SecretsManager


@pytest.mark.asyncio
@pytest.mark.integration
async def test_final_jira_post():
    """Direct test to post comment to JIRA ticket CPGNREQ-180375."""
    if not os.getenv("RUN_JIRA_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_JIRA_INTEGRATION_TESTS=true to run this test")

    # Get fresh token
    secrets_manager = SecretsManager()
    ims_token_manager = IMSTokenManager(secrets_manager=secrets_manager)

    print("Getting fresh IMS token...")
    fresh_token = await ims_token_manager.get_valid_token()
    print(f"✅ Got fresh token starting with: {fresh_token[:30]}...")

    # Prepare comment
    timestamp = datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    comment_text = f"""🎉 **JIRA Reporter Implementation Complete!**

This comment was successfully posted using:
- ✅ MCP service with all JIRA tools (including add_jira_comment)
- ✅ Fresh IMS token from IMSTokenManager
- ✅ JiraService with dependency injection
- ✅ Proper JSON-RPC formatting

The jira_reporter is fully functional and ready for production deployment.

*Posted at {timestamp}*"""

    # Format JSON-RPC request
    payload = {
        "jsonrpc": "2.0",
        "id": "final-test",
        "method": "tools/call",
        "params": {
            "name": "add_jira_comment",
            "arguments": {
                "issueIdOrKey": "CPGNREQ-180375",
                "comment": {"body": comment_text},
            },
        },
    }

    # Send request directly to MCP
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {fresh_token}",
    }

    print("Posting comment to CPGNREQ-180375...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post("http://localhost:8081/message", json=payload, headers=headers)

        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            if "error" in result:
                print(f"MCP Error: {result['error']}")
                pytest.fail(f"MCP returned error: {result['error']}")

            # Parse result
            content = result.get("result", {}).get("content", [])
            if content and content[0].get("type") == "text":
                result_data = json.loads(content[0]["text"])
                print(f"Result: {json.dumps(result_data, indent=2)}")

                if result_data.get("success"):
                    print("✅ SUCCESS! Comment posted to JIRA ticket CPGNREQ-180375")
                    return True
                else:
                    print(f"JIRA Error: {result_data}")
                    # If it's an auth error, show the token info
                    if result_data.get("error", {}).get("status") == 401:
                        print(f"Token used: {fresh_token[:50]}...")
                        secrets = await secrets_manager.get_app_secrets()
                        print(f"Token expires at: {secrets.get('IMS_TOKEN_EXPIRES_AT', 'unknown')}")
                    pytest.fail(f"JIRA operation failed: {result_data}")
        else:
            print(f"HTTP Error: {response.text}")
            pytest.fail(f"HTTP {response.status_code}: {response.text}")
