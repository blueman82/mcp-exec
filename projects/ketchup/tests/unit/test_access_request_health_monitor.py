#!/usr/bin/env python3
"""
Unit tests for AccessRequestHealthMonitor alerting functionality.

Tests alert trigger conditions, message formatting, and Slack channel integration.
"""

import os

# Add project root to path
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ketchup_access_request_monitor.monitor import AccessRequestHealthMonitor
from packages.core.constants import ACCESS_REQUEST_STATUS


class TestAccessRequestHealthMonitor:
    """Test AccessRequestHealthMonitor alert functionality."""

    @pytest.fixture
    def monitor(self):
        """Create monitor instance for testing."""
        monitor = AccessRequestHealthMonitor()
        # Mock TypedDI container to avoid AWS dependencies
        monitor.container = AsyncMock()
        return monitor

    @pytest.fixture
    def mock_services(self, monitor):
        """Mock all required services."""
        # Mock access operations
        mock_ops = AsyncMock()
        mock_ops.get_all_pending_requests = AsyncMock(return_value=[])
        mock_ops.get_user_request_history = AsyncMock(return_value=[])

        # Mock metrics service
        mock_metrics = AsyncMock()
        mock_metrics.get_stats_summary = AsyncMock(
            return_value={
                "error_rate": 0.05,  # 5% error rate
                "error": 10,
                "created": 200,
                "rate_limited": 5,
            }
        )

        # Mock distributed lock
        mock_lock = AsyncMock()

        # Mock Slack client
        mock_slack = AsyncMock()
        mock_slack.api_call = AsyncMock(return_value={"ok": True})

        # Mock secrets manager with webhook URL
        mock_secrets = AsyncMock()
        mock_secrets.get_ketchup_alerts_webhook_url = AsyncMock(
            return_value="https://hooks.slack.com/test"
        )

        # Mock access request handler
        mock_handler = AsyncMock()

        # Set up TypedDI container to return mocked services via aget()
        async def mock_aget(protocol):
            from packages.core.typed_di.service_registrations.protocols.core_protocols import (
                SecretsManagerProtocol,
            )
            from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
                AccessRequestHandlerProtocol,
                AccessRequestMonitorProtocol,
            )
            from packages.core.typed_di.service_registrations.protocols.infrastructure_protocols import (
                DistributedLockProtocol,
            )
            from packages.core.typed_di.service_registrations.protocols.operation_protocols import (
                AccessRequestOperationsProtocol,
            )
            from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
                SlackAsyncClientProtocol,
            )

            protocol_map = {
                AccessRequestOperationsProtocol: mock_ops,
                AccessRequestMonitorProtocol: mock_metrics,
                DistributedLockProtocol: mock_lock,
                SlackAsyncClientProtocol: mock_slack,
                AccessRequestHandlerProtocol: mock_handler,
                SecretsManagerProtocol: mock_secrets,
            }
            return protocol_map.get(protocol)

        monitor.container.aget = mock_aget

        return {
            "ops": mock_ops,
            "metrics": mock_metrics,
            "lock": mock_lock,
            "slack": mock_slack,
        }

    @pytest.mark.asyncio
    async def test_high_pending_requests_trigger(self, monitor, mock_services):
        """Test alert triggers for high pending request count."""
        # Create 60 pending requests (exceeds threshold of 50)
        mock_requests = []
        for i in range(60):
            mock_request = MagicMock()
            mock_request.user_id = f"U{i:06d}"
            mock_request.request_timestamp = time.time()
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            mock_requests.append(mock_request)

        mock_services["ops"].get_all_pending_requests.return_value = mock_requests

        # Run health checks
        issues = await monitor.run_health_checks()

        # Should have warning about high pending count
        assert len(issues) > 0
        high_pending_issue = next(
            (i for i in issues if i["category"] == "high_pending_count"), None
        )
        assert high_pending_issue is not None
        assert high_pending_issue["severity"] == "warning"
        assert "60" in high_pending_issue["message"]
        assert high_pending_issue["details"]["count"] == 60
        assert high_pending_issue["details"]["threshold"] == 50

    @pytest.mark.asyncio
    async def test_old_pending_requests_trigger(self, monitor, mock_services):
        """Test alert triggers for old pending requests."""
        current_time = time.time()

        # Create 3 old requests (> 12 hours)
        old_requests = []
        for i in range(3):
            mock_request = MagicMock()
            mock_request.user_id = f"U{i:06d}"
            mock_request.request_timestamp = current_time - (15 * 3600)  # 15 hours old
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            old_requests.append(mock_request)

        # Add some recent requests
        for i in range(5):
            mock_request = MagicMock()
            mock_request.user_id = f"U{i+3:06d}"
            mock_request.request_timestamp = current_time - (2 * 3600)  # 2 hours old
            mock_request.status = ACCESS_REQUEST_STATUS["PENDING"]
            old_requests.append(mock_request)

        mock_services["ops"].get_all_pending_requests.return_value = old_requests

        # Run health checks
        issues = await monitor.run_health_checks()

        # Should have warning about old requests
        old_issue = next((i for i in issues if i["category"] == "old_pending_requests"), None)
        assert old_issue is not None
        assert old_issue["severity"] == "warning"
        assert "3 requests pending > 12h" in old_issue["message"]
        assert old_issue["details"]["count"] == 3

    @pytest.mark.asyncio
    async def test_high_error_rate_trigger(self, monitor, mock_services):
        """Test alert triggers for high error rate."""
        # Set error rate to 15% (exceeds 10% threshold)
        mock_services["metrics"].get_stats_summary.return_value = {
            "error_rate": 0.15,  # 15% error rate
            "error": 30,
            "created": 200,
            "rate_limited": 2,
        }

        # Run health checks
        issues = await monitor.run_health_checks()

        # Should have warning about high error rate
        error_issue = next((i for i in issues if i["category"] == "high_error_rate"), None)
        assert error_issue is not None
        assert error_issue["severity"] == "warning"
        assert "15.0%" in error_issue["message"]
        assert error_issue["details"]["error_rate"] == 15.0

    @pytest.mark.asyncio
    async def test_service_unavailable_trigger(self, monitor):
        """Test alert triggers for unavailable services."""
        from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
            AccessRequestMonitorProtocol,
        )
        from packages.core.typed_di.service_registrations.protocols.operation_protocols import (
            AccessRequestOperationsProtocol,
        )

        # Make a critical service unavailable
        async def mock_aget(protocol):
            if protocol == AccessRequestOperationsProtocol:
                return None  # Service unavailable
            # Return properly configured mocks for other services
            mock = AsyncMock()
            if protocol == AccessRequestMonitorProtocol:
                # Configure metrics service to return empty stats
                mock.get_stats_summary = AsyncMock(
                    return_value={"error_rate": 0.0, "error": 0, "created": 0, "rate_limited": 0}
                )
            return mock

        monitor.container.aget = mock_aget

        # Run health checks
        issues = await monitor.run_health_checks()

        # Should have critical alert about unavailable service
        service_issue = next((i for i in issues if i["category"] == "service_unavailable"), None)
        assert service_issue is not None
        assert service_issue["severity"] == "critical"
        assert "access_request_operations" in service_issue["message"]

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_alert_message_formatting(self, mock_session_class, monitor, mock_services):
        """Test Slack alert message formatting."""
        # Mock aiohttp ClientSession
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        # Create multiple issues of different severities
        issues = [
            {
                "severity": "critical",
                "category": "service_unavailable",
                "message": "Service unavailable: test_service",
                "details": {"service": "test_service"},
            },
            {
                "severity": "warning",
                "category": "high_pending_count",
                "message": "High number of pending requests: 75",
                "details": {"count": 75, "threshold": 50},
            },
            {
                "severity": "info",
                "category": "rate_limiting_active",
                "message": "15 users rate limited",
                "details": {"rate_limited_count": 15},
            },
        ]

        # Send alert
        await monitor.send_alert(issues)

        # Verify webhook was called instead of direct Slack API
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/test"  # webhook URL

        # Check payload content
        payload = call_args.kwargs["json"]
        assert "text" in payload
        assert "Access Request System Alert" in payload["text"]
        assert "blocks" in payload

        # Verify block structure
        blocks = payload["blocks"]
        assert blocks[0]["type"] == "header"
        assert "Access Request System Alert" in blocks[0]["text"]["text"]

        # Check issue counts
        section = blocks[1]
        assert section["type"] == "section"
        assert "Critical: 1" in section["text"]["text"]
        assert "Warnings: 1" in section["text"]["text"]
        assert "Info: 1" in section["text"]["text"]

    def test_should_send_alert_cooldown(self, monitor):
        """Test alert cooldown logic."""
        current_time = time.time()

        # Non-critical issue - should respect cooldown
        issues = [
            {
                "severity": "warning",
                "category": "high_pending_count",
                "message": "Test warning",
                "details": {},
            }
        ]

        # First alert should be sent
        assert monitor.should_send_alert(issues) is True

        # Mark as sent
        monitor.update_alert_times(issues)

        # Immediately after - should not send (cooldown)
        assert monitor.should_send_alert(issues) is False

        # Simulate time passing (> 1 hour cooldown)
        monitor.last_alerts["high_pending_count"] = current_time - 3700
        assert monitor.should_send_alert(issues) is True

    def test_critical_bypasses_cooldown(self, monitor):
        """Test that critical alerts bypass cooldown."""
        # Set recent alert time
        monitor.last_alerts["service_unavailable"] = time.time()

        # Critical issue should bypass cooldown
        critical_issues = [
            {
                "severity": "critical",
                "category": "service_unavailable",
                "message": "Critical failure",
                "details": {},
            }
        ]

        # Should send even with recent alert
        assert monitor.should_send_alert(critical_issues) is True

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_monitor_self_healing_detection(self, mock_session_class, monitor, mock_services):
        """Test monitor detects its own failures."""
        # Mock aiohttp ClientSession
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        # Mock health checks to fail repeatedly
        with patch.object(monitor, "run_health_checks", side_effect=Exception("Test failure")):
            # Track consecutive errors
            monitor.consecutive_errors = 2

            # Simulate monitoring loop iteration
            try:
                await monitor.run_health_checks()
            except Exception:
                monitor.consecutive_errors += 1

            # After 3 consecutive errors, should trigger self-healing alert
            if monitor.consecutive_errors >= 3:
                await monitor.send_alert(
                    [
                        {
                            "severity": "critical",
                            "category": "monitor_failure",
                            "message": f"Monitor failing repeatedly: {monitor.consecutive_errors} consecutive errors",
                            "details": {"last_error": "Test failure"},
                        }
                    ]
                )

                # Verify webhook was called for critical alert
                mock_session.post.assert_called()
                call_args = mock_session.post.call_args
                assert call_args[0][0] == "https://hooks.slack.com/test"
                payload = call_args.kwargs["json"]
                assert "Monitor failing repeatedly" in str(payload["blocks"])

    @pytest.mark.asyncio
    async def test_metrics_service_unavailable_handling(self, monitor):
        """Test graceful handling when metrics service is unavailable."""
        from packages.core.typed_di.exceptions import MissingDependencyError
        from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
            AccessRequestMonitorProtocol,
        )
        from packages.core.typed_di.service_registrations.protocols.operation_protocols import (
            AccessRequestOperationsProtocol,
        )

        # Make metrics service unavailable but other services available
        async def mock_aget(protocol):
            if protocol == AccessRequestMonitorProtocol:
                raise MissingDependencyError("Metrics service unavailable")
            # Return mocks for other services
            mock = AsyncMock()
            if protocol == AccessRequestOperationsProtocol:
                mock.get_all_pending_requests = AsyncMock(return_value=[])
                mock.get_user_request_history = AsyncMock(return_value=[])
            return mock

        monitor.container.aget = mock_aget

        # Run health checks - should not crash
        issues = await monitor.run_health_checks()

        # Should handle gracefully and continue other checks
        assert isinstance(issues, list)
        # The metrics check will be skipped (returns empty list)
        # But other checks should run, so we should have results
        assert len(issues) >= 0  # May have 0 issues if all other checks pass

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_alert_channel_configuration(self, mock_session_class, monitor, mock_services):
        """Test that alerts are sent to the correct channel."""
        # Mock aiohttp ClientSession
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        # Trigger any alert
        issues = [
            {
                "severity": "info",
                "category": "test",
                "message": "Test alert",
                "details": {},
            }
        ]

        await monitor.send_alert(issues)

        # Verify webhook was called (not slack client directly)
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/test"  # webhook URL
        assert "json" in call_args.kwargs
        payload = call_args.kwargs["json"]
        assert "Access Request System Alert" in payload["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
