#!/usr/bin/env python3
"""
Tests for BaseScheduler abstract base class.

Tests cover:
- Initialization with various configurations
- Signal handling for graceful shutdown
- Health file management
- Last run file tracking
- Interval-based scheduling
- Time-based scheduling via get_sleep_seconds() override
- run_on_start parameter behavior
- Main loop execution
"""

import asyncio
import signal
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.core.schedulers.base_scheduler import BaseScheduler


class ConcreteScheduler(BaseScheduler):
    """Concrete implementation for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.task_run_count = 0
        self.task_exception = None

    async def run_task(self) -> None:
        """Simple task that counts executions."""
        if self.task_exception:
            raise self.task_exception
        self.task_run_count += 1


class TimedScheduler(BaseScheduler):
    """Scheduler with custom time-based scheduling."""

    def __init__(self, sleep_seconds: int = 3600, **kwargs):
        super().__init__(**kwargs)
        self._sleep_seconds = sleep_seconds
        self.task_run_count = 0

    def get_sleep_seconds(self) -> int:
        """Return custom sleep time."""
        return self._sleep_seconds

    async def run_task(self) -> None:
        self.task_run_count += 1


class TestBaseSchedulerInit:
    """Tests for BaseScheduler initialization."""

    def test_init_with_defaults(self, tmp_path):
        """Test initialization with default values."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test_scheduler",
            base_path=str(tmp_path),
        )

        assert scheduler.running is True
        assert scheduler.interval_minutes == 60
        assert scheduler.run_on_start is True
        assert scheduler.health_file == tmp_path / "test_scheduler_health"
        assert scheduler.last_run_file == tmp_path / "test_scheduler_last_run"

    def test_init_with_custom_values(self, tmp_path):
        """Test initialization with custom values."""
        scheduler = ConcreteScheduler(
            health_file_prefix="custom",
            base_path=str(tmp_path),
            interval_minutes=15,
            run_on_start=False,
            scheduler_name="CustomScheduler",
        )

        assert scheduler.interval_minutes == 15
        assert scheduler.run_on_start is False
        assert scheduler.scheduler_name == "CustomScheduler"

    def test_init_creates_correct_paths(self, tmp_path):
        """Test that health file paths are constructed correctly."""
        scheduler = ConcreteScheduler(
            health_file_prefix="metadata_scheduler",
            base_path=str(tmp_path / "health"),
        )

        assert scheduler.health_file == tmp_path / "health" / "metadata_scheduler_health"
        assert scheduler.last_run_file == tmp_path / "health" / "metadata_scheduler_last_run"

    def test_default_scheduler_name_is_class_name(self, tmp_path):
        """Test that scheduler_name defaults to class name."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        assert scheduler.scheduler_name == "ConcreteScheduler"


class TestSignalHandling:
    """Tests for signal handling."""

    def test_signal_handler_sets_running_false(self, tmp_path):
        """Test that signal handler sets running to False."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        assert scheduler.running is True
        scheduler._signal_handler(signal.SIGTERM, None)
        assert scheduler.running is False

    def test_signal_handler_logs_message(self, tmp_path):
        """Test that signal handler logs shutdown message."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        with patch.object(scheduler.logger, "info") as mock_log:
            scheduler._signal_handler(signal.SIGINT, None)
            mock_log.assert_called_once()
            assert "signal" in mock_log.call_args[0][0].lower()


class TestHealthFileManagement:
    """Tests for health file management."""

    def test_update_health_status_writes_correct_format(self, tmp_path):
        """Test health status file format: timestamp:status."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        before_time = int(time.time())
        scheduler._update_health_status("idle")
        after_time = int(time.time())

        content = scheduler.health_file.read_text()
        timestamp_str, status = content.split(":")

        assert status == "idle"
        timestamp = int(timestamp_str)
        assert before_time <= timestamp <= after_time

    def test_update_health_status_creates_parent_dirs(self, tmp_path):
        """Test that health status creates parent directories."""
        nested_path = tmp_path / "deep" / "nested" / "path"
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(nested_path),
        )

        scheduler._update_health_status("running")

        assert scheduler.health_file.exists()
        assert nested_path.exists()

    def test_update_health_status_handles_errors(self, tmp_path):
        """Test that errors are logged, not raised."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        # Make path unwritable by using invalid path
        scheduler.health_file = Path("/nonexistent/readonly/path/health")

        with patch.object(scheduler.logger, "error") as mock_log:
            scheduler._update_health_status("error")
            mock_log.assert_called_once()

    def test_update_last_run_writes_timestamp(self, tmp_path):
        """Test last run file contains unix timestamp."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        before_time = int(time.time())
        scheduler._update_last_run()
        after_time = int(time.time())

        content = scheduler.last_run_file.read_text()
        timestamp = int(content)
        assert before_time <= timestamp <= after_time

    def test_update_last_run_creates_parent_dirs(self, tmp_path):
        """Test that last run creates parent directories."""
        nested_path = tmp_path / "app" / "health"
        scheduler = ConcreteScheduler(
            health_file_prefix="maintenance",
            base_path=str(nested_path),
        )

        scheduler._update_last_run()

        assert scheduler.last_run_file.exists()


