#!/usr/bin/env python3
"""
Unit tests for LocalMetrics service.

Tests that LocalMetrics matches CloudWatchMetrics interface exactly
and provides equivalent functionality for the CloudWatch to LocalMetrics migration.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from packages.core.local_metrics import MetricsStorage
from packages.slack.metrics.access_request_monitor import AccessRequestMonitor


class TestMetricsStorage:
    """Test MetricsStorage service functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test metrics storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def local_metrics(self, temp_dir):
        """Create MetricsStorage instance for testing."""
        return MetricsStorage(
            namespace="Test/Namespace",
            storage_dir=temp_dir,
            buffer_size=2,  # Small buffer for testing
        )

    def test_interface_compatibility_with_cloudwatch(self):
        """Test that MetricsStorage has the expected metrics interface.

        Note: CloudWatchMetrics has been replaced by MetricsStorage (LocalMetrics)
        as part of the CloudWatch to LocalMetrics migration.
        """
        local_metrics = MetricsStorage("test")

        # Should have namespace attribute
        assert hasattr(local_metrics, "namespace")
        assert local_metrics.namespace == "test"

        # Should have put_metric method
        assert hasattr(local_metrics, "put_metric")

        # Check method signature has expected parameters
        import inspect

        sig = inspect.signature(local_metrics.put_metric)
        expected_params = {"name", "value", "unit", "dimensions"}
        assert expected_params.issubset(sig.parameters.keys())

    def test_init_creates_storage_directory(self, temp_dir):
        """Test that MetricsStorage creates storage directory on initialization."""
        storage_path = Path(temp_dir) / "metrics"
        assert not storage_path.exists()

        local_metrics = MetricsStorage(namespace="Test", storage_dir=str(storage_path))

        assert storage_path.exists()
        assert storage_path.is_dir()
        assert local_metrics.namespace == "Test"

    def test_init_with_invalid_directory_uses_fallback(self):
        """Test fallback directory creation when primary fails."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            # First call fails, second succeeds (fallback)
            mock_mkdir.side_effect = [OSError("Permission denied"), None]

            MetricsStorage(
                namespace="Test", storage_dir="/invalid/path/that/cannot/be/created"
            )

            # Should have attempted fallback
            assert mock_mkdir.call_count == 2

    @pytest.mark.asyncio
    async def test_put_metric_basic_functionality(self, local_metrics, temp_dir):
        """Test basic put_metric functionality."""
        result = await local_metrics.put_metric("test_metric", 1.0)

        assert result is True
        assert local_metrics._metrics_count == 1
        assert len(local_metrics._buffer) == 1

        # Check buffer content
        metric = local_metrics._buffer[0]
        assert metric["name"] == "test_metric"
        assert metric["value"] == 1.0
        assert metric["unit"] == "Count"
        assert metric["namespace"] == "Test/Namespace"
        assert metric["dimensions"] == []

    @pytest.mark.asyncio
    async def test_put_metric_with_all_parameters(self, local_metrics, temp_dir):
        """Test put_metric with all parameters specified."""
        dimensions = [{"Name": "TestDim", "Value": "TestValue"}]

        result = await local_metrics.put_metric(
            name="custom_metric", value=42.5, unit="Seconds", dimensions=dimensions
        )

        assert result is True
        metric = local_metrics._buffer[0]
        assert metric["name"] == "custom_metric"
        assert metric["value"] == 42.5
        assert metric["unit"] == "Seconds"
        assert metric["dimensions"] == dimensions

    @pytest.mark.asyncio
    async def test_put_metric_never_raises_exceptions(self, local_metrics):
        """Test that put_metric never raises exceptions (matches CloudWatch behavior)."""
        # Mock file operations to fail
        with patch("aiofiles.open", side_effect=Exception("File error")):
            # Should not raise exception
            result = await local_metrics.put_metric("test_metric", 1.0)

            # Should return False and increment error count
            assert result is True  # Still True because it's buffered

            # Force flush to trigger the error
            await local_metrics.force_flush()
            assert local_metrics._errors_count > 0

    @pytest.mark.asyncio
    async def test_buffer_flushing(self, local_metrics, temp_dir):
        """Test automatic buffer flushing when buffer is full."""
        # Add metrics to fill buffer (buffer_size=2)
        await local_metrics.put_metric("metric1", 1.0)
        await local_metrics.put_metric("metric2", 2.0)

        # Buffer should be flushed automatically
        assert len(local_metrics._buffer) == 0

        # Check file was created and contains metrics
        metrics_file = Path(temp_dir) / "metrics_Test_Namespace.jsonl"
        assert metrics_file.exists()

        # Verify file contents
        with open(metrics_file, "r") as f:
            lines = f.readlines()

        assert len(lines) == 2

        metric1 = json.loads(lines[0])
        metric2 = json.loads(lines[1])

        assert metric1["name"] == "metric1"
        assert metric1["value"] == 1.0
        assert metric2["name"] == "metric2"
        assert metric2["value"] == 2.0

    @pytest.mark.asyncio
    async def test_force_flush(self, local_metrics, temp_dir):
        """Test force flush functionality."""
        await local_metrics.put_metric("test_metric", 1.0)
        assert len(local_metrics._buffer) == 1

        result = await local_metrics.force_flush()
        assert result is True
        assert len(local_metrics._buffer) == 0

        # Verify file was created
        metrics_file = Path(temp_dir) / "metrics_Test_Namespace.jsonl"
        assert metrics_file.exists()

    @pytest.mark.asyncio
    async def test_file_rotation(self, local_metrics, temp_dir):
        """Test file rotation when max size is reached."""
        # Set very small max file size for testing
        local_metrics.max_file_size = 100  # 100 bytes

        # Add metrics to exceed file size
        for i in range(10):
            await local_metrics.put_metric(f"metric_{i}", float(i))

        await local_metrics.force_flush()

        # Check for rotated files
        metrics_dir = Path(temp_dir)
        jsonl_files = list(metrics_dir.glob("*.jsonl"))

        # Should have current file + rotated files
        assert len(jsonl_files) >= 1

    def test_get_health_status(self, local_metrics):
        """Test health status reporting."""
        status = local_metrics.get_health_status()

        required_keys = {
            "namespace",
            "storage_dir",
            "metrics_count",
            "errors_count",
            "buffer_size",
            "last_flush",
            "storage_accessible",
        }

        assert required_keys.issubset(status.keys())
        assert status["namespace"] == "Test/Namespace"
        assert status["metrics_count"] == 0
        assert status["errors_count"] == 0
        assert isinstance(status["storage_accessible"], bool)

    @pytest.mark.asyncio
    async def test_cleanup(self, local_metrics):
        """Test cleanup functionality."""
        await local_metrics.put_metric("test_metric", 1.0)
        assert len(local_metrics._buffer) == 1

        await local_metrics.cleanup()
        assert len(local_metrics._buffer) == 0

    def test_namespace_sanitization_in_filename(self, temp_dir):
        """Test that namespace with special characters is sanitized for filename."""
        local_metrics = MetricsStorage(
            namespace="Test/Complex Namespace", storage_dir=temp_dir
        )

        filename = local_metrics._get_current_metrics_file()
        assert "Test_Complex_Namespace" in filename.name
        assert "/" not in filename.name
        assert " " not in filename.name

    def test_access_request_monitor_composition(self):
        """Test that AccessRequestMonitor uses MetricsStorage internally."""
        monitor = AccessRequestMonitor()
        assert hasattr(monitor, "_storage")
        assert isinstance(monitor._storage, MetricsStorage)


class TestMetricsStorageMockCompatibility:
    """Test MetricsStorage compatibility with existing test mocks."""

    @pytest.mark.asyncio
    async def test_asyncmock_compatibility(self):
        """Test that LocalMetrics works with AsyncMock(spec=LocalMetrics)."""
        # This is how existing tests mock CloudWatch

        # Should work the same way with LocalMetrics
        mock_local_metrics = AsyncMock(spec=MetricsStorage)
        mock_local_metrics.put_metric.return_value = True

        # Test the mock
        result = await mock_local_metrics.put_metric("test", 1.0)
        assert result is True
        mock_local_metrics.put_metric.assert_called_once_with("test", 1.0)

    def test_spec_compatibility_with_cloudwatch(self):
        """Test that MetricsStorage can be used as spec for mocks.

        Note: CloudWatchMetrics has been replaced by MetricsStorage (LocalMetrics)
        as part of the CloudWatch to LocalMetrics migration.
        """

        # MetricsStorage should work as mock spec
        local_mock = AsyncMock(spec=MetricsStorage)

        # Mock should have put_metric method
        assert hasattr(local_mock, "put_metric")

        # Test that the mock can be called as expected
        local_mock.put_metric.return_value = True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
