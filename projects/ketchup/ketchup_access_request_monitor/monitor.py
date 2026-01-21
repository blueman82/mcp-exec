#!/usr/bin/env python3
"""
Access Request System Health Monitor

Monitors the health of the access request automation system and sends alerts
to #ketchup-alerts when issues are detected.
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import aiohttp

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.core.constants import ACCESS_REQUEST_STATUS, KETCHUP_ALERTS_CHANNEL
from packages.core.logging import setup_logger
from packages.core.typed_di.exceptions import MissingDependencyError
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
from packages.core.typed_di_integration import get_unified_container


def write_health_status(status: str) -> None:
    """Write health status to file for Docker health check monitoring.

    Args:
        status: Current service status ('running', 'idle', 'monitoring', 'error')
    """
    try:
        timestamp = int(time.time())
        health_data = f"{timestamp}:{status}"
        with open("/tmp/access_monitor_health", "w") as f:
            f.write(health_data)
    except Exception as e:
        # Use print as fallback since logger may not be available
        print(f"Failed to write health status: {e}")


class AccessRequestHealthMonitor:
    """Health monitor service for access request system.

    This service monitors the health of the access request automation system
    and sends alerts when issues are detected. It is distinct from the
    AccessRequestMonitor metrics collector.
    """

    def __init__(self):
        """Initialize the monitor."""
        self.logger = setup_logger("AccessRequestHealthMonitor")
        self.container = None  # Will hold TypedDI container
        self.check_interval = 300  # 5 minutes
        self.alert_cooldown = 3600  # 1 hour between same alerts
        self.last_alerts: Dict[str, float] = {}

        # Thresholds
        self.thresholds = {
            "pending_requests_max": 50,  # Alert if > 50 pending requests
            "old_pending_hours": 12,  # Alert if request pending > 12 hours
            "error_rate_percent": 10,  # Alert if error rate > 10%
            "approval_time_hours": 24,  # Alert if avg approval time > 24 hours
            "stale_lock_minutes": 10,  # Alert if lock held > 10 minutes
        }

    async def initialize(self):
        """Initialize the TypedDI container and services."""
        self.logger.info("Initializing Access Request Monitor...")

        # Set environment - use IAM role in production, don't set AWS_PROFILE
        os.environ["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

        # Initialize TypedDI container
        self.container = await get_unified_container()

        self.logger.info("Monitor initialized successfully")

    async def run_health_checks(self) -> List[Dict[str, Any]]:
        """Run all health checks and return issues found."""
        issues = []

        try:
            # Get required services from TypedDI container
            access_ops = await self.container.aget(AccessRequestOperationsProtocol)
            # Get metrics service from TypedDI container (optional)
            try:
                metrics_service = await self.container.aget(AccessRequestMonitorProtocol)
            except (MissingDependencyError, RuntimeError) as e:
                self.logger.warning(f"Metrics service unavailable: {e}")
                metrics_service = None
            distributed_lock = await self.container.aget(DistributedLockProtocol)

            # Check 1: Pending requests count and age
            self.logger.info("Checking pending requests...")
            pending_issues = await self._check_pending_requests(access_ops)
            issues.extend(pending_issues)

            # Check 2: Error rates
            self.logger.info("Checking error rates...")
            error_issues = await self._check_error_rates(metrics_service)
            issues.extend(error_issues)

            # Check 3: Processing times
            self.logger.info("Checking processing times...")
            time_issues = await self._check_processing_times(access_ops)
            issues.extend(time_issues)

            # Check 4: Stale locks
            self.logger.info("Checking for stale locks...")
            lock_issues = await self._check_stale_locks(distributed_lock)
            issues.extend(lock_issues)

            # Check 5: System availability
            self.logger.info("Checking system availability...")
            availability_issues = await self._check_system_availability()
            issues.extend(availability_issues)

        except Exception as e:
            self.logger.error(f"Error during health checks: {e}", exc_info=True)
            issues.append(
                {
                    "severity": "critical",
                    "category": "monitor_error",
                    "message": f"Monitor health check failed: {str(e)}",
                    "details": {},
                }
            )

        return issues

    async def _check_pending_requests(self, ops) -> List[Dict[str, Any]]:
        """Check pending requests for issues."""
        issues = []

        try:
            pending = await ops.get_all_pending_requests()

            # Check total count
            if len(pending) > self.thresholds["pending_requests_max"]:
                issues.append(
                    {
                        "severity": "warning",
                        "category": "high_pending_count",
                        "message": f"High number of pending requests: {len(pending)}",
                        "details": {
                            "count": len(pending),
                            "threshold": self.thresholds["pending_requests_max"],
                        },
                    }
                )

            # Check for old pending requests
            current_time = time.time()
            old_threshold = current_time - (self.thresholds["old_pending_hours"] * 3600)

            old_requests = [r for r in pending if r.request_timestamp < old_threshold]
            if old_requests:
                oldest = min(r.request_timestamp for r in old_requests)
                age_hours = (current_time - oldest) / 3600

                issues.append(
                    {
                        "severity": "warning",
                        "category": "old_pending_requests",
                        "message": f'{len(old_requests)} requests pending > {self.thresholds["old_pending_hours"]}h',
                        "details": {
                            "count": len(old_requests),
                            "oldest_age_hours": round(age_hours, 1),
                            "user_ids": [r.user_id for r in old_requests[:5]],  # First 5
                        },
                    }
                )

        except Exception as e:
            self.logger.error(f"Error checking pending requests: {e}")
            issues.append(
                {
                    "severity": "error",
                    "category": "check_failed",
                    "message": "Failed to check pending requests",
                    "details": {"error": str(e)},
                }
            )

        return issues

    async def _check_error_rates(self, metrics_service) -> List[Dict[str, Any]]:
        """Check error rates from metrics."""
        issues = []

        # Handle case where metrics service is unavailable
        if metrics_service is None:
            self.logger.warning("Metrics service unavailable, skipping error rate check")
            return issues

        try:
            summary = await metrics_service.get_stats_summary()

            error_rate = summary.get("error_rate", 0) * 100
            if error_rate > self.thresholds["error_rate_percent"]:
                issues.append(
                    {
                        "severity": "warning",
                        "category": "high_error_rate",
                        "message": f"High error rate: {error_rate:.1f}%",
                        "details": {
                            "error_rate": error_rate,
                            "total_errors": summary.get("error", 0),
                            "total_requests": summary.get("created", 0),
                        },
                    }
                )

            # Check for rate limiting issues
            rate_limited = summary.get("rate_limited", 0)
            if rate_limited > 10:  # More than 10 rate limited in current period
                issues.append(
                    {
                        "severity": "info",
                        "category": "rate_limiting_active",
                        "message": f"{rate_limited} users rate limited",
                        "details": {"rate_limited_count": rate_limited},
                    }
                )

        except Exception as e:
            self.logger.error(f"Error checking error rates: {e}")

        return issues

    async def _check_processing_times(self, ops) -> List[Dict[str, Any]]:
        """Check average processing times."""
        issues = []

        try:
            # Get recent approved/rejected requests
            current_time = time.time()
            last_24h = current_time - 86400

            # We'll need to scan for recent decisions
            # This is a simplified check - in production you'd want more sophisticated tracking
            all_requests = []

            # Sample a few users to check processing times
            sample_users = ["U" + str(i).zfill(6) for i in range(100)]  # Sample check
            for user_id in sample_users:
                try:
                    history = await ops.get_user_request_history(user_id)
                    all_requests.extend(history)
                except Exception:
                    continue

            # Filter recent processed requests
            recent_processed = [
                r
                for r in all_requests
                if r.decision_timestamp
                and r.decision_timestamp > last_24h
                and r.status
                in [ACCESS_REQUEST_STATUS["APPROVED"], ACCESS_REQUEST_STATUS["REJECTED"]]
            ]

            if recent_processed:
                processing_times = [
                    r.decision_timestamp - r.request_timestamp for r in recent_processed
                ]
                avg_time_hours = sum(processing_times) / len(processing_times) / 3600

                if avg_time_hours > self.thresholds["approval_time_hours"]:
                    issues.append(
                        {
                            "severity": "info",
                            "category": "slow_processing",
                            "message": f"Average processing time: {avg_time_hours:.1f}h",
                            "details": {
                                "avg_hours": round(avg_time_hours, 1),
                                "sample_size": len(recent_processed),
                            },
                        }
                    )

        except Exception as e:
            self.logger.error(f"Error checking processing times: {e}")

        return issues

    async def _check_stale_locks(self, distributed_lock) -> List[Dict[str, Any]]:
        """Check for stale distributed locks."""
        issues = []

        try:
            # Check a sample of potential locks

            # In a real implementation, you'd scan the lock table
            # For now, we'll just note this check exists
            self.logger.info("Stale lock check placeholder - would scan lock table")

        except Exception as e:
            self.logger.error(f"Error checking stale locks: {e}")

        return issues

    async def _check_system_availability(self) -> List[Dict[str, Any]]:
        """Check overall system availability."""
        issues = []

        try:
            # Test critical services with protocol mapping
            critical_protocols = {
                "access_request_operations": AccessRequestOperationsProtocol,
                "access_request_handler": AccessRequestHandlerProtocol,
                "slack_async_client": SlackAsyncClientProtocol,
                "secrets_manager": SecretsManagerProtocol,
                "access_request_monitor": AccessRequestMonitorProtocol,
            }

            for service_name, protocol in critical_protocols.items():
                try:
                    service = await self.container.aget(protocol)
                    if service is None:
                        issues.append(
                            {
                                "severity": "critical",
                                "category": "service_unavailable",
                                "message": f"Service unavailable: {service_name}",
                                "details": {"service": service_name},
                            }
                        )
                except Exception as e:
                    issues.append(
                        {
                            "severity": "critical",
                            "category": "service_error",
                            "message": f"Service error: {service_name}",
                            "details": {"service": service_name, "error": str(e)},
                        }
                    )

        except Exception as e:
            self.logger.error(f"Error checking system availability: {e}")

        return issues

    async def send_alert(self, issues: List[Dict[str, Any]]):
        """Send alert to Slack if there are issues."""
        if not issues:
            return

        try:
            # Try to get webhook URL from secrets via TypedDI
            webhook_url = None
            try:
                secrets_manager = await self.container.aget(SecretsManagerProtocol)
                if secrets_manager:
                    webhook_url = await secrets_manager.get_slack_webhook_url()
            except Exception as e:
                self.logger.info(f"Could not get webhook from secrets: {e}")

            # Fall back to environment variable if not in secrets
            if not webhook_url:
                webhook_url = os.environ.get("KETCHUP_ALERTS_WEBHOOK")

            if webhook_url:
                await self.send_webhook_alert(issues, webhook_url)
                return

            # Fall back to bot token API
            slack_client = await self.container.aget(SlackAsyncClientProtocol)

            # Group issues by severity
            critical = [i for i in issues if i["severity"] == "critical"]
            errors = [i for i in issues if i["severity"] == "error"]
            warnings = [i for i in issues if i["severity"] == "warning"]
            info = [i for i in issues if i["severity"] == "info"]

            # Build alert blocks
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚨 Access Request System Alert"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Issues detected:* {len(issues)} total\n"
                        f"• Critical: {len(critical)}\n"
                        f"• Errors: {len(errors)}\n"
                        f"• Warnings: {len(warnings)}\n"
                        f"• Info: {len(info)}",
                    },
                },
            ]

            # Add issue details
            for issue in issues[:10]:  # Limit to first 10 to avoid huge messages
                icon = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "ℹ️"}.get(
                    issue["severity"], "❓"
                )

                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{icon} *{issue['category']}*\n{issue['message']}",
                        },
                    }
                )

            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Monitor check at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                        }
                    ],
                }
            )

            # Send alert
            await slack_client.api_call(
                "chat.postMessage",
                {
                    "channel": KETCHUP_ALERTS_CHANNEL,
                    "blocks": blocks,
                    "text": f"Access Request System Alert: {len(issues)} issues detected",
                },
            )

            self.logger.info(f"Alert sent for {len(issues)} issues")

        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}", exc_info=True)

    async def send_webhook_alert(self, issues: List[Dict[str, Any]], webhook_url: str):
        """Send alert via webhook URL."""
        try:
            # Group issues by severity
            critical = [i for i in issues if i["severity"] == "critical"]
            errors = [i for i in issues if i["severity"] == "error"]
            warnings = [i for i in issues if i["severity"] == "warning"]
            info = [i for i in issues if i["severity"] == "info"]

            # Build alert blocks
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚨 Access Request System Alert"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Issues detected:* {len(issues)} total\n"
                        f"• Critical: {len(critical)}\n"
                        f"• Errors: {len(errors)}\n"
                        f"• Warnings: {len(warnings)}\n"
                        f"• Info: {len(info)}",
                    },
                },
            ]

            # Add issue details
            for issue in issues[:10]:  # Limit to first 10 to avoid huge messages
                icon = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "ℹ️"}.get(
                    issue["severity"], "❓"
                )

                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{icon} *{issue['category']}*\n{issue['message']}",
                        },
                    }
                )

            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Monitor check at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                        }
                    ],
                }
            )

            # Send via webhook
            payload = {
                "text": f"Access Request System Alert: {len(issues)} issues detected",
                "blocks": blocks,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        self.logger.info(f"Webhook alert sent for {len(issues)} issues")
                    else:
                        text = await response.text()
                        self.logger.error(f"Webhook failed: {response.status} - {text}")

        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}", exc_info=True)

    def should_send_alert(self, issues: List[Dict[str, Any]]) -> bool:
        """Check if we should send an alert based on cooldown."""
        # Always alert for critical issues
        if any(i["severity"] == "critical" for i in issues):
            return True

        # Check cooldown for other issues
        current_time = time.time()
        categories = set(i["category"] for i in issues)

        for category in categories:
            last_alert = self.last_alerts.get(category, 0)
            if current_time - last_alert > self.alert_cooldown:
                return True

        return False

    def update_alert_times(self, issues: List[Dict[str, Any]]):
        """Update last alert times for categories."""
        current_time = time.time()
        for issue in issues:
            self.last_alerts[issue["category"]] = current_time

    async def run_monitoring_loop(self):
        """Run the main monitoring loop."""
        self.logger.info("Starting monitoring loop...")
        write_health_status("running")

        consecutive_errors = 0

        while True:
            try:
                # Write monitoring status
                write_health_status("monitoring")

                # Run health checks
                issues = await self.run_health_checks()

                if issues:
                    self.logger.warning(f"Found {len(issues)} issues")

                    # Check if we should send alert
                    if self.should_send_alert(issues):
                        await self.send_alert(issues)
                        self.update_alert_times(issues)
                    else:
                        self.logger.info("Alert suppressed due to cooldown")
                else:
                    self.logger.info("All health checks passed")

                # Reset error counter on success and write idle status
                consecutive_errors = 0
                write_health_status("idle")

            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                write_health_status("error")

                # If too many consecutive errors, send alert
                if consecutive_errors >= 3:
                    await self.send_alert(
                        [
                            {
                                "severity": "critical",
                                "category": "monitor_failure",
                                "message": f"Monitor failing repeatedly: {consecutive_errors} consecutive errors",
                                "details": {"last_error": str(e)},
                            }
                        ]
                    )
                    consecutive_errors = 0  # Reset after alert

            # Wait for next check
            await asyncio.sleep(self.check_interval)

    async def run(self):
        """Main entry point for the monitor."""
        try:
            await self.initialize()
            await self.run_monitoring_loop()
        except KeyboardInterrupt:
            self.logger.info("Monitor stopped by user")
        except Exception as e:
            self.logger.error(f"Monitor failed: {e}", exc_info=True)
        finally:
            self.logger.info("Monitor stopped")


def main():
    """Main entry point."""
    monitor = AccessRequestHealthMonitor()
    asyncio.run(monitor.run())


if __name__ == "__main__":
    main()
