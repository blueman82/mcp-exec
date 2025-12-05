#!/usr/bin/env python3
"""
Load tests for access request automation.

Tests system performance under concurrent load.
"""

import asyncio
import statistics
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

from base_integration_test import BaseIntegrationTest

from packages.core.constants import ACCESS_REQUEST_STATUS
from packages.db.models.access_request import AccessRequest


class TestAccessRequestLoadTest(BaseIntegrationTest):
    """Load test for access request system."""

    def __init__(self):
        """Initialize load test."""
        super().__init__(
            test_name="AccessRequestLoadTest",
            env_vars={"LOG_LEVEL": "WARNING"},  # Reduce log noise during load test
        )

        # Test configuration
        self.concurrent_users = 50  # Number of concurrent users
        self.requests_per_user = 3  # Requests per user
        self.approval_ratio = 0.7  # 70% approved, 30% rejected

    async def run_test(self) -> bool:
        """Run the load test scenarios."""
        try:
            # Get required services
            services = self.get_services(
                [
                    "access_request_operations",
                    "access_request_handler",
                    "distributed_lock",
                    "local_metrics_service",
                ]
            )

            # Mock external services to reduce latency
            await self._mock_external_services(services)

            # Run load test scenarios
            passed = True

            # Test 1: Concurrent request creation
            self.logger.info(f"Test 1: {self.concurrent_users} concurrent request creations...")
            if not await self._test_concurrent_requests(services):
                passed = False

            # Test 2: Concurrent approvals/rejections
            self.logger.info("Test 2: Concurrent approval/rejection processing...")
            if not await self._test_concurrent_decisions(services):
                passed = False

            # Test 3: Rate limiting under load
            self.logger.info("Test 3: Rate limiting under load...")
            if not await self._test_rate_limiting_load(services):
                passed = False

            # Test 4: Cache performance
            self.logger.info("Test 4: Cache performance under load...")
            if not await self._test_cache_performance(services):
                passed = False

            # Display performance metrics
            await self._display_performance_metrics(services)

            return passed

        except Exception as e:
            self.logger.error(f"Load test failed: {e}", exc_info=True)
            return False

    async def _mock_external_services(self, services: Dict[str, Any]):
        """Mock external services to isolate system performance."""
        handler = services["access_request_handler"]

        # Mock Slack client
        handler.slack_client = Mock()
        handler.slack_client.api_call = AsyncMock(
            return_value={
                "ok": True,
                "ts": "1234567890.123456",
                "channel": {"id": "D123456"},
                "user": {"profile": {"email": "test@example.com"}},
            }
        )

        # Mock secrets manager
        handler.secrets_manager = Mock()
        handler.secrets_manager.add_authorized_user = AsyncMock(return_value=True)

    async def _test_concurrent_requests(self, services: Dict[str, Any]) -> bool:
        """Test concurrent request creation."""
        try:
            ops = services["access_request_operations"]

            # Create test users
            test_users = []
            for i in range(self.concurrent_users):
                test_users.append(
                    {
                        "id": f"ULOAD{i:04d}",
                        "name": f"load_user_{i}",
                        "email": f"load{i}@example.com",
                    }
                )

            # Measure request creation time
            start_time = time.time()
            tasks = []

            for user in test_users:
                request = AccessRequest(
                    user_id=user["id"],
                    user_name=user["name"],
                    user_email=user["email"],
                    request_timestamp=time.time(),
                    status=ACCESS_REQUEST_STATUS["PENDING"],
                )

                task = ops.create_request_with_validation(request)
                tasks.append(task)

            # Execute all requests concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            end_time = time.time()
            duration = end_time - start_time

            # Analyze results
            successful = sum(1 for r in results if isinstance(r, tuple) and r[0])
            failed = len(results) - successful

            self.logger.info(f"Created {successful}/{len(test_users)} requests in {duration:.2f}s")
            self.logger.info(f"Average: {duration/len(test_users)*1000:.2f}ms per request")

            if successful < len(test_users) * 0.95:  # Allow 5% failure rate
                self.logger.error(f"Too many failures: {failed}/{len(test_users)}")
                return False

            # Check database consistency
            all_requests = await ops.get_all_pending_requests()
            db_count = sum(1 for r in all_requests if r.user_id.startswith("ULOAD"))

            if db_count != successful:
                self.logger.error(
                    f"Database inconsistency: {db_count} in DB vs {successful} successful"
                )
                return False

            self.logger.info("✓ Concurrent request creation successful")
            return True

        except Exception as e:
            self.logger.error(f"Concurrent request test failed: {e}")
            return False

    async def _test_concurrent_decisions(self, services: Dict[str, Any]) -> bool:
        """Test concurrent approval/rejection processing."""
        try:
            ops = services["access_request_operations"]
            handler = services["access_request_handler"]

            # Get all pending requests
            pending = await ops.get_all_pending_requests()
            load_requests = [r for r in pending if r.user_id.startswith("ULOAD")]

            if not load_requests:
                self.logger.error("No pending requests found for decision test")
                return False

            # Prepare decision tasks
            decision_tasks = []
            approval_times = []
            rejection_times = []

            for i, request in enumerate(load_requests):
                is_approval = i < int(len(load_requests) * self.approval_ratio)

                if is_approval:
                    # Approval payload
                    payload = {
                        "user": {"id": f"UAPPROVER{i}", "name": f"approver_{i}"},
                        "channel": {"id": "C123456"},
                        "message": {"ts": "1234567890.123456", "blocks": []},
                        "actions": [{"value": f"{request.user_id}|{request.request_timestamp}"}],
                    }

                    async def timed_approval(p):
                        start = time.time()
                        result = await handler.handle_approve_access(p)
                        approval_times.append(time.time() - start)
                        return result

                    decision_tasks.append(timed_approval(payload))
                else:
                    # Rejection via direct database update (simulating modal submission)
                    async def timed_rejection(r):
                        start = time.time()
                        result = await ops.update_request_decision(
                            user_id=r.user_id,
                            request_timestamp=r.request_timestamp,
                            decision=ACCESS_REQUEST_STATUS["REJECTED"],
                            decided_by_id=f"UREJECTER{i}",
                            decided_by_name=f"rejecter_{i}",
                            rejection_reason="Load test rejection",
                        )
                        rejection_times.append(time.time() - start)
                        return result

                    decision_tasks.append(timed_rejection(request))

            # Execute all decisions concurrently
            start_time = time.time()
            results = await asyncio.gather(*decision_tasks, return_exceptions=True)
            end_time = time.time()

            # Analyze results
            successful_decisions = sum(1 for r in results if r and not isinstance(r, Exception))

            self.logger.info(
                f"Processed {successful_decisions}/{len(load_requests)} decisions in {end_time - start_time:.2f}s"
            )

            if approval_times:
                self.logger.info(
                    f"Approval times - Avg: {statistics.mean(approval_times)*1000:.2f}ms, "
                    f"Min: {min(approval_times)*1000:.2f}ms, "
                    f"Max: {max(approval_times)*1000:.2f}ms"
                )

            if rejection_times:
                self.logger.info(
                    f"Rejection times - Avg: {statistics.mean(rejection_times)*1000:.2f}ms, "
                    f"Min: {min(rejection_times)*1000:.2f}ms, "
                    f"Max: {max(rejection_times)*1000:.2f}ms"
                )

            # Verify no duplicate approvals (distributed lock test)
            for request in load_requests[: int(len(load_requests) * self.approval_ratio)]:
                history = await ops.get_user_request_history(request.user_id)
                approved_count = sum(
                    1 for h in history if h.status == ACCESS_REQUEST_STATUS["APPROVED"]
                )

                if approved_count > 1:
                    self.logger.error(f"Duplicate approval detected for {request.user_id}")
                    return False

            self.logger.info("✓ Concurrent decision processing successful")
            return True

        except Exception as e:
            self.logger.error(f"Concurrent decision test failed: {e}")
            return False

    async def _test_rate_limiting_load(self, services: Dict[str, Any]) -> bool:
        """Test rate limiting under concurrent load."""
        try:
            ops = services["access_request_operations"]

            # Create users that will hit rate limits
            rate_limit_users = []
            for i in range(10):  # 10 users
                rate_limit_users.append(
                    {
                        "id": f"URATE{i:02d}",
                        "name": f"rate_user_{i}",
                        "email": f"rate{i}@example.com",
                    }
                )

            # Each user will try to create 5 requests (limit is 3)
            tasks = []
            for user in rate_limit_users:
                for j in range(5):
                    request = AccessRequest(
                        user_id=user["id"],
                        user_name=user["name"],
                        user_email=user["email"],
                        request_timestamp=time.time() + j,
                        status=ACCESS_REQUEST_STATUS["PENDING"],
                    )

                    async def create_and_approve(req):
                        result = await ops.create_request_with_validation(req)
                        if result[0]:  # If created, immediately approve to allow next
                            await ops.update_request_decision(
                                user_id=req.user_id,
                                request_timestamp=req.request_timestamp,
                                decision=ACCESS_REQUEST_STATUS["APPROVED"],
                                decided_by_id="UAUTO",
                                decided_by_name="auto_approver",
                            )
                        return result

                    tasks.append(create_and_approve(request))

            # Execute all attempts
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Analyze rate limiting
            for i, user in enumerate(rate_limit_users):
                user_results = results[i * 5 : (i + 1) * 5]
                successful = sum(1 for r in user_results if isinstance(r, tuple) and r[0])
                rate_limited = sum(
                    1
                    for r in user_results
                    if isinstance(r, tuple) and not r[0] and "too many" in r[1].lower()
                )

                if successful > 3:
                    self.logger.error(
                        f"Rate limit not enforced for {user['id']}: {successful} succeeded"
                    )
                    return False

                if successful + rate_limited != 5:
                    self.logger.error(f"Unexpected results for {user['id']}")
                    return False

            self.logger.info("✓ Rate limiting working correctly under load")
            return True

        except Exception as e:
            self.logger.error(f"Rate limiting load test failed: {e}")
            return False

    async def _test_cache_performance(self, services: Dict[str, Any]) -> bool:
        """Test cache performance under load."""
        try:
            ops = services["access_request_operations"]

            # First, ensure cache is populated
            await ops.get_all_pending_requests()

            # Measure cached vs non-cached performance
            cache_times = []

            # Test 1: Repeated cached calls
            for i in range(100):
                start = time.time()
                await ops.get_all_pending_requests()
                cache_times.append(time.time() - start)

            avg_cache_time = statistics.mean(cache_times)

            # Invalidate cache
            ops.invalidate_cache()

            # Test 2: First call after invalidation
            start = time.time()
            await ops.get_all_pending_requests()
            uncached_time = time.time() - start

            self.logger.info(
                f"Cache performance - Cached: {avg_cache_time*1000:.2f}ms, "
                f"Uncached: {uncached_time*1000:.2f}ms, "
                f"Speedup: {uncached_time/avg_cache_time:.1f}x"
            )

            # Cache should be significantly faster
            if avg_cache_time > uncached_time * 0.1:  # Cache should be at least 10x faster
                self.logger.error("Cache not providing expected performance benefit")
                return False

            self.logger.info("✓ Cache performance verified")
            return True

        except Exception as e:
            self.logger.error(f"Cache performance test failed: {e}")
            return False

    async def _display_performance_metrics(self, services: Dict[str, Any]):
        """Display performance metrics from the test."""
        try:
            metrics = services["local_metrics_service"]

            # Get metrics summary
            summary = await metrics.get_metrics_summary()

            self.logger.info("\n=== Performance Metrics ===")
            self.logger.info(f"Total requests created: {summary.get('created', 0)}")
            self.logger.info(f"Total approved: {summary.get('approved', 0)}")
            self.logger.info(f"Total rejected: {summary.get('rejected', 0)}")
            self.logger.info(f"Rate limited: {summary.get('rate_limited', 0)}")
            self.logger.info(f"Errors: {summary.get('error', 0)}")

            if summary.get("created", 0) > 0:
                self.logger.info(f"Approval rate: {summary.get('approval_rate', 0):.1%}")
                self.logger.info(f"Rejection rate: {summary.get('rejection_rate', 0):.1%}")
                self.logger.info(f"Error rate: {summary.get('error_rate', 0):.1%}")

        except Exception as e:
            self.logger.error(f"Failed to display metrics: {e}")


# Run the test if executed directly
if __name__ == "__main__":
    import asyncio

    async def main():
        test = TestAccessRequestLoadTest()
        success = await test.execute()
        exit(0 if success else 1)

    asyncio.run(main())
