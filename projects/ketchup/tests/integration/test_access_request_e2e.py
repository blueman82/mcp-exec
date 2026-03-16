#!/usr/bin/env python3
"""
End-to-end tests for access request automation.

Simulates the complete user journey from command execution to approval/rejection.
"""

import json
import time
from typing import Any, Dict
from unittest.mock import AsyncMock

from base_integration_test import BaseIntegrationTest

from packages.core.constants import ACCESS_REQUEST_CHANNEL, ACCESS_REQUEST_STATUS


class TestAccessRequestE2E(BaseIntegrationTest):
    """End-to-end test for access request flow."""

    def __init__(self):
        """Initialize E2E test."""
        super().__init__(test_name="AccessRequestE2E", env_vars={"LOG_LEVEL": "INFO"})

        # Test users
        self.unauthorized_user = {
            "id": "UE2ETEST123",
            "name": "e2e_test_user",
            "email": "e2e@example.com",
        }

        self.approver = {"id": "UE2EAPPROVER", "name": "e2e_approver"}

    async def run_test(self) -> bool:
        """Run the E2E test scenarios."""
        try:
            # Get required services
            services = self.get_services(
                [
                    "command_router",
                    "payload_processor",
                    "user_verifier",
                    "slack_posting",
                    "access_request_handler",
                    "access_request_operations",
                ]
            )

            # Run test scenarios
            passed = True

            # Scenario 1: Unauthorized user in DM
            self.logger.info("Scenario 1: Unauthorized user runs command in DM...")
            if not await self._test_unauthorized_dm_flow(services):
                passed = False

            # Scenario 2: Unauthorized user in channel
            self.logger.info("Scenario 2: Unauthorized user runs command in channel...")
            if not await self._test_unauthorized_channel_flow(services):
                passed = False

            # Scenario 3: Complete request and approval flow
            self.logger.info("Scenario 3: Complete request and approval flow...")
            if not await self._test_complete_approval_flow(services):
                passed = False

            # Scenario 4: Request and rejection flow
            self.logger.info("Scenario 4: Request and rejection flow...")
            if not await self._test_complete_rejection_flow(services):
                passed = False

            return passed

        except Exception as e:
            self.logger.error(f"E2E test failed: {e}", exc_info=True)
            return False

    async def _test_unauthorized_dm_flow(self, services: Dict[str, Any]) -> bool:
        """Test unauthorized user command in DM."""
        try:
            router = services["command_router"]
            verifier = services["user_verifier"]
            posting = services["slack_posting"]

            # Mock user verifier to return False
            original_validate = verifier.validate_user_id
            verifier.validate_user_id = AsyncMock(return_value=False)

            # Mock posting handler
            posted_blocks = []
            original_post_blocks = posting.post_blocks

            async def capture_blocks(*args, **kwargs):
                posted_blocks.append(kwargs.get("blocks", []))
                return True

            posting.post_blocks = AsyncMock(side_effect=capture_blocks)
            posting.post_message = AsyncMock(return_value=True)

            try:
                # Simulate command in DM
                dm_command = {
                    "command": ["/ketchup"],
                    "text": ["status"],
                    "channel_id": ["D123456"],
                    "channel_name": ["directmessage"],
                    "user_id": [self.unauthorized_user["id"]],
                    "user_name": [self.unauthorized_user["name"]],
                    "response_url": ["https://hooks.slack.com/commands/123"],
                }

                result = await router.route_command(dm_command)

                # Verify response
                if result.status_code != 200:
                    self.logger.error(f"Unexpected status code: {result}")
                    return False

                # Check that access request UI was shown
                if not posted_blocks:
                    self.logger.error("No blocks were posted")
                    return False

                # Find request button in blocks
                request_button = None
                for blocks in posted_blocks:
                    for block in blocks:
                        if block.get("type") == "actions":
                            for element in block.get("elements", []):
                                if element.get("action_id") == "request_access":
                                    request_button = element
                                    break

                if not request_button:
                    self.logger.error("Request access button not found in blocks")
                    return False

                self.logger.info("✓ Access request UI shown in DM")
                return True

            finally:
                verifier.validate_user_id = original_validate
                posting.post_blocks = original_post_blocks

        except Exception as e:
            self.logger.error(f"Unauthorized DM test failed: {e}")
            return False

    async def _test_unauthorized_channel_flow(self, services: Dict[str, Any]) -> bool:
        """Test unauthorized user command in channel."""
        try:
            router = services["command_router"]
            verifier = services["user_verifier"]
            posting = services["slack_posting"]

            # Mock user verifier
            original_validate = verifier.validate_user_id
            verifier.validate_user_id = AsyncMock(return_value=False)

            # Mock posting handler
            posted_messages = []
            original_post = posting.post_message

            async def capture_message(*args, **kwargs):
                posted_messages.append(kwargs.get("message", ""))
                return True

            posting.post_message = AsyncMock(side_effect=capture_message)

            try:
                # Simulate command in channel
                channel_command = {
                    "command": ["/ketchup"],
                    "text": ["status"],
                    "channel_id": ["C123456"],
                    "channel_name": ["general"],
                    "user_id": [self.unauthorized_user["id"]],
                    "user_name": [self.unauthorized_user["name"]],
                    "response_url": ["https://hooks.slack.com/commands/456"],
                }

                await router.route_command(channel_command)

                # Check that message directs to DM
                if not posted_messages:
                    self.logger.error("No message was posted")
                    return False

                message = posted_messages[0]
                if "direct message" not in message.lower():
                    self.logger.error(f"Message doesn't mention DM: {message}")
                    return False

                self.logger.info("✓ User directed to use DM for access request")
                return True

            finally:
                verifier.validate_user_id = original_validate
                posting.post_message = original_post

        except Exception as e:
            self.logger.error(f"Unauthorized channel test failed: {e}")
            return False

    async def _test_complete_approval_flow(self, services: Dict[str, Any]) -> bool:
        """Test complete flow from request to approval."""
        try:
            processor = services["payload_processor"]
            handler = services["access_request_handler"]
            ops = services["access_request_operations"]
            posting = services["slack_posting"]

            # Mock Slack posting
            posted_to_channel = []
            posted_dms = []

            async def mock_post(*args, **kwargs):
                method = args[0] if args else kwargs.get("method")
                params = args[1] if len(args) > 1 else kwargs.get("params", {})

                if method == "chat.postMessage":
                    if params.get("channel") == ACCESS_REQUEST_CHANNEL:
                        posted_to_channel.append(params)
                    elif params.get("channel", "").startswith("D"):
                        posted_dms.append(params)
                elif method == "conversations.open":
                    return {"ok": True, "channel": {"id": "D789012"}}
                elif method == "users.info":
                    return {
                        "ok": True,
                        "user": {"profile": {"email": self.unauthorized_user["email"]}},
                    }

                return {"ok": True, "ts": "1234567890.123456"}

            original_api_call = handler.slack_client.api_call
            handler.slack_client.api_call = AsyncMock(side_effect=mock_post)

            # Mock secrets manager
            original_add_user = handler.secrets_manager.add_authorized_user
            handler.secrets_manager.add_authorized_user = AsyncMock(return_value=True)

            try:
                # Step 1: User clicks request access button
                request_payload = {
                    "type": "block_actions",
                    "user": {
                        "id": self.unauthorized_user["id"],
                        "name": self.unauthorized_user["name"],
                    },
                    "channel": {"id": "D123456"},
                    "actions": [
                        {
                            "action_id": "request_access",
                            "value": self.unauthorized_user["id"],
                        }
                    ],
                }

                success = await processor(
                    request_payload,
                    posting_handler=posting,
                    feedback_handler=None,
                    shortcut_handler=None,
                    feedback_report_handler=None,
                    channel_metadata_edit_handler=None,
                    home_tab_handler=None,
                    trust_endorsement_handler=None,
                    access_request_handler=handler,
                    flag_review_handler=None,
                )

                if not success:
                    self.logger.error("Request processing failed")
                    return False

                # Verify notification was posted
                if not posted_to_channel:
                    self.logger.error("No notification posted to channel")
                    return False

                # Get the request from DB
                requests = await ops.get_all_pending_requests()
                user_request = next(
                    (r for r in requests if r.user_id == self.unauthorized_user["id"]),
                    None,
                )

                if not user_request:
                    self.logger.error("Request not found in database")
                    return False

                # Step 2: Approver clicks approve button
                approve_payload = {
                    "type": "block_actions",
                    "user": {"id": self.approver["id"], "name": self.approver["name"]},
                    "channel": {"id": ACCESS_REQUEST_CHANNEL},
                    "message": {
                        "ts": "1234567890.123456",
                        "blocks": posted_to_channel[0]["blocks"],
                    },
                    "actions": [
                        {
                            "action_id": f"approve_access_{self.unauthorized_user['id']}",
                            "value": f"{self.unauthorized_user['id']}|{user_request.request_timestamp}",
                        }
                    ],
                }

                success = await processor(
                    approve_payload,
                    posting_handler=posting,
                    feedback_handler=None,
                    shortcut_handler=None,
                    feedback_report_handler=None,
                    channel_metadata_edit_handler=None,
                    home_tab_handler=None,
                    trust_endorsement_handler=None,
                    access_request_handler=handler,
                    flag_review_handler=None,
                )

                if not success:
                    self.logger.error("Approval processing failed")
                    return False

                # Verify DM was sent
                if not posted_dms:
                    self.logger.error("No approval DM sent")
                    return False

                # Verify user was added to authorized list
                handler.secrets_manager.add_authorized_user.assert_called_once_with(
                    self.unauthorized_user["id"]
                )

                # Verify request status in DB
                history = await ops.get_user_request_history(self.unauthorized_user["id"])
                approved = next(
                    (r for r in history if r.status == ACCESS_REQUEST_STATUS["APPROVED"]),
                    None,
                )

                if not approved:
                    self.logger.error("Request not marked as approved")
                    return False

                self.logger.info("✓ Complete approval flow successful")
                return True

            finally:
                handler.slack_client.api_call = original_api_call
                handler.secrets_manager.add_authorized_user = original_add_user

        except Exception as e:
            self.logger.error(f"Complete approval flow test failed: {e}")
            return False

    async def _test_complete_rejection_flow(self, services: Dict[str, Any]) -> bool:
        """Test complete flow from request to rejection."""
        try:
            processor = services["payload_processor"]
            handler = services["access_request_handler"]
            ops = services["access_request_operations"]
            posting = services["slack_posting"]

            # Create a different test user for rejection
            reject_user = {
                "id": "UREJECTE2E",
                "name": "reject_test_user",
                "email": "reject@example.com",
            }

            # Mock Slack API
            modal_opened = False
            rejection_dm_sent = False

            async def mock_api(*args, **kwargs):
                nonlocal modal_opened, rejection_dm_sent

                method = args[0] if args else kwargs.get("method")
                params = args[1] if len(args) > 1 else kwargs.get("params", {})

                if method == "views.open":
                    modal_opened = True
                    return {"ok": True}
                elif method == "chat.postMessage" and "rejected" in str(params):
                    rejection_dm_sent = True
                elif method == "conversations.open":
                    return {"ok": True, "channel": {"id": "DREJECT123"}}

                return {"ok": True, "ts": "1234567890.123456"}

            original_api_call = handler.slack_client.api_call
            handler.slack_client.api_call = AsyncMock(side_effect=mock_api)

            try:
                # First create a request
                from packages.db.models.access_request import AccessRequest

                request = AccessRequest(
                    user_id=reject_user["id"],
                    user_name=reject_user["name"],
                    user_email=reject_user["email"],
                    request_timestamp=time.time(),
                    status=ACCESS_REQUEST_STATUS["PENDING"],
                )

                success, _, created = await ops.create_request_with_validation(request)
                if not success:
                    self.logger.error("Failed to create request for rejection test")
                    return False

                # Step 1: Click reject button (opens modal)
                reject_button_payload = {
                    "type": "block_actions",
                    "user": self.approver,
                    "trigger_id": "12345.67890.abcdef",
                    "message": {
                        "blocks": [{"type": "section"}],
                        "ts": "1234567890.123456",
                    },
                    "actions": [
                        {
                            "action_id": f"reject_access_{reject_user['id']}",
                            "value": f"{reject_user['id']}|{created.request_timestamp}",
                        }
                    ],
                }

                await processor(
                    reject_button_payload,
                    posting_handler=posting,
                    feedback_handler=None,
                    shortcut_handler=None,
                    feedback_report_handler=None,
                    channel_metadata_edit_handler=None,
                    home_tab_handler=None,
                    trust_endorsement_handler=None,
                    access_request_handler=handler,
                    flag_review_handler=None,
                )

                if not modal_opened:
                    self.logger.error("Rejection modal was not opened")
                    return False

                # Step 2: Submit rejection modal
                modal_submit_payload = {
                    "type": "view_submission",
                    "user": self.approver,
                    "view": {
                        "callback_id": "reject_reason_modal",
                        "state": {
                            "values": {
                                "reason_block": {
                                    "reason_input": {"value": "Does not meet requirements"}
                                }
                            }
                        },
                        "private_metadata": json.dumps(
                            {
                                "user_id": reject_user["id"],
                                "request_timestamp": str(created.request_timestamp),
                                "channel_ts": "1234567890.123456",
                                "original_blocks": [],
                            }
                        ),
                    },
                }

                await processor(
                    modal_submit_payload,
                    posting_handler=posting,
                    feedback_handler=None,
                    shortcut_handler=None,
                    feedback_report_handler=None,
                    channel_metadata_edit_handler=None,
                    home_tab_handler=None,
                    trust_endorsement_handler=None,
                    access_request_handler=handler,
                    flag_review_handler=None,
                )

                if not rejection_dm_sent:
                    self.logger.error("Rejection DM was not sent")
                    return False

                # Verify request status
                history = await ops.get_user_request_history(reject_user["id"])
                rejected = next(
                    (r for r in history if r.status == ACCESS_REQUEST_STATUS["REJECTED"]),
                    None,
                )

                if not rejected:
                    self.logger.error("Request not marked as rejected")
                    return False

                if rejected.rejection_reason != "Does not meet requirements":
                    self.logger.error(f"Wrong rejection reason: {rejected.rejection_reason}")
                    return False

                self.logger.info("✓ Complete rejection flow successful")
                return True

            finally:
                handler.slack_client.api_call = original_api_call

        except Exception as e:
            self.logger.error(f"Complete rejection flow test failed: {e}")
            return False


# Run the test if executed directly
if __name__ == "__main__":
    import asyncio

    async def main():
        test = TestAccessRequestE2E()
        success = await test.execute()
        exit(0 if success else 1)

    asyncio.run(main())