class TestGetSleepSeconds:
    """Tests for get_sleep_seconds method."""

    def test_default_returns_interval_in_seconds(self, tmp_path):
        """Test default implementation returns interval_minutes * 60."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
            interval_minutes=15,
        )

        assert scheduler.get_sleep_seconds() == 15 * 60

    def test_override_get_sleep_seconds(self, tmp_path):
        """Test that get_sleep_seconds can be overridden."""
        scheduler = TimedScheduler(
            sleep_seconds=7200,  # 2 hours
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        assert scheduler.get_sleep_seconds() == 7200


class TestRunTask:
    """Tests for run_task execution."""

    @pytest.mark.asyncio
    async def test_execute_task_with_tracking_updates_health(self, tmp_path):
        """Test that _execute_task_with_tracking updates health files."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )

        await scheduler._execute_task_with_tracking()

        assert scheduler.task_run_count == 1
        assert scheduler.health_file.exists()
        assert scheduler.last_run_file.exists()
        assert "idle" in scheduler.health_file.read_text()

    @pytest.mark.asyncio
    async def test_execute_task_with_tracking_handles_exception(self, tmp_path):
        """Test that exceptions are caught and health set to error."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
        )
        scheduler.task_exception = ValueError("Test error")

        await scheduler._execute_task_with_tracking()

        assert "error" in scheduler.health_file.read_text()


class TestStartMethod:
    """Tests for the start() main loop."""

    @pytest.mark.asyncio
    async def test_start_runs_initial_task_when_run_on_start_true(self, tmp_path):
        """Test that initial task runs when run_on_start=True."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
            run_on_start=True,
        )

        # Use side_effect to stop scheduler after first sleep call
        sleep_call_count = 0

        async def stop_on_first_sleep(seconds):
            nonlocal sleep_call_count
            sleep_call_count += 1
            if sleep_call_count >= 1:
                scheduler.running = False

        # Mock asyncio.sleep to prevent infinite loop
        with patch(
            "packages.core.schedulers.base_scheduler.asyncio.sleep", side_effect=stop_on_first_sleep
        ):
            await scheduler.start()

        assert scheduler.task_run_count == 1

    @pytest.mark.asyncio
    async def test_start_skips_initial_task_when_run_on_start_false(self, tmp_path):
        """Test that initial task is skipped when run_on_start=False."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
            run_on_start=False,
        )

        # Use side_effect to stop scheduler immediately
        async def stop_immediately(seconds):
            scheduler.running = False

        # Mock asyncio.sleep to prevent infinite loop
        with patch(
            "packages.core.schedulers.base_scheduler.asyncio.sleep", side_effect=stop_immediately
        ):
            await scheduler.start()

        assert scheduler.task_run_count == 0

    @pytest.mark.asyncio
    async def test_start_updates_health_to_starting(self, tmp_path):
        """Test that start() sets health to 'starting'."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
            run_on_start=False,
        )

        health_statuses = []

        original_update = scheduler._update_health_status

        def track_health(status):
            health_statuses.append(status)
            original_update(status)

        scheduler._update_health_status = track_health

        # Use side_effect to stop scheduler immediately
        async def stop_immediately(seconds):
            scheduler.running = False

        # Mock asyncio.sleep to prevent infinite loop
        with patch(
            "packages.core.schedulers.base_scheduler.asyncio.sleep", side_effect=stop_immediately
        ):
            await scheduler.start()

        assert "starting" in health_statuses

    @pytest.mark.asyncio
    async def test_start_handles_cancelled_error(self, tmp_path):
        """Test that CancelledError is handled gracefully (no re-raise)."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
            run_on_start=False,
            interval_minutes=1,
        )

        # Create an async side effect that raises CancelledError
        async def raise_cancelled(seconds):
            raise asyncio.CancelledError()

        # Mock asyncio.sleep to raise CancelledError
        with patch(
            "packages.core.schedulers.base_scheduler.asyncio.sleep", side_effect=raise_cancelled
        ):
            # CancelledError is caught inside start() and handled gracefully
            await scheduler.start()

        # Verify scheduler logged cancellation and set stopped status
        assert "stopped" in scheduler.health_file.read_text()

    @pytest.mark.asyncio
    async def test_start_sets_stopped_on_exit(self, tmp_path):
        """Test that health is set to 'stopped' when scheduler exits."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
            run_on_start=False,
        )

        # Use side_effect to stop scheduler immediately
        async def stop_scheduler(seconds):
            scheduler.running = False

        # Mock asyncio.sleep to prevent infinite loop
        with patch(
            "packages.core.schedulers.base_scheduler.asyncio.sleep", side_effect=stop_scheduler
        ):
            await scheduler.start()

        assert "stopped" in scheduler.health_file.read_text()


