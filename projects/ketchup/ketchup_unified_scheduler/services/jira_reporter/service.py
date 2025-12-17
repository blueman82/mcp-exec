"""
service.py

Service for interacting with JIRA via MCP.
"""

import json
import os
from typing import Dict

import httpx

from packages.core.logging import setup_logger
from packages.core.typed_di_integration import get_unified_container
from packages.integrations.ims_token_manager import IMSTokenManager
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


def _get_orchestration_functions():
    """Lazy import to avoid circular dependency."""
    from ketchup_unified_scheduler.services.jira_reporter.orchestration import (
        process_channel as _process_channel,
        run_reporting_cycle as _run_reporting_cycle,
    )
    return _run_reporting_cycle, _process_channel


# Re-export orchestration functions for backward compatibility
from typing import Optional, Any, Dict
from packages.core.typed_di.registry import TypedServiceRegistry


async def run_reporting_cycle(
    container: Optional[TypedServiceRegistry] = None,
) -> None:
    """Run a single reporting cycle. Wrapper for backward compatibility."""
    _run_reporting_cycle, _ = _get_orchestration_functions()
    # If no container provided, create one here so tests can patch at this location
    if container is None:
        container = await get_unified_container()
    return await _run_reporting_cycle(container=container)


async def process_channel(
    channel_data: Dict[str, Any],
    report_generator: Any,
    jira_service: Any,
    jira_discovery: Any,
    dynamodb_store: Any,
    skip_activity_check: bool = False,
) -> bool:
    """Process a single channel. Wrapper for backward compatibility."""
    _, _process_channel = _get_orchestration_functions()
    return await _process_channel(
        channel_data=channel_data,
        report_generator=report_generator,
        jira_service=jira_service,
        jira_discovery=jira_discovery,
        dynamodb_store=dynamodb_store,
        skip_activity_check=skip_activity_check,
    )


class JiraService:
    """Service for posting reports to JIRA."""

    def __init__(self, secrets_manager: SecretsManager, ims_token_manager: IMSTokenManager):
        """
        Initialize the JIRA service.

        Args:
            secrets_manager: Pre-initialized SecretsManager
            ims_token_manager: Pre-initialized IMSTokenManager for authentication
        """
        self.secrets_manager = secrets_manager
        self.ims_token_manager = ims_token_manager
        self.mcp_base_url = os.environ.get("MCP_BASE_URL", "http://mcp-jira:8081")

    async def post_comment_to_ticket(self, jira_ticket_id: str, comment_text: str) -> bool:
        """
        Post a comment to a JIRA ticket.

        Args:
            jira_ticket_id: The JIRA ticket ID (e.g., CPGNREQ-12345)
            comment_text: The text of the comment to post

        Returns:
            True if comment was posted successfully, False otherwise
        """
        try:
            # Normalize the ticket ID
            ticket_id = jira_ticket_id.strip()
            if not ticket_id:
                logger.error("Empty JIRA ticket ID provided")
                return False

            # Remove URL parts if present
            if "/" in ticket_id:
                ticket_id = ticket_id.split("/")[-1]

            # Validate ticket exists
            if not await self._validate_ticket_exists(ticket_id):
                logger.error(f"JIRA ticket {ticket_id} not found or not accessible")
                return False

            # Format the JSON-RPC request for MCP
            payload = {
                "jsonrpc": "2.0",
                "id": f"jira-reporter-{ticket_id}",
                "method": "tools/call",
                "params": {
                    "name": "add_jira_comment",
                    "arguments": {"issueIdOrKey": ticket_id, "comment": {"body": comment_text}},
                },
            }

            # Post to MCP JIRA
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_base_url}/message", json=payload, headers=await self._get_headers()
                )

                if response.status_code != 200:
                    logger.error(
                        f"Failed to post comment to JIRA ticket {ticket_id}. "
                        f"Status: {response.status_code}, Response: {response.text}"
                    )
                    return False

                logger.info(f"Successfully posted comment to JIRA ticket {ticket_id}")
                return True

        except Exception as e:
            logger.error(f"Error posting comment to JIRA: {str(e)}")
            return False

    async def _validate_ticket_exists(self, ticket_id: str) -> bool:
        """Validate that the ticket exists and is accessible."""
        try:
            # Use search to validate ticket exists
            payload = {
                "jsonrpc": "2.0",
                "id": f"validate-{ticket_id}",
                "method": "tools/call",
                "params": {
                    "name": "search_jira_issues",
                    "arguments": {"jql": f"key = {ticket_id}", "maxResults": 1},
                },
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.mcp_base_url}/message", json=payload, headers=await self._get_headers()
                )

                if response.status_code != 200:
                    return False

                # Check if we got a result
                try:
                    result = response.json()
                    if result.get("result", {}).get("content"):
                        content = json.loads(result["result"]["content"][0]["text"])
                        return content.get("total", 0) > 0
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

                return False

        except Exception as e:
            logger.error(f"Error validating ticket {ticket_id}: {str(e)}")
            return False

    async def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for MCP JIRA."""
        # Get a valid IMS token for authentication
        token = await self.ims_token_manager.get_valid_token()

        return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
