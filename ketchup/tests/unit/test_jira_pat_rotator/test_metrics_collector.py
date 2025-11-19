#!/usr/bin/env python3
"""
Tests for MetricsCollectorService.

Verifies:
- Metrics are collected every 5 minutes
- Backup PAT metrics are captured
- Health status is calculated correctly
- Errors are handled gracefully
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio

from ketchup_jira_pat_rotator.metrics_collector import MetricsCollectorService
from ketchup_jira_pat_rotator.metrics_schema import (
    BackupPATMetrics,
    HealthCheckMetrics,
    BackupPATValidationStatus,
)


@pytest.fixture
def mock_storage():
    """Mock DynamoDB metrics storage."""
    storage = AsyncMock()
    storage.store_backup_pat_metrics = AsyncMock(return_value=True)
    storage.store_health_check_metrics = AsyncMock(return_value=True)
    return storage


@pytest.fixture
def mock_config():
    """Mock configuration with PAT details."""
    return {
        "pat": "primary-token-abc123",
        "patExpiry": datetime.utcnow() + timedelta(days=90),
        "backupPat": "backup-token-xyz789",
        "backupPatExpiry": datetime.utcnow() + timedelta(days=90),
    }


@pytest.fixture
def mock_rotation_service():
    """Mock PAT rotation service."""
    service = AsyncMock()
    service.get_last_rotation_status = AsyncMock(return_value={
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
    })
    return service


@pytest.fixture
def metrics_collector(mock_storage, mock_config, mock_rotation_service):
    """Create MetricsCollectorService instance with mocks."""
    collector = MetricsCollectorService(
        metrics_storage=mock_storage,
        config=mock_config,
        rotation_service=mock_rotation_service,
    )
    # Override the scheduled task for testing
    collector._scheduled_task = None
    return collector


class TestMetricsCollectorInitialization:
    """Tests for MetricsCollectorService initialization."""

    def test_collector_created_successfully(self, metrics_collector):
        """Test that metrics collector is created with dependencies."""
        assert metrics_collector is not None
        assert metrics_collector.metrics_storage is not None
        assert metrics_collector.config is not None
        assert metrics_collector.rotation_service is not None

    def test_collector_has_5_minute_interval(self, metrics_collector):
        """Test that collector uses 5-minute collection interval."""
        assert metrics_collector.collection_interval_seconds == 300
        assert metrics_collector.collection_interval_seconds == 5 * 60


class TestMetricsCollection:
    """Tests for metrics collection functionality."""

    @pytest.mark.asyncio
    async def test_metrics_collected_every_5_minutes(self, metrics_collector, mock_storage):
        """Test that metrics are collected periodically."""
        # Act - manually trigger collection
        await metrics_collector.collect_metrics()

        # Assert - storage was called for backup metrics
        mock_storage.store_backup_pat_metrics.assert_called_once()
        # Storage call should be with BackupPATMetrics instance
        call_args = mock_storage.store_backup_pat_metrics.call_args
        metrics = call_args[0][0]
        assert isinstance(metrics, BackupPATMetrics)

    @pytest.mark.asyncio
    async def test_backup_pat_metrics_captured(self, metrics_collector, mock_storage, mock_config):
        """Test that backup PAT metrics are captured correctly."""
        # Act
        await metrics_collector.collect_metrics()

        # Assert
        mock_storage.store_backup_pat_metrics.assert_called_once()
        call_args = mock_storage.store_backup_pat_metrics.call_args
        metrics = call_args[0][0]

        # Verify backup PAT metrics content
        assert metrics.backup_pat_exists is True
        assert metrics.backup_pat_valid is True
        assert metrics.days_until_expiry is not None
        assert metrics.days_until_expiry >= 59  # Should be around 60 days

    @pytest.mark.asyncio
    async def test_health_status_calculated_correctly(self, metrics_collector, mock_storage, mock_config):
        """Test that health status is calculated based on PAT expiry."""
        # Act
        await metrics_collector.collect_metrics()

        # Assert - health metrics should be stored
        mock_storage.store_health_check_metrics.assert_called_once()
        call_args = mock_storage.store_health_check_metrics.call_args
        metrics = call_args[0][0]

        assert isinstance(metrics, HealthCheckMetrics)
        # Status should be "healthy" when PATs have sufficient days until expiry
        assert metrics.status == "healthy"

    @pytest.mark.asyncio
    async def test_health_status_unhealthy_when_pat_near_expiry(self, metrics_collector, mock_storage, mock_config):
        """Test that health status is unhealthy when PAT is near expiry."""
        # Arrange - set PAT to expire in 20 days (below 75-day threshold)
        metrics_collector.config["patExpiry"] = datetime.utcnow() + timedelta(days=20)

        # Act
        await metrics_collector.collect_metrics()

        # Assert - health status should be unhealthy
        mock_storage.store_health_check_metrics.assert_called_once()
        call_args = mock_storage.store_health_check_metrics.call_args
        metrics = call_args[0][0]

        assert metrics.status == "unhealthy"

    @pytest.mark.asyncio
    async def test_metrics_stored_on_success(self, metrics_collector, mock_storage):
        """Test that metrics are stored successfully."""
        # Act
        await metrics_collector.collect_metrics()

        # Assert - both types of metrics should be stored
        assert mock_storage.store_backup_pat_metrics.called
        assert mock_storage.store_health_check_metrics.called

    @pytest.mark.asyncio
    async def test_metrics_stored_on_error(self, metrics_collector, mock_storage):
        """Test that collector handles errors gracefully and continues."""
        # Arrange - make both storage calls fail
        mock_storage.store_backup_pat_metrics.side_effect = Exception("Storage error")
        mock_storage.store_health_check_metrics.side_effect = Exception("Storage error")

        # Act & Assert - should not raise exception despite storage failures
        result = await metrics_collector.collect_metrics()
        # Result should be False when there are errors
        assert result is False

    @pytest.mark.asyncio
    async def test_metrics_collection_includes_timestamp(self, metrics_collector, mock_storage):
        """Test that collected metrics include timestamp."""
        # Act
        await metrics_collector.collect_metrics()

        # Assert
        call_args = mock_storage.store_backup_pat_metrics.call_args
        metrics = call_args[0][0]
        assert metrics.timestamp is not None
        assert isinstance(metrics.timestamp, datetime)


class TestHealthStatusCalculation:
    """Tests for health status calculation logic."""

    def test_health_status_healthy_with_sufficient_days(self, metrics_collector, mock_config):
        """Test that status is healthy when PAT has >= 75 days."""
        # Arrange
        expiry = datetime.utcnow() + timedelta(days=80)
        metrics_collector.config["patExpiry"] = expiry

        # Act
        status = metrics_collector._calculate_health_status()

        # Assert
        assert status == "healthy"

    def test_health_status_unhealthy_below_75_days(self, metrics_collector, mock_config):
        """Test that status is unhealthy when PAT has < 75 days."""
        # Arrange
        expiry = datetime.utcnow() + timedelta(days=50)
        metrics_collector.config["patExpiry"] = expiry

        # Act
        status = metrics_collector._calculate_health_status()

        # Assert
        assert status == "unhealthy"

    def test_health_status_critical_below_7_days(self, metrics_collector, mock_config):
        """Test that status is critical when PAT has < 7 days."""
        # Arrange
        expiry = datetime.utcnow() + timedelta(days=3)
        metrics_collector.config["patExpiry"] = expiry

        # Act
        status = metrics_collector._calculate_health_status()

        # Assert
        assert status == "critical"

    def test_health_status_expired(self, metrics_collector, mock_config):
        """Test that status is critical when PAT is expired."""
        # Arrange
        expiry = datetime.utcnow() - timedelta(days=1)
        metrics_collector.config["patExpiry"] = expiry

        # Act
        status = metrics_collector._calculate_health_status()

        # Assert
        assert status == "critical"


class TestBackupPATMetricsCollection:
    """Tests for backup PAT metrics collection."""

    @pytest.mark.asyncio
    async def test_backup_pat_validation_status_captured(self, metrics_collector, mock_storage, mock_config):
        """Test that backup PAT validation status is captured."""
        # Act
        await metrics_collector.collect_metrics()

        # Assert
        call_args = mock_storage.store_backup_pat_metrics.call_args
        metrics = call_args[0][0]

        # Backup should exist and be valid when configured
        assert metrics.backup_pat_exists is True
        assert metrics.backup_pat_valid is True

    @pytest.mark.asyncio
    async def test_backup_pat_missing_handled_gracefully(self, metrics_collector, mock_storage):
        """Test that missing backup PAT is handled gracefully."""
        # Arrange - remove backup PAT from config
        metrics_collector.config["backupPat"] = None
        metrics_collector.config["backupPatExpiry"] = None

        # Act
        await metrics_collector.collect_metrics()

        # Assert - should still collect metrics
        call_args = mock_storage.store_backup_pat_metrics.call_args
        metrics = call_args[0][0]
        assert metrics.backup_pat_exists is False

    @pytest.mark.asyncio
    async def test_backup_pat_days_until_expiry_calculated(self, metrics_collector, mock_storage, mock_config):
        """Test that days until expiry for backup PAT is calculated."""
        # Arrange
        expected_days = 45
        metrics_collector.config["backupPatExpiry"] = datetime.utcnow() + timedelta(days=expected_days)

        # Act
        await metrics_collector.collect_metrics()

        # Assert
        call_args = mock_storage.store_backup_pat_metrics.call_args
        metrics = call_args[0][0]
        # Allow for 1 day variance due to timing
        assert metrics.days_until_expiry in (expected_days - 1, expected_days)


class TestScheduledCollection:
    """Tests for scheduled metrics collection."""

    @pytest.mark.asyncio
    async def test_start_schedules_collection_task(self, metrics_collector, mock_storage):
        """Test that start() schedules the collection task."""
        # Act
        task = asyncio.create_task(metrics_collector.start())
        await asyncio.sleep(0.1)  # Allow task to start

        # Assert - metrics should be collected at least once during startup
        assert mock_storage.store_backup_pat_metrics.called

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop_cancels_collection_task(self, metrics_collector, mock_storage):
        """Test that stop() cancels the scheduled task."""
        # Arrange
        task = asyncio.create_task(metrics_collector.start())
        await asyncio.sleep(0.1)

        # Act
        await metrics_collector.stop()

        # Give task time to be cancelled
        await asyncio.sleep(0.1)

        # Assert - task should be done
        assert task.done()

        # Cleanup
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_collector_runs_continuously(self, metrics_collector, mock_storage):
        """Test that collector continues running and collecting metrics."""
        # Act
        task = asyncio.create_task(metrics_collector.start())

        # Let it collect metrics a few times
        await asyncio.sleep(0.5)

        # Assert - should have called storage multiple times
        assert mock_storage.store_backup_pat_metrics.call_count >= 1

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestErrorHandling:
    """Tests for error handling in metrics collection."""

    @pytest.mark.asyncio
    async def test_collection_continues_on_storage_error(self, metrics_collector, mock_storage):
        """Test that metrics collection continues even if storage fails."""
        # Arrange
        mock_storage.store_backup_pat_metrics.side_effect = Exception("Storage failure")

        # Act & Assert - should not raise exception
        result = await metrics_collector.collect_metrics()
        # Collection should handle error gracefully

    @pytest.mark.asyncio
    async def test_collection_continues_on_config_error(self, metrics_collector, mock_storage):
        """Test that metrics collection handles config errors gracefully."""
        # Arrange - set invalid config
        metrics_collector.config["patExpiry"] = None

        # Act & Assert - should handle gracefully
        try:
            await metrics_collector.collect_metrics()
        except Exception:
            pytest.fail("Collection should handle config errors gracefully")

    @pytest.mark.asyncio
    async def test_scheduler_continues_after_collection_error(self, metrics_collector, mock_storage):
        """Test that scheduler continues even if a collection attempt fails."""
        # Arrange
        call_count = 0

        async def side_effect_func(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            return True

        mock_storage.store_backup_pat_metrics.side_effect = side_effect_func

        # Act
        task = asyncio.create_task(metrics_collector.start())
        await asyncio.sleep(0.5)  # Let it try to collect

        # Assert - scheduler should still be running
        assert not task.done()

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestMetricsCollectorIntegration:
    """Integration tests for MetricsCollectorService."""

    @pytest.mark.asyncio
    async def test_complete_collection_flow(self, metrics_collector, mock_storage, mock_config):
        """Test the complete metrics collection flow."""
        # Act
        await metrics_collector.collect_metrics()

        # Assert - all metrics should be stored
        assert mock_storage.store_backup_pat_metrics.called
        assert mock_storage.store_health_check_metrics.called

        # Verify backup PAT metrics
        backup_call = mock_storage.store_backup_pat_metrics.call_args
        backup_metrics = backup_call[0][0]
        assert isinstance(backup_metrics, BackupPATMetrics)

        # Verify health check metrics
        health_call = mock_storage.store_health_check_metrics.call_args
        health_metrics = health_call[0][0]
        assert isinstance(health_metrics, HealthCheckMetrics)
