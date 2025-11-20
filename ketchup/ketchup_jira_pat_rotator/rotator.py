#!/usr/bin/env python3
"""
PAT rotation orchestrator that coordinates the full rotation flow.

Orchestrates:
1. Check expiry (monitor)
2. Create new PAT (call MCP)
3. Validate new PAT works (call MCP)
4. Update secrets (AWS Secrets Manager)
5. Revoke old PAT (call MCP)
6. Alert on Slack (success/failure)

Runs as singleton service on prod1 only - no distributed locking needed.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class SecretsManager:
    """Manages AWS Secrets Manager operations for PAT storage."""

    def __init__(self):
        """Initialize secrets manager."""
        import boto3
        self.client = boto3.client("secretsmanager")
        # CRITICAL: Use correct secret name matching AWS and env-aws.ts
        self.secret_name = "Ketchup_Token_Secrets"

    async def get_current_pat(self) -> Dict[str, str]:
        """
        Get current PAT from AWS Secrets Manager.

        Returns:
            Dictionary containing ketchup_jira_pat, ketchup_jira_pat_id, ketchup_jira_pat_expiry
        """
        try:
            response = self.client.get_secret_value(SecretId=self.secret_name)
            secret_string = response.get("SecretString")

            if not secret_string:
                logger.warning("No secret found")
                return {}

            try:
                secret_dict = json.loads(secret_string)
                # Return the full secret dict to preserve all fields
                return secret_dict
            except json.JSONDecodeError:
                logger.error("Failed to parse secret as JSON")
                return {}

        except Exception as e:
            logger.error(f"Failed to get current PAT: {e}")
            return {}

    async def update_pat(
        self,
        new_pat: str,
        new_pat_id: str,
        new_expiry: str,
    ) -> bool:
        """
        Update PAT in AWS Secrets Manager while preserving ALL other secrets.

        CRITICAL: This method MUST NOT overwrite other credentials like:
        - ipaas_username, ipaas_password, ipaas_api_key
        - ims_access_token

        Args:
            new_pat: New PAT token
            new_pat_id: New PAT ID from MCP
            new_expiry: New expiry date (ISO 8601)

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Step 1: Get current secrets first to preserve all fields
            response = self.client.get_secret_value(SecretId=self.secret_name)
            secret_string = response.get("SecretString")

            if not secret_string:
                logger.error("Cannot update PAT: No existing secrets found")
                return False

            # Parse existing secrets
            secret_dict = json.loads(secret_string)

            # Log which fields we're preserving
            preserved_fields = [k for k in secret_dict.keys() if k not in [
                "ketchup_jira_pat", "ketchup_jira_pat_id", "ketchup_jira_pat_expiry"
            ]]
            logger.info(f"Preserving {len(preserved_fields)} existing secret fields: {preserved_fields}")

            # Step 2: Update ONLY the PAT-related fields, preserve everything else
            secret_dict["ketchup_jira_pat"] = new_pat
            secret_dict["ketchup_jira_pat_id"] = new_pat_id
            secret_dict["ketchup_jira_pat_expiry"] = new_expiry

            # Step 3: Update secret with ALL fields preserved
            self.client.update_secret(
                SecretId=self.secret_name,
                SecretString=json.dumps(secret_dict),
            )

            logger.info(
                f"PAT updated in Secrets Manager "
                f"(preserved {len(secret_dict)} total fields including iPaaS credentials)"
            )
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse existing secrets as JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to update PAT in Secrets Manager: {e}")
            return False


