#!/usr/bin/env python3
"""
Integration tests for access request automation feature.

Tests the complete flow from request creation through approval/rejection.
"""

import json
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

from base_integration_test import BaseIntegrationTest

from packages.core.constants import ACCESS_REQUEST_CHANNEL, ACCESS_REQUEST_STATUS
from packages.db.models.access_request import AccessRequest


class TestAccessRequestIntegration(BaseIntegrationTest):
    """Test the complete access request flow with real services."""

    def __init__(self):
        """Initialize access request integration test."""
        super().__init__(test_name="AccessRequestIntegration", env_vars={"LOG_LEVEL": "DEBUG"})

        # Test data
        self.test_user_id = "UTEST12345"
        self.test_user_name = "integration_test_user"
        self.test_user_email = "test@example.com"
        self.approver_user_id = "UAPPROVER789"
        self.approver_name = "integration_approver"

    async def run_test(self) -> bool:
        """Run the access request integration test."""
        try:
            # Get required services
            services = self.get_services(
                [
                    "access_request_operations",
                    "access_request_handler",
                    "slack_posting",
                    "local_metrics_service",
                    "secrets_manager",
                    "distributed_lock",
                ]
            )

            # Run test scenarios
            passed = True

            # Test 1: Create access request
            self.logger.info("Test 1: Creating access request...")
            if not await self._test_create_request(services):
                passed = False

            # Test 2: Duplicate request prevention
            self.logger.info("Test 2: Testing duplicate request prevention...")
            if not await self._test_duplicate_prevention(services):
                passed = False

            # Test 3: Rate limiting
            self.logger.info("Test 3: Testing rate limiting...")
            if not await self._test_rate_limiting(services):
                passed = False

            # Test 4: Approval flow
            self.logger.info("Test 4: Testing approval flow...")
            if not await self._test_approval_flow(services):
                passed = False

            # Test 5: Rejection flow
            self.logger.info("Test 5: Testing rejection flow...")
            if not await self._test_rejection_flow(services):
                passed = False

            # Test 6: Concurrent approvals (distributed lock)
            self.logger.info("Test 6: Testing concurrent approvals...")
            if not await self._test_concurrent_approvals(services):
                passed = False

            return passed

        except Exception as e:
            self.logger.error(f"Test failed with error: {e}", exc_info=True)
            return False

    async def _test_create_request(self, services: Dict[str, Any]) -> bool:
        """Test creating a new access request."""
        try:
            ops = services["access_request_operations"]

            # Create request
            request = AccessRequest(
                user_id=self.test_user_id,
                user_name=self.test_user_name,
                user_email=self.test_user_email,
                request_timestamp=time.time(),
                status=ACCESS_REQUEST_STATUS["PENDING"],
            )

            success, message, created_request = await ops.create_request_with_validation(request)

            if not success:
                self.logger.error(f"Failed to create request: {message}")
                return False

            # Verify request was created
            self.logger.info(f"✓ Request created successfully: {created_request.user_id}")

            # Check if request appears in pending list
            pending = await ops.get_all_pending_requests()
            found = any(r.user_id == self.test_user_id for r in pending)

            if not found:
                self.logger.error("Request not found in pending list")
                return False

            self.logger.info("✓ Request appears in pending list")
            return True

        except Exception as e:
            self.logger.error(f"Create request test failed: {e}")
            return False

    async def _test_duplicate_prevention(self, services: Dict[str, Any]) -> bool:
        """Test that duplicate requests are prevented."""
        try:
            ops = services["access_request_operations"]

            # Try to create another request for same user
            request = AccessRequest(
                user_id=self.test_user_id,
                user_name=self.test_user_name,
                user_email=self.test_user_email,
                request_timestamp=time.time(),
                status=ACCESS_REQUEST_STATUS["PENDING"],
            )

            success, message, created_request = await ops.create_request_with_validation(request)

            if success:
                self.logger.error("Duplicate request was allowed!")
                return False

            if "already have a pending request" not in message:
                self.logger.error(f"Unexpected duplicate message: {message}")
                return False

            self.logger.info("✓ Duplicate request correctly prevented")
            return True

        except Exception as e:
            self.logger.error(f"Duplicate prevention test failed: {e}")
            return False

    async def _test_rate_limiting(self, services: Dict[str, Any]) -> bool:
        """Test rate limiting functionality."""
        try:
            ops = services["access_request_operations"]

            # First approve the existing request to allow new ones
            pending = await ops.get_all_pending_requests()
            existing = next((r for r in pending if r.user_id == self.test_user_id), None)

            if existing:
                await ops.update_request_decision(
                    user_id=self.test_user_id,
                    request_timestamp=existing.request_timestamp,
                    decision=ACCESS_REQUEST_STATUS["APPROVED"],
                    decided_by_id=self.approver_user_id,
                    decided_by_name=self.approver_name,
                )

            # Create requests up to the rate limit
            rate_limit_user = "URATELIMIT123"
            for i in range(4):  # Try 4 requests (limit is 3)
                request = AccessRequest(
                    user_id=rate_limit_user,
                    user_name=f"ratelimit_user_{i}",
                    user_email=f"ratelimit{i}@example.com",
                    request_timestamp=time.time() + i,
                    status=ACCESS_REQUEST_STATUS["PENDING"],
                )

                success, message, _ = await ops.create_request_with_validation(request)

                if i < 3:  # First 3 should succeed
                    if not success:
                        self.logger.error(f"Request {i+1} failed unexpectedly: {message}")
                        return False
                    # Immediately approve to allow next request
                    await ops.update_request_decision(
                        user_id=rate_limit_user,
                        request_timestamp=request.request_timestamp,
                        decision=ACCESS_REQUEST_STATUS["APPROVED"],
                        decided_by_id=self.approver_user_id,
                        decided_by_name=self.approver_name,
                    )
                else:  # 4th should be rate limited
                    if success:
                        self.logger.error("4th request was not rate limited!")
                        return False
                    if "too many requests" not in message.lower():
                        self.logger.error(f"Unexpected rate limit message: {message}")
                        return False

            self.logger.info("✓ Rate limiting working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Rate limiting test failed: {e}")
            return False

    async def _test_approval_flow(self, services: Dict[str, Any]) -> bool:
        """Test the approval flow."""
        try:
            handler = services["access_request_handler"]
            ops = services["access_request_operations"]

            # Create a new request for approval test
            approval_user = "UAPPROVAL456"
            request = AccessRequest(
                user_id=approval_user,
                user_name="approval_test_user",
                user_email="approval@example.com",
                request_timestamp=time.time(),
                status=ACCESS_REQUEST_STATUS["PENDING"],
            )

            success, _, created_request = await ops.create_request_with_validation(request)
            if not success:
                self.logger.error("Failed to create request for approval test")
                return False

            # Mock the Slack client for testing
            original_client = handler.slack_client
            handler.slack_client = Mock()
            handler.slack_client.api_call = AsyncMock(
                return_value={"ok": True, "channel": {"id": "D123"}}
            )

            # Mock secrets manager to avoid actual AWS updates
            original_secrets = handler.secrets_manager
            handler.secrets_manager = Mock()
            handler.secrets_manager.add_authorized_user = AsyncMock(return_value=True)

            try:
                # Create approval payload
                payload = {
                    "user": {"id": self.approver_user_id, "name": self.approver_name},
                    "channel": {"id": ACCESS_REQUEST_CHANNEL},
                    "message": {"ts": "1234567890.123456", "blocks": []},
                    "actions": [{"value": f"{approval_user}|{created_request.request_timestamp}"}],
                }

                # Handle approval
                response = await handler.handle_approve_access(payload)

                if "approved" not in response.get("text", "").lower():
                    self.logger.error(f"Unexpected approval response: {response}")
                    return False

                # Verify request status was updated
                history = await ops.get_user_request_history(approval_user)
                approved = next(
                    (r for r in history if r.status == ACCESS_REQUEST_STATUS["APPROVED"]),
                    None,
                )

                if not approved:
                    self.logger.error("Request was not marked as approved")
                    return False

                self.logger.info("✓ Approval flow completed successfully")
                return True

            finally:
                # Restore original services
                handler.slack_client = original_client
                handler.secrets_manager = original_secrets

        except Exception as e:
            self.logger.error(f"Approval flow test failed: {e}")
            return False

    async def _test_rejection_flow(self, services: Dict[str, Any]) -> bool:
        """Test the rejection flow."""
        try:
            handler = services["access_request_handler"]
            ops = services["access_request_operations"]

            # Create a new request for rejection test
            rejection_user = "UREJECT789"
            request = AccessRequest(
                user_id=rejection_user,
                user_name="rejection_test_user",
                user_email="reject@example.com",
                request_timestamp=time.time(),
                status=ACCESS_REQUEST_STATUS["PENDING"],
            )

            success, _, created_request = await ops.create_request_with_validation(request)
            if not success:
                self.logger.error("Failed to create request for rejection test")
                return False

            # Mock the Slack client
            original_client = handler.slack_client
            handler.slack_client = Mock()
            handler.slack_client.api_call = AsyncMock(
                return_value={"ok": True, "channel": {"id": "D456"}}
            )

            try:
                # Create rejection submission payload
                payload = {
                    "user": {"id": self.approver_user_id, "name": self.approver_name},
                    "view": {
                        "state": {
                            "values": {
                                "reason_block": {"reason_input": {"value": "Test rejection reason"}}
                            }
                        },
                        "private_metadata": json.dumps(
                            {
                                "user_id": rejection_user,
                                "request_timestamp": str(created_request.request_timestamp),
                                "channel_ts": "1234567890.123456",
                                "original_blocks": [],
                            }
                        ),
                    },
                }

                # Handle rejection
                response = await handler.handle_rejection_submission(payload)

                if response.get("response_type") != "clear":
                    self.logger.error(f"Unexpected rejection response: {response}")
                    return False

                # Verify request status was updated
                history = await ops.get_user_request_history(rejection_user)
                rejected = next(
                    (r for r in history if r.status == ACCESS_REQUEST_STATUS["REJECTED"]),
                    None,
                )

                if not rejected:
                    self.logger.error("Request was not marked as rejected")
                    return False

                if rejected.rejection_reason != "Test rejection reason":
                    self.logger.error(f"Rejection reason mismatch: {rejected.rejection_reason}")
                    return False

                self.logger.info("✓ Rejection flow completed successfully")
                return True

            finally:
                handler.slack_client = original_client

        except Exception as e:
            self.logger.error(f"Rejection flow test failed: {e}")
            return False

    async def _test_concurrent_approvals(self, services: Dict[str, Any]) -> bool:
        """Test that distributed lock prevents concurrent approvals."""
        try:
            handler = services["access_request_handler"]
            ops = services["access_request_operations"]

            # Create a request for concurrent test
            concurrent_user = "UCONCURRENT999"
            request = AccessRequest(
                user_id=concurrent_user,
                user_name="concurrent_test_user",
                user_email="concurrent@example.com",
                request_timestamp=time.time(),
                status=ACCESS_REQUEST_STATUS["PENDING"],
            )

            success, _, created_request = await ops.create_request_with_validation(request)
            if not success:
                self.logger.error("Failed to create request for concurrent test")
                return False

            # Mock services
            original_client = handler.slack_client
            original_secrets = handler.secrets_manager
            handler.slack_client = Mock()
            handler.slack_client.api_call = AsyncMock(
                return_value={"ok": True, "channel": {"id": "D789"}}
            )
            handler.secrets_manager = Mock()
            handler.secrets_manager.add_authorized_user = AsyncMock(return_value=True)

            try:
                # Create two approval payloads
                payload1 = {
                    "user": {"id": "UAPPROVER1", "name": "approver1"},
                    "channel": {"id": ACCESS_REQUEST_CHANNEL},
                    "message": {"ts": "1234567890.123456", "blocks": []},
                    "actions": [
                        {"value": f"{concurrent_user}|{created_request.request_timestamp}"}
                    ],
                }

                payload2 = {
                    "user": {"id": "UAPPROVER2", "name": "approver2"},
                    "channel": {"id": ACCESS_REQUEST_CHANNEL},
                    "message": {"ts": "1234567890.123456", "blocks": []},
                    "actions": [
                        {"value": f"{concurrent_user}|{created_request.request_timestamp}"}
                    ],
                }

                # Try to approve concurrently
                import asyncio

                results = await asyncio.gather(
                    handler.handle_approve_access(payload1),
                    handler.handle_approve_access(payload2),
                    return_exceptions=True,
                )

                # Check that at least one succeeded
                approved_count = sum(
                    1
                    for r in results
                    if isinstance(r, dict) and "approved" in r.get("text", "").lower()
                )

                if approved_count == 0:
                    self.logger.error("No approvals succeeded")
                    return False

                # Check request history - should only have one approval
                history = await ops.get_user_request_history(concurrent_user)
                approved_requests = [
                    r for r in history if r.status == ACCESS_REQUEST_STATUS["APPROVED"]
                ]

                if len(approved_requests) != 1:
                    self.logger.error(f"Expected 1 approval, got {len(approved_requests)}")
                    return False

                self.logger.info("✓ Distributed lock prevented concurrent approvals")
                return True

            finally:
                handler.slack_client = original_client
                handler.secrets_manager = original_secrets

        except Exception as e:
            self.logger.error(f"Concurrent approvals test failed: {e}")
            return False


# Run the test if executed directly
if __name__ == "__main__":
    import asyncio

    async def main():
        test = TestAccessRequestIntegration()
        success = await test.execute()
        exit(0 if success else 1)

    asyncio.run(main())