class TestAbstractMethod:
    """Tests for abstract method enforcement."""

    def test_cannot_instantiate_base_scheduler_directly(self, tmp_path):
        """Test that BaseScheduler cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseScheduler(
                health_file_prefix="test",
                base_path=str(tmp_path),
            )


class TestIntegration:
    """Integration tests for realistic scheduler scenarios."""

    @pytest.mark.asyncio
    async def test_short_interval_scheduler(self, tmp_path):
        """Test scheduler with very short interval for testing."""
        scheduler = ConcreteScheduler(
            health_file_prefix="test",
            base_path=str(tmp_path),
            interval_minutes=1,  # Will be very short in practice
            run_on_start=True,
        )

        # Use side_effect to stop scheduler after first sleep call
        async def stop_on_first_sleep(seconds):
            scheduler.running = False

        # Mock asyncio.sleep to prevent infinite loop
        with patch(
            "packages.core.schedulers.base_scheduler.asyncio.sleep", side_effect=stop_on_first_sleep
        ):
            await scheduler.start()

        assert scheduler.task_run_count >= 1
        assert scheduler.health_file.exists()
        assert scheduler.last_run_file.exists()

    @pytest.mark.asyncio
    async def test_time_based_scheduler(self, tmp_path):
        """Test scheduler with time-based scheduling override."""
        scheduler = TimedScheduler(
            sleep_seconds=1,  # 1 second for testing
            health_file_prefix="daily",
            base_path=str(tmp_path),
            run_on_start=False,
        )

        # Use side_effect to stop scheduler immediately
        async def stop_immediately(seconds):
            scheduler.running = False

        # Mock asyncio.sleep to prevent infinite loop
        with patch(
            "packages.core.schedulers.base_scheduler.asyncio.sleep", side_effect=stop_immediately
        ):
            await scheduler.start()

        # Should not have run since we stopped quickly
        assert scheduler.task_run_count == 0
