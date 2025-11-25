"""
access_request_monitor.py

Access request monitoring service with Slack alerting capabilities.
Monitors access request metrics and sends alerts when thresholds are exceeded.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

from packages.core.constants import (
    ACCESS_REQUEST_METRICS_LOG_FILE,
    ACCESS_REQUEST_STATS_FILE,
    KETCHUP_ALERTS_CHANNEL,
)
from packages.core.local_metrics import MetricsStorage
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class AccessRequestMonitor:
    """Access request monitoring service with Slack alerting capabilities."""

    def __init__(self, slack_client=None):
        """
        Initialize access request monitoring service.

        Args:
            slack_client: Optional Slack client for sending alerts
        """
        # Use MetricsStorage as the core storage engine
        self._storage = MetricsStorage(
            namespace="AccessRequests",
            storage_dir=os.path.dirname(ACCESS_REQUEST_METRICS_LOG_FILE),
            max_file_size=5 * 1024 * 1024,  # 5MB for access requests
            max_files=10,
        )

        # Keep legacy file paths for compatibility
        self.stats_file = ACCESS_REQUEST_STATS_FILE
        self.log_file = ACCESS_REQUEST_METRICS_LOG_FILE
        self.slack_client = slack_client  # Optional, for sending alerts
        self.alert_thresholds = {
            "access_request_error": 5,  # Alert after 5 errors in an hour
            "access_request_rate_limited": 10,  # Alert after 10 rate limits
            "secrets_update_failed": 1,  # Alert immediately on secrets failure
        }

        # Ensure legacy stats directory exists for compatibility
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
            logger.info("Access request monitoring initialized with MetricsStorage")
        except OSError as e:
            logger.error("Failed to create legacy stats directory: %s", e)

    async def increment_metric(
        self, metric_name: str, value: int = 1, **kwargs
    ) -> None:
        """
        Increment a metric by the specified value.

        Args:
            metric_name: Name of the metric to increment
            value: Value to increment by (default: 1)
            **kwargs: Additional metadata to log
        """
        try:
            # Store via MetricsStorage (primary storage)
            dimensions = (
                [{"key": k, "value": str(v)} for k, v in kwargs.items()]
                if kwargs
                else None
            )
            await self._storage.put_metric(
                metric_name, float(value), unit="Count", dimensions=dimensions
            )

            # Update aggregated stats for alerting (legacy compatibility)
            await self._update_stats(metric_name, value)

            # Check for alerts
            if self.slack_client:
                await self._check_alert_thresholds(metric_name)

            logger.info(
                "Incremented metric %s by %d via MetricsStorage", metric_name, value
            )

        except Exception as e:
            logger.error("Failed to increment metric %s: %s", metric_name, e)

    async def _update_stats(self, metric_name: str, value: int) -> None:
        """Update aggregated statistics file."""
        try:
            # Load existing stats
            stats = {}
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r") as f:
                    stats = json.load(f)

            # Update stats
            if metric_name not in stats:
                stats[metric_name] = {
                    "total": 0,
                    "hourly": {},
                    "daily": {},
                    "last_updated": None,
                }

            stats[metric_name]["total"] += value

            # Current hour and day keys for bucketing
            now = datetime.now(timezone.utc)
            hour_key = now.strftime("%Y-%m-%d_%H")
            day_key = now.strftime("%Y-%m-%d")

            stats[metric_name]["hourly"][hour_key] = (
                stats[metric_name]["hourly"].get(hour_key, 0) + value
            )
            stats[metric_name]["daily"][day_key] = (
                stats[metric_name]["daily"].get(day_key, 0) + value
            )
            stats[metric_name]["last_updated"] = now.isoformat()

            # Clean up old hourly data (keep last 24 hours)
            cutoff_time = time.time() - (24 * 3600)
            to_remove = []
            for hour_key in stats[metric_name]["hourly"]:
                try:
                    hour_timestamp = datetime.strptime(
                        hour_key, "%Y-%m-%d_%H"
                    ).timestamp()
                    if hour_timestamp < cutoff_time:
                        to_remove.append(hour_key)
                except ValueError:
                    continue

            for hour_key in to_remove:
                del stats[metric_name]["hourly"][hour_key]

            # Save updated stats
            with open(self.stats_file, "w") as f:
                json.dump(stats, f, indent=2)

        except Exception as e:
            logger.error("Failed to update stats for metric %s: %s", metric_name, e)

    async def _check_alert_thresholds(self, metric_name: str) -> None:
        """Check if metric has exceeded alert thresholds."""
        try:
            if metric_name not in self.alert_thresholds:
                return

            threshold = self.alert_thresholds[metric_name]

            # Get current hour count
            current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H")
            hourly_count = await self._get_hourly_count(metric_name, current_hour)

            if hourly_count >= threshold:
                alert_message = (
                    f"🚨 *Access Request Alert*\n"
                    f"Metric: `{metric_name}`\n"
                    f"Count in current hour: {hourly_count}\n"
                    f"Threshold: {threshold}\n"
                    f"Time: {datetime.now(timezone.utc).isoformat()}"
                )

                await self._send_alert(alert_message)
                logger.warning(
                    "Alert sent for metric %s: %d >= %d",
                    metric_name,
                    hourly_count,
                    threshold,
                )

        except Exception as e:
            logger.error("Failed to check alert thresholds for %s: %s", metric_name, e)

    async def _get_hourly_count(self, metric_name: str, hour_key: str) -> int:
        """Get count for a specific hour."""
        try:
            if not os.path.exists(self.stats_file):
                return 0

            with open(self.stats_file, "r") as f:
                stats = json.load(f)

            return stats.get(metric_name, {}).get("hourly", {}).get(hour_key, 0)

        except Exception as e:
            logger.error("Failed to get hourly count for %s: %s", metric_name, e)
            return 0

    async def _send_alert(self, message: str) -> None:
        """Send alert message to Slack."""
        try:
            if not self.slack_client:
                logger.warning("No Slack client available for alert: %s", message)
                return

            await self.slack_client.chat_postMessage(
                channel=KETCHUP_ALERTS_CHANNEL, text=message
            )

        except Exception as e:
            logger.error("Failed to send alert: %s", e)

    async def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        try:
            if not os.path.exists(self.stats_file):
                return {}

            with open(self.stats_file, "r") as f:
                stats = json.load(f)

            # Convert defaultdict to regular dict for JSON serialization
            cleaned_stats = {}
            for metric_name, data in stats.items():
                cleaned_stats[metric_name] = {
                    "total": data["total"],
                    "hourly": dict(data["hourly"]),
                    "daily": dict(data["daily"]),
                    "last_updated": data["last_updated"],
                }

            return cleaned_stats

        except Exception as e:
            logger.error("Failed to get stats summary: %s", e)
            return {}

    async def cleanup(self) -> None:
        """Cleanup resources and delegate to MetricsStorage."""
        try:
            await self._storage.cleanup()
            logger.info("AccessRequestMonitor cleanup completed")
        except Exception as e:
            logger.error("Error during AccessRequestMonitor cleanup: %s", e)
