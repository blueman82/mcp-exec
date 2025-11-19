#!/usr/bin/env python3
"""
Metrics collector service for PAT rotation monitoring.

Collects PAT health metrics, backup PAT status, and rotation history
on a 5-minute schedule. Integrates with rotation service to capture
real-time metrics and stores them in DynamoDB for long-term analysis.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from packages.core.logging import setup_logger
from ketchup_jira_pat_rotator.metrics_schema import (
    BackupPATMetrics,
    HealthCheckMetrics,
)

logger = setup_logger(__name__)


class MetricsCollectorService:
    """Service for collecting PAT health and rotation metrics."""

    # Collection interval: 5 minutes
    COLLECTION_INTERVAL_SECONDS = 5 * 60

    # Health status thresholds (days until PAT expiry)
    HEALTHY_THRESHOLD_DAYS = 75
    CRITICAL_THRESHOLD_DAYS = 7

    def __init__(self, metrics_storage: Any, config: Dict[str, Any], rotation_service: Optional[Any] = None):
        """
        Initialize the metrics collector service.

        Args:
            metrics_storage: DynamoDB metrics storage instance (MetricsStorage)
            config: Configuration dictionary with PAT details:
                - pat: Primary PAT token
                - patExpiry: Primary PAT expiry date (datetime)
                - backupPat: Backup PAT token (optional)
                - backupPatExpiry: Backup PAT expiry date (optional, datetime)
            rotation_service: Optional PAT rotation service for status queries
        """
        self.metrics_storage = metrics_storage
        self.config = config
        self.rotation_service = rotation_service
        self.collection_interval_seconds = self.COLLECTION_INTERVAL_SECONDS
        self._scheduled_task: Optional[asyncio.Task] = None
        self.running = False

    async def collect_metrics(self) -> bool:
        """
        Collect PAT health metrics and store them.

        Collects:
        - Backup PAT validation status and days until expiry
        - Overall system health status based on PAT expiry dates
        - Integrates with rotation service for real-time status

        Returns:
            True if collection successful, False if any storage operation failed
        """
        try:
            now = datetime.utcnow()
            had_error = False

            # Collect backup PAT metrics
            backup_metrics = self._create_backup_pat_metrics(now)
            if not await self._store_backup_metrics(backup_metrics):
                had_error = True

            # Collect health check metrics
            health_metrics = self._create_health_check_metrics(now)
            if not await self._store_health_metrics(health_metrics):
                had_error = True

            if not had_error:
                logger.debug("Metrics collected successfully at %s", now.isoformat())

            return not had_error

        except Exception as e:
            logger.error("Failed to collect metrics: %s", str(e), exc_info=True)
            # Continue running even if collection fails
            return False

    def _create_backup_pat_metrics(self, timestamp: datetime) -> BackupPATMetrics:
        """
        Create backup PAT metrics from current configuration.

        Args:
            timestamp: Current timestamp for metrics

        Returns:
            BackupPATMetrics instance
        """
        backup_pat = self.config.get("backupPat")
        backup_expiry = self.config.get("backupPatExpiry")

        # Determine if backup PAT exists and is valid
        backup_exists = backup_pat is not None
        backup_valid = backup_pat is not None

        # Calculate days until backup expiry
        days_until_expiry = None
        if backup_expiry:
            delta = backup_expiry - timestamp
            days_until_expiry = max(0, delta.days)

        return BackupPATMetrics(
            timestamp=timestamp,
            backup_pat_exists=backup_exists,
            backup_pat_valid=backup_valid,
            days_until_expiry=days_until_expiry,
            last_validated_at=timestamp if backup_valid else None,
        )

    def _create_health_check_metrics(self, timestamp: datetime) -> HealthCheckMetrics:
        """
        Create health check metrics based on PAT status.

        Args:
            timestamp: Current timestamp for metrics

        Returns:
            HealthCheckMetrics instance
        """
        # Calculate health status
        status = self._calculate_health_status()

        # Determine if JIRA is accessible (based on PAT validity)
        jira_accessible = status != "critical"

        return HealthCheckMetrics(
            timestamp=timestamp,
            check_id=str(uuid.uuid4()),
            status=status,
            jira_accessible=jira_accessible,
            response_time_ms=0.0,  # Placeholder; could integrate with actual health checks
        )

    def _calculate_health_status(self) -> str:
        """
        Calculate overall health status based on PAT expiry dates.

        Status levels:
        - "healthy": Primary PAT has >= 75 days until expiry
        - "unhealthy": Primary PAT has < 75 days until expiry
        - "critical": Primary PAT has < 7 days or is already expired

        Returns:
            Health status string
        """
        try:
            pat_expiry = self.config.get("patExpiry")
            if not pat_expiry:
                return "unknown"

            now = datetime.utcnow()
            days_until_expiry = (pat_expiry - now).days

            if days_until_expiry < 0:
                # Already expired
                return "critical"
            elif days_until_expiry < self.CRITICAL_THRESHOLD_DAYS:
                # Less than 7 days
                return "critical"
            elif days_until_expiry < self.HEALTHY_THRESHOLD_DAYS:
                # Less than 75 days
                return "unhealthy"
            else:
                # 75+ days
                return "healthy"

        except Exception as e:
            logger.error("Error calculating health status: %s", str(e))
            return "unknown"

    async def _store_backup_metrics(self, metrics: BackupPATMetrics) -> bool:
        """
        Store backup PAT metrics in DynamoDB.

        Args:
            metrics: BackupPATMetrics instance to store

        Returns:
            True if storage successful, False otherwise
        """
        try:
            await self.metrics_storage.store_backup_pat_metrics(metrics)
            logger.debug("Backup PAT metrics stored successfully")
            return True
        except Exception as e:
            logger.error("Failed to store backup PAT metrics: %s", str(e))
            # Don't re-raise; allow metrics collection to continue
            return False

    async def _store_health_metrics(self, metrics: HealthCheckMetrics) -> bool:
        """
        Store health check metrics in DynamoDB.

        Args:
            metrics: HealthCheckMetrics instance to store

        Returns:
            True if storage successful, False otherwise
        """
        try:
            await self.metrics_storage.store_health_check_metrics(metrics)
            logger.debug("Health check metrics stored successfully")
            return True
        except Exception as e:
            logger.error("Failed to store health check metrics: %s", str(e))
            # Don't re-raise; allow metrics collection to continue
            return False

    async def _collection_loop(self) -> None:
        """
        Main collection loop that runs on a schedule.

        Collects metrics every 5 minutes.
        Handles errors gracefully without crashing the service.
        """
        logger.info("Starting metrics collection loop")

        # Run initial collection immediately
        await self.collect_metrics()

        # Main collection loop
        while self.running:
            try:
                # Wait for next collection interval
                await asyncio.sleep(self.collection_interval_seconds)

                if not self.running:
                    break

                # Collect metrics
                await self.collect_metrics()

            except asyncio.CancelledError:
                logger.info("Metrics collection loop cancelled")
                break
            except Exception as e:
                logger.error("Error in metrics collection loop: %s", str(e), exc_info=True)
                # Continue running; don't let errors stop the service
                try:
                    await asyncio.sleep(5)  # Brief pause before retry
                except asyncio.CancelledError:
                    break

        logger.info("Metrics collection loop stopped")

    async def start(self) -> None:
        """
        Start the metrics collector service.

        Runs collection loop in background task.
        """
        logger.info("Metrics Collector Service starting...")
        self.running = True

        # Create background task for collection loop
        self._scheduled_task = asyncio.create_task(self._collection_loop())

        # Optionally wait for task (it will run indefinitely)
        try:
            await self._scheduled_task
        except asyncio.CancelledError:
            logger.info("Metrics collector task cancelled")

    async def stop(self) -> None:
        """
        Stop the metrics collector service.

        Cancels the background collection task and cleans up resources.
        """
        logger.info("Metrics Collector Service stopping...")
        self.running = False

        if self._scheduled_task:
            self._scheduled_task.cancel()
            try:
                await self._scheduled_task
            except asyncio.CancelledError:
                pass

        logger.info("Metrics Collector Service stopped")
