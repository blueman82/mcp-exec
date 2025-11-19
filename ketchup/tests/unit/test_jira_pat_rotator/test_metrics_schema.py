#!/usr/bin/env python3
"""
Tests for metrics schema and DynamoDB storage.

Verifies:
- Rotation metrics are stored with correct schema
- Backup PAT metrics are stored correctly
- Date range queries work properly
- Metrics aggregation calculates correctly
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from ketchup_jira_pat_rotator.metrics_schema import (
    RotationMetrics,
    RotationStatus,
    BackupPATMetrics,
    BackupPATValidationStatus,
    HealthCheckMetrics,
    MetricsStorage,
)


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB resource."""
    return MagicMock()


@pytest.fixture
def sample_rotation_metrics():
    """Create sample rotation metrics."""
    return RotationMetrics(
        timestamp=datetime.utcnow(),
        rotation_id="rot-001",
        status=RotationStatus.SUCCESS,
        duration_seconds=12.5,
        old_pat="old-token-abc",
        new_pat="new-token-xyz",
    )


@pytest.fixture
def sample_backup_metrics():
    """Create sample backup PAT metrics."""
    return BackupPATMetrics(
        timestamp=datetime.utcnow(),
        backup_pat_exists=True,
        backup_pat_valid=True,
        days_until_expiry=45,
        last_validated_at=datetime.utcnow(),
    )


@pytest.fixture
def metrics_storage(mock_dynamodb):
    """Create metrics storage instance with mock."""
    return MetricsStorage(mock_dynamodb)


class TestRotationMetricsDataclass:
    """Tests for RotationMetrics dataclass."""

    def test_rotation_metrics_creation(self, sample_rotation_metrics):
        """Test that rotation metrics are created correctly."""
        assert sample_rotation_metrics.rotation_id == "rot-001"
        assert sample_rotation_metrics.status == RotationStatus.SUCCESS
        assert sample_rotation_metrics.duration_seconds == 12.5
        assert sample_rotation_metrics.retry_count == 0
        assert sample_rotation_metrics.error_message is None

    def test_rotation_metrics_with_error(self):
        """Test rotation metrics with error message."""
        metrics = RotationMetrics(
            timestamp=datetime.utcnow(),
            rotation_id="rot-002",
            status=RotationStatus.FAILURE,
            duration_seconds=5.2,
            old_pat="old-token",
            new_pat="new-token",
            error_message="PAT validation failed",
            retry_count=2,
        )
        assert metrics.error_message == "PAT validation failed"
        assert metrics.status == RotationStatus.FAILURE
        assert metrics.retry_count == 2

    def test_rotation_metrics_to_dynamodb_item(self, sample_rotation_metrics):
        """Test conversion of rotation metrics to DynamoDB item format."""
        item = sample_rotation_metrics.to_dynamodb_item()

        assert item["pk"] == f"ROT#{sample_rotation_metrics.rotation_id}"
        assert item["sk"] == sample_rotation_metrics.timestamp.isoformat()
        assert item["status"] == "success"
        assert item["duration_seconds"] == 12.5
        assert item["retry_count"] == 0
        assert "ttl" in item
        assert "timestamp_epoch" in item

    def test_rotation_metrics_to_dynamodb_item_with_error(self):
        """Test DynamoDB conversion with error message."""
        now = datetime.utcnow()
        metrics = RotationMetrics(
            timestamp=now,
            rotation_id="rot-003",
            status=RotationStatus.FAILURE,
            duration_seconds=2.1,
            old_pat="old",
            new_pat="new",
            error_message="Test error",
        )
        item = metrics.to_dynamodb_item()

        assert item["error_message"] == "Test error"
        assert item["status"] == "failure"


