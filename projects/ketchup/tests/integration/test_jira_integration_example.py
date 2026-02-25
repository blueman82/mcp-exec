#!/usr/bin/env python3
"""
Example JIRA integration test using the base integration test framework.

This demonstrates how easy it is to create new integration tests.
"""

import asyncio
import sys

from base_integration_test import BaseIntegrationTest, run_simple_integration_test


class JiraIntegrationTest(BaseIntegrationTest):
    """Integration test for JIRA functionality."""

    def __init__(self):
        super().__init__(
            test_name="jira_integration", env_vars={"KETCHUP_JIRA_MCP_FEATURE": "true"}
        )

    async def run_test(self) -> bool:
        """Test JIRA search and issue creation."""
        # Get required services
        mcp_client = self.get_service("mcp_client")
        self.get_service("secrets_manager")

        # Test 1: Search for issues
        self.logger.info("Testing JIRA search...")
        try:
            search_results = await mcp_client.call_tool(
                "search_jira_issues", {"jql": "project = CPGNCX AND created >= -7d"}
            )

            if search_results and "issues" in search_results:
                self.logger.info(f"Found {len(search_results['issues'])} issues")
            else:
                self.logger.error("No issues found or invalid response")
                return False

        except Exception as e:
            self.logger.error(f"JIRA search failed: {e}")
            return False

        # Test 2: Get issue details
        if search_results and search_results.get("issues"):
            issue_key = search_results["issues"][0]["key"]
            self.logger.info(f"Getting details for issue {issue_key}...")

            try:
                issue_details = await mcp_client.call_tool("get_issue", {"issueIdOrKey": issue_key})

                if issue_details:
                    self.logger.info(
                        f"Successfully retrieved issue: {issue_details.get('fields', {}).get('summary')}"
                    )
                else:
                    self.logger.error("Failed to get issue details")
                    return False

            except Exception as e:
                self.logger.error(f"Failed to get issue details: {e}")
                return False

        return True


# Alternative: Using the simple test approach
async def test_jira_search_simple(services, logger):
    """Simple JIRA search test using functional approach."""
    mcp_client = services["mcp_client"]

    logger.info("Performing simple JIRA search...")

    try:
        results = await mcp_client.call_tool(
            "search_jira_issues",
            {"jql": "project = CPGNCX ORDER BY created DESC", "maxResults": 5},
        )

        if results and "issues" in results:
            logger.info(f"✅ Found {len(results['issues'])} JIRA issues")
            for issue in results["issues"][:3]:  # Show first 3
                logger.info(f"  - {issue['key']}: {issue['fields']['summary']}")
            return True
        else:
            logger.error("❌ No issues found")
            return False

    except Exception as e:
        logger.error(f"❌ JIRA search failed: {e}")
        return False


async def main():
    """Run JIRA integration tests."""
    # Method 1: Using class-based approach
    print("Running class-based JIRA test...")
    test = JiraIntegrationTest()
    success1 = await test.execute()

    print("\n" + "=" * 60 + "\n")

    # Method 2: Using functional approach
    print("Running functional JIRA test...")
    success2 = await run_simple_integration_test(
        test_name="jira_search_simple",
        test_func=test_jira_search_simple,
        required_services=["mcp_client", "secrets_manager"],
        env_vars={"KETCHUP_JIRA_MCP_FEATURE": "true"},
    )

    return success1 and success2


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