class SlackNotifier:
    """Sends alerts to Slack about rotation status."""

    def __init__(self):
        """Initialize Slack notifier."""
        import os
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    async def notify_success(
        self,
        new_pat_id: str,
        new_expiry: str,
        old_pat_id: str,
    ) -> None:
        """
        Send success notification to Slack.

        Args:
            new_pat_id: ID of newly created PAT
            new_expiry: Expiry date of new PAT
            old_pat_id: ID of revoked old PAT
        """
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return

        try:
            message = {
                "text": ":white_check_mark: JIRA PAT Rotation Successful",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":white_check_mark: *JIRA PAT Rotation Successful*\n"
                                    f"New PAT ID: `{new_pat_id}`\n"
                                    f"Expiry: `{new_expiry}`\n"
                                    f"Old PAT ID: `{old_pat_id}` (revoked)",
                        },
                    },
                ],
            }

            await self._send_slack_message(message)
            logger.info("Success notification sent to Slack")

        except Exception as e:
            logger.error(f"Failed to send success notification: {e}")

    async def notify_failure(
        self,
        reason: str,
        error_details: str,
    ) -> None:
        """
        Send failure notification to Slack.

        Args:
            reason: Reason for rotation failure
            error_details: Details about the error
        """
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return

        try:
            message = {
                "text": ":x: JIRA PAT Rotation Failed",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":x: *JIRA PAT Rotation Failed*\n"
                                    f"Reason: `{reason}`\n"
                                    f"Details: {error_details}",
                        },
                    },
                ],
            }

            await self._send_slack_message(message)
            logger.info("Failure notification sent to Slack")

        except Exception as e:
            logger.error(f"Failed to send failure notification: {e}")

    async def notify_partial_success(
        self,
        new_pat_rotated: bool,
        old_pat_revoked: bool,
        new_pat_id: str,
        revocation_error: Optional[str] = None,
    ) -> None:
        """
        Send partial success notification to Slack (rotation succeeded, revocation failed).

        Args:
            new_pat_rotated: Whether new PAT was created and activated
            old_pat_revoked: Whether old PAT was revoked
            new_pat_id: ID of new PAT
            revocation_error: Error details if revocation failed
        """
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return

        try:
            status_new = ":white_check_mark:" if new_pat_rotated else ":x:"
            status_old = ":white_check_mark:" if old_pat_revoked else ":warning:"

            message = {
                "text": ":warning: JIRA PAT Rotation - Partial Success",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":warning: *JIRA PAT Rotation - Partial Success*\n"
                                    f"{status_new} New PAT Created & Activated: `{new_pat_id}`\n"
                                    f"{status_old} Old PAT Revoked: {'Yes' if old_pat_revoked else 'No'}\n"
                                    + (f"Revocation Error: {revocation_error}" if revocation_error else ""),
                        },
                    },
                ],
            }

            await self._send_slack_message(message)
            logger.info("Partial success notification sent to Slack")

        except Exception as e:
            logger.error(f"Failed to send partial success notification: {e}")

    async def _send_slack_message(self, message: Dict[str, Any]) -> None:
        """
        Send message to Slack via webhook.

        Args:
            message: Message payload
        """
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=message,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        logger.error(f"Slack API error: {response.status}")
                    else:
                        logger.info("Message sent to Slack")

        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")