class TestBackupPATMetricsDataclass:
    """Tests for BackupPATMetrics dataclass."""

    def test_backup_pat_metrics_creation(self, sample_backup_metrics):
        """Test that backup PAT metrics are created correctly."""
        assert sample_backup_metrics.backup_pat_exists is True
        assert sample_backup_metrics.backup_pat_valid is True
        assert sample_backup_metrics.days_until_expiry == 45

    def test_backup_pat_metrics_to_dynamodb_item(self, sample_backup_metrics):
        """Test conversion of backup PAT metrics to DynamoDB item."""
        item = sample_backup_metrics.to_dynamodb_item()

        assert item["pk"] == "BACKUP#PAT"
        assert item["sk"] == sample_backup_metrics.timestamp.isoformat()
        assert item["backup_pat_exists"] is True
        assert item["backup_pat_valid"] is True
        assert item["days_until_expiry"] == 45
        assert "ttl" in item

    def test_backup_pat_metrics_invalid_backup(self):
        """Test backup PAT metrics when backup is invalid."""
        now = datetime.utcnow()
        metrics = BackupPATMetrics(
            timestamp=now,
            backup_pat_exists=False,
            backup_pat_valid=False,
            days_until_expiry=None,
        )
        item = metrics.to_dynamodb_item()

        assert item["backup_pat_exists"] is False
        assert item["backup_pat_valid"] is False
        assert "days_until_expiry" not in item


class TestHealthCheckMetrics:
    """Tests for HealthCheckMetrics dataclass."""

    def test_health_check_metrics_creation(self):
        """Test health check metrics creation."""
        metrics = HealthCheckMetrics(
            timestamp=datetime.utcnow(),
            check_id="check-001",
            status="healthy",
            jira_accessible=True,
            response_time_ms=245.5,
        )
        assert metrics.check_id == "check-001"
        assert metrics.jira_accessible is True
        assert metrics.response_time_ms == 245.5

    def test_health_check_metrics_to_dynamodb_item(self):
        """Test conversion of health check metrics to DynamoDB item."""
        now = datetime.utcnow()
        metrics = HealthCheckMetrics(
            timestamp=now,
            check_id="check-002",
            status="unhealthy",
            jira_accessible=False,
            response_time_ms=5000.0,
            error_details="Connection timeout",
        )
        item = metrics.to_dynamodb_item()

        assert item["pk"] == "HEALTH#check-002"
        assert item["status"] == "unhealthy"
        assert item["jira_accessible"] is False
        assert item["error_details"] == "Connection timeout"


class TestMetricsStorageRotation:
    """Tests for MetricsStorage rotation metrics operations."""

    def test_rotation_metrics_stored_correctly(self, metrics_storage, mock_dynamodb, sample_rotation_metrics):
        """Test that rotation metrics are stored with correct schema."""
        metrics_storage.store_rotation_metrics(sample_rotation_metrics)

        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["Item"]["pk"] == f"ROT#{sample_rotation_metrics.rotation_id}"
        assert call_args[1]["Item"]["sk"] == sample_rotation_metrics.timestamp.isoformat()
        assert call_args[1]["Item"]["status"] == "success"

    def test_store_rotation_metrics_with_failure(self, metrics_storage, mock_dynamodb):
        """Test storing failed rotation metrics."""
        metrics = RotationMetrics(
            timestamp=datetime.utcnow(),
            rotation_id="rot-fail-001",
            status=RotationStatus.FAILURE,
            duration_seconds=8.3,
            old_pat="old",
            new_pat="new",
            error_message="Validation failed",
            retry_count=3,
        )
        metrics_storage.store_rotation_metrics(metrics)

        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["Item"]["status"] == "failure"
        assert call_args[1]["Item"]["error_message"] == "Validation failed"
        assert call_args[1]["Item"]["retry_count"] == 3

    def test_rotation_metrics_storage_error_handling(self, metrics_storage, mock_dynamodb):
        """Test error handling when storage fails."""
        mock_dynamodb.put_item.side_effect = Exception("DynamoDB error")
        metrics = RotationMetrics(
            timestamp=datetime.utcnow(),
            rotation_id="rot-error",
            status=RotationStatus.SUCCESS,
            duration_seconds=10.0,
            old_pat="old",
            new_pat="new",
        )

        with pytest.raises(RuntimeError, match="Failed to store rotation metrics"):
            metrics_storage.store_rotation_metrics(metrics)


class TestMetricsStorageBackupPAT:
    """Tests for MetricsStorage backup PAT operations."""

    def test_backup_pat_metrics_stored_correctly(self, metrics_storage, mock_dynamodb, sample_backup_metrics):
        """Test that backup PAT metrics are stored correctly."""
        metrics_storage.store_backup_pat_metrics(sample_backup_metrics)

        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["Item"]["pk"] == "BACKUP#PAT"
        assert call_args[1]["Item"]["backup_pat_exists"] is True

    def test_backup_pat_metrics_storage_error(self, metrics_storage, mock_dynamodb):
        """Test error handling for backup PAT storage."""
        mock_dynamodb.put_item.side_effect = Exception("Storage error")
        metrics = BackupPATMetrics(
            timestamp=datetime.utcnow(),
            backup_pat_exists=True,
            backup_pat_valid=True,
        )

        with pytest.raises(RuntimeError, match="Failed to store backup PAT metrics"):
            metrics_storage.store_backup_pat_metrics(metrics)


