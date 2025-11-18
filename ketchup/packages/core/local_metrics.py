"""
local_metrics.py

Core metrics storage engine for application telemetry.
Provides async file-based metrics storage with JSON Lines format, file rotation, and health monitoring.

Features:
- Thread-safe async implementation
- File-based storage with rotation and safety
- Graceful error handling (no exceptions thrown)
- Health monitoring and diagnostics
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class MetricsStorage:
    """
    Core metrics storage engine for application telemetry.

    Features:
    - Thread-safe async implementation
    - JSON Lines file format for easy parsing
    - File rotation to prevent disk space issues
    - Graceful error handling (no exceptions thrown)
    - Health monitoring and diagnostics
    """

    def __init__(
        self,
        namespace: str,
        storage_dir: str = "/var/log/ketchup",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_files: int = 5,
        buffer_size: int = 100,
    ):
        """
        Initialize the MetricsStorage service.

        Args:
            namespace: The metrics namespace for categorization
            storage_dir: Directory for storing metrics files
            max_file_size: Maximum size per file before rotation
            max_files: Maximum number of rotated files to keep
            buffer_size: Number of metrics to buffer before flush
        """
        self.namespace = namespace
        self.storage_dir = Path(storage_dir)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.buffer_size = buffer_size

        # Internal state
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._metrics_count = 0
        self._errors_count = 0
        self._last_flush = time.time()

        # Initialize storage
        self._ensure_storage_directory()

        logger.info(
            "MetricsStorage initialized with namespace='%s', storage_dir='%s'",
            namespace,
            storage_dir,
        )

    def _ensure_storage_directory(self) -> None:
        """Ensure the storage directory exists with proper permissions."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Metrics storage directory ensured at: %s", self.storage_dir)
        except OSError as e:
            logger.error(
                "Failed to create metrics directory %s: %s", self.storage_dir, e
            )
            # Try fallback to current directory
            try:
                fallback_dir = Path.cwd() / "ketchup_metrics"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                self.storage_dir = fallback_dir
                logger.warning("Using fallback metrics directory: %s", self.storage_dir)
            except OSError:
                logger.error(
                    "Failed to create fallback directory, metrics will be lost"
                )

    async def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """
        Store a metric locally using JSON Lines format.

        Args:
            name: The name of the metric
            value: The value of the metric
            unit: The unit of the metric (default: Count)
            dimensions: Optional list of dimensions for the metric

        Returns:
            Boolean indicating success or failure (never raises exceptions)
        """
        logger.info("Storing metric %s with value %s locally", name, value)

        try:
            # Create metric entry in JSON Lines format
            metric_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "namespace": self.namespace,
                "name": name,
                "value": value,
                "unit": unit,
                "dimensions": dimensions or [],
            }

            # Add to buffer thread-safely
            async with self._buffer_lock:
                self._buffer.append(metric_entry)
                self._metrics_count += 1

                # Flush if buffer is full
                if len(self._buffer) >= self.buffer_size:
                    await self._flush_buffer()

            logger.info("Successfully buffered metric %s", name)
            return True

        except Exception as e:
            self._errors_count += 1
            logger.error("Error storing metric %s: %s", name, str(e))
            return False

    async def _flush_buffer(self) -> None:
        """Flush buffered metrics to disk."""
        if not self._buffer:
            return

        async with self._write_lock:
            try:
                current_file = self._get_current_metrics_file()

                # Check if rotation is needed
                if await self._should_rotate_file(current_file):
                    await self._rotate_files()
                    current_file = self._get_current_metrics_file()

                # Write buffered metrics
                async with aiofiles.open(current_file, "a") as f:
                    for metric in self._buffer:
                        await f.write(json.dumps(metric) + "\n")

                logger.info("Flushed %d metrics to %s", len(self._buffer), current_file)
                self._buffer.clear()
                self._last_flush = time.time()

            except Exception as e:
                self._errors_count += 1
                logger.error("Error flushing metrics buffer: %s", e)

    def _get_current_metrics_file(self) -> Path:
        """Get the current metrics file path."""
        # Use namespace to create unique filename
        safe_namespace = self.namespace.replace("/", "_").replace(" ", "_")
        return self.storage_dir / f"metrics_{safe_namespace}.jsonl"

    async def _should_rotate_file(self, file_path: Path) -> bool:
        """Check if file rotation is needed."""
        try:
            if not file_path.exists():
                return False
            return file_path.stat().st_size >= self.max_file_size
        except OSError:
            return False

    async def _rotate_files(self) -> None:
        """Rotate metrics files to prevent disk space issues."""
        try:
            current_file = self._get_current_metrics_file()

            if not current_file.exists():
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_file = current_file.with_suffix(f".{timestamp}.jsonl")

            # Rename current file
            current_file.rename(rotated_file)

            # Clean up old files
            await self._cleanup_old_files()

            logger.info("Rotated metrics file to %s", rotated_file)

        except Exception as e:
            logger.error("Error rotating metrics files: %s", e)

    async def _cleanup_old_files(self) -> None:
        """Remove old rotated files to prevent disk space issues."""
        try:
            safe_namespace = self.namespace.replace("/", "_").replace(" ", "_")
            pattern = f"metrics_{safe_namespace}.*.jsonl"

            # Get all rotated files
            rotated_files = list(self.storage_dir.glob(pattern))

            # Sort by creation time (newest first)
            rotated_files.sort(key=lambda p: p.stat().st_ctime, reverse=True)

            # Remove files beyond max_files limit
            for old_file in rotated_files[self.max_files :]:
                old_file.unlink()
                logger.info("Removed old metrics file: %s", old_file)

        except Exception as e:
            logger.error("Error cleaning up old metrics files: %s", e)

    async def force_flush(self) -> bool:
        """Force flush all buffered metrics to disk."""
        try:
            async with self._buffer_lock:
                await self._flush_buffer()
            logger.info("Force flushed all buffered metrics")
            return True
        except Exception as e:
            logger.error("Error force flushing metrics: %s", e)
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """Get health and diagnostic information."""
        return {
            "namespace": self.namespace,
            "storage_dir": str(self.storage_dir),
            "metrics_count": self._metrics_count,
            "errors_count": self._errors_count,
            "buffer_size": len(self._buffer),
            "last_flush": self._last_flush,
            "storage_accessible": self.storage_dir.exists()
            and self.storage_dir.is_dir(),
        }

    async def cleanup(self) -> None:
        """Cleanup resources (flush remaining metrics)."""
        try:
            await self.force_flush()
            logger.info("MetricsStorage cleanup completed")
        except Exception as e:
            logger.error("Error during MetricsStorage cleanup: %s", e)