class PATRotator:
    """
    Orchestrator for safe PAT rotation (singleton service on prod1 only).

    Implements safe rotation sequence:
    1. Check expiry needed (return if not)
    2. Create new PAT via MCP
    3. Validate new PAT works
    4. Update secrets with new PAT + expiry
    5. Revoke old PAT
    6. Send success alert
    """

    def __init__(self):
        """Initialize PAT rotator with all required dependencies."""
        # Import here to avoid circular dependencies and enable mocking
        from ketchup_jira_pat_rotator.pat_monitor import PatMonitor
        from packages.integrations.mcp_client import MCPClient
        from packages.integrations.ims_token_manager import IMSTokenManager

        self._monitor = PatMonitor()
        self._secrets_manager = SecretsManager()
        self._slack_notifier = SlackNotifier()

        # MCP client requires token manager
        try:
            token_manager = IMSTokenManager()
            self._mcp_client = MCPClient(token_manager)
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            self._mcp_client = None

    async def rotate(self) -> Dict[str, Any]:
        """
        Execute PAT rotation with safe fallback.

        Returns:
            Dictionary with rotation status and details
        """
        try:
            # Step 1: Check if rotation is needed
            logger.info("Starting PAT rotation check")
            should_rotate = self._monitor.should_rotate()

            if not should_rotate:
                logger.info("PAT rotation not needed")
                return {
                    "status": "skipped",
                    "action": "no_rotation_needed",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            # Get current PAT for revocation later
            current_secrets = await self._secrets_manager.get_current_pat()
            # Use correct field names matching AWS Secrets Manager
            old_pat_id = current_secrets.get("ketchup_jira_pat_id", "unknown")

            # Step 2: Create new PAT via MCP
            logger.info("Creating new PAT via MCP")
            try:
                new_pat_response = await self._mcp_client.create_pat()
                new_pat = new_pat_response.get("pat")
                new_pat_id = new_pat_response.get("id")
                new_expiry = new_pat_response.get("expiryDate")

                if not new_pat or not new_pat_id:
                    raise Exception("Invalid response from create_pat")

                logger.info(f"New PAT created: {new_pat_id}")

            except Exception as e:
                logger.error(f"Failed to create new PAT: {e}")
                return await self._handle_rotation_failure(
                    "create_pat_failed",
                    str(e),
                )

            # Step 3: Validate new PAT works
            logger.info("Validating new PAT")
            try:
                validation_result = await self._mcp_client.validate_pat(new_pat)

                if not validation_result.get("valid"):
                    raise Exception(
                        f"PAT validation failed: {validation_result.get('error', 'Unknown error')}"
                    )

                logger.info("New PAT validated successfully")

            except Exception as e:
                logger.error(f"Failed to validate new PAT: {e}")
                # Clean up: revoke the new invalid PAT
                try:
                    await self._mcp_client.revoke_pat(new_pat_id)
                    logger.info(f"Revoked invalid PAT: {new_pat_id}")
                except Exception as revoke_error:
                    logger.error(f"Failed to revoke invalid PAT: {revoke_error}")

                return await self._handle_rotation_failure(
                    "validation_failed",
                    str(e),
                )

            # Step 4: Update secrets with new PAT
            logger.info("Updating secrets with new PAT")
            try:
                update_success = await self._secrets_manager.update_pat(
                    new_pat,
                    new_pat_id,
                    new_expiry,
                )

                if not update_success:
                    raise Exception("Secrets Manager update returned False")

                logger.info("PAT updated in Secrets Manager")

            except Exception as e:
                logger.error(f"Failed to update secrets: {e}")
                # Clean up: revoke the new PAT since we couldn't activate it
                try:
                    await self._mcp_client.revoke_pat(new_pat_id)
                    logger.info(f"Revoked new PAT due to secrets update failure: {new_pat_id}")
                except Exception as revoke_error:
                    logger.error(f"Failed to revoke new PAT: {revoke_error}")

                return await self._handle_rotation_failure(
                    "secrets_update_failed",
                    str(e),
                )

            # Step 5: Revoke old PAT
            logger.info(f"Revoking old PAT: {old_pat_id}")
            old_pat_revoked = False
            revocation_error = None

            try:
                revoke_result = await self._mcp_client.revoke_pat(old_pat_id)

                if revoke_result.get("success"):
                    old_pat_revoked = True
                    logger.info(f"Old PAT revoked successfully: {old_pat_id}")
                else:
                    revocation_error = revoke_result.get("error", "Unknown error")
                    logger.warning(f"Failed to revoke old PAT: {revocation_error}")

            except Exception as e:
                revocation_error = str(e)
                logger.error(f"Exception during PAT revocation: {e}")

            # Step 6: Send alerts
            if old_pat_revoked:
                await self._slack_notifier.notify_success(
                    new_pat_id,
                    new_expiry,
                    old_pat_id,
                )

                return {
                    "status": "success",
                    "action": "rotated",
                    "newPatId": new_pat_id,
                    "oldPatId": old_pat_id,
                    "newExpiry": new_expiry,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                # Partial success: new PAT is active but old one wasn't revoked
                await self._slack_notifier.notify_partial_success(
                    new_pat_rotated=True,
                    old_pat_revoked=False,
                    new_pat_id=new_pat_id,
                    revocation_error=revocation_error,
                )

                return {
                    "status": "partial_success",
                    "newPatRotated": True,
                    "oldPatRevoked": False,
                    "newPatId": new_pat_id,
                    "revocationError": revocation_error,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Unexpected error during rotation: {e}", exc_info=True)
            return await self._handle_rotation_failure(
                "unexpected_error",
                str(e),
            )

    async def _handle_rotation_failure(
        self,
        reason: str,
        error_details: str,
    ) -> Dict[str, Any]:
        """
        Handle rotation failure with cleanup and alerting.

        Args:
            reason: Reason for failure
            error_details: Error details

        Returns:
            Failure response dictionary
        """
        await self._slack_notifier.notify_failure(reason, error_details)

        return {
            "status": "failed",
            "reason": reason,
            "error": error_details,
            "timestamp": datetime.utcnow().isoformat(),
        }
