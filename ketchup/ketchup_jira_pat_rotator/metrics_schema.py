#!/usr/bin/env python3
"""
Metrics schema for storing PAT rotation metrics in DynamoDB.

Defines tables, indexes, and data structures for tracking rotation
success/failure rates, timing, and backup PAT health.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class RotationStatus(str, Enum):
    """Status of a PAT rotation event."""
    SUCCESS = "success"
    FAILURE = "failure"
    IN_PROGRESS = "in_progress"


class BackupPATValidationStatus(str, Enum):
    """Status of backup PAT validation."""
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


@dataclass
class RotationMetrics:
    """Metrics for a single PAT rotation event."""
    timestamp: datetime
    rotation_id: str
    status: RotationStatus
    duration_seconds: float
    old_pat: str
    new_pat: str
    error_message: Optional[str] = None
    retry_count: int = 0

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert metrics to DynamoDB item format."""
        item = {
            "pk": f"ROT#{self.rotation_id}",
            "sk": self.timestamp.isoformat(),
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "old_pat_hash": hash(self.old_pat) if self.old_pat else None,
            "new_pat_hash": hash(self.new_pat) if self.new_pat else None,
            "retry_count": self.retry_count,
            "timestamp_epoch": int(self.timestamp.timestamp()),
            "ttl": int(self.timestamp.timestamp()) + (30 * 24 * 60 * 60),  # 30-day retention
        }
        if self.error_message:
            item["error_message"] = self.error_message
        return item


@dataclass
class BackupPATMetrics:
    """Metrics for backup PAT health."""
    timestamp: datetime
    backup_pat_exists: bool
    backup_pat_valid: bool
    days_until_expiry: Optional[int] = None
    last_validated_at: Optional[datetime] = None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert metrics to DynamoDB item format."""
        item = {
            "pk": "BACKUP#PAT",
            "sk": self.timestamp.isoformat(),
            "backup_pat_exists": self.backup_pat_exists,
            "backup_pat_valid": self.backup_pat_valid,
            "timestamp_epoch": int(self.timestamp.timestamp()),
            "ttl": int(self.timestamp.timestamp()) + (30 * 24 * 60 * 60),  # 30-day retention
        }
        if self.days_until_expiry is not None:
            item["days_until_expiry"] = self.days_until_expiry
        if self.last_validated_at:
            item["last_validated_at"] = self.last_validated_at.isoformat()
        return item


@dataclass
class HealthCheckMetrics:
    """Metrics for PAT health check events."""
    timestamp: datetime
    check_id: str
    status: str
    jira_accessible: bool
    response_time_ms: float
    error_details: Optional[str] = None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert metrics to DynamoDB item format."""
        item = {
            "pk": f"HEALTH#{self.check_id}",
            "sk": self.timestamp.isoformat(),
            "status": self.status,
            "jira_accessible": self.jira_accessible,
            "response_time_ms": self.response_time_ms,
            "timestamp_epoch": int(self.timestamp.timestamp()),
            "ttl": int(self.timestamp.timestamp()) + (30 * 24 * 60 * 60),  # 30-day retention
        }
        if self.error_details:
            item["error_details"] = self.error_details
        return item


class MetricsStorage:
    """DynamoDB storage for rotation metrics."""

    def __init__(self, dynamodb_resource: Any, table_name: str = "ketchup_jira_pat_rotations"):
        """
        Initialize metrics storage.

        Args:
            dynamodb_resource: Boto3 DynamoDB resource or mock
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = dynamodb_resource
        self.table_name = table_name

    def store_rotation_metrics(self, metrics: RotationMetrics) -> bool:
        """
        Store rotation metrics in DynamoDB.

        Args:
            metrics: RotationMetrics instance to store

        Returns:
            True if storage successful, False otherwise
        """
        try:
            item = metrics.to_dynamodb_item()
            self.dynamodb.put_item(Item=item)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to store rotation metrics: {e}")

    def store_backup_pat_metrics(self, metrics: BackupPATMetrics) -> bool:
        """
        Store backup PAT metrics in DynamoDB.

        Args:
            metrics: BackupPATMetrics instance to store

        Returns:
            True if storage successful, False otherwise
        """
        try:
            item = metrics.to_dynamodb_item()
            self.dynamodb.put_item(Item=item)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to store backup PAT metrics: {e}")

    def store_health_check_metrics(self, metrics: HealthCheckMetrics) -> bool:
        """
        Store health check metrics in DynamoDB.

        Args:
            metrics: HealthCheckMetrics instance to store

        Returns:
            True if storage successful, False otherwise
        """
        try:
            item = metrics.to_dynamodb_item()
            self.dynamodb.put_item(Item=item)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to store health check metrics: {e}")

    def query_rotation_metrics_by_date_range(self, start_date: datetime, end_date: datetime) -> list:
        """
        Query rotation metrics within a date range.

        Args:
            start_date: Start datetime
            end_date: End datetime

        Returns:
            List of rotation metrics
        """
        try:
            response = self.dynamodb.query(
                KeyConditionExpression="pk = :pk AND sk BETWEEN :start AND :end",
                ExpressionAttributeValues={
                    ":pk": "ROT#all",
                    ":start": start_date.isoformat(),
                    ":end": end_date.isoformat(),
                },
            )
            return response.get("Items", [])
        except Exception as e:
            raise RuntimeError(f"Failed to query rotation metrics: {e}")

    def query_metrics_by_status(self, status: RotationStatus, limit: int = 100) -> list:
        """
        Query metrics by rotation status.

        Args:
            status: RotationStatus enum value
            limit: Maximum number of results

        Returns:
            List of metrics
        """
        try:
            response = self.dynamodb.query(
                IndexName="status-timestamp-index",
                KeyConditionExpression="status = :status",
                ExpressionAttributeValues={
                    ":status": status.value,
                },
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
            return response.get("Items", [])
        except Exception as e:
            raise RuntimeError(f"Failed to query metrics by status: {e}")

    def get_backup_pat_health(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent backup PAT health metrics.

        Returns:
            Most recent backup PAT metrics or None
        """
        try:
            response = self.dynamodb.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={
                    ":pk": "BACKUP#PAT",
                },
                Limit=1,
                ScanIndexForward=False,  # Most recent first
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except Exception as e:
            raise RuntimeError(f"Failed to get backup PAT health: {e}")

    def get_aggregated_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get aggregated metrics for a given number of days.

        Args:
            days: Number of days to aggregate

        Returns:
            Aggregated metrics dictionary
        """
        try:
            from datetime import timedelta

            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            metrics = self.query_rotation_metrics_by_date_range(start_date, end_date)

            if not metrics:
                return {
                    "total_rotations": 0,
                    "successful_rotations": 0,
                    "failed_rotations": 0,
                    "success_rate": 0.0,
                    "average_duration_seconds": 0.0,
                }

            total = len(metrics)
            successful = sum(1 for m in metrics if m.get("status") == "success")
            failed = sum(1 for m in metrics if m.get("status") == "failure")
            avg_duration = sum(m.get("duration_seconds", 0) for m in metrics) / total if total > 0 else 0

            return {
                "total_rotations": total,
                "successful_rotations": successful,
                "failed_rotations": failed,
                "success_rate": (successful / total * 100) if total > 0 else 0.0,
                "average_duration_seconds": avg_duration,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get aggregated metrics: {e}")