class TestMetricsStorageHealthCheck:
    """Tests for MetricsStorage health check operations."""

    def test_health_check_metrics_stored_correctly(self, metrics_storage, mock_dynamodb):
        """Test that health check metrics are stored correctly."""
        metrics = HealthCheckMetrics(
            timestamp=datetime.utcnow(),
            check_id="check-001",
            status="healthy",
            jira_accessible=True,
            response_time_ms=150.0,
        )
        metrics_storage.store_health_check_metrics(metrics)

        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["Item"]["pk"] == "HEALTH#check-001"
        assert call_args[1]["Item"]["jira_accessible"] is True


class TestMetricsQueryOperations:
    """Tests for metrics query operations."""

    def test_metrics_query_by_date_range(self, metrics_storage, mock_dynamodb):
        """Test querying metrics by date range."""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        mock_dynamodb.query.return_value = {"Items": []}

        result = metrics_storage.query_rotation_metrics_by_date_range(start_date, end_date)

        assert result == []

    def test_metrics_query_by_status(self, metrics_storage, mock_dynamodb):
        """Test querying metrics by status."""
        mock_dynamodb.query.return_value = {"Items": []}

        result = metrics_storage.query_metrics_by_status(RotationStatus.SUCCESS)

        assert result == []

    def test_get_backup_pat_health(self, metrics_storage, mock_dynamodb):
        """Test retrieving backup PAT health metrics."""
        mock_dynamodb.query.return_value = {"Items": []}

        result = metrics_storage.get_backup_pat_health()

        assert result is None


class TestMetricsAggregation:
    """Tests for metrics aggregation."""

    def test_metrics_aggregation_empty(self, metrics_storage, mock_dynamodb):
        """Test aggregation with no metrics."""
        mock_dynamodb.query.return_value = {"Items": []}

        with patch.object(metrics_storage, 'query_rotation_metrics_by_date_range', return_value=[]):
            result = metrics_storage.get_aggregated_metrics(days=7)

            assert result["total_rotations"] == 0
            assert result["successful_rotations"] == 0
            assert result["failed_rotations"] == 0
            assert result["success_rate"] == 0.0
            assert result["average_duration_seconds"] == 0.0

    def test_metrics_aggregation_with_data(self, metrics_storage):
        """Test aggregation with sample metrics."""
        metrics_data = [
            {"status": "success", "duration_seconds": 10.0},
            {"status": "success", "duration_seconds": 15.0},
            {"status": "failure", "duration_seconds": 5.0},
        ]

        with patch.object(
            metrics_storage,
            'query_rotation_metrics_by_date_range',
            return_value=metrics_data
        ):
            result = metrics_storage.get_aggregated_metrics(days=7)

            assert result["total_rotations"] == 3
            assert result["successful_rotations"] == 2
            assert result["failed_rotations"] == 1
            assert result["success_rate"] == pytest.approx(66.666, rel=0.01)
            assert result["average_duration_seconds"] == pytest.approx(10.0, rel=0.01)

    def test_metrics_aggregation_all_successful(self, metrics_storage):
        """Test aggregation when all rotations succeed."""
        metrics_data = [
            {"status": "success", "duration_seconds": 12.0},
            {"status": "success", "duration_seconds": 14.0},
        ]

        with patch.object(
            metrics_storage,
            'query_rotation_metrics_by_date_range',
            return_value=metrics_data
        ):
            result = metrics_storage.get_aggregated_metrics(days=7)

            assert result["total_rotations"] == 2
            assert result["successful_rotations"] == 2
            assert result["failed_rotations"] == 0
            assert result["success_rate"] == 100.0
            assert result["average_duration_seconds"] == 13.0

    def test_metrics_aggregation_error_handling(self, metrics_storage):
        """Test error handling in aggregation."""
        with patch.object(
            metrics_storage,
            'query_rotation_metrics_by_date_range',
            side_effect=Exception("Query error")
        ):
            with pytest.raises(RuntimeError, match="Failed to get aggregated metrics"):
                metrics_storage.get_aggregated_metrics(days=7)
